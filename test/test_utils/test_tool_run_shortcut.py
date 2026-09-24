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


# The AI panels have one send button each, and a code or prompt box where Enter is a new line
AI_PANELS = [
    ("pybreeze.pybreeze_ui.connect_gui.url.ai_code_review_gui", "AICodeReviewClient"),
    ("pybreeze.pybreeze_ui.extend_ai_gui.code_review.cot_code_review_gui", "CoTCodeReviewGUI"),
    ("pybreeze.pybreeze_ui.extend_ai_gui.skills.skills_send_gui", "SkillsSendGUI"),
]


@pytest.mark.parametrize(("module", "name"), AI_PANELS, ids=[panel[1] for panel in AI_PANELS])
def test_ctrl_enter_sends_from_an_ai_panel(app, module, name):
    import importlib

    panel = getattr(importlib.import_module(module), name)()
    pressed: list = []
    panel.send_button.clicked.disconnect()  # nothing goes out
    panel.send_button.clicked.connect(lambda: pressed.append(True))

    shortcuts = _run_shortcuts(panel)
    assert len(shortcuts) == 2
    shortcuts[0].activated.emit()

    assert pressed == [True]
    panel.deleteLater()


# The tools with a button for each direction: (module, class, to-JSON button, from-JSON button, text that is not JSON)
TWO_WAY = [
    ("query_json_gui", "QueryJsonGUI", "to_json_button", "to_query_button", "a=1&b=2"),
    ("url_builder_gui", "UrlBuilderGUI", "to_json_button", "to_url_button", "https://api.example.com/v1?x=1"),
]


@pytest.mark.parametrize(("module", "name", "to_json", "from_json", "text"), TWO_WAY, ids=[t[1] for t in TWO_WAY])
@pytest.mark.parametrize("pasted", ["text", "json"])
def test_ctrl_enter_goes_the_way_the_input_reads(app, module, name, to_json, from_json, text, pasted):
    tool = _tool(module, name)
    pressed: list = []
    getattr(tool, to_json).clicked.connect(lambda: pressed.append(to_json))
    getattr(tool, from_json).clicked.connect(lambda: pressed.append(from_json))
    tool.input_edit.setPlainText(text if pasted == "text" else '  {"a": "1"}')

    shortcuts = _run_shortcuts(tool)
    assert len(shortcuts) == 2
    shortcuts[0].activated.emit()

    assert pressed == [to_json if pasted == "text" else from_json]
    assert "Ctrl+Enter" in getattr(tool, to_json).toolTip()
    assert "Ctrl+Enter" in getattr(tool, from_json).toolTip()
    tool.deleteLater()
