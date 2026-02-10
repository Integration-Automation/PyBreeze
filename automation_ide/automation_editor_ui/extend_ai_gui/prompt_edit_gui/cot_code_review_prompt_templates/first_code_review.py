FIRST_CODE_REVIEW_TEMPLATE = """
# Code Review Template

## Review Rules
Perform a first-step code review focusing on:
1. Code readability (indentation, formatting, comments).
2. Clarity and descriptiveness of variable, function, and class names; avoid vague or cryptic naming.
3. Adherence to basic software engineering standards (modularity, maintainability, avoidance of duplicate code).
4. Identification of obvious logical errors or potential bugs.
5. Provide concise improvement suggestions with short explanations.
6. Focus only on the most obvious issues; avoid deep analysis at this stage.

Respond in a structured bullet-point format, keeping feedback concise and professional.

## Code diff
{code_diff}
"""
