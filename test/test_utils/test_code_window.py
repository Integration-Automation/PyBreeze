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


class TestOutputPastTheCap:
    def test_a_line_written_past_the_cap_is_cheap(self, qt_app):
        # In a QTextEdit each one took about 15 ms to drop the oldest line:
        # 2000 of them, 30 s with the IDE frozen
        import time

        from pybreeze.pybreeze_ui.show_code_window.code_window import MAX_OUTPUT_BLOCKS, CodeWindow

        window = CodeWindow()
        for i in range(MAX_OUTPUT_BLOCKS):
            window.append_output(f"line {i}\n")
        started = time.perf_counter()
        for i in range(2000):
            window.append_output(f"more {i}\n", is_error=i % 2 == 0)
        elapsed = time.perf_counter() - started

        assert elapsed < 5
        assert window.code_result.document().blockCount() <= MAX_OUTPUT_BLOCKS
        assert window.code_result.toPlainText().endswith("more 1999\n")

    def test_the_error_colour_still_applies(self, qt_app):
        from je_editor.pyside_ui.main_ui.save_settings.user_color_setting_file import actually_color_dict
        from PySide6.QtGui import QTextCursor

        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        window = CodeWindow()
        window.append_output("fine\n")
        window.append_output("broken\n", is_error=True)
        cursor = QTextCursor(window.code_result.document().findBlockByNumber(1))
        cursor.movePosition(QTextCursor.MoveOperation.Right)

        assert cursor.charFormat().foreground().color() == actually_color_dict.get("error_output_color")


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


class TestClosedWhileRunning:
    """A run window closed mid-run is let go of when its run ends, not at IDE exit."""

    class Running:
        def __init__(self) -> None:
            self.returncode = None

        def poll(self):
            return self.returncode

    def _window(self):
        from types import SimpleNamespace

        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        window = CodeWindow()
        process = self.Running()
        window.runner = SimpleNamespace(process=process)
        forgotten: list = []
        window.finished_and_closed.connect(lambda: forgotten.append(window))
        return window, process, forgotten

    def test_it_is_kept_while_the_run_goes_on(self, qt_app):
        window, _process, forgotten = self._window()

        window.close()
        qt_app.processEvents()

        assert forgotten == []

    def test_it_is_let_go_of_when_the_run_ends(self, qt_app):
        window, process, forgotten = self._window()
        window.close()

        process.returncode = 0
        window.run_ended()
        assert forgotten == []  # not from inside the executor's timer slot
        qt_app.processEvents()

        # It used to stay in the main window's list until the IDE exited.
        assert forgotten == [window]

    def test_a_window_still_open_is_not_let_go_of(self, qt_app):
        window, process, forgotten = self._window()

        process.returncode = 0
        window.run_ended()
        qt_app.processEvents()

        assert forgotten == []


def test_the_file_runner_says_when_the_run_ended(qt_app, tmp_path):
    import sys
    import time

    from PySide6.QtWidgets import QApplication

    from pybreeze.extend.process_executor.file_runner_process import FileRunnerProcess
    from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

    script = tmp_path / "quick.py"
    script.write_text("print('done')\n", encoding="utf-8")
    window = CodeWindow()
    ended: list = []
    window.run_ended = lambda: ended.append(True)
    runner = FileRunnerProcess(window)

    runner.run_file({"name": "Python", "compiler": sys.executable}, str(script))
    deadline = time.monotonic() + 30
    while not ended:
        assert time.monotonic() < deadline, "the run never ended"
        QApplication.processEvents()
        time.sleep(0.01)

    assert ended == [True]
