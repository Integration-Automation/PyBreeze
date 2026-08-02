"""How a chain-of-thought review is wired: what each step quotes from the ones before it.

A step is one prompt sent to the review endpoint. Its answer is kept under a short
result key so a later step can quote it, and that quoting is what decides the order
the steps run in: a judge cannot score a review that has not been written yet, and
the step-by-step analysis has nothing to walk through until the linter and the code
smell detector have reported.

Pure logic with no Qt and no network, so the wiring can be tested on its own.
"""
from __future__ import annotations

from collections.abc import Mapping

from pybreeze.pybreeze_ui.extend_ai_gui.ai_gui_global_variable import COT_TEMPLATE_RELATION
from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.cot_code_review_prompt_templates.global_rule import (
    build_global_rule_template
)
from pybreeze.pybreeze_ui.extend_ai_gui.prompt_store import load_prompt
from pybreeze.utils.logging.logger import pybreeze_logger

# The key the code under review is seeded into the results under.
CODE_DIFF = "code_diff"

# The result key each step's answer is stored under.
STEP_RESULT_KEY: dict[str, str] = {
    "first_summary_prompt.md": "first_summary",
    "first_code_review.md": "first_code_review",
    "judge_single_review.md": "judge_single_review",
    "linter.md": "linter",
    "code_smell_detector.md": "code_smell",
    "step_by_step_analysis.md": "step_by_step",
    "total_summary.md": "total_summary",
    "judge.md": "judge",
}

# Each step's template placeholders, and the result key that fills each one.
STEP_ARGUMENTS: dict[str, dict[str, str]] = {
    "first_summary_prompt.md": {"code_diff": CODE_DIFF},
    "first_code_review.md": {"code_diff": CODE_DIFF},
    # Scores the one review just written, against the code it was written about.
    "judge_single_review.md": {
        "review_comment": "first_code_review",
        "code_diff": CODE_DIFF,
    },
    "linter.md": {"code_diff": CODE_DIFF},
    "code_smell_detector.md": {"code_diff": CODE_DIFF},
    # Walks every lint message and code smell through cause, impact and fix.
    "step_by_step_analysis.md": {
        "linter_result": "linter",
        "code_smell_result": "code_smell",
    },
    "total_summary.md": {
        "first_code_review": "first_code_review",
        "first_summary": "first_summary",
        "linter_result": "linter",
        "code_smell_result": "code_smell",
        "code_diff": CODE_DIFF,
    },
    # Scores the finished summary with the findings it was meant to cover in hand.
    "judge.md": {
        "review_comment": "total_summary",
        "code_smell_detector_messages": "code_smell",
        "linter_messages": "linter",
        "code_diff": CODE_DIFF,
    },
}


def build_prompt(step: str, results: Mapping[str, str]) -> str | None:
    """Return the prompt for *step*, wrapped in the global review rules.

    :param step: the template file name the step is known by
    :param results: the answers collected so far, keyed as in
        :data:`STEP_RESULT_KEY`, with the code under review under
        :data:`CODE_DIFF`
    :return: the prompt to send, or ``None`` when *step* is not part of the chain
    """
    built_in = COT_TEMPLATE_RELATION.get(step)
    arguments = STEP_ARGUMENTS.get(step)
    if built_in is None or arguments is None:
        return None
    # A step whose input never ran quotes an empty section rather than the word
    # "None": the model should see that there is nothing there, not read a value.
    filled = {
        placeholder: results.get(key, "")
        for placeholder, key in arguments.items()
    }
    template = load_prompt(step, built_in)
    try:
        body = template.format(**filled)
    except (KeyError, IndexError, ValueError) as error:
        # An edited prompt that names a placeholder the chain cannot fill would
        # otherwise take the whole review down. Fall back to the built-in and say
        # so, rather than failing a step the user cannot debug from the UI.
        pybreeze_logger.error(
            "Edited prompt %s could not be filled in (%r); using the built-in",
            step, error)
        body = built_in.format(**filled)
    return build_global_rule_template(prompt=body)
