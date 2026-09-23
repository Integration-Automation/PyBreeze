"""Text from a server or a file is shown as text, never as markup Qt would load."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.plain_text import as_text

_HOSTILE = 'Listing failed: <img src="\\\\attacker@80\\x.png"> & <a href="https://x">click</a>'


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.mark.parametrize("text", [_HOSTILE, "plain words", "two\nlines", "a < b && c > d"])
def test_what_is_shown_is_the_text_itself(app, text):
    document = QTextDocument()
    document.setHtml(as_text(text))

    assert document.toPlainText() == text


def test_a_failed_sftp_listing_shows_the_servers_text_as_text(app, monkeypatch):
    # A hostile server's error went into the box as HTML: an <img> with a UNC
    # path made Windows connect out
    from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_file_viewer_widget as viewer

    shown: list = []
    monkeypatch.setattr(viewer.QMessageBox, "critical", staticmethod(lambda *args: shown.append(args[2])))
    tree = viewer.SSHFileTreeManager()

    tree._on_connect_failed('Indecipherable protocol version "<img src=x>"')

    assert "&lt;img src=x&gt;" in shown[0] and "<img" not in shown[0]
    tree.close()


def test_the_har_summary_is_plain_text(app):
    # It lists host names from the file
    from PySide6.QtCore import Qt

    from pybreeze.pybreeze_ui.tools_gui.har_import_gui import HarImportGUI

    tab = HarImportGUI()

    assert tab.summary_label.textFormat() == Qt.TextFormat.PlainText
    tab.close()


def test_the_file_trees_messages_show_names_as_text(app, tmp_path, monkeypatch):
    # A cloned project may hold a file whose name is markup (allowed off Windows)
    from pybreeze.pybreeze_ui.editor_main import file_tree_context_menu as ctx

    shown: list = []
    monkeypatch.setattr(ctx.QMessageBox, "warning", staticmethod(lambda *args: shown.append(args[2])))

    ctx._inside(None, tmp_path, "/<b>x</b>")

    assert "&lt;b&gt;" in shown[0] and "<b>" not in shown[0]
