"""Ctrl+Enter runs a tool: its text boxes take Enter as a new line, and only the mouse ran it."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


def _tool(module: str, name: str, *args):
    import importlib
    return getattr(importlib.import_module(f"pybreeze.pybreeze_ui.tools_gui.{module}"), name)(*args)


# (module, class, constructor arguments, the button Ctrl+Enter presses)
TOOLS = [
    ("curl_import_gui", "CurlImportGUI", (None,), "convert_button"),
    ("diff_gui", "DiffGUI", (None,), "compare_button"),
    ("hash_gui", "HashGUI", (), "hash_button"),
    ("header_analyzer_gui", "HeaderAnalyzerGUI", (), "analyze_button"),
    ("json_format_gui", "JsonFormatGUI", (), "format_button"),
    ("jwt_decoder_gui", "JwtDecoderGUI", (), "decode_button"),
    ("regex_gui", "RegexGUI", (), "test_button"),
    ("response_inspector_gui", "ResponseInspectorGUI", (), "analyze_button"),
]


def _run_shortcuts(tool) -> list[QShortcut]:
    return [shortcut for shortcut in tool.findChildren(QShortcut)
            if shortcut.key() in (QKeySequence("Ctrl+Return"), QKeySequence("Ctrl+Enter"))]


@pytest.mark.parametrize(("module", "name", "args", "button"), TOOLS, ids=[tool[1] for tool in TOOLS])
def test_ctrl_enter_presses_the_tools_button(app, module, name, args, button):
    tool = _tool(module, name, *args)
    pressed: list = []
    getattr(tool, button).clicked.connect(lambda: pressed.append(True))

    shortcuts = _run_shortcuts(tool)
    assert len(shortcuts) == 2  # the main keyboard's Enter and the keypad's
    assert all(shortcut.context() == Qt.ShortcutContext.WidgetWithChildrenShortcut for shortcut in shortcuts)
    shortcuts[0].activated.emit()

    assert pressed == [True]
    assert "Ctrl+Enter" in getattr(tool, button).toolTip()
    tool.deleteLater()


def test_a_disabled_button_is_not_pressed(app):
    # A diff still being worked out keeps Compare greyed out
    tool = _tool("diff_gui", "DiffGUI", None)
    pressed: list = []
    tool.compare_button.clicked.connect(lambda: pressed.append(True))
    tool.compare_button.setEnabled(False)

    _run_shortcuts(tool)[0].activated.emit()

    assert pressed == []
    tool.deleteLater()


def test_the_keys_work_from_the_text_box(app):
    tool = _tool("hash_gui", "HashGUI")
    tool.show()
    tool.activateWindow()
    tool.input_edit.setFocus()
    tool.input_edit.setPlainText("abc")
    QApplication.processEvents()

    QTest.keyClick(tool.input_edit, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)

    assert "ba7816bf" in tool.output_edit.toPlainText()  # SHA-256 of "abc"
    tool.close()
    tool.deleteLater()
