from __future__ import annotations

GLOBAL_RULE_TEMPLATE = """
Please conduct a code review according to the following global rules:

1. Readability & Consistency
   - Check indentation, formatting, and comments for clarity.
   - Ensure code style follows team conventions (naming rules, formatting tools).

2. Naming Conventions
   - Variable, function, and class names must be descriptive and meaningful.
   - Maintain semantic clarity and consistency across the codebase.

3. Software Engineering Standards
   - Code should be modular, maintainable, and testable.
   - Avoid duplicate code; encourage refactoring and abstraction.

4. Logic & Correctness
   - Verify correctness of program logic and identify potential bugs.
   - Check boundary conditions and exception handling.

5. Performance & Security
   - Assess for unnecessary performance bottlenecks.
   - Review for security risks (e.g., input validation, resource management).

6. Documentation & Testing
   - Ensure necessary comments and documentation are present.
   - Verify sufficient unit and integration tests are included.

7. Scoring & Feedback Style
   - Balance conciseness with comprehensiveness.
   - Do not penalize completeness for being less concise.


---

# Prompt Content
{prompt}
"""


def build_global_rule_template(prompt: str = "") -> str:
    """*prompt* under the global review rules every CoT step is sent with."""
    return GLOBAL_RULE_TEMPLATE.format(prompt=prompt)
