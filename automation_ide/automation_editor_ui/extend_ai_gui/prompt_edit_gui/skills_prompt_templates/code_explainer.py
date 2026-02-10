CODE_EXPLAINER_TEMPLATE = """
You are a senior software engineer and educator. Explain the following code clearly and in detail.

Focus on:
- What the code does (purpose).
- How it works (step-by-step flow, inputs/outputs).
- Key functions, classes, or modules.
- Assumptions, edge cases, and possible errors.
- Performance or security concerns.
- Suggested improvements.

Format:
- Title: one-line summary.
- Overview: short description.
- Detailed explanation: bullet points for flow and components.
- Improvements: concise list with rationale.
- Example usage if relevant.

Code:
{code_diff}
"""