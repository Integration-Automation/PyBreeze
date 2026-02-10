from automation_ide.automation_editor_ui.extend_ai_gui.prompt_edit_gui.cot_code_review_prompt_templates.code_smell_detector import \
    CODE_SMELL_DETECTOR_TEMPLATE
from automation_ide.automation_editor_ui.extend_ai_gui.prompt_edit_gui.cot_code_review_prompt_templates.first_code_review import \
    FIRST_CODE_REVIEW_TEMPLATE
from automation_ide.automation_editor_ui.extend_ai_gui.prompt_edit_gui.cot_code_review_prompt_templates.first_summary_prompt import \
    FIRST_SUMMARY_TEMPLATE
from automation_ide.automation_editor_ui.extend_ai_gui.prompt_edit_gui.cot_code_review_prompt_templates.global_rule import \
    GLOBAL_RULE_TEMPLATE
from automation_ide.automation_editor_ui.extend_ai_gui.prompt_edit_gui.cot_code_review_prompt_templates.linter import \
    LINTER_TEMPLATE
from automation_ide.automation_editor_ui.extend_ai_gui.prompt_edit_gui.cot_code_review_prompt_templates.total_summary import \
    TOTAL_SUMMARY_TEMPLATE
from automation_ide.automation_editor_ui.extend_ai_gui.prompt_edit_gui.skills_prompt_templates.code_explainer import \
    CODE_EXPLAINER_TEMPLATE
from automation_ide.automation_editor_ui.extend_ai_gui.prompt_edit_gui.skills_prompt_templates.code_review import \
    CODE_REVIEW_SKILL_TEMPLATE

COT_TEMPLATE_FILES = [
    "global_rule.md",
    "first_summary_prompt.md",
    "first_code_review.md",
    "linter.md",
    "code_smell_detector.md",
    "total_summary.md",
]

COT_TEMPLATE_RELATION = {
    "global_rule.md": GLOBAL_RULE_TEMPLATE,
    "first_summary_prompt.md": FIRST_SUMMARY_TEMPLATE,
    "first_code_review.md": FIRST_CODE_REVIEW_TEMPLATE,
    "linter.md": LINTER_TEMPLATE,
    "code_smell_detector.md": CODE_SMELL_DETECTOR_TEMPLATE,
    "total_summary.md": TOTAL_SUMMARY_TEMPLATE,
}

SKILLS_TEMPLATE_FILES = [
    "code_review_skill.md",
    "code_explainer_skill.md",
]

SKILLS_TEMPLATE_RELATION = {
    "code_review_skill.md": CODE_REVIEW_SKILL_TEMPLATE,
    "code_explainer_skill.md": CODE_EXPLAINER_TEMPLATE
}
