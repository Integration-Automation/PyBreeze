"""Tests for the regex tester tool widget."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


def run(widget) -> None:
    """Start the pattern and wait for its answer, as the tab would on the event loop."""
    widget.test()
    thread = widget._match_thread
    assert thread.wait(30_000), "the pattern did not come back"
    QApplication.processEvents()


@pytest.fixture()
def widget(app):
    from pybreeze.pybreeze_ui.tools_gui.regex_gui import RegexGUI
    gui = RegexGUI()
    yield gui
    gui.close()
    gui.deleteLater()


class TestRegexGUI:
    def test_finds_matches(self, widget):
        widget.pattern_edit.setText(r"\d+")
        widget.text_edit.setPlainText("a1 b22")
        run(widget)
        output = widget.output_edit.toPlainText()
        assert "'1'" in output
        assert "'22'" in output

    def test_no_match_message(self, widget):
        widget.pattern_edit.setText(r"z")
        widget.text_edit.setPlainText("abc")
        run(widget)
        assert widget.output_edit.toPlainText() != ""
        assert "'z'" not in widget.output_edit.toPlainText()

    def test_invalid_pattern_shows_error(self, widget):
        widget.pattern_edit.setText("(")
        widget.text_edit.setPlainText("abc")
        run(widget)
        assert widget.output_edit.toPlainText() != ""

    def test_ignorecase_flag_used(self, widget):
        widget.pattern_edit.setText("abc")
        widget.text_edit.setPlainText("ABC")
        widget.flag_checkboxes["IGNORECASE"].setChecked(True)
        run(widget)
        assert "'ABC'" in widget.output_edit.toPlainText()
        widget.flag_checkboxes["IGNORECASE"].setChecked(False)

    def test_selected_flags(self, widget):
        widget.flag_checkboxes["DOTALL"].setChecked(True)
        assert "DOTALL" in widget.selected_flags()
        widget.flag_checkboxes["DOTALL"].setChecked(False)

    def test_copy_output(self, app, widget):
        widget.pattern_edit.setText(r"\d+")
        widget.text_edit.setPlainText("a1")
        run(widget)
        widget.actions.copy()
        assert "'1'" in QApplication.clipboard().text()

    def test_build_matches_text_no_matches(self, app):
        from pybreeze.pybreeze_ui.tools_gui.regex_gui import build_matches_text
        assert build_matches_text([], "none") == "none"


class TestAPatternThatNeverFinishes:
    def test_the_tab_does_not_wait_for_it(self, widget, monkeypatch):
        import threading

        from pybreeze.pybreeze_ui.tools_gui import regex_gui

        answering = threading.Event()

        def slow(*_args):
            answering.wait(10)
            return []

        monkeypatch.setattr(regex_gui, "find_matches_bounded", slow)
        widget.pattern_edit.setText("a")
        widget.text_edit.setPlainText("a")

        widget.test()

        assert widget._match_thread.isRunning(), "test() waited for the pattern"
        assert not widget.test_button.isEnabled()
        answering.set()
        assert widget._match_thread.wait(10_000)
        QApplication.processEvents()
        assert widget.test_button.isEnabled()

    def test_catastrophic_backtracking_is_stopped_and_reported(self, widget, monkeypatch):
        from pybreeze.utils.regex_tools import regex_tester

        # A 2 s deadline instead of the tab's 5 s, to keep the test short. The
        # default is bound at definition, so it is the defaults that are patched.
        monkeypatch.setattr(
            regex_tester.find_matches_bounded, "__defaults__", (None, 2.0))
        widget.pattern_edit.setText("(a+)+$")
        widget.text_edit.setPlainText("a" * 40 + "b")

        run(widget)

        assert "still running" in widget.output_edit.toPlainText()


class TestWhatTheTabOffersToSave:
    def test_nothing_is_saved_while_a_pattern_runs(self, widget):
        # Save during a run wrote "Running the pattern..."
        widget.pattern_edit.setText(r"\d")
        widget.text_edit.setPlainText("a1")
        run(widget)
        assert widget._valid_output

        widget.pattern_edit.setText("(a+)+$")
        widget.text_edit.setPlainText("a" * 60 + "b")
        widget.test()

        assert widget._valid_output is False
        widget.close()  # stops the worker
        widget._match_thread.wait(30_000)

    def test_a_list_cut_at_the_cap_says_so(self, app):
        from pybreeze.pybreeze_ui.tools_gui.regex_gui import build_matches_text
        from pybreeze.utils.regex_tools.regex_tester import MAX_MATCHES, MatchResult

        matches = [MatchResult("a", i, i + 1) for i in range(MAX_MATCHES)]

        assert "may be more" in build_matches_text(matches, "none")
        assert "may be more" not in build_matches_text(matches[:3], "none")
