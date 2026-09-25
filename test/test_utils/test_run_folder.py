"""Running a folder of action files: which files, and what the user hears when there are none."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox

from pybreeze.extend.process_executor import process_executor_utils
from pybreeze.extend_multi_language.update_language_dict import update_language_dict


@pytest.fixture(scope="module")
def window():
    QApplication.instance() or QApplication([])
    update_language_dict()
    made = QMainWindow()
    yield made
    made.deleteLater()


@pytest.fixture
def picked(monkeypatch):
    """The folder the dialog returns, and the parents it was opened with."""
    state = {"folder": "", "parents": [], "told": []}

    def pick(parent, *_args, **_kwargs):
        state["parents"].append(parent)
        return state["folder"]

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(pick))
    monkeypatch.setattr(
        QMessageBox, "information", staticmethod(lambda *args: state["told"].append(args)))
    return state


def test_the_dialog_belongs_to_the_main_window(window, picked):
    process_executor_utils._ask_for_action_files(window)

    # It was opened through a throwaway instance, so it had no parent.
    assert picked["parents"] == [window]


def test_cancelling_runs_nothing_and_says_nothing(window, picked):
    assert process_executor_utils._ask_for_action_files(window) == []
    assert picked["told"] == []


def test_the_json_files_under_the_folder_are_returned(window, picked, tmp_path):
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "login.json").write_text("[]", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("", encoding="utf-8")
    picked["folder"] = str(tmp_path)

    files = process_executor_utils._ask_for_action_files(window)

    assert [os.path.basename(file) for file in files] == ["login.json"]
    assert picked["told"] == []


def test_a_folder_with_nothing_to_run_says_so(window, picked, tmp_path):
    picked["folder"] = str(tmp_path)

    assert process_executor_utils._ask_for_action_files(window) == []
    # It used to do nothing at all.
    (told,) = picked["told"]
    assert str(tmp_path) in told[2]
