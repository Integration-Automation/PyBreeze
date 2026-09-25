"""A file the user opens is not read on the UI thread when it is too large."""
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.utils.file_process import read_capped
from pybreeze.utils.file_process.read_capped import FileTooLargeError, read_text_capped


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


def test_a_file_within_the_limit_is_read(tmp_path):
    path = tmp_path / "small.json"
    path.write_text("{}", encoding="utf-8")

    assert read_text_capped(path, max_bytes=10) == "{}"


def test_a_file_over_the_limit_is_refused_as_a_read_error(tmp_path):
    path = tmp_path / "big.json"
    path.write_bytes(b"x" * 11)

    with pytest.raises(FileTooLargeError) as raised:
        read_text_capped(path, max_bytes=10)

    assert isinstance(raised.value, OSError)
    assert "not opened" in raised.value.strerror


def test_the_har_tab_says_why_it_did_not_open_a_huge_export(app, tmp_path, monkeypatch):
    # It read a multi-GB export whole, on the UI thread
    from pybreeze.pybreeze_ui.tools_gui import har_import_gui

    monkeypatch.setattr(read_capped, "MAX_OPEN_BYTES", 10)
    path = tmp_path / "session.har"
    path.write_text(json.dumps({"log": {"entries": []}}), encoding="utf-8")
    monkeypatch.setattr(har_import_gui.QFileDialog, "getOpenFileName",
                        staticmethod(lambda *args, **kwargs: (str(path), "")))
    tab = har_import_gui.HarImportGUI()

    assert tab.open_file() is None
    assert "not opened" in tab.summary_label.text()
    tab.close()


def test_the_diagram_editor_says_why_it_did_not_open_a_huge_file(app, tmp_path, monkeypatch):
    from pybreeze.pybreeze_ui.diagram_editor import diagram_editor_widget

    monkeypatch.setattr(read_capped, "MAX_OPEN_BYTES", 10)
    path = tmp_path / "big.diagram.json"
    path.write_text(json.dumps({"nodes": [], "connections": [], "images": []}), encoding="utf-8")
    said: list = []
    monkeypatch.setattr(diagram_editor_widget.QFileDialog, "getOpenFileName",
                        staticmethod(lambda *args, **kwargs: (str(path), "")))
    monkeypatch.setattr(diagram_editor_widget.QMessageBox, "warning",
                        staticmethod(lambda *args, **kwargs: said.append(args[2])))
    editor = diagram_editor_widget.DiagramEditorWidget()

    editor._open_diagram()

    assert said
    assert "not opened" in said[0]
    assert editor._current_path is None
    editor.deleteLater()
