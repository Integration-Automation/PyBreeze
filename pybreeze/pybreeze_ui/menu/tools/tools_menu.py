from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtGui import QAction, Qt
from je_editor import language_wrapper

from je_editor import jeditor_logger

from pybreeze.pybreeze_ui.busy_cursor import busy_cursor
from pybreeze.pybreeze_ui.closing import AskingDock
from pybreeze.pybreeze_ui.design.tokens import apply_spacing
from pybreeze.pybreeze_ui.connect_gui.url.ai_code_review_gui import AICodeReviewClient
from pybreeze.pybreeze_ui.diagram_editor.diagram_editor_widget import DiagramEditorWidget
from pybreeze.pybreeze_ui.extend_ai_gui.code_review.cot_code_review_gui import CoTCodeReviewGUI
from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.cot_prompt_editor_widget import CoTPromptEditor
from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.skills_prompt_editor_widget import \
    SkillPromptEditor
from pybreeze.pybreeze_ui.extend_ai_gui.skills.skills_send_gui import SkillsSendGUI
from pybreeze.pybreeze_ui.mcp_gui.mcp_client_gui import McpClientGUI
from pybreeze.pybreeze_ui.tools_gui.curl_import_gui import CurlImportGUI
from pybreeze.pybreeze_ui.tools_gui.diff_gui import DiffGUI
from pybreeze.pybreeze_ui.tools_gui.json_editor_gui import JsonEditorGUI
from pybreeze.pybreeze_ui.tools_gui.json_format_gui import JsonFormatGUI
from pybreeze.pybreeze_ui.tools_gui.jwt_decoder_gui import JwtDecoderGUI
from pybreeze.pybreeze_ui.tools_gui.keyword_reference_gui import KeywordReferenceGUI
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
    from PySide6.QtWidgets import QWidget

    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow

# ---------------------------------------------------------------------------
# The tools
# ---------------------------------------------------------------------------

# What follows "extend_tools_menu_<words>" in a tool's four language keys
TOOL_WORD_SUFFIXES = ("_tab_action", "_tab_label", "_dock_action", "_dock_title")
_WORD_PREFIX = "extend_tools_menu_"


@dataclass(frozen=True)
class ToolDescriptor:
    """One tool: what builds it, and how the menus and the navigation panel name it.

    A tool used to be a row in four tables keyed by the same string (its
    factory, its dock title, its tab entry and its dock entry). It is one
    descriptor now, and the Tools menu, the Dock menu and the navigation panel
    are all built from the same table.

    :param key: the tool's stable name
    :param words: the stem of its language keys, ``extend_tools_menu_<words>``
        followed by each of ``TOOL_WORD_SUFFIXES``
    :param factory: builds the widget, given the main window
    :param tab_attribute: the main-window attribute that keeps its tab entry alive
    :param dock_attribute: the same for its dock entry
    :param group: the submenu it is listed in: none, ``"ssh"`` or ``"ai"``
    :param category: where the navigation panel lists it
        (``navigation_model.CATEGORIES``)
    """

    key: str
    words: str
    factory: Callable[[PyBreezeMainWindow], QWidget]
    tab_attribute: str
    dock_attribute: str
    group: str = ""
    category: str = "tools"

    @property
    def tab_action_key(self) -> str:
        """The language key of its Tools menu entry."""
        return f"{_WORD_PREFIX}{self.words}_tab_action"

    @property
    def tab_label_key(self) -> str:
        """The language key of its tab's label."""
        return f"{_WORD_PREFIX}{self.words}_tab_label"

    @property
    def dock_action_key(self) -> str:
        """The language key of its Dock menu entry."""
        return f"{_WORD_PREFIX}{self.words}_dock_action"

    @property
    def dock_title_key(self) -> str:
        """The language key of its dock's title."""
        return f"{_WORD_PREFIX}{self.words}_dock_title"


def _tool(
        key: str, words: str, factory: Callable[[PyBreezeMainWindow], QWidget], *,
        group: str = "", category: str = "tools",
        tab_attribute: str | None = None, dock_attribute: str | None = None) -> ToolDescriptor:
    """A descriptor whose action attributes are ``tools_<words>_action`` and ``tools_<words>_dock_action`` unless given."""
    return ToolDescriptor(
        key=key, words=words, factory=factory, group=group, category=category,
        tab_attribute=tab_attribute or f"tools_{words}_action",
        dock_attribute=dock_attribute or f"tools_{words}_dock_action")


def _ssh_widget() -> QWidget:
    # Imported when the SSH client first opens: paramiko and cryptography take
    # about a sixth of a second of the IDE's start
    from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_main_widget import SSHMainWidget
    return SSHMainWidget()


_SSH_GROUP = "ssh"
_AI_GROUP = "ai"

# Every tool, in the order the menus list them. A new tool is one line here.
TOOLS: dict[str, ToolDescriptor] = {tool.key: tool for tool in (
    _tool("SSH", "ssh_client", lambda _win: _ssh_widget(), group=_SSH_GROUP,
          tab_attribute="tools_ssh_client_tab_action"),
    _tool("AICodeReview", "ai_code_review", lambda _win: AICodeReviewClient(), group=_AI_GROUP),
    _tool("CoTPromptEditor", "cot_prompt_editor", lambda _win: CoTPromptEditor(), group=_AI_GROUP,
          tab_attribute="tools_ai_cot_prompt_editor_action"),
    _tool("CoTCodeReview", "cot_code_review", lambda _win: CoTCodeReviewGUI(), group=_AI_GROUP,
          tab_attribute="tools_ai_cot_code_review_action"),
    _tool("SkillPromptEditor", "skill_prompt_editor", lambda _win: SkillPromptEditor(), group=_AI_GROUP,
          tab_attribute="tools_ai_skill_prompt_editor_action"),
    _tool("SkillSendGUI", "skill_prompt_send", lambda _win: SkillsSendGUI(), group=_AI_GROUP,
          tab_attribute="tools_ai_skill_send_action", dock_attribute="tools_skill_send_dock_action"),
    _tool("DiagramEditor", "diagram_editor", lambda _win: DiagramEditorWidget()),
    _tool("CurlImport", "curl_import", lambda win: CurlImportGUI(win)),
    _tool("HarImport", "har_import", lambda win: HarImportGUI(win)),
    _tool("JwtDecoder", "jwt_decoder", lambda win: JwtDecoderGUI(main_window=win)),
    _tool("Timestamp", "timestamp", lambda win: TimestampGUI(win)),
    _tool("Hash", "hash", lambda win: HashGUI(win)),
    _tool("QueryJson", "query_json", lambda win: QueryJsonGUI(win)),
    _tool("UrlBuilder", "url_builder", lambda win: UrlBuilderGUI(win)),
    _tool("Regex", "regex", lambda win: RegexGUI(win)),
    _tool("HttpStatus", "http_status", lambda win: HttpStatusGUI(main_window=win)),
    _tool("Diff", "diff", lambda win: DiffGUI(win)),
    _tool("JsonFormat", "json_format", lambda win: JsonFormatGUI(win)),
    _tool("JsonEditor", "json_editor", lambda _win: JsonEditorGUI()),
    _tool("KeywordReference", "keyword_reference", lambda win: KeywordReferenceGUI(win)),
    _tool("McpClient", "mcp_client", lambda _win: McpClientGUI(), category="mcp"),
    _tool("HeaderAnalyzer", "header_analyzer", lambda win: HeaderAnalyzerGUI(win)),
    _tool("ResponseInspector", "response", lambda win: ResponseInspectorGUI(win)),
)}

# Group -> (the main-window attribute of its Tools submenu, of its Dock submenu)
_GROUP_MENUS: dict[str, tuple[str, str]] = {
    "": ("tools_menu", "dock_menu"),
    _SSH_GROUP: ("tools_ssh_menu", "dock_ssh_menu"),
    _AI_GROUP: ("tools_ai_menu", "dock_ai_menu"),
}


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def build_tool_widget(ui_we_want_to_set: PyBreezeMainWindow, key: str) -> QWidget:
    """Build the widget of the tool *key*, with the gaps every PyBreeze panel has around its content."""
    with busy_cursor():
        widget = TOOLS[key].factory(ui_we_want_to_set)
    layout = widget.layout()
    # A panel that fills its tab edge to edge (the diagram editor) set its own margins to none
    if layout is not None and not layout.contentsMargins().isNull():
        apply_spacing(layout)
    return widget


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


def _open_tab_handler(ui_we_want_to_set: PyBreezeMainWindow, tool: ToolDescriptor) -> Callable[[], None]:
    """Return a handler opening *tool*'s widget as a new tab."""

    def handler() -> None:
        widget = build_tool_widget(ui_we_want_to_set, tool.key)
        ui_we_want_to_set.tab_widget.addTab(widget, language_wrapper.language_word_dict.get(tool.tab_label_key))

    return handler


def _open_dock_handler(ui_we_want_to_set: PyBreezeMainWindow, tool: ToolDescriptor) -> Callable[[], None]:
    """Return a handler opening *tool*'s widget as a dock."""

    def handler() -> None:
        add_dock(ui_we_want_to_set, tool.key)

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

    for tool in TOOLS.values():
        _register_action(
            ui_we_want_to_set, tool.tab_attribute, _GROUP_MENUS[tool.group][0], tool.tab_action_key,
            _open_tab_handler(ui_we_want_to_set, tool),
        )


def extend_dock_menu(ui_we_want_to_set: PyBreezeMainWindow):
    # Sub menu
    ui_we_want_to_set.dock_ssh_menu = ui_we_want_to_set.dock_menu.addMenu(
        language_wrapper.language_word_dict.get("extend_tools_menu_dock_ssh_menu")
    )
    # JEditor's Dock menu has an AI submenu of its own (Chat UI): the review docks
    # join it. A second one beside it showed two "AI" entries
    if getattr(ui_we_want_to_set, "dock_ai_menu", None) is None:
        ui_we_want_to_set.dock_ai_menu = ui_we_want_to_set.dock_menu.addMenu(
            language_wrapper.language_word_dict.get("extend_tools_menu_dock_ai_menu")
        )

    for tool in TOOLS.values():
        _register_action(
            ui_we_want_to_set, tool.dock_attribute, _GROUP_MENUS[tool.group][1], tool.dock_action_key,
            _open_dock_handler(ui_we_want_to_set, tool),
        )


def add_dock(ui_we_want_to_set: PyBreezeMainWindow, widget_type: str | None = None):
    jeditor_logger.info("build_dock_menu.py add_dock_widget ui_we_want_to_set: %s widget_type: %s",
                        ui_we_want_to_set, widget_type)

    # 建立一個可銷毀的 Dock 容器
    # Create a destroyable dock container
    # One that asks its widget first: a docked prompt or diagram editor with
    # unsaved changes closed from the dock's button without a word
    dock_widget = AskingDock()

    tool = TOOLS.get(widget_type)
    if tool is not None:
        dock_widget.setWindowTitle(language_wrapper.language_word_dict.get(tool.dock_title_key))
        dock_widget.setWidget(build_tool_widget(ui_we_want_to_set, tool.key))

    # 如果成功建立了 widget，將其加到主視窗右側 Dock 區域
    # If widget is created, add it to the right dock area of the main window
    if dock_widget.widget() is not None:
        ui_we_want_to_set.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_widget)
