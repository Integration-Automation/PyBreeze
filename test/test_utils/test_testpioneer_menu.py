"""Running a TestPioneer script from its menu."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.menu.automation_menu.test_pioneer_menu import build_test_pioneer_menu as menu


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture()
def chosen(monkeypatch) -> dict:
    """Answer the file dialog with ``chosen["path"]``; record the filter and what ran."""
    state: dict = {"path": "", "ran": [], "filter": None, "told": 0}

    def get_open_file_name(_parent=None, *args, filter="", **kwargs):
        state["filter"] = filter
        return state["path"], filter

    class Message:
        def __init__(self, _parent=None) -> None:
            """Collects nothing but the fact it was shown."""

        def setWindowTitle(self, _title) -> None:
            """Title is not checked."""

        def setText(self, _text) -> None:
            """Text is not checked."""

        def exec(self) -> None:
            state["told"] += 1

    monkeypatch.setattr(menu.QFileDialog, "getOpenFileName", staticmethod(get_open_file_name))
    monkeypatch.setattr(menu, "QMessageBox", Message)
    monkeypatch.setattr(
        menu, "init_and_start_test_pioneer_process", lambda _window, path: state["ran"].append(path))
    return state


@pytest.mark.parametrize("name", ["run.yml", "run.yaml", "RUN.YAML"])
def test_either_yaml_extension_runs(app, tmp_path, chosen, name):
    script = tmp_path / name
    script.write_text("jobs: []", encoding="utf-8")
    chosen["path"] = str(script)

    menu.check_file(None)

    assert chosen["ran"] == [str(script)]
    assert chosen["told"] == 0


def test_the_dialog_is_given_the_yaml_filter(app, chosen):
    menu.check_file(None)

    assert "*.yaml" in chosen["filter"] and "*.yml" in chosen["filter"]


def test_another_file_is_refused(app, tmp_path, chosen):
    script = tmp_path / "run.txt"
    script.write_text("x", encoding="utf-8")
    chosen["path"] = str(script)

    menu.check_file(None)

    assert chosen["ran"] == []
    assert chosen["told"] == 1


def test_cancelling_does_nothing(app, chosen):
    menu.check_file(None)

    assert chosen["ran"] == [] and chosen["told"] == 0
