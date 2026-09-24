"""TestPioneer's Create template: where it writes, and what it does to a template already there."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.menu.automation_menu.test_pioneer_menu import build_test_pioneer_menu as menu


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture()
def window(app, tmp_path, monkeypatch):
    made = QMainWindow()
    made.working_dir = str(tmp_path / "project")
    (tmp_path / "project").mkdir()
    made.told = []
    for kind in ("information", "warning"):
        monkeypatch.setattr(
            QMessageBox, kind,
            staticmethod(lambda *a, kind=kind, **k: made.told.append((kind, a[2]))))
    yield made
    made.deleteLater()


def _template(window):
    from pathlib import Path

    return Path(window.working_dir) / ".TestPioneer" / ".TestPioneer.yml"


def test_it_goes_in_the_ide_working_directory(window, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    menu.create_template(window)

    assert _template(window).is_file()
    assert not (tmp_path / ".TestPioneer").exists()
    assert window.told[-1][0] == "information"


def test_an_edited_template_is_kept_unless_the_user_says_so(window, monkeypatch):
    template = _template(window)
    template.parent.mkdir()
    template.write_text("my edited steps", encoding="utf-8")
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))

    menu.create_template(window)

    # A second click used to overwrite it without asking.
    assert template.read_text(encoding="utf-8") == "my edited steps"


def test_saying_yes_replaces_it(window, monkeypatch):
    template = _template(window)
    template.parent.mkdir()
    template.write_text("my edited steps", encoding="utf-8")
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

    menu.create_template(window)

    assert template.read_text(encoding="utf-8") != "my edited steps"


def test_a_failed_write_is_reported_not_raised(window, monkeypatch):
    def refuse(*_args, **_kwargs):
        raise OSError(13, "Access is denied")

    monkeypatch.setattr(menu, "create_template_dir", refuse)

    menu.create_template(window)

    assert window.told and window.told[-1][0] == "warning"
