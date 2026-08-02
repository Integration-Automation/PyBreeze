"""The editor for the chain-of-thought review prompts."""
from __future__ import annotations

from pybreeze.pybreeze_ui.extend_ai_gui.ai_gui_global_variable import (
    COT_TEMPLATE_FILES, COT_TEMPLATE_RELATION
)
from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.prompt_editor_widget import (
    PromptEditorLabels, PromptEditorWidget
)

COT_LABELS = PromptEditorLabels(
    window_title="cot_prompt_editor_window_title",
    edit_group="cot_prompt_editor_groupbox_edit_file_content",
    create_button="cot_prompt_editor_button_create_file",
    save_button="cot_prompt_editor_button_save_file",
    reload_button="cot_prompt_editor_button_reload_file",
    file_not_exist="cot_prompt_editor_file_not_exist",
    info_title="cot_prompt_editor_msgbox_info_title",
    error_title="cot_prompt_editor_msgbox_error_title",
    success_title="cot_prompt_editor_msgbox_success_title",
    file_exists="cot_prompt_editor_msgbox_file_exists",
    file_created="cot_prompt_editor_msgbox_file_created",
    file_saved="cot_prompt_editor_msgbox_file_saved",
    no_file_selected="cot_prompt_editor_msgbox_no_file_selected",
)


class CoTPromptEditor(PromptEditorWidget):
    """Edit the prompts the chain-of-thought review sends, step by step."""

    def __init__(self, prompt_files=None, parent=None) -> None:
        super().__init__(
            prompt_files or COT_TEMPLATE_FILES, COT_TEMPLATE_RELATION,
            COT_LABELS, parent)
