from __future__ import annotations

import re
from typing import TYPE_CHECKING

from je_editor.pyside_ui.main_ui.save_settings.user_color_setting_file import actually_color_dict
from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QGuiApplication, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QWidget, QGridLayout, QPlainTextEdit, QScrollArea

if TYPE_CHECKING:
    from pybreeze.extend.process_executor.file_runner_process import FileRunnerProcess
    from pybreeze.extend.process_executor.python_task_process_manager import TaskProcessManager

# Cap the output scrollback so a runaway script (e.g. an infinite print loop)
# cannot grow the document without bound and exhaust memory; the oldest lines
# are dropped once the limit is reached, like a terminal's scrollback buffer.
# The output is a QPlainTextEdit, which is built for this: in a QTextEdit
# every line written past the cap cost about 15 ms to drop the oldest one, and
# a chatty run froze the IDE for seconds a tick.
MAX_OUTPUT_BLOCKS = 10000


def normalize_line_endings(text: str) -> str:
    """Turn ``\r\n`` and a lone ``\r`` into ``\n``.

    A child on Windows writes ``\r\n``, and a progress bar rewinds its line
    with a bare ``\r``; the text widget only breaks lines on ``\n``.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


# A terminal's control sequences: CSI (colours, cursor moves: ESC [ ... final
# byte), OSC (titles, links: ESC ] ... BEL or ESC \), and any other two-byte
# escape
_TERMINAL_SEQUENCE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]")
# Control characters a text view cannot show: all of C0 but tab, newline and
# carriage return (which normalize_line_endings turns into a line break), and DEL
_CONTROL_CHARACTER = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def strip_terminal_codes(text: str) -> str:
    """*text* without the terminal's control sequences and control characters.

    A script that colours its output (``colorama``, ``rich``, ``pytest
    --color=yes``, ``FORCE_COLOR``) filled the window with ``←[31m``; a
    backspace or form feed showed as a box. Carriage returns are left for
    :func:`normalize_line_endings`.
    """
    return _CONTROL_CHARACTER.sub("", _TERMINAL_SEQUENCE.sub("", text))


class CodeWindow(QWidget):

    # Emitted when a window closes with nothing left running in it, so the
    # main window can let go of it: run windows are kept in a list that only
    # ever grew, one per run, each holding its executor, queues and timer.
    finished_and_closed = Signal()

    def __init__(self):
        # UI used to show run code or shell command result.
        super().__init__()
        self.python_compiler = None
        # The executor writing to this window. Holding it here keeps it alive as
        # long as the window: its timer's connection to its pump does not, so
        # an executor nobody else holds is collected once its reader threads
        # end, and the rest of the output and the exit line never arrive.
        self.runner: TaskProcessManager | FileRunnerProcess | None = None
        self._closed_while_running = False
        self.grid_layout = QGridLayout()
        self.code_result = QPlainTextEdit()
        self.code_result.setLineWrapMode(self.code_result.LineWrapMode.NoWrap)
        self.code_result.setReadOnly(True)
        self.code_result.document().setMaximumBlockCount(MAX_OUTPUT_BLOCKS)
        self.code_result_scroll_area = QScrollArea()
        self.code_result_scroll_area.setWidgetResizable(True)
        self.code_result_scroll_area.setViewportMargins(0, 0, 0, 0)
        self.code_result_scroll_area.setWidget(self.code_result)
        self.grid_layout.addWidget(self.code_result_scroll_area, 0, 0)
        # Adaptive sizing based on screen
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            screen_size = screen.availableSize()
            self.resize(
                max(500, screen_size.width() // 3),
                max(400, screen_size.height() // 3)
            )
        else:
            self.resize(500, 500)
        self.setLayout(self.grid_layout)
        self.setFocus()

    def closeEvent(self, event) -> None:
        """Let the main window forget this one, unless its run is still going.

        A run that is still going keeps its window in the list: it is where
        the rest of the output goes, and closing the IDE stops it from there.
        It is let go of when the run ends (``run_ended``); it used to stay for
        the rest of the session.
        """
        if self.is_running():
            self._closed_while_running = True
        else:
            self.finished_and_closed.emit()
        super().closeEvent(event)

    def run_ended(self) -> None:
        """Called by the executor once its run is over and its output is in.

        A window the user closed while the run went on can go now. Emitted
        after the executor's timer slot returns, not from inside it: the list
        may hold the last reference to this window, and the timer is its child.
        """
        if self._closed_while_running:
            self._closed_while_running = False
            QTimer.singleShot(0, self, self.finished_and_closed.emit)

    def is_running(self) -> bool:
        """Whether the executor writing here still has a child running."""
        runner = self.runner
        process = getattr(runner, "process", None) if runner is not None else None
        return process is not None and process.poll() is None

    def stop_runner(self) -> None:
        """Stop the child this window shows, if one is still running."""
        if self.runner is not None:
            self.runner.stop()

    def append_output(self, text: str, is_error: bool = False, *, own_line: bool = False) -> None:
        """Append *text* to the end of the output, in the normal or the error colour.

        The text goes in as written: a line break is wherever *text* has one.
        *own_line* is for the window's own status messages, which should not
        continue a line the program left unfinished. The text always lands at
        the end, because the widget's own cursor follows the user's clicks and
        selections, and writing there would splice output into the middle or
        overwrite whatever the user had selected.

        The view follows the output while it is scrolled to the bottom, like a
        terminal; once the user scrolls up to read, it stays where they left it.
        """
        scroll_bar = self.code_result.verticalScrollBar()
        follow_output = scroll_bar.value() >= scroll_bar.maximum()
        cursor = QTextCursor(self.code_result.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if own_line and cursor.positionInBlock() > 0:
            text = "\n" + text
        text_format = QTextCharFormat()
        color_key = "error_output_color" if is_error else "normal_output_color"
        text_format.setForeground(actually_color_dict.get(color_key))
        cursor.insertText(normalize_line_endings(strip_terminal_codes(text)), text_format)
        if follow_output:
            scroll_bar.setValue(scroll_bar.maximum())
