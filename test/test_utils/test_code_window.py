from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qt_app():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        try:
            app = QApplication([])
        except Exception as exc:  # pragma: no cover - no usable Qt platform
            pytest.skip(f"Cannot start QApplication: {exc}")
    return app


class TestCodeWindowScrollbackCap:
    def test_block_count_is_capped(self, qt_app):
        from pybreeze.pybreeze_ui.show_code_window.code_window import (
            MAX_OUTPUT_BLOCKS,
            CodeWindow,
        )

        window = CodeWindow()
        assert window.code_result.document().maximumBlockCount() == MAX_OUTPUT_BLOCKS

    def test_old_lines_dropped_once_capped(self, qt_app):
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        window = CodeWindow()
        window.code_result.document().setMaximumBlockCount(50)
        cursor = window.code_result.textCursor()
        for i in range(500):
            cursor.insertText(f"line {i}")
            cursor.insertBlock()

        assert window.code_result.document().blockCount() <= 50
        text = window.code_result.toPlainText()
        assert "line 499" in text       # newest kept
        assert "line 0\n" not in text   # oldest dropped


class TestAppendOutput:
    def test_indentation_and_blank_lines_are_kept(self, qt_app):
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        window = CodeWindow()
        for line in ["def f():\n", "    return 1\n", "\n", "\tdone\n"]:
            window.append_output(line)

        assert window.code_result.toPlainText() == "def f():\n    return 1\n\n\tdone\n"

    def test_windows_and_carriage_return_endings_become_line_breaks(self, qt_app):
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        window = CodeWindow()
        window.append_output("one\r\ntwo\r 50%\r100%\n")

        assert window.code_result.toPlainText() == "one\ntwo\n 50%\n100%\n"

    def test_pieces_of_one_line_join_up(self, qt_app):
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        window = CodeWindow()
        for piece in ["abcd", "efgh", "ij\n"]:
            window.append_output(piece)

        assert window.code_result.toPlainText() == "abcdefghij\n"

    def test_a_selection_is_not_overwritten(self, qt_app):
        from PySide6.QtGui import QTextCursor

        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        window = CodeWindow()
        window.append_output("first\nsecond\n")
        selection = window.code_result.textCursor()
        selection.setPosition(0)
        selection.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
        window.code_result.setTextCursor(selection)

        window.append_output("third\n")

        assert window.code_result.toPlainText() == "first\nsecond\nthird\n"

    def test_own_line_starts_after_an_unfinished_line(self, qt_app):
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        window = CodeWindow()
        window.append_output("progress 90%")
        window.append_output("Task exit with code 0\n", own_line=True)
        window.append_output("Task exit with code 0\n", own_line=True)

        assert window.code_result.toPlainText() == (
            "progress 90%\nTask exit with code 0\nTask exit with code 0\n")

    def test_errors_use_the_error_colour(self, qt_app):
        from je_editor.pyside_ui.main_ui.save_settings.user_color_setting_file import (
            actually_color_dict,
        )
        from PySide6.QtGui import QTextCursor

        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        window = CodeWindow()
        window.append_output("ok\n")
        window.append_output("boom\n", is_error=True)

        cursor = QTextCursor(window.code_result.document())
        cursor.setPosition(1)
        assert cursor.charFormat().foreground().color() == actually_color_dict["normal_output_color"]
        cursor.setPosition(len("ok\n") + 1)
        assert cursor.charFormat().foreground().color() == actually_color_dict["error_output_color"]


class TestFollowOutput:
    def test_the_view_follows_output_at_the_bottom(self, qt_app):
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        window = CodeWindow()
        window.show()
        for i in range(300):
            window.append_output(f"line {i}\n")

        scroll_bar = window.code_result.verticalScrollBar()
        assert scroll_bar.maximum() > 0
        assert scroll_bar.value() == scroll_bar.maximum()

    def test_a_reader_who_scrolled_up_is_left_alone(self, qt_app):
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        window = CodeWindow()
        window.show()
        for i in range(300):
            window.append_output(f"line {i}\n")
        scroll_bar = window.code_result.verticalScrollBar()
        scroll_bar.setValue(10)

        for i in range(50):
            window.append_output(f"more {i}\n")

        assert scroll_bar.value() == 10
        assert scroll_bar.maximum() > 10
