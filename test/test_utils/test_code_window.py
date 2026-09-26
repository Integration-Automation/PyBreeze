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

    def test_a_windows_line_ending_is_a_line_break(self, qt_app):
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        window = CodeWindow()
        window.append_output("one\r\ntwo\r\n")

        assert window.code_result.toPlainText() == "one\ntwo\n"

    def test_a_lone_carriage_return_redraws_the_line(self, qt_app):
        # As a terminal does: a progress bar made one line per step
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        window = CodeWindow()
        window.append_output("one\n")
        for step in ["  0%", "\r 50%", "\r100%", "\rdone\n"]:
            window.append_output(step)

        assert window.code_result.toPlainText() == "one\ndone\n"

    @pytest.mark.parametrize("buffer_size", range(1, 16))
    def test_a_rewind_and_clear_cut_anywhere_still_rewinds(self, qt_app, buffer_size):
        # A read ending on "\r\x1b[" sent the "\r" on its own, the window
        # dropped it as the end of a piece, and "50%" stayed: "50%60%"
        import io
        from queue import Queue

        from pybreeze.extend.process_executor.queue_pump import read_stream_into_queue
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        pieces: Queue = Queue()
        read_stream_into_queue(io.BytesIO(b"50%\r\x1b[K60%\n"), pieces, buffer_size=buffer_size,
                               encoding="utf-8", keep_reading=lambda: True)
        window = CodeWindow()
        while not pieces.empty():
            window.append_output(pieces.get())

        assert window.code_result.toPlainText() == "60%\n"

    def test_a_backspace_takes_back_what_an_earlier_piece_showed(self, qt_app):
        # A spinner writing each frame separately showed "|/-done"
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        window = CodeWindow()
        for piece in ["line\n", "|", "\b/", "\b-", "\b\b\b\bdone\n"]:
            window.append_output(piece)

        # Never past the start of the line: "line" stays
        assert window.code_result.toPlainText() == "line\ndone\n"

    def test_a_bar_that_ends_on_a_carriage_return_stays_shown(self, qt_app):
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        window = CodeWindow()
        window.append_output(" 50%\r100%\r")

        assert window.code_result.toPlainText() == "100%"

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


class TestClosingARunningWindowAsks:
    """Closed by the user mid-run, the window asks: stop the run, let it go on, or stay open."""

    def _window(self, monkeypatch, answer: str):
        from types import SimpleNamespace

        from PySide6.QtWidgets import QMessageBox

        from pybreeze.pybreeze_ui.show_code_window import code_window as window_mod

        asked: list = []

        def exec_(box):
            no_is_the_default = box.defaultButton() is box.button(QMessageBox.StandardButton.No)
            asked.append((box.windowTitle(), box.text(), box.standardButtons(), no_is_the_default))
            return getattr(QMessageBox.StandardButton, answer)

        monkeypatch.setattr(window_mod.QMessageBox, "exec", exec_)
        monkeypatch.setattr(window_mod.CodeWindow, "_closed_by_the_user", staticmethod(lambda _event: True))
        window = window_mod.CodeWindow()
        stopped: list = []
        window.runner = SimpleNamespace(process=TestClosedWhileRunning.Running(), stop=lambda: stopped.append(True))
        window.show()
        return window, asked, stopped

    def test_yes_stops_the_run_and_closes(self, qt_app, monkeypatch):
        from je_editor import language_wrapper
        from PySide6.QtWidgets import QMessageBox

        from pybreeze.extend_multi_language.update_language_dict import update_language_dict

        update_language_dict()
        window, asked, stopped = self._window(monkeypatch, "Yes")

        window.close()

        word = language_wrapper.language_word_dict
        buttons = QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
        assert asked == [(word.get("code_window_close_running_title"),
                          word.get("code_window_close_running_message"), buttons, True)]
        assert stopped == [True]
        assert not window.isVisible()

    def test_no_lets_the_run_go_on_and_closes(self, qt_app, monkeypatch):
        window, _asked, stopped = self._window(monkeypatch, "No")

        window.close()

        assert stopped == []
        assert not window.isVisible()
        assert window._closed_while_running

    def test_cancel_keeps_the_window_open(self, qt_app, monkeypatch):
        window, _asked, stopped = self._window(monkeypatch, "Cancel")

        window.close()

        assert stopped == []
        assert window.isVisible()
        window.runner.process.returncode = 0
        window.close()

    def test_a_close_from_code_asks_nothing(self, qt_app, monkeypatch):
        # The IDE closing stops every run itself, then closes the windows
        from pybreeze.pybreeze_ui.show_code_window import code_window as window_mod

        window, asked, _stopped = self._window(monkeypatch, "Cancel")
        monkeypatch.setattr(window_mod.CodeWindow, "_closed_by_the_user", staticmethod(lambda event: event.spontaneous()))

        window.close()

        assert asked == []
        assert not window.isVisible()

    def test_a_finished_run_asks_nothing(self, qt_app, monkeypatch):
        window, asked, _stopped = self._window(monkeypatch, "Cancel")
        window.runner.process.returncode = 0

        window.close()

        assert asked == []
        assert not window.isVisible()


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


class TestTerminalCodes:
    """A coloured or redrawn line shows as its text, not as escape codes."""

    @pytest.mark.parametrize(("written", "shown"), [
        ("\x1b[31mred\x1b[0m done\n", "red done\n"),
        ("\x1b[1;32mok\x1b[m\n", "ok\n"),
        ("\x1b]0;window title\x07after\n", "after\n"),
        ("\x1b]8;;https://example.com\x1b\\link\x1b]8;;\x1b\\\n", "link\n"),
        ("\x1b[2K\x1b[1Gprogress 50%\n", "progress 50%\n"),
        # A backspace takes the character before it back, as in a terminal
        ("a\bb\x0cc\x00\tt\n", "bc\tt\n"),
        # Two-byte escapes: tput sgr0's character-set reset, save/restore cursor
        ("a\x1b(Bb\x1b7c\x1b8d\n", "abcd\n"),
        ("\u4e2d\u6587 stays\n", "\u4e2d\u6587 stays\n"),
    ])
    def test_what_the_window_shows(self, qt_app, written, shown):
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        window = CodeWindow()
        window.append_output(written)

        assert window.code_result.toPlainText() == shown

    def test_a_colour_code_cut_between_two_reads_is_not_shown(self, qt_app):
        # The reader hands output over in pieces; stripped one by one,
        # "\x1b[3" + "2m" showed "[32m"
        import io
        from queue import Queue

        from pybreeze.extend.process_executor.queue_pump import read_stream_into_queue
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        written = b"".join(b"\x1b[32mPASSED test_%d\x1b[0m\n" % number for number in range(300))
        pieces: Queue = Queue()
        read_stream_into_queue(
            io.BufferedReader(io.BytesIO(written), buffer_size=7), pieces,
            buffer_size=7, encoding="utf-8", keep_reading=lambda: True)
        window = CodeWindow()
        while not pieces.empty():
            window.append_output(pieces.get())

        shown = window.code_result.toPlainText()
        assert "[" not in shown
        assert shown.splitlines() == [f"PASSED test_{number}" for number in range(300)]

    def test_a_coloured_progress_bar_still_redraws_its_line(self, qt_app):
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        window = CodeWindow()
        window.append_output("10%\r\x1b[32m20%\x1b[0m\r\n")

        assert window.code_result.toPlainText() == "20%\n"


class TestTheStopButton:
    """A run could be stopped only by closing the IDE: closing its window lets it go on."""

    def test_is_off_until_a_run_starts_and_after_it_ends(self, qt_app):
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        window = CodeWindow()
        assert not window.stop_button.isEnabled()

        window.run_started()
        assert window.stop_button.isEnabled()

        window.run_ended()
        assert not window.stop_button.isEnabled()

    def test_stops_the_runner(self, qt_app):
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        class Runner:
            stopped = 0

            def stop(self):
                self.stopped += 1

        window = CodeWindow()
        window.runner = Runner()
        window.run_started()

        window.stop_button.click()

        assert window.runner.stopped == 1

    def test_stops_a_script_that_would_run_forever(self, qt_app, tmp_path):
        import sys
        import time

        from PySide6.QtWidgets import QApplication

        from pybreeze.extend.process_executor.file_runner_process import FileRunnerProcess
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        script = tmp_path / "forever.py"
        script.write_text("import time\nwhile True:\n    time.sleep(0.1)\n", encoding="utf-8")
        window = CodeWindow()
        window.runner = FileRunnerProcess(window)
        window.runner.run_file({"name": "Python", "compiler": sys.executable}, str(script))
        assert window.stop_button.isEnabled()

        window.stop_button.click()
        deadline = time.monotonic() + 30
        while window.stop_button.isEnabled():
            assert time.monotonic() < deadline, "the run was not stopped"
            QApplication.processEvents()
            time.sleep(0.01)

        assert not window.is_running()
        window.close()
