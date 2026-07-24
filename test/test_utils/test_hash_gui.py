"""Tests for the hash generator tool widget."""
from __future__ import annotations

import hashlib
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture()
def widget(app):
    from pybreeze.pybreeze_ui.tools_gui.hash_gui import HashGUI
    gui = HashGUI()
    yield gui
    gui.close()
    gui.deleteLater()


class TestHashGUI:
    def test_compute_shows_all_digests(self, widget):
        widget.input_edit.setPlainText("hello")
        widget.compute()
        output = widget.output_edit.toPlainText()
        assert hashlib.sha256(b"hello").hexdigest() in output
        assert "SHA256" in output
        assert "MD5" in output

    def test_empty_input_still_hashes(self, widget):
        widget.input_edit.setPlainText("")
        widget.compute()
        # The empty string has well-defined digests.
        assert hashlib.sha256(b"").hexdigest() in widget.output_edit.toPlainText()

    def test_copy_output(self, app, widget):
        widget.input_edit.setPlainText("hello")
        widget.compute()
        widget.actions.copy()
        assert hashlib.sha256(b"hello").hexdigest() in QApplication.clipboard().text()

    def test_build_hash_text_formats_lines(self):
        from pybreeze.pybreeze_ui.tools_gui.hash_gui import build_hash_text
        text = build_hash_text({"sha256": "abc", "md5": "def"})
        assert "SHA256: abc" in text
        assert "MD5: def" in text
