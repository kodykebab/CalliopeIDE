"""
Context selection strategy for Calliope IDE.

Decides WHAT to include in the AI prompt — current file, related files,
project metadata — without ever dumping the full project.

Selection priority:
  1. Current file (always included, truncated if needed)
  2. Related files by import/reference scoring
  3. Project type + framework metadata
  4. Fallback strategies when total size exceeds budget
"""

import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional

# ── Size budgets (characters, not tokens; ~4 chars ≈ 1 token for code) ────────
CURRENT_FILE_BUDGET  = 8_000   # chars reserved for the active file
RELATED_FILE_BUDGET  = 4_000   # chars per related file
MAX_RELATED_FILES    = 4       # hard cap on related file count
TOTAL_CONTEXT_BUDGET = 32_000  # absolute ceiling for everything combined

# ── Caching ───────────────────────────────────────────────────────────────────
_CONTEXT_CACHE: dict[str, "_CacheEntry"] = {}
CACHE_TTL_SECONDS = 30   # invalidate after 30 s of inactivity

# Fix issue 1: cap the cache size so it never grows unbounded in long-running
# server processes.  When the limit is hit, the oldest half is evicted.
_CACHE_MAX_ENTRIES = 200


@dataclass
class _CacheEntry:
    context: "ProjectContext"
    created_at: float = field(default_factory=time.time)

    def is_fresh(self) -> bool:
        return (time.time() - self.created_at) < CACHE_TTL_SECONDS


@dataclass
class FileContext:
    """Represents a single file's contribution to the prompt."""
    path: str
    content: str          # may be truncated
    was_truncated: bool = False
    relevance_score: float = 0.0
    language: str = ""


@dataclass
class ProjectContext:
    """Complete context payload ready for the prompt builder."""
    current_file: Optional[FileContext]
    related_files: list[FileContext]
    project_type: str = ""
    language: str = ""
    framework: str = ""
    project_name: str = ""
    total_chars: int = 0
    cache_hit: bool = False


# ── Language detection ─────────────────────────────────────────────────────────
_EXTENSION_TO_LANG = {
    ".rs": "Rust", ".py": "Python", ".js": "JavaScript",
    ".ts": "TypeScript", ".jsx": "JavaScript (React)",
    ".tsx": "TypeScript (React)", ".toml": "TOML", ".json": "JSON",
    ".md": "Markdown", ".sol": "Solidity",
}

def _detect_language(path: str) -> str:
    _, ext = os.path.splitext(path)
    return _EXTENSION_TO_LANG.get(ext.lower(), "")


# ── Import / reference extraction ─────────────────────────────────────────────
def _extract_references(content: str, language: str) -> set[str]:
    """Return bare module/file names referenced in this file."""
    refs: set[str] = set()

    if language in ("Rust",):
        for m in re.finditer(r'\buse\s+([\w:]+)', content):
            refs.add(m.group(1).split("::")[0])
        for m in re.finditer(r'\bmod\s+(\w+)', content):
            refs.add(m.group(1))

    elif language in ("Python",):
        for m in re.finditer(r'^\s*(?:from|import)\s+([\w.]+)', content, re.M):
            refs.add(m.group(1).split(".")[0])

    elif language in ("JavaScript", "TypeScript",
                      "JavaScript (React)", "TypeScript (React)"):
        for m in re.finditer(r'''(?:from|require)\s+['"]([^'"]+)['"]''', content):
            name = m.group(1)
            # keep only local imports (start with . or /)
            if name.startswith(".") or name.startswith("/"):
                refs.add(os.path.basename(name).split(".")[0])

    return refs


# ── Relevance scoring ──────────────────────────────────────────────────────────
# Fix issue 2: RECENTLY_MODIFIED_BOOST_LIMIT is the single source of truth used
# by both the scoring function and the caller.  Previously the frontend sliced
# to 10 but the scorer only boosted the first 5 — now both sides agree on 5.
RECENTLY_MODIFIED_BOOST_LIMIT = 5

def _score_file(
    candidate_path: str,
    candidate_content: str,
    current_refs: set[str],
    current_path: str,
    language: str,
    recently_modified: list[str],
) -> float:
    """
    Score a candidate file's relevance to the current file.
    Higher = more relevant.
    """
    score = 0.0
    name = os.path.splitext(os.path.basename(candidate_path))[0]

    # Direct reference match
    if name in current_refs:
        score += 10.0

    # Same directory
    if os.path.dirname(candidate_path) == os.path.dirname(current_path):
        score += 3.0

    # Same language
    if _detect_language(candidate_path) == language:
        score += 2.0

    # Recently modified — only boost up to RECENTLY_MODIFIED_BOOST_LIMIT
    if candidate_path in recently_modified[:RECENTLY_MODIFIED_BOOST_LIMIT]:
        score += 2.0

    # The candidate itself references the current file
    candidate_name = os.path.splitext(os.path.basename(current_path))[0]
    if candidate_name in _extract_references(candidate_content, language):
        score += 5.0

    # Soroban-specific: test files always relevant to lib.rs
    if "lib.rs" in current_path and "test" in candidate_path.lower():
        score += 4.0

    return score


# ── Safe file reading ──────────────────────────────────────────────────────────
def _read_file(path: str, budget: int) -> tuple[str, bool]:
    """Read a file up to `budget` characters. Returns (content, was_truncated)."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
        if len(raw) <= budget:
            return raw, False
        # Truncate at a line boundary near the budget
        truncated = raw[:budget]
        last_newline = truncated.rfind("\n")
        if last_newline > budget // 2:
            truncated = truncated[:last_newline]
        return truncated + f"\n... [truncated — {len(raw) - len(truncated)} chars omitted]", True
    except (OSError, PermissionError):
        return "", False


# ── Cache helpers ──────────────────────────────────────────────────────────────
def _evict_stale_cache() -> None:
    """
    Fix issue 1: remove expired entries and, if the cache has grown beyond
    _CACHE_MAX_ENTRIES, evict the oldest half to bound memory usage.
    """
    global _CONTEXT_CACHE

    # Remove TTL-expired entries
    stale = [k for k, v in _CONTEXT_CACHE.items() if not v.is_fresh()]
    for k in stale:
        del _CONTEXT_CACHE[k]

    # If still over the size cap, evict the oldest half by creation time
    if len(_CONTEXT_CACHE) >= _CACHE_MAX_ENTRIES:
        sorted_keys = sorted(
            _CONTEXT_CACHE.keys(),
            key=lambda k: _CONTEXT_CACHE[k].created_at,
        )
        for k in sorted_keys[: len(sorted_keys) // 2]:
            del _CONTEXT_CACHE[k]


# ── Public API ─────────────────────────────────────────────────────────────────
def build_project_context(
    project_path: str,
    current_file_path: Optional[str],
    project_metadata: Optional[dict] = None,
    recently_modified: Optional[list[str]] = None,
    force_refresh: bool = False,
) -> ProjectContext:
    """
    Main entry point.  Call this before building the prompt.

    Args:
        project_path:      Absolute path to the project root.
        current_file_path: Absolute path to the file the user is editing.
        project_metadata:  Dict with keys: project_type, language, framework,
                           project_name.  Falls back to heuristics if None.
        recently_modified: Ordered list of recently touched file paths (most
                           recent first).  Used for relevance boosting.
                           Capped at RECENTLY_MODIFIED_BOOST_LIMIT entries for
                           scoring; pass as many as you like, extras are ignored.
        force_refresh:     Bypass cache.

    Returns:
        ProjectContext ready to pass into PromptBuilder.
    """
    recently_modified = recently_modified or []
    meta = project_metadata or {}

    # ── Cache eviction (fix issue 1) ──────────────────────────────────────────
    _evict_stale_cache()

    # ── Cache lookup ──────────────────────────────────────────────────────────
    cache_key = f"{project_path}::{current_file_path}"
    if not force_refresh and cache_key in _CONTEXT_CACHE:
        entry = _CONTEXT_CACHE[cache_key]
        if entry.is_fresh():
            ctx = entry.context
            ctx.cache_hit = True
            return ctx

    # ── Current file ──────────────────────────────────────────────────────────
    current_fc: Optional[FileContext] = None
    current_refs: set[str] = set()
    current_lang = meta.get("language", "")

    if current_file_path and os.path.isfile(current_file_path):
        content, truncated = _read_file(current_file_path, CURRENT_FILE_BUDGET)
        current_lang = current_lang or _detect_language(current_file_path)
        current_refs = _extract_references(content, current_lang)
        current_fc = FileContext(
            path=current_file_path,
            content=content,
            was_truncated=truncated,
            language=current_lang,
            relevance_score=1_000.0,   # always top priority
        )

    # ── Candidate files ───────────────────────────────────────────────────────
    related: list[FileContext] = []
    used_budget = len(current_fc.content) if current_fc else 0

    skip_dirs = {"node_modules", ".git", "target", "__pycache__", ".next",
                 "dist", "build", ".venv", "venv"}

    candidates: list[tuple[float, str]] = []

    for dirpath, dirnames, filenames in os.walk(project_path):
        # Prune heavy directories in-place so os.walk skips them
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]

        for fname in filenames:
            fpath = os.path.join(dirpath, fname)

            # Skip the current file itself
            if current_file_path and os.path.abspath(fpath) == os.path.abspath(current_file_path):
                continue

            lang = _detect_language(fpath)
            if not lang:
                continue   # skip binary / unknown files

            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    preview = f.read(2_000)   # small read for scoring only
            except OSError:
                continue

            score = _score_file(
                candidate_path=fpath,
                candidate_content=preview,
                current_refs=current_refs,
                current_path=current_file_path or "",
                language=current_lang,
                recently_modified=recently_modified,
            )

            if score > 0:
                candidates.append((score, fpath))

    # Sort descending by score, then take the best up to MAX_RELATED_FILES
    candidates.sort(key=lambda t: t[0], reverse=True)

    for score, fpath in candidates[:MAX_RELATED_FILES]:
        remaining_budget = min(
            RELATED_FILE_BUDGET,
            TOTAL_CONTEXT_BUDGET - used_budget,
        )
        if remaining_budget < 200:
            break   # not enough budget left

        content, truncated = _read_file(fpath, remaining_budget)
        if not content:
            continue

        lang = _detect_language(fpath)
        fc = FileContext(
            path=fpath,
            content=content,
            was_truncated=truncated,
            language=lang,
            relevance_score=score,
        )
        related.append(fc)
        used_budget += len(content)

    # ── Project metadata heuristics ───────────────────────────────────────────
    project_type = meta.get("project_type", "")
    if not project_type:
        if os.path.exists(os.path.join(project_path, "Cargo.toml")):
            project_type = "soroban_contract"
        elif os.path.exists(os.path.join(project_path, "package.json")):
            project_type = "node"
        elif os.path.exists(os.path.join(project_path, "requirements.txt")):
            project_type = "python"

    ctx = ProjectContext(
        current_file=current_fc,
        related_files=related,
        project_type=project_type,
        language=current_lang or meta.get("language", ""),
        framework=meta.get("framework", ""),
        project_name=meta.get("project_name", os.path.basename(project_path)),
        total_chars=used_budget,
        cache_hit=False,
    )

    # ── Populate cache ────────────────────────────────────────────────────────
    _CONTEXT_CACHE[cache_key] = _CacheEntry(context=ctx)

    return ctx


def invalidate_cache(project_path: str) -> None:
    """Call whenever a file in the project is saved or created."""
    keys_to_drop = [k for k in _CONTEXT_CACHE if k.startswith(project_path)]
    for k in keys_to_drop:
        del _CONTEXT_CACHE[k]