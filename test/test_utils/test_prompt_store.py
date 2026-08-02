"""An edited prompt file must be what the review actually sends."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from pybreeze.pybreeze_ui.extend_ai_gui import prompt_store
from pybreeze.pybreeze_ui.extend_ai_gui.ai_gui_global_variable import (
    COT_TEMPLATE_RELATION, SKILLS_TEMPLATE_RELATION
)
from pybreeze.pybreeze_ui.extend_ai_gui.code_review.cot_chain import CODE_DIFF, build_prompt
from pybreeze.pybreeze_ui.extend_ai_gui.prompt_store import (
    load_prompt, prompt_dir, prompt_path
)

CODE = "def f():\n    pass\n"


@pytest.fixture()
def prompts(tmp_path, monkeypatch):
    """Point the prompt directory at a temporary one, never the real home."""
    monkeypatch.setattr(prompt_store, "pybreeze_data_dir", lambda: tmp_path)
    return tmp_path / "prompts"


def write(prompts, name: str, text: str) -> None:
    prompts.mkdir(parents=True, exist_ok=True)
    (prompts / name).write_text(text, encoding="utf-8")


class TestWhereThePromptsLive:
    def test_looking_at_a_prompt_creates_no_directory(self, prompts):
        # Opening the editor on a built-in prompt must leave nothing behind.
        load_prompt("linter.md", "built-in")
        assert not prompt_dir().exists()

    def test_saving_creates_the_directory(self, prompts, tmp_path):
        from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.prompt_file_io import (
            save_prompt_text
        )

        assert save_prompt_text(None, str(prompt_path("linter.md")), "text", "error")
        assert prompt_dir().is_dir()
        assert load_prompt("linter.md", "built-in") == "text"

    def test_it_sits_under_the_user_directory_not_the_working_one(self, prompts):
        # The whole point of moving off bare filenames: the prompts a user wrote
        # are the same whichever folder the IDE was started from.
        assert prompt_path("linter.md").parent == prompts

    def test_a_prompt_path_is_named_after_its_template(self, prompts):
        assert prompt_path("linter.md").name == "linter.md"


class TestResolvingAPrompt:
    def test_no_file_means_the_built_in_is_used(self, prompts):
        assert load_prompt("linter.md", "built-in") == "built-in"

    def test_an_edited_file_wins(self, prompts):
        write(prompts, "linter.md", "my own linter prompt")
        assert load_prompt("linter.md", "built-in") == "my own linter prompt"

    def test_an_empty_file_falls_back_rather_than_asking_nothing(self, prompts):
        write(prompts, "linter.md", "   \n  ")
        assert load_prompt("linter.md", "built-in") == "built-in"

    def test_an_unreadable_file_falls_back_instead_of_stopping_the_review(
            self, prompts, monkeypatch):
        write(prompts, "linter.md", "my own linter prompt")

        def refuse(*_args, **_kwargs):
            raise OSError("permission denied")

        monkeypatch.setattr(prompt_store.Path, "read_text", refuse)
        assert load_prompt("linter.md", "built-in") == "built-in"


class TestTheChainUsesTheEditedPrompt:
    def test_an_edited_step_reaches_the_prompt_that_is_sent(self, prompts):
        write(prompts, "linter.md", "Only report imports. Code:\n{code_diff}")
        prompt = build_prompt("linter.md", {CODE_DIFF: CODE})
        assert "Only report imports" in prompt
        assert CODE in prompt

    def test_an_unedited_step_still_uses_its_built_in(self, prompts):
        prompt = build_prompt("linter.md", {CODE_DIFF: CODE})
        assert "Only report imports" not in prompt
        assert prompt

    def test_the_edited_prompt_is_still_wrapped_in_the_global_rules(self, prompts):
        write(prompts, "linter.md", "Only report imports.")
        prompt = build_prompt("linter.md", {CODE_DIFF: CODE})
        assert "conduct a code review according to the following global rules" in prompt

    def test_an_edit_that_drops_a_placeholder_is_honoured(self, prompts):
        # Removing {code_diff} is a legitimate edit, not an error.
        write(prompts, "linter.md", "Say hello and nothing else.")
        assert "Say hello" in build_prompt("linter.md", {CODE_DIFF: CODE})

    def test_an_edit_naming_an_unknown_placeholder_falls_back(self, prompts):
        # A prompt the chain cannot fill would otherwise take the review down
        # with a KeyError the user could not diagnose from the UI.
        write(prompts, "linter.md", "Review {this_does_not_exist}")
        prompt = build_prompt("linter.md", {CODE_DIFF: CODE})
        assert prompt is not None
        assert "this_does_not_exist" not in prompt
        assert CODE in prompt

    def test_every_template_can_be_overridden(self, prompts):
        for name in COT_TEMPLATE_RELATION:
            write(prompts, name, f"edited {name}")
            prompt = build_prompt(name, {CODE_DIFF: CODE})
            assert f"edited {name}" in prompt, name


class TestTheEditorAndTheChainAgree:
    """The point of the editor: what is saved there is what a review sends."""

    def test_saving_in_the_editor_changes_what_the_chain_sends(self, prompts):
        from PySide6.QtWidgets import QApplication, QMessageBox

        from pybreeze.extend_multi_language.update_language_dict import update_language_dict
        from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.cot_prompt_editor_widget import (
            CoTPromptEditor
        )

        QApplication.instance() or QApplication([])
        update_language_dict()
        editor = CoTPromptEditor()
        # The confirmation dialogs would block; the save itself is what matters.
        QMessageBox.information = staticmethod(lambda *a, **k: None)

        editor.file_selector.setCurrentIndex(
            editor.prompt_files.index("linter.md"))
        editor.middle_editor.setPlainText("Only report imports. Code:\n{code_diff}")
        editor.save_file()

        assert "Only report imports" in build_prompt("linter.md", {CODE_DIFF: CODE})
        editor.deleteLater()

    def test_the_editor_writes_where_the_chain_reads(self, prompts):
        from PySide6.QtWidgets import QApplication

        from pybreeze.extend_multi_language.update_language_dict import update_language_dict
        from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.cot_prompt_editor_widget import (
            CoTPromptEditor
        )

        QApplication.instance() or QApplication([])
        update_language_dict()
        editor = CoTPromptEditor()
        editor.file_selector.setCurrentIndex(0)
        assert editor.current_file == str(prompt_path(editor.prompt_files[0]))
        editor.deleteLater()

    def test_the_editor_shows_an_edited_file_rather_than_the_built_in(self, prompts):
        from PySide6.QtWidgets import QApplication

        from pybreeze.extend_multi_language.update_language_dict import update_language_dict
        from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.cot_prompt_editor_widget import (
            CoTPromptEditor
        )

        QApplication.instance() or QApplication([])
        update_language_dict()
        write(prompts, "linter.md", "my own linter prompt")
        editor = CoTPromptEditor()
        editor.file_selector.setCurrentIndex(editor.prompt_files.index("linter.md"))
        assert editor.middle_editor.toPlainText() == "my own linter prompt"
        editor.deleteLater()


class TestTheSkillSelectorLoadsWhatItNames:
    def test_choosing_a_skill_loads_its_built_in_text(self, prompts):
        from PySide6.QtWidgets import QApplication

        from pybreeze.extend_multi_language.update_language_dict import update_language_dict
        from pybreeze.pybreeze_ui.extend_ai_gui.skills.skills_send_gui import SkillsSendGUI

        QApplication.instance() or QApplication([])
        update_language_dict()
        widget = SkillsSendGUI()
        first = widget.prompt_select.currentText()
        assert widget.prompt_input.toPlainText() == SKILLS_TEMPLATE_RELATION[first]
        widget.deleteLater()

    def test_an_edited_skill_is_what_the_selector_loads(self, prompts):
        from PySide6.QtWidgets import QApplication

        from pybreeze.extend_multi_language.update_language_dict import update_language_dict
        from pybreeze.pybreeze_ui.extend_ai_gui.skills.skills_send_gui import SkillsSendGUI

        QApplication.instance() or QApplication([])
        update_language_dict()
        name = next(iter(SKILLS_TEMPLATE_RELATION))
        write(prompts, name, "my own skill prompt")
        widget = SkillsSendGUI()
        widget.prompt_select.setCurrentText(name)
        assert widget.prompt_input.toPlainText() == "my own skill prompt"
        widget.deleteLater()
