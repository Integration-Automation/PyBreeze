from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtGui import QAction, Qt
from je_editor import language_wrapper
from je_editor.pyside_ui.main_ui.dock.destroy_dock import DestroyDock
from je_editor import jeditor_logger

from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_main_widget import SSHMainWidget
from pybreeze.pybreeze_ui.connect_gui.url.ai_code_review_gui import AICodeReviewClient
from pybreeze.pybreeze_ui.diagram_editor.diagram_editor_widget import DiagramEditorWidget
from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.cot_prompt_editor_widget import CoTPromptEditor
from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.skills_prompt_editor_widget import \
    SkillPromptEditor
from pybreeze.pybreeze_ui.extend_ai_gui.skills.skills_send_gui import SkillsSendGUI
from pybreeze.pybreeze_ui.tools_gui.curl_import_gui import CurlImportGUI
from pybreeze.pybreeze_ui.tools_gui.diff_gui import DiffGUI
from pybreeze.pybreeze_ui.tools_gui.json_format_gui import JsonFormatGUI
from pybreeze.pybreeze_ui.tools_gui.jwt_decoder_gui import JwtDecoderGUI
from pybreeze.pybreeze_ui.tools_gui.har_import_gui import HarImportGUI
from pybreeze.pybreeze_ui.tools_gui.hash_gui import HashGUI
from pybreeze.pybreeze_ui.tools_gui.header_analyzer_gui import HeaderAnalyzerGUI
from pybreeze.pybreeze_ui.tools_gui.http_status_gui import HttpStatusGUI
from pybreeze.pybreeze_ui.tools_gui.query_json_gui import QueryJsonGUI
from pybreeze.pybreeze_ui.tools_gui.regex_gui import RegexGUI
from pybreeze.pybreeze_ui.tools_gui.response_inspector_gui import ResponseInspectorGUI
from pybreeze.pybreeze_ui.tools_gui.timestamp_gui import TimestampGUI
from pybreeze.pybreeze_ui.tools_gui.url_builder_gui import UrlBuilderGUI

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow

# ---------------------------------------------------------------------------
# Widget registry
# ---------------------------------------------------------------------------

# Widget key -> factory taking the main window. Shared by the Tools-menu tab
# actions and the dock actions so each widget's constructor is written once.
_WIDGET_FACTORIES: dict[str, Callable[[PyBreezeMainWindow], object]] = {
    "SSH": lambda _win: SSHMainWidget(),
    "AICodeReview": lambda _win: AICodeReviewClient(),
    "CoTPromptEditor": lambda _win: CoTPromptEditor(),
    "SkillPromptEditor": lambda _win: SkillPromptEditor(),
    "SkillSendGUI": lambda _win: SkillsSendGUI(),
    "DiagramEditor": lambda _win: DiagramEditorWidget(),
    "CurlImport": lambda win: CurlImportGUI(win),
    "HarImport": lambda win: HarImportGUI(win),
    "JwtDecoder": lambda win: JwtDecoderGUI(main_window=win),
    "Timestamp": lambda win: TimestampGUI(win),
    "Hash": lambda win: HashGUI(win),
    "QueryJson": lambda win: QueryJsonGUI(win),
    "UrlBuilder": lambda win: UrlBuilderGUI(win),
    "Regex": lambda win: RegexGUI(win),
    "HttpStatus": lambda win: HttpStatusGUI(main_window=win),
    "Diff": lambda win: DiffGUI(win),
    "JsonFormat": lambda win: JsonFormatGUI(win),
    "HeaderAnalyzer": lambda win: HeaderAnalyzerGUI(win),
    "ResponseInspector": lambda win: ResponseInspectorGUI(win),
}

# Widget key -> language key for the dock window title.
_DOCK_TITLES: dict[str, str] = {
    "SSH": "extend_tools_menu_ssh_client_dock_title",
    "AICodeReview": "extend_tools_menu_ai_code_review_dock_title",
    "CoTPromptEditor": "extend_tools_menu_cot_prompt_editor_dock_title",
    "SkillPromptEditor": "extend_tools_menu_skill_prompt_editor_dock_title",
    "SkillSendGUI": "extend_tools_menu_skill_prompt_send_dock_title",
    "DiagramEditor": "extend_tools_menu_diagram_editor_dock_title",
    "CurlImport": "extend_tools_menu_curl_import_dock_title",
    "HarImport": "extend_tools_menu_har_import_dock_title",
    "JwtDecoder": "extend_tools_menu_jwt_decoder_dock_title",
    "Timestamp": "extend_tools_menu_timestamp_dock_title",
    "Hash": "extend_tools_menu_hash_dock_title",
    "QueryJson": "extend_tools_menu_query_json_dock_title",
    "UrlBuilder": "extend_tools_menu_url_builder_dock_title",
    "Regex": "extend_tools_menu_regex_dock_title",
    "HttpStatus": "extend_tools_menu_http_status_dock_title",
    "Diff": "extend_tools_menu_diff_dock_title",
    "JsonFormat": "extend_tools_menu_json_format_dock_title",
    "HeaderAnalyzer": "extend_tools_menu_header_analyzer_dock_title",
    "ResponseInspector": "extend_tools_menu_response_dock_title",
}

# ---------------------------------------------------------------------------
# Menu tables
# ---------------------------------------------------------------------------

# (widget key, main-window attribute, menu attribute, action key, tab label key)
_TAB_ACTIONS: tuple[tuple[str, str, str, str, str], ...] = (
    ("SSH", "tools_ssh_client_tab_action", "tools_ssh_menu",
     "extend_tools_menu_ssh_client_tab_action", "extend_tools_menu_ssh_client_tab_label"),
    ("AICodeReview", "tools_ai_code_review_action", "tools_ai_menu",
     "extend_tools_menu_ai_code_review_tab_action", "extend_tools_menu_ai_code_review_tab_label"),
    ("CoTPromptEditor", "tools_ai_cot_prompt_editor_action", "tools_ai_menu",
     "extend_tools_menu_cot_prompt_editor_tab_action",
     "extend_tools_menu_cot_prompt_editor_tab_label"),
    ("SkillPromptEditor", "tools_ai_skill_prompt_editor_action", "tools_ai_menu",
     "extend_tools_menu_skill_prompt_editor_tab_action",
     "extend_tools_menu_skill_prompt_editor_tab_label"),
    ("SkillSendGUI", "tools_ai_skill_send_action", "tools_ai_menu",
     "extend_tools_menu_skill_prompt_send_tab_label",
     "extend_tools_menu_skill_prompt_send_tab_label"),
    ("DiagramEditor", "tools_diagram_editor_action", "tools_menu",
     "extend_tools_menu_diagram_editor_tab_action", "extend_tools_menu_diagram_editor_tab_label"),
    ("CurlImport", "tools_curl_import_action", "tools_menu",
     "extend_tools_menu_curl_import_tab_action", "extend_tools_menu_curl_import_tab_label"),
    ("HarImport", "tools_har_import_action", "tools_menu",
     "extend_tools_menu_har_import_tab_action", "extend_tools_menu_har_import_tab_label"),
    ("JwtDecoder", "tools_jwt_decoder_action", "tools_menu",
     "extend_tools_menu_jwt_decoder_tab_action", "extend_tools_menu_jwt_decoder_tab_label"),
    ("Timestamp", "tools_timestamp_action", "tools_menu",
     "extend_tools_menu_timestamp_tab_action", "extend_tools_menu_timestamp_tab_label"),
    ("Hash", "tools_hash_action", "tools_menu",
     "extend_tools_menu_hash_tab_action", "extend_tools_menu_hash_tab_label"),
    ("QueryJson", "tools_query_json_action", "tools_menu",
     "extend_tools_menu_query_json_tab_action", "extend_tools_menu_query_json_tab_label"),
    ("UrlBuilder", "tools_url_builder_action", "tools_menu",
     "extend_tools_menu_url_builder_tab_action", "extend_tools_menu_url_builder_tab_label"),
    ("Regex", "tools_regex_action", "tools_menu",
     "extend_tools_menu_regex_tab_action", "extend_tools_menu_regex_tab_label"),
    ("HttpStatus", "tools_http_status_action", "tools_menu",
     "extend_tools_menu_http_status_tab_action", "extend_tools_menu_http_status_tab_label"),
    ("Diff", "tools_diff_action", "tools_menu",
     "extend_tools_menu_diff_tab_action", "extend_tools_menu_diff_tab_label"),
    ("JsonFormat", "tools_json_format_action", "tools_menu",
     "extend_tools_menu_json_format_tab_action", "extend_tools_menu_json_format_tab_label"),
    ("HeaderAnalyzer", "tools_header_analyzer_action", "tools_menu",
     "extend_tools_menu_header_analyzer_tab_action",
     "extend_tools_menu_header_analyzer_tab_label"),
    ("ResponseInspector", "tools_response_action", "tools_menu",
     "extend_tools_menu_response_tab_action", "extend_tools_menu_response_tab_label"),
)

# (widget key, main-window attribute, menu attribute, action key)
_DOCK_ACTIONS: tuple[tuple[str, str, str, str], ...] = (
    ("SSH", "tools_ssh_client_dock_action", "dock_ssh_menu",
     "extend_tools_menu_ssh_client_dock_action"),
    ("AICodeReview", "tools_ai_code_review_dock_action", "dock_ai_menu",
     "extend_tools_menu_ai_code_review_dock_action"),
    ("CoTPromptEditor", "tools_cot_prompt_editor_dock_action", "dock_ai_menu",
     "extend_tools_menu_cot_prompt_editor_dock_action"),
    ("SkillPromptEditor", "tools_skill_prompt_editor_dock_action", "dock_ai_menu",
     "extend_tools_menu_skill_prompt_editor_dock_action"),
    ("SkillSendGUI", "tools_skill_send_dock_action", "dock_ai_menu",
     "extend_tools_menu_skill_prompt_send_dock_action"),
    ("DiagramEditor", "tools_diagram_editor_dock_action", "dock_menu",
     "extend_tools_menu_diagram_editor_dock_action"),
    ("CurlImport", "tools_curl_import_dock_action", "dock_menu",
     "extend_tools_menu_curl_import_dock_action"),
    ("HarImport", "tools_har_import_dock_action", "dock_menu",
     "extend_tools_menu_har_import_dock_action"),
    ("JwtDecoder", "tools_jwt_decoder_dock_action", "dock_menu",
     "extend_tools_menu_jwt_decoder_dock_action"),
    ("Timestamp", "tools_timestamp_dock_action", "dock_menu",
     "extend_tools_menu_timestamp_dock_action"),
    ("Hash", "tools_hash_dock_action", "dock_menu",
     "extend_tools_menu_hash_dock_action"),
    ("QueryJson", "tools_query_json_dock_action", "dock_menu",
     "extend_tools_menu_query_json_dock_action"),
    ("UrlBuilder", "tools_url_builder_dock_action", "dock_menu",
     "extend_tools_menu_url_builder_dock_action"),
    ("Regex", "tools_regex_dock_action", "dock_menu",
     "extend_tools_menu_regex_dock_action"),
    ("HttpStatus", "tools_http_status_dock_action", "dock_menu",
     "extend_tools_menu_http_status_dock_action"),
    ("Diff", "tools_diff_dock_action", "dock_menu",
     "extend_tools_menu_diff_dock_action"),
    ("JsonFormat", "tools_json_format_dock_action", "dock_menu",
     "extend_tools_menu_json_format_dock_action"),
    ("HeaderAnalyzer", "tools_header_analyzer_dock_action", "dock_menu",
     "extend_tools_menu_header_analyzer_dock_action"),
    ("ResponseInspector", "tools_response_dock_action", "dock_menu",
     "extend_tools_menu_response_dock_action"),
)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _register_action(
        ui_we_want_to_set: PyBreezeMainWindow, attribute: str, menu_attribute: str,
        action_key: str, handler: Callable[[], None]) -> None:
    """Create a QAction for *action_key*, wire *handler*, add it to the menu.

    The action is also stored on the main window under *attribute*: Qt keeps no
    owning reference to a QAction built here, so a local-only action would be
    garbage-collected and the menu entry would stop responding.
    """
    action = QAction(language_wrapper.language_word_dict.get(action_key))
    action.triggered.connect(handler)
    setattr(ui_we_want_to_set, attribute, action)
    getattr(ui_we_want_to_set, menu_attribute).addAction(action)


def _open_tab_handler(
        ui_we_want_to_set: PyBreezeMainWindow, widget_key: str,
        label_key: str) -> Callable[[], None]:
    """Return a handler opening *widget_key*'s widget as a new tab."""

    def handler() -> None:
        ui_we_want_to_set.tab_widget.addTab(
            _WIDGET_FACTORIES[widget_key](ui_we_want_to_set),
            language_wrapper.language_word_dict.get(label_key),
        )

    return handler


def _open_dock_handler(
        ui_we_want_to_set: PyBreezeMainWindow, widget_key: str) -> Callable[[], None]:
    """Return a handler opening *widget_key*'s widget as a dock."""

    def handler() -> None:
        add_dock(ui_we_want_to_set, widget_key)

    return handler


def build_tools_menu(ui_we_want_to_set: PyBreezeMainWindow):
    # Menus
    ui_we_want_to_set.tools_menu = ui_we_want_to_set.menu.addMenu(language_wrapper.language_word_dict.get(
        "extend_tools_menu_tools_menu"
    ))
    ui_we_want_to_set.tools_ssh_menu = ui_we_want_to_set.tools_menu.addMenu(language_wrapper.language_word_dict.get(
        "extend_tools_menu_tools_ssh_menu"
    ))
    ui_we_want_to_set.tools_ai_menu = ui_we_want_to_set.tools_menu.addMenu(language_wrapper.language_word_dict.get(
        "extend_tools_menu_tools_ai_menu"
    ))

    for widget_key, attribute, menu_attribute, action_key, label_key in _TAB_ACTIONS:
        _register_action(
            ui_we_want_to_set, attribute, menu_attribute, action_key,
            _open_tab_handler(ui_we_want_to_set, widget_key, label_key),
        )


def extend_dock_menu(ui_we_want_to_set: PyBreezeMainWindow):
    # Sub menu
    ui_we_want_to_set.dock_ssh_menu = ui_we_want_to_set.dock_menu.addMenu(
        language_wrapper.language_word_dict.get("extend_tools_menu_dock_ssh_menu")
    )
    ui_we_want_to_set.dock_ai_menu = ui_we_want_to_set.dock_menu.addMenu(
        language_wrapper.language_word_dict.get("extend_tools_menu_dock_ai_menu")
    )

    for widget_key, attribute, menu_attribute, action_key in _DOCK_ACTIONS:
        _register_action(
            ui_we_want_to_set, attribute, menu_attribute, action_key,
            _open_dock_handler(ui_we_want_to_set, widget_key),
        )


def add_dock(ui_we_want_to_set: PyBreezeMainWindow, widget_type: str | None = None):
    jeditor_logger.info("build_dock_menu.py add_dock_widget "
                        f"ui_we_want_to_set: {ui_we_want_to_set} "
                        f"widget_type: {widget_type}")

    # 建立一個可銷毀的 Dock 容器
    # Create a destroyable dock container
    dock_widget = DestroyDock()

    title_key = _DOCK_TITLES.get(widget_type)
    if title_key is not None:
        dock_widget.setWindowTitle(language_wrapper.language_word_dict.get(title_key))
        dock_widget.setWidget(_WIDGET_FACTORIES[widget_type](ui_we_want_to_set))

    # 如果成功建立了 widget，將其加到主視窗右側 Dock 區域
    # If widget is created, add it to the right dock area of the main window
    if dock_widget.widget() is not None:
        ui_we_want_to_set.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_widget)
