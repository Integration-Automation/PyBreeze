"""Create Project: into the folder open in the IDE, asking before it writes over a template.

The packages rewrite every template file whenever they run. The entry called
them with no path, so the files went to the process's working directory; a
second click wiped the user's edits without a word, and a failure to write
raised out of the menu slot.
"""
from __future__ import annotations

import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.menu.automation_menu.automation_menu_factory import safe_create_project

_PACKAGE = "fake_automation_package"


@pytest.fixture(scope="module", autouse=True)
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture
def package(monkeypatch):
    """A package whose create_project_dir writes one template file, as the real ones do."""
    fake = types.ModuleType(_PACKAGE)
    fake.fail_with = None

    def create_project_dir(project_path: str | None = None, parent_name: str = "FakeProject") -> None:
        if fake.fail_with is not None:
            raise fake.fail_with
        folder = os.path.join(project_path or os.getcwd(), parent_name, "keyword")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "keyword1.json"), "w", encoding="utf-8") as file:
            file.write("template")

    fake.create_project_dir = create_project_dir
    monkeypatch.setitem(sys.modules, _PACKAGE, fake)
    return fake


@pytest.fixture
def dialogs(monkeypatch):
    """Record every message box; ``answer`` is what a question gets."""
    shown: dict = {"question": [], "warning": [], "information": [], "answer": QMessageBox.StandardButton.No}

    def question(_parent, _title, text, *_args):
        shown["question"].append(text)
        return shown["answer"]

    monkeypatch.setattr(QMessageBox, "question", staticmethod(question))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda _p, _t, text: shown["warning"].append(text)))
    monkeypatch.setattr(
        QMessageBox, "information", staticmethod(lambda _p, _t, text: shown["information"].append(text)))
    return shown


def _window(working_dir) -> QWidget:
    window = QWidget()
    window.working_dir = str(working_dir)
    return window


def test_the_project_goes_into_the_folder_open_in_the_ide(package, dialogs, tmp_path, monkeypatch):
    elsewhere = tmp_path / "process_cwd"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    opened = tmp_path / "opened"
    opened.mkdir()

    safe_create_project(_window(opened), _PACKAGE)()

    assert (opened / "FakeProject" / "keyword" / "keyword1.json").is_file()
    assert not (elsewhere / "FakeProject").exists()
    assert dialogs["question"] == []
    assert str(opened / "FakeProject") in dialogs["information"][0]


def test_an_edited_template_is_kept_unless_the_user_agrees(package, dialogs, tmp_path):
    edited = tmp_path / "FakeProject" / "keyword" / "keyword1.json"
    edited.parent.mkdir(parents=True)
    edited.write_text("my edits", encoding="utf-8")

    safe_create_project(_window(tmp_path), _PACKAGE)()

    assert edited.read_text(encoding="utf-8") == "my edits"
    assert len(dialogs["question"]) == 1
    assert dialogs["information"] == []


def test_the_user_can_agree_to_replace_it(package, dialogs, tmp_path):
    edited = tmp_path / "FakeProject" / "keyword" / "keyword1.json"
    edited.parent.mkdir(parents=True)
    edited.write_text("my edits", encoding="utf-8")
    dialogs["answer"] = QMessageBox.StandardButton.Yes

    safe_create_project(_window(tmp_path), _PACKAGE)()

    assert edited.read_text(encoding="utf-8") == "template"


def test_a_write_that_fails_is_reported_not_raised(package, dialogs, tmp_path):
    package.fail_with = PermissionError(13, "Access is denied")

    safe_create_project(_window(tmp_path), _PACKAGE)()

    assert "Access is denied" in dialogs["warning"][0]
    assert dialogs["information"] == []


def test_a_package_that_is_not_installed_is_reported(dialogs, tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, _PACKAGE, None)  # makes the import fail

    safe_create_project(_window(tmp_path), _PACKAGE)()

    assert _PACKAGE in dialogs["warning"][0]


def test_without_a_folder_open_it_uses_the_working_directory(package, dialogs, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    window = QWidget()

    safe_create_project(window, _PACKAGE)()

    assert (tmp_path / "FakeProject" / "keyword" / "keyword1.json").is_file()
