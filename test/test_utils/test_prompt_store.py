"""An edited prompt file must be what the review actually sends."""
from __future__ import annotations

import os
from pathlib import Path

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


@pytest.fixture
def prompts(tmp_path, monkeypatch):
    """Point the prompt directory at a temporary one, never the real home."""
    monkeypatch.setattr(prompt_store, "pybreeze_data_path", lambda: tmp_path)
    return tmp_path / "prompts"


def write(prompts, name: str, text: str) -> None:
    prompts.mkdir(parents=True, exist_ok=True)
    (prompts / name).write_text(text, encoding="utf-8")


class TestWhereThePromptsLive:
    def test_looking_at_a_prompt_creates_no_directory(self, prompts):
        # Opening the editor on a built-in prompt must leave nothing behind.
        load_prompt("linter.md", "built-in")
        assert not prompt_dir().exists()

    def test_looking_at_a_prompt_does_not_create_the_data_directory_either(self, tmp_path, monkeypatch):
        data = tmp_path / "home" / ".pybreeze"
        monkeypatch.setattr(prompt_store, "pybreeze_data_path", lambda: data)

        assert load_prompt("linter.md", "built-in") == "built-in"
        assert not data.exists()

    def test_a_file_where_the_data_directory_should_be_gives_the_built_in(self, tmp_path, monkeypatch):
        # Making the directory raised FileExistsError on the review's worker
        # thread, and the review stopped with nothing in the panel.
        data = tmp_path / ".pybreeze"
        data.write_text("not a folder", encoding="utf-8")
        monkeypatch.setattr(prompt_store, "pybreeze_data_path", lambda: data)

        assert load_prompt("linter.md", "built-in") == "built-in"

    def test_a_prompt_folder_that_cannot_be_looked_into_gives_the_built_in(self, prompts, monkeypatch):
        looked_up = prompt_store.Path.is_file

        def refuse(path) -> bool:
            if path.name == "linter.md":
                raise PermissionError(13, "Access is denied")
            return looked_up(path)

        monkeypatch.setattr(prompt_store.Path, "is_file", refuse)

        assert load_prompt("linter.md", "built-in") == "built-in"

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

    def test_saving_in_the_editor_changes_what_the_chain_sends(self, prompts, monkeypatch):
        from PySide6.QtWidgets import QApplication, QMessageBox

        from pybreeze.extend_multi_language.update_language_dict import update_language_dict
        from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.cot_prompt_editor_widget import (
            CoTPromptEditor
        )

        QApplication.instance() or QApplication([])
        update_language_dict()
        editor = CoTPromptEditor()
        # The confirmation dialogs would block; the save itself is what matters.
        monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))

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


def _cot_editor(monkeypatch):
    """A CoT prompt editor whose message boxes answer without blocking."""
    from PySide6.QtWidgets import QApplication, QMessageBox

    from pybreeze.extend_multi_language.update_language_dict import update_language_dict
    from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.cot_prompt_editor_widget import (
        CoTPromptEditor
    )

    QApplication.instance() or QApplication([])
    update_language_dict()
    shown: list = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: shown.append(a)))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a)))
    editor = CoTPromptEditor()
    editor.shown = shown
    return editor


class TestAPromptFileInAnotherEncoding:
    """A prompt saved as "ANSI" on Windows is not UTF-8; it must not break anything."""

    def test_the_review_falls_back_to_the_built_in(self, prompts):
        prompts.mkdir(parents=True, exist_ok=True)
        (prompts / "linter.md").write_bytes("檢查這段程式碼".encode("cp950"))

        assert load_prompt("linter.md", "built-in") == "built-in"

    def test_a_byte_order_mark_does_not_reach_the_prompt(self, prompts):
        prompts.mkdir(parents=True, exist_ok=True)
        (prompts / "linter.md").write_text("my prompt", encoding="utf-8-sig")

        assert load_prompt("linter.md", "built-in") == "my prompt"

    def test_the_editor_opens_it_and_says_so(self, prompts, monkeypatch):
        prompts.mkdir(parents=True, exist_ok=True)
        (prompts / "linter.md").write_bytes("檢查這段程式碼".encode("cp950"))
        editor = _cot_editor(monkeypatch)

        editor.file_selector.setCurrentIndex(editor.prompt_files.index("linter.md"))

        assert editor.shown, "the user was not told the file is not UTF-8"
        assert editor.current_file == str(prompt_path("linter.md"))
        editor.close()
        editor.deleteLater()


class TestAChangeOnDiskWhileEditing:
    def test_unsaved_edits_are_kept_unless_the_user_says_otherwise(self, prompts, monkeypatch):
        from PySide6.QtWidgets import QMessageBox

        write(prompts, "linter.md", "on disk")
        editor = _cot_editor(monkeypatch)
        editor.file_selector.setCurrentIndex(editor.prompt_files.index("linter.md"))
        # Typed, the way a keystroke arrives: setPlainText() would reset the
        # document's modified flag, which is what a real edit sets.
        editor.middle_editor.selectAll()
        editor.middle_editor.textCursor().insertText("typed here, not saved")
        monkeypatch.setattr(
            QMessageBox, "question",
            staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))

        write(prompts, "linter.md", "changed elsewhere")
        editor.on_file_changed(editor.current_file)

        assert editor.middle_editor.toPlainText() == "typed here, not saved"
        editor.close()
        editor.deleteLater()

    def test_with_nothing_unsaved_it_reloads_without_asking(self, prompts, monkeypatch):
        from PySide6.QtWidgets import QMessageBox

        write(prompts, "linter.md", "on disk")
        editor = _cot_editor(monkeypatch)
        editor.file_selector.setCurrentIndex(editor.prompt_files.index("linter.md"))
        asked: list = []
        monkeypatch.setattr(
            QMessageBox, "question", staticmethod(lambda *a, **k: asked.append(a)))

        write(prompts, "linter.md", "changed elsewhere")
        editor.on_file_changed(editor.current_file)

        assert editor.middle_editor.toPlainText() == "changed elsewhere"
        assert asked == []
        editor.close()
        editor.deleteLater()


class TestSavingAPrompt:
    def test_a_save_that_fails_leaves_the_last_good_file(self, prompts, monkeypatch):
        from pybreeze.utils.file_process import replace_file

        write(prompts, "linter.md", "the last good prompt")
        editor = _cot_editor(monkeypatch)
        editor.file_selector.setCurrentIndex(editor.prompt_files.index("linter.md"))
        editor.middle_editor.setPlainText("a new prompt")

        def refuse(*_args):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(replace_file.os, "replace", refuse)
        editor.save_file()

        assert (prompts / "linter.md").read_text(encoding="utf-8") == "the last good prompt"
        assert [path.name for path in prompts.iterdir()] == ["linter.md"]
        editor.close()
        editor.deleteLater()


class TestClosingThePromptEditor:
    def test_its_file_watcher_goes_with_it(self, prompts, monkeypatch):
        # An orphan watcher outlived the editor and delivered the next change on
        # disk to a deleted widget -- a crash, once the slot touched the editor.
        from PySide6.QtCore import QObject

        editor = _cot_editor(monkeypatch)

        assert editor.watcher.parent() is editor
        assert isinstance(editor.watcher, QObject)
        editor.close()
        editor.deleteLater()

    def test_closing_it_stops_watching(self, prompts, monkeypatch):
        write(prompts, "linter.md", "on disk")
        editor = _cot_editor(monkeypatch)

        editor.close()

        assert editor.watcher.files() == []
        editor.deleteLater()


class TestATemplateWithNoFileYet:
    def test_saving_it_does_not_write_the_does_not_exist_note(self, prompts, monkeypatch):
        # The note used to be the edit area's text, so Save wrote it to disk and
        # every review then sent "(File linter.md does not exist)" as the prompt.
        editor = _cot_editor(monkeypatch)
        editor.file_selector.setCurrentIndex(editor.prompt_files.index("linter.md"))

        assert editor.middle_editor.toPlainText() == ""
        assert "linter.md" in editor.middle_editor.placeholderText()
        editor.save_file()

        assert load_prompt("linter.md", "built-in") == "built-in"
        editor.close()
        editor.deleteLater()


class TestSwitchingTemplatesWithUnsavedEdits:
    @staticmethod
    def _typed(editor, text):
        editor.middle_editor.selectAll()
        editor.middle_editor.textCursor().insertText(text)

    def test_keeping_the_edits_stays_on_the_template(self, prompts, monkeypatch):
        from PySide6.QtWidgets import QMessageBox

        write(prompts, "linter.md", "on disk")
        editor = _cot_editor(monkeypatch)
        linter = editor.prompt_files.index("linter.md")
        editor.file_selector.setCurrentIndex(linter)
        self._typed(editor, "MY EDITS")
        monkeypatch.setattr(
            QMessageBox, "question",
            staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))

        editor.file_selector.setCurrentIndex((linter + 1) % len(editor.prompt_files))

        assert editor.file_selector.currentIndex() == linter
        assert editor.middle_editor.toPlainText() == "MY EDITS"
        assert editor.current_file == str(prompt_path("linter.md"))
        editor.close()
        editor.deleteLater()

    def test_letting_them_go_switches(self, prompts, monkeypatch):
        from PySide6.QtWidgets import QMessageBox

        editor = _cot_editor(monkeypatch)
        linter = editor.prompt_files.index("linter.md")
        editor.file_selector.setCurrentIndex(linter)
        self._typed(editor, "MY EDITS")
        monkeypatch.setattr(
            QMessageBox, "question",
            staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
        other = (linter + 1) % len(editor.prompt_files)

        editor.file_selector.setCurrentIndex(other)

        assert editor.current_file == str(prompt_path(editor.prompt_files[other]))
        assert editor.middle_editor.toPlainText() != "MY EDITS"
        editor.close()
        editor.deleteLater()

    def test_reload_asks_before_losing_edits(self, prompts, monkeypatch):
        from PySide6.QtWidgets import QMessageBox

        write(prompts, "linter.md", "on disk")
        editor = _cot_editor(monkeypatch)
        editor.file_selector.setCurrentIndex(editor.prompt_files.index("linter.md"))
        self._typed(editor, "MY EDITS")
        monkeypatch.setattr(
            QMessageBox, "question",
            staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))

        editor.reload_button.click()

        assert editor.middle_editor.toPlainText() == "MY EDITS"
        editor.close()
        editor.deleteLater()


class TestAnEditedPromptThatReachesIntoAPlaceholder:
    @pytest.mark.parametrize("edited", [
        "Review {code_diff[x]}",      # a TypeError that used to end the whole chain
        "Review {code_diff.upper}",   # quietly sent "<built-in method upper ...>"
        "Review {code_diff[0]}",      # quietly sent one character of the code
        "Review {0}",
        "Review {}",
    ])
    def test_it_falls_back_to_the_built_in(self, prompts, edited):
        write(prompts, "linter.md", edited)

        prompt = build_prompt("linter.md", {CODE_DIFF: CODE})

        assert CODE in prompt
        assert "built-in method" not in prompt

    def test_escaped_braces_and_a_format_spec_still_work(self, prompts):
        write(prompts, "linter.md", "{{literal}} then {code_diff!s:>1}")

        prompt = build_prompt("linter.md", {CODE_DIFF: CODE})

        assert "{literal}" in prompt
        assert CODE in prompt


def _prompt_editor():
    from PySide6.QtWidgets import QApplication

    from pybreeze.extend_multi_language.update_language_dict import update_language_dict
    from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.cot_prompt_editor_widget import CoTPromptEditor

    QApplication.instance() or QApplication([])
    update_language_dict()
    return CoTPromptEditor()


class TestThePromptEditorKeepsWhatWasTyped:
    def test_create_asks_before_replacing_typed_text(self, prompts, monkeypatch):
        # Create wrote the built-in template over it without asking
        from PySide6.QtWidgets import QMessageBox

        editor = _prompt_editor()
        editor.file_selector.setCurrentIndex(editor.prompt_files.index("linter.md"))
        editor.middle_editor.setPlainText("my own prompt")
        editor.middle_editor.document().setModified(True)
        asked: list = []
        monkeypatch.setattr(QMessageBox, "question",
                            staticmethod(lambda *args: asked.append(args[2]) or QMessageBox.StandardButton.No))

        editor.create_file()

        assert asked
        assert not (prompts / "linter.md").exists()
        assert editor.middle_editor.toPlainText() == "my own prompt"
        editor.deleteLater()

    def test_a_file_that_cannot_be_read_does_not_show_the_previous_text(self, prompts, monkeypatch):
        # The previous template's text stayed on screen under this one's name
        from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui import prompt_editor_widget

        write(prompts, "linter.md", "the linter prompt")
        editor = _prompt_editor()
        editor.middle_editor.setPlainText("the previous template")
        monkeypatch.setattr(prompt_editor_widget, "read_prompt_file", lambda _path: None)

        def locked(_path):
            raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(Path, "read_bytes", locked)
        editor.load_file_content(editor.prompt_files.index("linter.md"))

        assert editor.middle_editor.toPlainText() == ""
        assert editor.current_file is None
        assert "Permission denied" in editor.middle_editor.placeholderText()
        editor.deleteLater()

    def test_saving_writes_back_the_characters_it_did_not_touch(self, prompts, monkeypatch):
        # Saved from toPlainText(), a no-break space became a space and U+2028 a newline
        original = "Review\xa0this: {code_diff}\n"
        write(prompts, "linter.md", original)
        editor = _cot_editor(monkeypatch)
        editor.file_selector.setCurrentIndex(editor.prompt_files.index("linter.md"))

        editor.save_file()

        assert (prompts / "linter.md").read_text(encoding="utf-8") == original
        editor.close()
        editor.deleteLater()



class TestCreatingAPromptFile:
    def test_create_writes_the_built_in_and_watches_it(self, prompts, monkeypatch):
        editor = _cot_editor(monkeypatch)
        editor.file_selector.setCurrentIndex(editor.prompt_files.index("linter.md"))

        editor.create_file()

        built_in = editor.templates["linter.md"]
        assert (prompts / "linter.md").read_text(encoding="utf-8") == built_in
        assert editor.middle_editor.toPlainText() == built_in
        assert not editor.middle_editor.document().isModified()
        assert str(prompts / "linter.md") in editor.watcher.files()
        assert len(editor.shown) == 1  # the file was created
        editor.close()
        editor.deleteLater()

    def test_a_file_already_there_is_left_as_it_is(self, prompts, monkeypatch):
        write(prompts, "linter.md", "my own linter prompt")
        editor = _cot_editor(monkeypatch)
        editor.file_selector.setCurrentIndex(editor.prompt_files.index("linter.md"))

        editor.create_file()

        assert (prompts / "linter.md").read_text(encoding="utf-8") == "my own linter prompt"
        assert len(editor.shown) == 1
        assert "linter.md" in editor.shown[0][2]  # it says which file is already there
        editor.close()
        editor.deleteLater()


class TestWithNoFileShown:
    # As after a prompt file that could not be read: nothing was shown, so
    # nothing may be written back or created in its place.
    def test_save_says_no_file_is_selected_and_writes_nothing(self, prompts, monkeypatch):
        editor = _cot_editor(monkeypatch)
        editor.current_file = None
        editor.middle_editor.setPlainText("typed with no file")

        editor.save_file()

        assert len(editor.shown) == 1
        assert not prompts.exists() or list(prompts.iterdir()) == []
        editor.close()
        editor.deleteLater()

    def test_create_does_nothing(self, prompts, monkeypatch):
        editor = _cot_editor(monkeypatch)
        editor.current_file = None

        editor.create_file()

        assert editor.shown == []
        assert not prompts.exists()
        editor.close()
        editor.deleteLater()

    def test_a_change_to_another_file_is_not_reloaded(self, prompts, monkeypatch):
        write(prompts, "linter.md", "the linter prompt")
        editor = _cot_editor(monkeypatch)
        editor.file_selector.setCurrentIndex(editor.prompt_files.index("linter.md"))
        editor.middle_editor.setPlainText("typed")
        editor.middle_editor.document().setModified(True)

        editor.on_file_changed(str(prompts / "judge.md"))

        assert editor.middle_editor.toPlainText() == "typed"
        editor.close()
        editor.deleteLater()
