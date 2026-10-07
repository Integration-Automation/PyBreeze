"""What the navigation panel lists: PyBreeze's areas, and what can be done in each.

The IDE's functions sit in menus several levels deep, and a menu shows nothing
until it is opened. The navigation panel lists the same functions as a tree
that stays in view and can be searched: Automation, Tools, MCP, Reports and
Settings.

Nothing is listed twice by hand. An entry is taken from the menu action or the
tool descriptor that already exists, and choosing it triggers that same
action, so the panel cannot offer something the menus do not, or do it another
way. A category with nothing in it is left out.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.menu.tools.tools_menu import TOOLS

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow

# The categories, in the order they are listed: (key, language key of its title)
CATEGORIES: tuple[tuple[str, str], ...] = (
    ("automation", "navigation_category_automation"),
    ("tools", "navigation_category_tools"),
    ("mcp", "navigation_category_mcp"),
    ("reports", "navigation_category_reports"),
    ("settings", "navigation_category_settings"),
)

# Group of a tool -> the main-window attribute of the Tools submenu whose title names the group
_GROUP_TITLE_MENUS = {"ssh": "tools_ssh_menu", "ai": "tools_ai_menu"}
# The main-window attributes of the menus listed under Settings, in order
_SETTINGS_MENUS = ("language_menu", "venv_menu", "install_menu")
# JEditor's language key for the title of its UI Style menu, which it keeps no attribute for
_STYLE_MENU_TITLE_KEY = "style_menu_label"


@dataclass
class NavigationEntry:
    """One line of the navigation tree.

    :param text: what it shows
    :param activate: what choosing it does; ``None`` for a line that only holds others
    :param children: the lines under it
    """

    text: str
    activate: Callable[[], None] | None = None
    children: list[NavigationEntry] = field(default_factory=list)


def _shown(text: str) -> str:
    """A menu text without the ``&`` that marks its mnemonic (``&&`` is a real ampersand)."""
    return text.replace("&&", "\0").replace("&", "").replace("\0", "&")


def submenus_under(parent: QObject) -> dict[QAction, QMenu]:
    """Every menu under *parent*, by the action that opens it.

    This is how a submenu is found from its entry. ``QAction.menu()`` is not
    asked: under PySide6 6.11.0 the object it returns takes the menu with it
    when it is dropped, and reading a menu must leave the menu as it was.
    """
    return {menu.menuAction(): menu for menu in parent.findChildren(QMenu)}


def entries_from_menu(menu: QMenu, submenus: dict[QAction, QMenu] | None = None) -> list[NavigationEntry]:
    """The entries of *menu* as navigation lines, submenus as lines that hold others.

    A separator, a hidden entry and a submenu with nothing in it are left out.

    :param menu: the menu to read
    :param submenus: the menus an entry may open (:func:`submenus_under`); those under *menu* when not given
    """
    if submenus is None:
        submenus = submenus_under(menu)
    entries: list[NavigationEntry] = []
    for action in menu.actions():
        if action.isSeparator() or not action.isVisible():
            continue
        submenu = submenus.get(action)
        if submenu is None:
            entries.append(NavigationEntry(_shown(action.text()), activate=action.trigger))
            continue
        children = entries_from_menu(submenu, submenus)
        if children:
            entries.append(NavigationEntry(_shown(action.text()), children=children))
    return entries


def _menu_entry(menu: object, submenus: dict[QAction, QMenu]) -> list[NavigationEntry]:
    """*menu* as one line holding its entries; nothing when it is not a menu or holds nothing."""
    children = entries_from_menu(menu, submenus) if isinstance(menu, QMenu) else []
    return [NavigationEntry(_shown(menu.title()), children=children)] if children else []


def _style_menu(window: PyBreezeMainWindow, submenus: dict[QAction, QMenu]) -> QMenu | None:
    """JEditor's UI Style menu, found on the menu bar by its title."""
    title = language_wrapper.language_word_dict.get(_STYLE_MENU_TITLE_KEY)
    for action in window.menuBar().actions():
        if title and action.text() == title:
            return submenus.get(action)
    return None


def _tool_entries(window: PyBreezeMainWindow, category: str) -> list[NavigationEntry]:
    """The tools of *category*, each opening its tab; the tools of a group under a line named as its submenu."""
    word = language_wrapper.language_word_dict
    entries: list[NavigationEntry] = []
    groups: dict[str, NavigationEntry] = {}
    for tool in TOOLS.values():
        action = getattr(window, tool.tab_attribute, None)
        if tool.category != category or action is None:
            continue
        line = NavigationEntry(word.get(tool.tab_label_key), activate=action.trigger)
        group_menu = getattr(window, _GROUP_TITLE_MENUS.get(tool.group, ""), None)
        if group_menu is None:
            entries.append(line)
            continue
        if tool.group not in groups:
            groups[tool.group] = NavigationEntry(_shown(group_menu.title()))
            entries.append(groups[tool.group])
        groups[tool.group].children.append(line)
    return entries


def build_navigation(window: PyBreezeMainWindow) -> dict[str, list[NavigationEntry]]:
    """What each category holds for *window*, by the category's key.

    Called once the menus are built: every entry is one of their actions.
    """
    submenus = submenus_under(window) if isinstance(window, QObject) else {}
    automation_menu = getattr(window, "automation_menu", None)
    settings = _menu_entry(_style_menu(window, submenus), submenus)
    for attribute in _SETTINGS_MENUS:
        settings.extend(_menu_entry(getattr(window, attribute, None), submenus))
    return {
        "automation": entries_from_menu(automation_menu, submenus) if isinstance(automation_menu, QMenu) else [],
        "tools": _tool_entries(window, "tools"),
        "mcp": _tool_entries(window, "mcp"),
        "reports": _tool_entries(window, "reports"),
        "settings": settings,
    }
