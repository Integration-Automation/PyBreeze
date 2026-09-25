"""PyBreeze's docks in JEditor's Dock menu: the AI ones join JEditor's AI submenu."""
from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMenu

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.menu.tools.tools_menu import extend_dock_menu

_AI_DOCKS = 5  # AI Code Review, CoT Prompt Editor, CoT Code Review, Skill Prompt Editor, Skill Send


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


def _submenus(menu: QMenu) -> list[str]:
    return [action.text() for action in menu.actions() if action.menu() is not None]


def test_the_ai_docks_join_jeditors_ai_submenu(app):
    dock_menu = QMenu()
    jeditor_ai = dock_menu.addMenu("AI")
    jeditor_ai.addAction("Chat UI")
    window = SimpleNamespace(dock_menu=dock_menu, dock_ai_menu=jeditor_ai)

    extend_dock_menu(window)

    assert window.dock_ai_menu is jeditor_ai
    assert _submenus(dock_menu).count("AI") == 1
    assert len(jeditor_ai.actions()) == 1 + _AI_DOCKS


def test_without_one_they_get_their_own(app):
    dock_menu = QMenu()
    window = SimpleNamespace(dock_menu=dock_menu)

    extend_dock_menu(window)

    assert "AI" in _submenus(dock_menu)
    assert len(window.dock_ai_menu.actions()) == _AI_DOCKS


def test_each_entry_opens_its_own_dock(app, monkeypatch):
    from pybreeze.pybreeze_ui.menu.tools import tools_menu

    opened: list = []
    monkeypatch.setattr(tools_menu, "add_dock", lambda window, widget_key: opened.append(widget_key))
    window = SimpleNamespace(dock_menu=QMenu())
    extend_dock_menu(window)

    for widget_key, attribute, _menu, _label in tools_menu._DOCK_ACTIONS:
        getattr(window, attribute).trigger()

    assert opened == [widget_key for widget_key, *_rest in tools_menu._DOCK_ACTIONS]
