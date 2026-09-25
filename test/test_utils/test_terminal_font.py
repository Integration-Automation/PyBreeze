"""Terminal views: a fixed-pitch font, so columns line up, and the size a pty is given."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QWidget

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_command_widget import SSHCommandWidget
from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow
from pybreeze.pybreeze_ui import fixed_pitch
from pybreeze.pybreeze_ui.fixed_pitch import fixed_pitch_font, use_fixed_pitch_font
from pybreeze.pybreeze_ui.terminal_view import MIN_COLUMNS, MIN_ROWS, terminal_size


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


def _fixed_family() -> str:
    return fixed_pitch_font().family()


def test_the_view_gets_the_fixed_pitch_font_at_its_own_size(app):
    view = QPlainTextEdit()
    font = view.font()
    font.setPointSizeF(13.5)
    view.setFont(font)

    use_fixed_pitch_font(view)

    assert view.font().family() == _fixed_family()
    assert view.font().pointSizeF() == 13.5


def test_a_theme_style_sheet_does_not_take_the_font_back(app):
    # qt_material names a font for every widget ("* { font-family: Roboto }"),
    # and a style sheet's font overrides setFont: the IDE showed Roboto
    theme = QWidget()
    theme.setStyleSheet('* { font-family: "Arial"; }')
    view = QPlainTextEdit(theme)
    use_fixed_pitch_font(view)

    view.ensurePolished()

    assert view.font().family() == _fixed_family()
    theme.close()


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


def _view(width: int, height: int) -> QPlainTextEdit:
    view = QPlainTextEdit()
    use_fixed_pitch_font(view)
    view.resize(width, height)
    view.show()
    QApplication.processEvents()
    return view


def test_a_wider_view_has_more_columns_and_a_taller_one_more_rows(app):
    small, wide, tall = _view(400, 300), _view(800, 300), _view(400, 600)
    try:
        assert terminal_size(wide)[0] > terminal_size(small)[0]
        assert terminal_size(tall)[1] > terminal_size(small)[1]
        assert terminal_size(wide)[1] == terminal_size(small)[1]
    finally:
        for view in (small, wide, tall):
            view.close()


def test_a_squeezed_view_still_gives_a_usable_size(app):
    view = _view(10, 10)
    try:
        assert terminal_size(view) == (MIN_COLUMNS, MIN_ROWS)
    finally:
        view.close()


class TestTheFamilyChosen:
    def test_consolas_comes_before_the_system_font_when_it_is_installed(self, app, monkeypatch):
        # The system's fixed-pitch font on Windows is Courier New
        monkeypatch.setattr(fixed_pitch.QFontDatabase, "hasFamily", staticmethod(lambda family: family == "Consolas"))

        assert fixed_pitch_font().family() == "Consolas"

    def test_without_it_the_system_font_is_used(self, app, monkeypatch):
        monkeypatch.setattr(fixed_pitch.QFontDatabase, "hasFamily", staticmethod(lambda family: False))

        assert fixed_pitch_font().family() == QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
