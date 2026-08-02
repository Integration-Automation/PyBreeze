from __future__ import annotations

from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.cot_code_review_prompt_templates.code_smell_detector import \
    CODE_SMELL_DETECTOR_TEMPLATE
from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.cot_code_review_prompt_templates.first_code_review import \
    FIRST_CODE_REVIEW_TEMPLATE
from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.cot_code_review_prompt_templates.first_summary_prompt import \
    FIRST_SUMMARY_TEMPLATE
from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.cot_code_review_prompt_templates.judge import \
    JUDGE_TEMPLATE
from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.cot_code_review_prompt_templates.judge_single_review import \
    JUDGE_SINGLE_REVIEW_TEMPLATE
from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.cot_code_review_prompt_templates.linter import \
    LINTER_TEMPLATE
from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.cot_code_review_prompt_templates.step_by_step_analysis import \
    STEP_BY_STEP_ANALYSIS_TEMPLATE
from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.cot_code_review_prompt_templates.total_summary import \
    TOTAL_SUMMARY_TEMPLATE
from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.skills_prompt_templates.code_explainer import \
    CODE_EXPLAINER_TEMPLATE
from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.skills_prompt_templates.code_review import \
    CODE_REVIEW_SKILL_TEMPLATE

# The order the chain runs in. Each step may only quote steps above it, so the
# order is a dependency order, not a preference: judge_single_review scores the
# review written just before it, step_by_step_analysis walks the linter and code
# smell findings, and judge scores the finished summary.
COT_TEMPLATE_FILES = [
    "first_summary_prompt.md",
    "first_code_review.md",
    "judge_single_review.md",
    "linter.md",
    "code_smell_detector.md",
    "step_by_step_analysis.md",
    "total_summary.md",
    "judge.md",
]

COT_TEMPLATE_RELATION = {
    "first_summary_prompt.md": FIRST_SUMMARY_TEMPLATE,
    "first_code_review.md": FIRST_CODE_REVIEW_TEMPLATE,
    "judge_single_review.md": JUDGE_SINGLE_REVIEW_TEMPLATE,
    "linter.md": LINTER_TEMPLATE,
    "code_smell_detector.md": CODE_SMELL_DETECTOR_TEMPLATE,
    "step_by_step_analysis.md": STEP_BY_STEP_ANALYSIS_TEMPLATE,
    "total_summary.md": TOTAL_SUMMARY_TEMPLATE,
    "judge.md": JUDGE_TEMPLATE,
}

SKILLS_TEMPLATE_FILES = [
    "code_review_skill.md",
    "code_explainer_skill.md",
]

SKILLS_TEMPLATE_RELATION = {
    "code_review_skill.md": CODE_REVIEW_SKILL_TEMPLATE,
    "code_explainer_skill.md": CODE_EXPLAINER_TEMPLATE
}
