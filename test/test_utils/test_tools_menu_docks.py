"""Guard: add_dock builds the right widget for each new tool dock type."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow

from je_editor.pyside_ui.main_ui.dock.destroy_dock import DestroyDock

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.extend_ai_gui.code_review.cot_code_review_gui import CoTCodeReviewGUI
from pybreeze.pybreeze_ui.menu.tools import tools_menu
from pybreeze.pybreeze_ui.menu.tools.tools_menu import add_dock
from pybreeze.pybreeze_ui.tools_gui.curl_import_gui import CurlImportGUI
from pybreeze.pybreeze_ui.tools_gui.diff_gui import DiffGUI
from pybreeze.pybreeze_ui.tools_gui.har_import_gui import HarImportGUI
from pybreeze.pybreeze_ui.tools_gui.hash_gui import HashGUI
from pybreeze.pybreeze_ui.tools_gui.header_analyzer_gui import HeaderAnalyzerGUI
from pybreeze.pybreeze_ui.tools_gui.http_status_gui import HttpStatusGUI
from pybreeze.pybreeze_ui.tools_gui.json_format_gui import JsonFormatGUI
from pybreeze.pybreeze_ui.tools_gui.jwt_decoder_gui import JwtDecoderGUI
from pybreeze.pybreeze_ui.tools_gui.query_json_gui import QueryJsonGUI
from pybreeze.pybreeze_ui.tools_gui.regex_gui import RegexGUI
from pybreeze.pybreeze_ui.tools_gui.response_inspector_gui import ResponseInspectorGUI
from pybreeze.pybreeze_ui.tools_gui.timestamp_gui import TimestampGUI
from pybreeze.pybreeze_ui.tools_gui.url_builder_gui import UrlBuilderGUI


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.mark.parametrize(
    "widget_type,widget_class",
    [
        ("CoTCodeReview", CoTCodeReviewGUI),
        ("CurlImport", CurlImportGUI),
        ("HarImport", HarImportGUI),
        ("JwtDecoder", JwtDecoderGUI),
        ("Timestamp", TimestampGUI),
        ("Hash", HashGUI),
        ("QueryJson", QueryJsonGUI),
        ("UrlBuilder", UrlBuilderGUI),
        ("Regex", RegexGUI),
        ("HttpStatus", HttpStatusGUI),
        ("Diff", DiffGUI),
        ("JsonFormat", JsonFormatGUI),
        ("HeaderAnalyzer", HeaderAnalyzerGUI),
        ("ResponseInspector", ResponseInspectorGUI),
    ],
)
def test_add_dock_creates_expected_widget(app, widget_type, widget_class):
    window = QMainWindow()
    try:
        add_dock(window, widget_type)
        docks = window.findChildren(DestroyDock)
        assert any(isinstance(dock.widget(), widget_class) for dock in docks)
    finally:
        window.deleteLater()


def test_add_dock_unknown_type_adds_nothing(app):
    window = QMainWindow()
    try:
        add_dock(window, "DefinitelyNotAToolType")
        # An unknown type leaves the dock without a widget, so it is not attached.
        attached = [d for d in window.findChildren(DestroyDock) if d.widget() is not None]
        assert attached == []
    finally:
        window.deleteLater()


def test_every_tool_widget_has_a_tab_a_dock_and_a_dock_title():
    # The CoT code review panel had a widget and no entry in any menu, so there
    # was no way to open it.
    factories = set(tools_menu._WIDGET_FACTORIES)

    assert {entry[0] for entry in tools_menu._TAB_ACTIONS} == factories
    assert {entry[0] for entry in tools_menu._DOCK_ACTIONS} == factories
    assert set(tools_menu._DOCK_TITLES) == factories
