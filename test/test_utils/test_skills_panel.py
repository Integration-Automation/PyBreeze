"""The Skills panel keeps what the user put in the prompt, and sends only a prompt with code in it.

Switching the template replaced the edit area without a word, taking the code
the user had pasted with it; and a template sent as it was asked the endpoint
to review ``{code_diff}``.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.extend_ai_gui import prompt_store
from pybreeze.pybreeze_ui.extend_ai_gui.ai_gui_global_variable import SKILLS_TEMPLATE_FILES
from pybreeze.pybreeze_ui.extend_ai_gui.skills import skills_send_gui
from pybreeze.pybreeze_ui.extend_ai_gui.skills.skills_send_gui import SkillsSendGUI

_PASTED = "please look at this:\ndef f():\n    return 1\n"


@pytest.fixture(scope="module", autouse=True)
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture
def panel(tmp_path, monkeypatch):
    # The built-in prompts, never the user's own
    monkeypatch.setattr(prompt_store, "pybreeze_data_path", lambda: tmp_path)
    widget = SkillsSendGUI()
    yield widget
    widget.deleteLater()


@pytest.fixture
def answer(monkeypatch):
    """What the replace question gets, and how often it was asked."""
    state = {"reply": QMessageBox.StandardButton.No, "asked": 0}

    def question(*_args):
        state["asked"] += 1
        return state["reply"]

    monkeypatch.setattr(QMessageBox, "question", staticmethod(question))
    return state


def _type(panel, text: str) -> None:
    """Put *text* in the prompt as typing or pasting does, marking it edited."""
    panel.prompt_input.selectAll()
    panel.prompt_input.insertPlainText(text)


class TestSwitchingTheTemplate:
    def test_an_untouched_prompt_is_replaced_without_asking(self, panel, answer):
        panel.prompt_select.setCurrentText(SKILLS_TEMPLATE_FILES[1])

        assert answer["asked"] == 0
        assert panel.prompt_input.toPlainText() != ""

    def test_an_edited_prompt_is_kept_when_the_user_says_no(self, panel, answer):
        _type(panel, _PASTED)

        panel.prompt_select.setCurrentText(SKILLS_TEMPLATE_FILES[1])

        assert answer["asked"] == 1
        assert panel.prompt_input.toPlainText() == _PASTED
        # The selector names what is in the edit area
        assert panel.prompt_select.currentText() == SKILLS_TEMPLATE_FILES[0]

    def test_an_edited_prompt_is_replaced_when_the_user_says_yes(self, panel, answer):
        _type(panel, _PASTED)
        answer["reply"] = QMessageBox.StandardButton.Yes

        panel.prompt_select.setCurrentText(SKILLS_TEMPLATE_FILES[1])

        assert panel.prompt_input.toPlainText() != _PASTED
        # A fresh template is not an edit: the next switch does not ask
        panel.prompt_select.setCurrentText(SKILLS_TEMPLATE_FILES[0])
        assert answer["asked"] == 1


class TestSending:
    def test_a_template_with_no_code_in_it_is_not_sent(self, panel, monkeypatch):
        started: list = []
        monkeypatch.setattr(skills_send_gui, "RequestThread", lambda *args: started.append(args))
        panel.api_url_input.setText("https://skills.example/api")

        panel.send_prompt()  # the template as loaded, {code_diff} and all

        assert started == []
        assert "{code_diff}" in panel.response_output.toPlainText()

    def test_a_prompt_with_the_code_in_place_is_sent(self, panel, monkeypatch):
        sent: list = []

        class Thread:
            def __init__(self, url, text) -> None:
                sent.append(text)
                self.answered = self.error = self.finished = self

            def connect(self, _slot) -> None:
                """Nothing to connect to."""

            def start(self) -> None:
                """Nothing to run."""

        monkeypatch.setattr(skills_send_gui, "RequestThread", Thread)
        panel.api_url_input.setText("https://skills.example/api")
        _type(panel, panel.prompt_input.toPlainText().replace("{code_diff}", _PASTED))

        panel.send_prompt()

        assert len(sent) == 1
        assert _PASTED.strip() in sent[0]

    @pytest.mark.parametrize(("url", "prompt"), [("", _PASTED), ("https://skills.example/api", "   ")])
    def test_a_missing_url_or_prompt_is_asked_for(self, panel, monkeypatch, url, prompt):
        monkeypatch.setattr(skills_send_gui, "RequestThread", lambda *args: pytest.fail("a request was sent"))
        panel.api_url_input.setText(url)
        _type(panel, prompt)

        panel.send_prompt()

        assert panel.response_output.toPlainText() == skills_send_gui.language_wrapper.language_word_dict.get(
            "skills_missing_input")

    def test_a_second_send_while_one_is_running_is_ignored(self, panel, monkeypatch):
        class Running:
            @staticmethod
            def isRunning() -> bool:
                return True

        running = Running()
        panel.request_thread = running
        monkeypatch.setattr(skills_send_gui, "RequestThread", lambda *args: pytest.fail("a second request"))
        panel.api_url_input.setText("https://skills.example/api")
        _type(panel, _PASTED)

        panel.send_prompt()

        assert panel.request_thread is running
        panel.request_thread = None

    def test_the_answer_is_shown_and_send_is_offered_again(self, panel):
        panel.send_button.setEnabled(False)

        panel.on_finished("the review")

        assert panel.response_output.toPlainText() == "the review"
        assert panel.send_button.isEnabled()


def test_a_template_it_does_not_know_changes_nothing(panel):
    before = panel.prompt_input.toPlainText()

    panel.load_selected_prompt("no_such_template.md")

    assert panel.prompt_input.toPlainText() == before
