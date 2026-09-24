"""Terminal output is shown in a fixed-pitch font, so columns line up."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QPlainTextEdit

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_command_widget import SSHCommandWidget
from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow
from pybreeze.pybreeze_ui.terminal_view import use_terminal_font


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


def _fixed_family() -> str:
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()


def test_the_view_gets_the_fixed_pitch_font_at_its_own_size(app):
    view = QPlainTextEdit()
    font = view.font()
    font.setPointSizeF(13.5)
    view.setFont(font)

    use_terminal_font(view)

    assert view.font().family() == _fixed_family()
    assert view.font().pointSizeF() == 13.5


def test_the_ssh_terminal_shows_a_fixed_pitch_font(app):
    widget = SSHCommandWidget()
    try:
        assert widget.terminal.font().family() == _fixed_family()
    finally:
        widget.close()


def test_the_run_window_shows_a_fixed_pitch_font(app):
    window = CodeWindow()
    try:
        assert window.code_result.font().family() == _fixed_family()
    finally:
        window.close()
