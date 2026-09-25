"""Tests for the text diff tool widget."""
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


@pytest.fixture
def widget(app):
    from pybreeze.pybreeze_ui.tools_gui.diff_gui import DiffGUI
    gui = DiffGUI()
    yield gui
    gui.close()
    gui.deleteLater()


def _compare(widget, *, start: bool = True) -> None:
    """Compare (unless *start* is false), and wait for the result: it is worked out off the UI thread."""
    import time

    if start:
        widget.compare()
    deadline = time.monotonic() + 120
    while widget._compare_thread.isRunning() and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)
    widget._compare_thread.wait(1000)
    QApplication.processEvents()


class TestDiffGUI:
    def test_shows_diff(self, widget):
        widget.left_edit.setPlainText("a\nb")
        widget.right_edit.setPlainText("a\nc")
        _compare(widget)
        output = widget.output_edit.toPlainText()
        assert "-b" in output
        assert "+c" in output

    def test_identical_summary(self, widget):
        widget.left_edit.setPlainText("same")
        widget.right_edit.setPlainText("same")
        _compare(widget)
        assert widget.summary_label.text() != ""
        assert widget.output_edit.toPlainText() == ""

    def test_summary_counts(self, widget):
        widget.left_edit.setPlainText("a")
        widget.right_edit.setPlainText("a\nb")
        _compare(widget)
        # The summary mentions one added line.
        assert "1" in widget.summary_label.text()

    def test_copy_output(self, app, widget):
        widget.left_edit.setPlainText("a")
        widget.right_edit.setPlainText("b")
        _compare(widget)
        widget.output_actions.copy()
        assert QApplication.clipboard().text() != ""

    def test_build_summary_line_identical(self, app):
        from pybreeze.pybreeze_ui.tools_gui.diff_gui import build_summary_line
        from pybreeze.utils.diff_tools.text_diff import DiffSummary
        text = build_summary_line(DiffSummary(added=0, removed=0, is_equal=True))
        assert text != ""


class TestALargeComparison:
    def test_the_window_keeps_answering_while_it_is_compared(self, widget):
        # Large texts took seconds to compare (40,000 lines over four), on the UI thread
        import time

        rows = [f'  {{"id": {i}, "value": {i * 7 % 13}}},' for i in range(20000)]
        widget.left_edit.setPlainText("\n".join(rows))
        rows[::10] = [row.replace("value", "VALUE") for row in rows[::10]]
        widget.right_edit.setPlainText("\n".join(rows))

        started = time.monotonic()
        widget.compare()
        returned = time.monotonic() - started
        _compare(widget, start=False)

        assert returned < 0.5
        assert "2000 line(s) added" in widget.summary_label.text()

    def test_a_second_compare_while_one_runs_is_ignored(self, widget, monkeypatch):
        import threading

        from pybreeze.pybreeze_ui.tools_gui import diff_gui

        release = threading.Event()
        real = diff_gui.compare_texts
        monkeypatch.setattr(diff_gui, "compare_texts", lambda left, right: release.wait(10) and real(left, right))
        widget.left_edit.setPlainText("a")
        widget.right_edit.setPlainText("b")
        widget.compare()
        first = widget._compare_thread
        widget.compare()

        assert widget._compare_thread is first
        release.set()
        _compare(widget, start=False)
        assert "+b" in widget.output_edit.toPlainText()


class TestTheColours:
    @pytest.mark.parametrize(("line", "number", "key"), [
        ("--- expected", 0, None),
        ("+++ actual", 1, None),
        ("@@ -1,2 +1,2 @@", 2, "syntax_keyword_color"),
        ("+added", 5, "diff_added_marker_color"),
        ("-removed", 5, "diff_removed_marker_color"),
        ("---x", 7, "diff_removed_marker_color"),  # a removed "--x", not a header
        ("+++x", 7, "diff_added_marker_color"),
        (" unchanged", 5, None),
        ("\\ No newline at end of file", 6, "blame_annotation_color"),
        ("", 5, None),
    ])
    def test_each_kind_of_line_has_its_theme_colour(self, line, number, key):
        from pybreeze.pybreeze_ui.tools_gui.diff_gui import diff_line_colour

        assert diff_line_colour(line, number) == key

    def test_the_diff_is_shown_in_colour(self, widget):
        # It was all one colour: added and removed lines had to be read by their sign
        from je_editor.pyside_ui.main_ui.save_settings.user_color_setting_file import actually_color_dict

        widget.left_edit.setPlainText("a\nb")
        widget.right_edit.setPlainText("a\nc")
        _compare(widget)

        colours = {}
        block = widget.output_edit.document().begin()
        while block.isValid():
            ranges = block.layout().formats()
            colours[block.text()] = ranges[0].format.foreground().color() if ranges else None
            block = block.next()
        assert colours["-b"] == actually_color_dict["diff_removed_marker_color"]
        assert colours["+c"] == actually_color_dict["diff_added_marker_color"]
        assert colours[" a"] is None
