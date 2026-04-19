"""
Soroban-specific AI prompt actions for Calliope IDE.
Addresses issue #54.

Provides 4 prebuilt prompt templates:
  - generate_contract  : generate a Soroban smart contract from a description
  - explain_contract   : explain an existing contract in plain language
  - generate_tests     : generate a Rust test suite for a contract
  - security_review    : perform a security audit of a contract

Each prompt is designed to produce focused, actionable AI output
that can be inserted directly into the editor.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable

# ── Prompt registry ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SorobanPromptTemplate:
    id: str
    name: str
    description: str
    category: str
    requires_code: bool  # True if user must supply contract code as context
    placeholder: str     # Hint shown in the input field


def _generate_contract(description: str, context_code: str = "") -> str:
    ctx = f"\n\nExisting context:\n```rust\n{context_code}\n```" if context_code else ""
    return f"""You are an expert Soroban smart contract developer for the Stellar blockchain.

Generate a complete, production-ready Soroban smart contract for the following requirement:
{description}{ctx}

Requirements:
- Use #![no_std] and soroban_sdk
- Include proper #[contract] and #[contractimpl] annotations
- Add #[contracttype] for all custom data structures
- Use persistent storage with typed DataKey enum
- Include proper authorization with require_auth() where needed
- Add inline comments explaining key logic
- Include a complete #[cfg(test)] module with at least 3 meaningful tests
- Follow Soroban best practices (no panics in production paths, proper error handling)

Output ONLY the complete Rust source code, ready to save as src/lib.rs.
Do not include any explanation outside the code."""


def _explain_contract(description: str, context_code: str = "") -> str:
    code_section = f"\n\nContract code:\n```rust\n{context_code}\n```" if context_code else ""
    extra = f"\nFocus on: {description}" if description else ""
    return f"""You are an expert Soroban smart contract auditor and educator.

Explain the following Soroban smart contract in clear, plain language.{code_section}{extra}

Your explanation must cover:
1. **Purpose** — What does this contract do? What problem does it solve?
2. **Storage** — What data does it store and how is it organized?
3. **Functions** — Explain each public function: inputs, outputs, side effects
4. **Authorization** — Who can call each function and how is access controlled?
5. **Events** — What events are emitted and when?
6. **Limitations** — Any edge cases, assumptions, or known constraints?

Write for a developer who understands Rust but is new to Soroban.
Use clear headings and bullet points."""


def _generate_tests(description: str, context_code: str = "") -> str:
    code_section = f"\n\nContract code:\n```rust\n{context_code}\n```" if context_code else ""
    focus = f"\nTest focus: {description}" if description else ""
    return f"""You are an expert Soroban smart contract tester.

Generate a comprehensive Rust test suite for the following Soroban contract.{code_section}{focus}

Requirements:
- Use soroban_sdk::testutils::Address as _ for Address::generate
- Use Env::default() and mock_all_auths() where appropriate
- Cover all public functions with at least one test each
- Include happy path tests AND edge case / failure tests
- Use #[should_panic(expected = "...")] for expected failures
- Add a setup() helper function to reduce boilerplate
- Group tests into logical test classes with descriptive names
- Each test should have a clear docstring explaining what it verifies

Output ONLY the complete Rust test module code (the #[cfg(test)] block).
Do not include any explanation outside the code."""


def _security_review(description: str, context_code: str = "") -> str:
    code_section = f"\n\nContract code:\n```rust\n{context_code}\n```" if context_code else ""
    scope = f"\nReview scope: {description}" if description else ""
    return f"""You are an expert Soroban smart contract security auditor.

Perform a thorough security review of the following Soroban smart contract.{code_section}{scope}

Review checklist:
1. **Access Control** — Are all sensitive functions properly protected with require_auth()?
   Are there any functions that should require admin-only access?
2. **Input Validation** — Are all inputs validated? Could any cause panics or unexpected behavior?
3. **Integer Overflow/Underflow** — Are arithmetic operations safe? (Soroban uses overflow-checks=true but review anyway)
4. **Storage Manipulation** — Can unauthorized callers read or write sensitive storage keys?
5. **Initialization** — Is there a risk of re-initialization or missing initialization?
6. **Reentrancy** — Are there any cross-contract call patterns that could be exploited?
7. **Event Emission** — Are sensitive operations properly logged via events?
8. **Denial of Service** — Are there unbounded loops or storage operations that could be abused?
9. **Logic Errors** — Any business logic flaws or incorrect assumptions?
10. **Best Practices** — Any deviations from Soroban / Stellar security best practices?

For each issue found, provide:
- **Severity**: Critical / High / Medium / Low / Informational
- **Location**: Function name and line description
- **Description**: What the issue is and why it matters
- **Recommendation**: How to fix it with a code example if applicable

End with an overall risk rating and a summary of the most important fixes."""


# ── Registry ──────────────────────────────────────────────────────────────────

PROMPT_TEMPLATES: dict[str, SorobanPromptTemplate] = {
    "generate_contract": SorobanPromptTemplate(
        id="generate_contract",
        name="Generate Contract",
        description="Generate a complete Soroban smart contract from a description",
        category="generation",
        requires_code=False,
        placeholder="Describe the contract you want to build (e.g. 'A token vesting contract that releases tokens linearly over 12 months')",
    ),
    "explain_contract": SorobanPromptTemplate(
        id="explain_contract",
        name="Explain Contract",
        description="Explain an existing Soroban contract in plain language",
        category="education",
        requires_code=True,
        placeholder="Paste your contract code in the context field, or describe what aspect to focus on",
    ),
    "generate_tests": SorobanPromptTemplate(
        id="generate_tests",
        name="Generate Tests",
        description="Generate a Rust test suite for a Soroban contract",
        category="testing",
        requires_code=True,
        placeholder="Paste your contract code in the context field, or describe specific test scenarios to cover",
    ),
    "security_review": SorobanPromptTemplate(
        id="security_review",
        name="Security Review",
        description="Perform a security audit of a Soroban contract",
        category="security",
        requires_code=True,
        placeholder="Paste your contract code in the context field, or specify the review scope",
    ),
}

_BUILDERS: dict[str, Callable[[str, str], str]] = {
    "generate_contract": _generate_contract,
    "explain_contract": _explain_contract,
    "generate_tests": _generate_tests,
    "security_review": _security_review,
}


def list_prompt_templates() -> list[dict]:
    """Return metadata for all available prompt templates."""
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "category": t.category,
            "requires_code": t.requires_code,
            "placeholder": t.placeholder,
        }
        for t in PROMPT_TEMPLATES.values()
    ]


def get_prompt_template(prompt_id: str) -> dict | None:
    """Return metadata for a single template, or None if not found."""
    t = PROMPT_TEMPLATES.get(prompt_id)
    if not t:
        return None
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "category": t.category,
        "requires_code": t.requires_code,
        "placeholder": t.placeholder,
    }


def build_soroban_prompt(
    prompt_id: str,
    user_description: str,
    context_code: str = "",
) -> str:
    """
    Build the full prompt string for a given prompt template.

    Args:
        prompt_id:        One of the keys in PROMPT_TEMPLATES.
        user_description: User's task description or focus area.
        context_code:     Optional contract source code to include.

    Returns:
        The complete prompt string ready to send to the AI model.

    Raises:
        ValueError: If prompt_id is not recognized.
    """
    if prompt_id not in _BUILDERS:
        raise ValueError(
            f"Unknown prompt '{prompt_id}'. "
            f"Available: {', '.join(_BUILDERS.keys())}"
        )
    return _BUILDERS[prompt_id](user_description, context_code)
