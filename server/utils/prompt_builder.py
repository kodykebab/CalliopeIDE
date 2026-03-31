"""
Prompt assembly for Calliope IDE.

Takes a ProjectContext (from context_builder.py) + the base system prompt
and produces the final string that gets sent to Gemini.

Responsibilities:
  - Inject only the context that was selected
  - Enforce total size budget (TOTAL_CONTEXT_BUDGET)
  - Apply fallback strategies when over budget
  - Keep the structure readable for the model
"""

from server.utils.context_builder import ProjectContext, TOTAL_CONTEXT_BUDGET

# How many characters the base system prompt is allowed to consume before we
# start shrinking context.  Adjust if get_prompt() in agent.py grows.
BASE_PROMPT_CHARS = 6_000

# Minimum content kept per file even after fallback truncation
MIN_FILE_SNIPPET = 300


def build_prompt(base_system_prompt: str, context: ProjectContext) -> str:
    """
    Merge the base system prompt with project context.

    Returns the final prompt string to send to the model.
    The context section is injected right before the last paragraph of the
    base prompt so the model sees it as part of its operating instructions.
    """
    context_block = _build_context_block(context)

    available = TOTAL_CONTEXT_BUDGET - BASE_PROMPT_CHARS
    if len(context_block) > available:
        context_block = _apply_fallback(context, available)

    if not context_block:
        return base_system_prompt

    # Inject context between the system prompt and the closing reminder
    divider = "\n\n---\n"
    return base_system_prompt + divider + context_block


def build_task_prompt(user_input: str, context: ProjectContext) -> str:
    """
    Build the per-turn user message that accompanies the task.

    This is sent as the initial chat.send_message(...) content (not the
    system prompt), so it can carry file context specific to this request
    without polluting the conversation history with large blobs.

    Fix issue 3: the "start by exploring" nudge is only appended when there
    is no current file context — if the model already has file contents it
    should not be told to explore from scratch.
    """
    parts: list[str] = []

    parts.append(f"Task: {user_input}")

    if context.current_file:
        cf = context.current_file
        rel_path = _relative_or_basename(cf.path)
        truncation_note = " [truncated]" if cf.was_truncated else ""
        parts.append(
            f"\n### Active file: {rel_path} ({cf.language}){truncation_note}\n"
            f"```{_lang_fence(cf.language)}\n{cf.content}\n```"
        )

    if context.related_files:
        parts.append("\n### Related files (for reference):")
        for rf in context.related_files:
            rel_path = _relative_or_basename(rf.path)
            truncation_note = " [truncated]" if rf.was_truncated else ""
            parts.append(
                f"\n#### {rel_path}{truncation_note}\n"
                f"```{_lang_fence(rf.language)}\n{rf.content}\n```"
            )

    # Fix issue 3: only ask the model to explore when we have no file context.
    # When context is rich, the exploration nudge contradicts the purpose of
    # injecting context and wastes the first agentic step.
    if context.current_file is None:
        parts.append(
            "\nBreak this down into small steps. Start by exploring the environment.\n"
            "REMEMBER: Keep your JSON response VERY BRIEF to avoid truncation."
        )
    else:
        parts.append(
            "\nBreak this down into small steps. Use the file context above instead of "
            "re-reading files via commands.\n"
            "REMEMBER: Keep your JSON response VERY BRIEF to avoid truncation."
        )

    return "\n".join(parts)


# ── Internal helpers ───────────────────────────────────────────────────────────

def _build_context_block(context: ProjectContext) -> str:
    """Render the full context section before any budget checks."""
    lines: list[str] = ["## Project context"]

    # Project metadata
    meta_parts = []
    if context.project_name:
        meta_parts.append(f"Project: **{context.project_name}**")
    if context.project_type:
        meta_parts.append(f"Type: {context.project_type}")
    if context.language:
        meta_parts.append(f"Language: {context.language}")
    if context.framework:
        meta_parts.append(f"Framework: {context.framework}")
    if meta_parts:
        lines.append("  ".join(meta_parts))

    if context.cache_hit:
        lines.append("_(context from cache)_")

    # Current file
    if context.current_file:
        cf = context.current_file
        rel = _relative_or_basename(cf.path)
        note = " _(truncated)_" if cf.was_truncated else ""
        lines.append(
            f"\n### Current file: `{rel}`{note}\n"
            f"```{_lang_fence(cf.language)}\n{cf.content}\n```"
        )

    # Related files
    if context.related_files:
        lines.append("\n### Related files")
        for rf in context.related_files:
            rel = _relative_or_basename(rf.path)
            note = " _(truncated)_" if rf.was_truncated else ""
            lines.append(
                f"\n#### `{rel}`{note}\n"
                f"```{_lang_fence(rf.language)}\n{rf.content}\n```"
            )

    return "\n".join(lines)


def _apply_fallback(context: ProjectContext, budget: int) -> str:
    """
    Three-tier fallback when we're over budget:
      1. Truncate related files further
      2. Truncate current file to MIN_FILE_SNIPPET
      3. Metadata only (no file content at all)
    """
    lines: list[str] = ["## Project context (condensed — over budget)"]

    # Metadata always fits
    meta_parts = []
    if context.project_name:
        meta_parts.append(f"Project: {context.project_name}")
    if context.project_type:
        meta_parts.append(f"Type: {context.project_type}")
    if context.language:
        meta_parts.append(f"Language: {context.language}")
    if context.framework:
        meta_parts.append(f"Framework: {context.framework}")
    if meta_parts:
        lines.append("  ".join(meta_parts))

    used = sum(len(l) for l in lines)

    # Current file — at minimum include the snippet
    if context.current_file:
        cf = context.current_file
        rel = _relative_or_basename(cf.path)
        snippet = cf.content[:MIN_FILE_SNIPPET]
        block = (
            f"\n### Current file: `{rel}` _(heavily truncated — budget exceeded)_\n"
            f"```{_lang_fence(cf.language)}\n{snippet}\n... [omitted]\n```"
        )
        if used + len(block) <= budget:
            lines.append(block)
            used += len(block)

    # Related files — include as many as fit, shortest first
    for rf in sorted(context.related_files, key=lambda f: len(f.content)):
        rel = _relative_or_basename(rf.path)
        block = (
            f"\n#### `{rel}` _(condensed)_\n"
            f"```{_lang_fence(rf.language)}\n{rf.content[:MIN_FILE_SNIPPET]}\n... [omitted]\n```"
        )
        if used + len(block) > budget:
            break
        lines.append(block)
        used += len(block)

    return "\n".join(lines)


def _relative_or_basename(path: str) -> str:
    """Use only the last two path components to keep prompts clean."""
    parts = path.replace("\\", "/").split("/")
    return "/".join(parts[-2:]) if len(parts) >= 2 else parts[-1]


def _lang_fence(language: str) -> str:
    """Map display language name to markdown fence identifier."""
    mapping = {
        "Rust": "rust",
        "Python": "python",
        "JavaScript": "js",
        "TypeScript": "ts",
        "JavaScript (React)": "jsx",
        "TypeScript (React)": "tsx",
        "TOML": "toml",
        "JSON": "json",
        "Markdown": "md",
        "Solidity": "solidity",
    }
    return mapping.get(language, "")