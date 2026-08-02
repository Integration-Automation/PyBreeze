"""The editor for the reusable skill prompts."""
from __future__ import annotations

from pybreeze.pybreeze_ui.extend_ai_gui.ai_gui_global_variable import (
    SKILLS_TEMPLATE_FILES, SKILLS_TEMPLATE_RELATION
)
from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.prompt_editor_widget import (
    PromptEditorLabels, PromptEditorWidget
)

SKILL_LABELS = PromptEditorLabels(
    window_title="skill_prompt_editor_window_title",
    edit_group="skill_prompt_editor_groupbox_edit_file_content",
    create_button="skill_prompt_editor_button_create_file",
    save_button="skill_prompt_editor_button_save_file",
    reload_button="skill_prompt_editor_button_reload_file",
    file_not_exist="skill_prompt_editor_file_not_exist",
    info_title="skill_prompt_editor_msgbox_info_title",
    error_title="skill_prompt_editor_msgbox_error_title",
    success_title="skill_prompt_editor_msgbox_success_title",
    file_exists="skill_prompt_editor_msgbox_file_exists",
    file_created="skill_prompt_editor_msgbox_file_created",
    file_saved="skill_prompt_editor_msgbox_file_saved",
    no_file_selected="skill_prompt_editor_msgbox_no_file_selected",
)


class SkillPromptEditor(PromptEditorWidget):
    """Edit the reusable skill prompts the send window offers."""

    def __init__(self, skill_files=None, parent=None) -> None:
        super().__init__(
            skill_files or SKILLS_TEMPLATE_FILES, SKILLS_TEMPLATE_RELATION,
            SKILL_LABELS, parent)
