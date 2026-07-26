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

    ui_we_want_to_set.tools_ssh_client_tab_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_ssh_client_tab_action"
    ))
    ui_we_want_to_set.tools_ssh_client_tab_action.triggered.connect(lambda: ui_we_want_to_set.tab_widget.addTab(
        SSHMainWidget(), language_wrapper.language_word_dict.get("extend_tools_menu_ssh_client_tab_label")
    ))
    ui_we_want_to_set.tools_ssh_menu.addAction(ui_we_want_to_set.tools_ssh_client_tab_action)

    ui_we_want_to_set.tools_ai_code_review_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_ai_code_review_tab_action"
    ))
    ui_we_want_to_set.tools_ai_code_review_action.triggered.connect(lambda: ui_we_want_to_set.tab_widget.addTab(
        AICodeReviewClient(), language_wrapper.language_word_dict.get(
            "extend_tools_menu_ai_code_review_tab_label"
        )
    ))
    ui_we_want_to_set.tools_ai_menu.addAction(ui_we_want_to_set.tools_ai_code_review_action)

    ui_we_want_to_set.tools_ai_cot_prompt_editor_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_cot_prompt_editor_tab_action"
    ))
    ui_we_want_to_set.tools_ai_cot_prompt_editor_action.triggered.connect(lambda: ui_we_want_to_set.tab_widget.addTab(
        CoTPromptEditor(), language_wrapper.language_word_dict.get(
            "extend_tools_menu_cot_prompt_editor_tab_label"
        )
    ))
    ui_we_want_to_set.tools_ai_menu.addAction(ui_we_want_to_set.tools_ai_cot_prompt_editor_action)

    ui_we_want_to_set.tools_ai_skill_prompt_editor_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_skill_prompt_editor_tab_action"
    ))
    ui_we_want_to_set.tools_ai_skill_prompt_editor_action.triggered.connect(lambda: ui_we_want_to_set.tab_widget.addTab(
        SkillPromptEditor(), language_wrapper.language_word_dict.get(
            "extend_tools_menu_skill_prompt_editor_tab_label"
        )
    ))
    ui_we_want_to_set.tools_ai_menu.addAction(ui_we_want_to_set.tools_ai_skill_prompt_editor_action)

    ui_we_want_to_set.tools_ai_skill_send_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_skill_prompt_send_tab_label"
    ))
    ui_we_want_to_set.tools_ai_skill_send_action.triggered.connect(lambda: ui_we_want_to_set.tab_widget.addTab(
        SkillsSendGUI(), language_wrapper.language_word_dict.get(
            "extend_tools_menu_skill_prompt_send_tab_label"
        )
    ))
    ui_we_want_to_set.tools_ai_menu.addAction(ui_we_want_to_set.tools_ai_skill_send_action)

    # Diagram Editor
    ui_we_want_to_set.tools_diagram_editor_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_diagram_editor_tab_action"
    ))
    ui_we_want_to_set.tools_diagram_editor_action.triggered.connect(lambda: ui_we_want_to_set.tab_widget.addTab(
        DiagramEditorWidget(), language_wrapper.language_word_dict.get(
            "extend_tools_menu_diagram_editor_tab_label"
        )
    ))
    ui_we_want_to_set.tools_menu.addAction(ui_we_want_to_set.tools_diagram_editor_action)

    # cURL Import
    ui_we_want_to_set.tools_curl_import_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_curl_import_tab_action"
    ))
    ui_we_want_to_set.tools_curl_import_action.triggered.connect(lambda: ui_we_want_to_set.tab_widget.addTab(
        CurlImportGUI(ui_we_want_to_set), language_wrapper.language_word_dict.get(
            "extend_tools_menu_curl_import_tab_label"
        )
    ))
    ui_we_want_to_set.tools_menu.addAction(ui_we_want_to_set.tools_curl_import_action)

    # HAR Import
    ui_we_want_to_set.tools_har_import_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_har_import_tab_action"
    ))
    ui_we_want_to_set.tools_har_import_action.triggered.connect(lambda: ui_we_want_to_set.tab_widget.addTab(
        HarImportGUI(ui_we_want_to_set), language_wrapper.language_word_dict.get(
            "extend_tools_menu_har_import_tab_label"
        )
    ))
    ui_we_want_to_set.tools_menu.addAction(ui_we_want_to_set.tools_har_import_action)

    # JWT Decoder
    ui_we_want_to_set.tools_jwt_decoder_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_jwt_decoder_tab_action"
    ))
    ui_we_want_to_set.tools_jwt_decoder_action.triggered.connect(lambda: ui_we_want_to_set.tab_widget.addTab(
        JwtDecoderGUI(main_window=ui_we_want_to_set), language_wrapper.language_word_dict.get(
            "extend_tools_menu_jwt_decoder_tab_label"
        )
    ))
    ui_we_want_to_set.tools_menu.addAction(ui_we_want_to_set.tools_jwt_decoder_action)

    # Timestamp Converter
    ui_we_want_to_set.tools_timestamp_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_timestamp_tab_action"
    ))
    ui_we_want_to_set.tools_timestamp_action.triggered.connect(lambda: ui_we_want_to_set.tab_widget.addTab(
        TimestampGUI(ui_we_want_to_set), language_wrapper.language_word_dict.get(
            "extend_tools_menu_timestamp_tab_label"
        )
    ))
    ui_we_want_to_set.tools_menu.addAction(ui_we_want_to_set.tools_timestamp_action)

    # Hash Generator
    ui_we_want_to_set.tools_hash_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_hash_tab_action"
    ))
    ui_we_want_to_set.tools_hash_action.triggered.connect(lambda: ui_we_want_to_set.tab_widget.addTab(
        HashGUI(ui_we_want_to_set), language_wrapper.language_word_dict.get(
            "extend_tools_menu_hash_tab_label"
        )
    ))
    ui_we_want_to_set.tools_menu.addAction(ui_we_want_to_set.tools_hash_action)

    # Query <-> JSON
    ui_we_want_to_set.tools_query_json_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_query_json_tab_action"
    ))
    ui_we_want_to_set.tools_query_json_action.triggered.connect(lambda: ui_we_want_to_set.tab_widget.addTab(
        QueryJsonGUI(ui_we_want_to_set), language_wrapper.language_word_dict.get(
            "extend_tools_menu_query_json_tab_label"
        )
    ))
    ui_we_want_to_set.tools_menu.addAction(ui_we_want_to_set.tools_query_json_action)

    # URL Parser / Builder
    ui_we_want_to_set.tools_url_builder_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_url_builder_tab_action"
    ))
    ui_we_want_to_set.tools_url_builder_action.triggered.connect(lambda: ui_we_want_to_set.tab_widget.addTab(
        UrlBuilderGUI(ui_we_want_to_set), language_wrapper.language_word_dict.get(
            "extend_tools_menu_url_builder_tab_label"
        )
    ))
    ui_we_want_to_set.tools_menu.addAction(ui_we_want_to_set.tools_url_builder_action)

    # Regex Tester
    ui_we_want_to_set.tools_regex_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_regex_tab_action"
    ))
    ui_we_want_to_set.tools_regex_action.triggered.connect(lambda: ui_we_want_to_set.tab_widget.addTab(
        RegexGUI(ui_we_want_to_set), language_wrapper.language_word_dict.get(
            "extend_tools_menu_regex_tab_label"
        )
    ))
    ui_we_want_to_set.tools_menu.addAction(ui_we_want_to_set.tools_regex_action)

    # HTTP Status Reference
    ui_we_want_to_set.tools_http_status_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_http_status_tab_action"
    ))
    ui_we_want_to_set.tools_http_status_action.triggered.connect(lambda: ui_we_want_to_set.tab_widget.addTab(
        HttpStatusGUI(main_window=ui_we_want_to_set), language_wrapper.language_word_dict.get(
            "extend_tools_menu_http_status_tab_label"
        )
    ))
    ui_we_want_to_set.tools_menu.addAction(ui_we_want_to_set.tools_http_status_action)

    # Text Diff
    ui_we_want_to_set.tools_diff_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_diff_tab_action"
    ))
    ui_we_want_to_set.tools_diff_action.triggered.connect(lambda: ui_we_want_to_set.tab_widget.addTab(
        DiffGUI(ui_we_want_to_set), language_wrapper.language_word_dict.get(
            "extend_tools_menu_diff_tab_label"
        )
    ))
    ui_we_want_to_set.tools_menu.addAction(ui_we_want_to_set.tools_diff_action)

    # JSON Format
    ui_we_want_to_set.tools_json_format_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_json_format_tab_action"
    ))
    ui_we_want_to_set.tools_json_format_action.triggered.connect(lambda: ui_we_want_to_set.tab_widget.addTab(
        JsonFormatGUI(ui_we_want_to_set), language_wrapper.language_word_dict.get(
            "extend_tools_menu_json_format_tab_label"
        )
    ))
    ui_we_want_to_set.tools_menu.addAction(ui_we_want_to_set.tools_json_format_action)

    # HTTP Header Analyzer
    ui_we_want_to_set.tools_header_analyzer_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_header_analyzer_tab_action"
    ))
    ui_we_want_to_set.tools_header_analyzer_action.triggered.connect(lambda: ui_we_want_to_set.tab_widget.addTab(
        HeaderAnalyzerGUI(ui_we_want_to_set), language_wrapper.language_word_dict.get(
            "extend_tools_menu_header_analyzer_tab_label"
        )
    ))
    ui_we_want_to_set.tools_menu.addAction(ui_we_want_to_set.tools_header_analyzer_action)

    # Response Inspector
    ui_we_want_to_set.tools_response_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_response_tab_action"
    ))
    ui_we_want_to_set.tools_response_action.triggered.connect(lambda: ui_we_want_to_set.tab_widget.addTab(
        ResponseInspectorGUI(ui_we_want_to_set), language_wrapper.language_word_dict.get(
            "extend_tools_menu_response_tab_label"
        )
    ))
    ui_we_want_to_set.tools_menu.addAction(ui_we_want_to_set.tools_response_action)


def extend_dock_menu(ui_we_want_to_set: PyBreezeMainWindow):
    # Sub menu
    ui_we_want_to_set.dock_ssh_menu = ui_we_want_to_set.dock_menu.addMenu(
        language_wrapper.language_word_dict.get("extend_tools_menu_dock_ssh_menu")
    )
    ui_we_want_to_set.dock_ai_menu = ui_we_want_to_set.dock_menu.addMenu(
        language_wrapper.language_word_dict.get("extend_tools_menu_dock_ai_menu")
    )
    # SSH
    ui_we_want_to_set.tools_ssh_client_dock_action = QAction(
        language_wrapper.language_word_dict.get("extend_tools_menu_ssh_client_dock_action")
    )
    ui_we_want_to_set.tools_ssh_client_dock_action.triggered.connect(
        lambda: add_dock(ui_we_want_to_set, "SSH"))
    ui_we_want_to_set.dock_ssh_menu.addAction(ui_we_want_to_set.tools_ssh_client_dock_action)

    # AI
    ui_we_want_to_set.tools_ai_code_review_dock_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_ai_code_review_dock_action"
    ))
    ui_we_want_to_set.tools_ai_code_review_dock_action.triggered.connect(
        lambda: add_dock(ui_we_want_to_set, "AICodeReview"))
    ui_we_want_to_set.dock_ai_menu.addAction(ui_we_want_to_set.tools_ai_code_review_dock_action)

    ui_we_want_to_set.tools_cot_prompt_editor_dock_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_cot_prompt_editor_dock_action"))
    ui_we_want_to_set.tools_cot_prompt_editor_dock_action.triggered.connect(
        lambda: add_dock(ui_we_want_to_set, "CoTPromptEditor"))
    ui_we_want_to_set.dock_ai_menu.addAction(ui_we_want_to_set.tools_cot_prompt_editor_dock_action)

    ui_we_want_to_set.tools_skill_prompt_editor_dock_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_skill_prompt_editor_dock_action"))
    ui_we_want_to_set.tools_skill_prompt_editor_dock_action.triggered.connect(
        lambda: add_dock(ui_we_want_to_set, "SkillPromptEditor"))
    ui_we_want_to_set.dock_ai_menu.addAction(ui_we_want_to_set.tools_skill_prompt_editor_dock_action)

    ui_we_want_to_set.tools_skill_send_dock_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_skill_prompt_send_dock_action"))
    ui_we_want_to_set.tools_skill_send_dock_action.triggered.connect(
        lambda: add_dock(ui_we_want_to_set, "SkillSendGUI"))
    ui_we_want_to_set.dock_ai_menu.addAction(ui_we_want_to_set.tools_skill_send_dock_action)

    # Diagram Editor Dock
    ui_we_want_to_set.tools_diagram_editor_dock_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_diagram_editor_dock_action"))
    ui_we_want_to_set.tools_diagram_editor_dock_action.triggered.connect(
        lambda: add_dock(ui_we_want_to_set, "DiagramEditor"))
    ui_we_want_to_set.dock_menu.addAction(ui_we_want_to_set.tools_diagram_editor_dock_action)

    # cURL Import Dock
    ui_we_want_to_set.tools_curl_import_dock_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_curl_import_dock_action"))
    ui_we_want_to_set.tools_curl_import_dock_action.triggered.connect(
        lambda: add_dock(ui_we_want_to_set, "CurlImport"))
    ui_we_want_to_set.dock_menu.addAction(ui_we_want_to_set.tools_curl_import_dock_action)

    # HAR Import Dock
    ui_we_want_to_set.tools_har_import_dock_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_har_import_dock_action"))
    ui_we_want_to_set.tools_har_import_dock_action.triggered.connect(
        lambda: add_dock(ui_we_want_to_set, "HarImport"))
    ui_we_want_to_set.dock_menu.addAction(ui_we_want_to_set.tools_har_import_dock_action)

    # JWT Decoder Dock
    ui_we_want_to_set.tools_jwt_decoder_dock_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_jwt_decoder_dock_action"))
    ui_we_want_to_set.tools_jwt_decoder_dock_action.triggered.connect(
        lambda: add_dock(ui_we_want_to_set, "JwtDecoder"))
    ui_we_want_to_set.dock_menu.addAction(ui_we_want_to_set.tools_jwt_decoder_dock_action)

    # Timestamp Converter Dock
    ui_we_want_to_set.tools_timestamp_dock_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_timestamp_dock_action"))
    ui_we_want_to_set.tools_timestamp_dock_action.triggered.connect(
        lambda: add_dock(ui_we_want_to_set, "Timestamp"))
    ui_we_want_to_set.dock_menu.addAction(ui_we_want_to_set.tools_timestamp_dock_action)

    # Hash Generator Dock
    ui_we_want_to_set.tools_hash_dock_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_hash_dock_action"))
    ui_we_want_to_set.tools_hash_dock_action.triggered.connect(
        lambda: add_dock(ui_we_want_to_set, "Hash"))
    ui_we_want_to_set.dock_menu.addAction(ui_we_want_to_set.tools_hash_dock_action)

    # Query <-> JSON Dock
    ui_we_want_to_set.tools_query_json_dock_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_query_json_dock_action"))
    ui_we_want_to_set.tools_query_json_dock_action.triggered.connect(
        lambda: add_dock(ui_we_want_to_set, "QueryJson"))
    ui_we_want_to_set.dock_menu.addAction(ui_we_want_to_set.tools_query_json_dock_action)

    # URL Parser / Builder Dock
    ui_we_want_to_set.tools_url_builder_dock_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_url_builder_dock_action"))
    ui_we_want_to_set.tools_url_builder_dock_action.triggered.connect(
        lambda: add_dock(ui_we_want_to_set, "UrlBuilder"))
    ui_we_want_to_set.dock_menu.addAction(ui_we_want_to_set.tools_url_builder_dock_action)

    # Regex Tester Dock
    ui_we_want_to_set.tools_regex_dock_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_regex_dock_action"))
    ui_we_want_to_set.tools_regex_dock_action.triggered.connect(
        lambda: add_dock(ui_we_want_to_set, "Regex"))
    ui_we_want_to_set.dock_menu.addAction(ui_we_want_to_set.tools_regex_dock_action)

    # HTTP Status Reference Dock
    ui_we_want_to_set.tools_http_status_dock_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_http_status_dock_action"))
    ui_we_want_to_set.tools_http_status_dock_action.triggered.connect(
        lambda: add_dock(ui_we_want_to_set, "HttpStatus"))
    ui_we_want_to_set.dock_menu.addAction(ui_we_want_to_set.tools_http_status_dock_action)

    # Text Diff Dock
    ui_we_want_to_set.tools_diff_dock_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_diff_dock_action"))
    ui_we_want_to_set.tools_diff_dock_action.triggered.connect(
        lambda: add_dock(ui_we_want_to_set, "Diff"))
    ui_we_want_to_set.dock_menu.addAction(ui_we_want_to_set.tools_diff_dock_action)

    # JSON Format Dock
    ui_we_want_to_set.tools_json_format_dock_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_json_format_dock_action"))
    ui_we_want_to_set.tools_json_format_dock_action.triggered.connect(
        lambda: add_dock(ui_we_want_to_set, "JsonFormat"))
    ui_we_want_to_set.dock_menu.addAction(ui_we_want_to_set.tools_json_format_dock_action)

    # HTTP Header Analyzer Dock
    ui_we_want_to_set.tools_header_analyzer_dock_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_header_analyzer_dock_action"))
    ui_we_want_to_set.tools_header_analyzer_dock_action.triggered.connect(
        lambda: add_dock(ui_we_want_to_set, "HeaderAnalyzer"))
    ui_we_want_to_set.dock_menu.addAction(ui_we_want_to_set.tools_header_analyzer_dock_action)

    # Response Inspector Dock
    ui_we_want_to_set.tools_response_dock_action = QAction(language_wrapper.language_word_dict.get(
        "extend_tools_menu_response_dock_action"))
    ui_we_want_to_set.tools_response_dock_action.triggered.connect(
        lambda: add_dock(ui_we_want_to_set, "ResponseInspector"))
    ui_we_want_to_set.dock_menu.addAction(ui_we_want_to_set.tools_response_dock_action)

# widget_type -> (dock-title language key, factory taking the main window).
# A dispatch table keeps ``add_dock`` flat instead of a long if/elif chain.
_DOCK_WIDGETS: dict[str, tuple[str, Callable[[PyBreezeMainWindow], object]]] = {
    "SSH": ("extend_tools_menu_ssh_client_dock_title", lambda _win: SSHMainWidget()),
    "AICodeReview": (
        "extend_tools_menu_ai_code_review_dock_title", lambda _win: AICodeReviewClient()),
    "CoTPromptEditor": (
        "extend_tools_menu_cot_prompt_editor_dock_title", lambda _win: CoTPromptEditor()),
    "SkillPromptEditor": (
        "extend_tools_menu_skill_prompt_editor_dock_title", lambda _win: SkillPromptEditor()),
    "SkillSendGUI": (
        "extend_tools_menu_skill_prompt_send_dock_title", lambda _win: SkillsSendGUI()),
    "DiagramEditor": (
        "extend_tools_menu_diagram_editor_dock_title", lambda _win: DiagramEditorWidget()),
    "CurlImport": (
        "extend_tools_menu_curl_import_dock_title", lambda win: CurlImportGUI(win)),
    "HarImport": ("extend_tools_menu_har_import_dock_title", lambda win: HarImportGUI(win)),
    "JwtDecoder": (
        "extend_tools_menu_jwt_decoder_dock_title", lambda win: JwtDecoderGUI(main_window=win)),
    "Timestamp": ("extend_tools_menu_timestamp_dock_title", lambda win: TimestampGUI(win)),
    "Hash": ("extend_tools_menu_hash_dock_title", lambda win: HashGUI(win)),
    "QueryJson": ("extend_tools_menu_query_json_dock_title", lambda win: QueryJsonGUI(win)),
    "UrlBuilder": ("extend_tools_menu_url_builder_dock_title", lambda win: UrlBuilderGUI(win)),
    "Regex": ("extend_tools_menu_regex_dock_title", lambda win: RegexGUI(win)),
    "HttpStatus": (
        "extend_tools_menu_http_status_dock_title", lambda win: HttpStatusGUI(main_window=win)),
    "Diff": ("extend_tools_menu_diff_dock_title", lambda win: DiffGUI(win)),
    "JsonFormat": ("extend_tools_menu_json_format_dock_title", lambda win: JsonFormatGUI(win)),
    "HeaderAnalyzer": (
        "extend_tools_menu_header_analyzer_dock_title", lambda win: HeaderAnalyzerGUI(win)),
    "ResponseInspector": (
        "extend_tools_menu_response_dock_title", lambda win: ResponseInspectorGUI(win)),
}


def add_dock(ui_we_want_to_set: PyBreezeMainWindow, widget_type: str | None = None):
    jeditor_logger.info("build_dock_menu.py add_dock_widget "
                        f"ui_we_want_to_set: {ui_we_want_to_set} "
                        f"widget_type: {widget_type}")

    # 建立一個可銷毀的 Dock 容器
    # Create a destroyable dock container
    dock_widget = DestroyDock()

    entry = _DOCK_WIDGETS.get(widget_type)
    if entry is not None:
        title_key, widget_factory = entry
        dock_widget.setWindowTitle(language_wrapper.language_word_dict.get(title_key))
        dock_widget.setWidget(widget_factory(ui_we_want_to_set))

    # 如果成功建立了 widget，將其加到主視窗右側 Dock 區域
    # If widget is created, add it to the right dock area of the main window
    if dock_widget.widget() is not None:
        ui_we_want_to_set.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_widget)
