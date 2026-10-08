from __future__ import annotations

from typing import TYPE_CHECKING

from pybreeze.pybreeze_ui.menu.automation_menu.automation_menu_factory import (
    AutomationMenu, HelpLink, build_automation_menu, package_run_actions, safe_create_project
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow


def _load_density_gui() -> QWidget:
    # Imported when its tab opens: the package brings locust and gevent, about
    # half a second of the IDE's start
    from je_load_density.gui.main_widget import LoadDensityWidget
    return LoadDensityWidget()


def set_load_density_menu(ui_we_want_to_set: PyBreezeMainWindow):
    build_automation_menu(ui_we_want_to_set, AutomationMenu(
        label_key="load_density_menu_label",
        run_actions=package_run_actions(ui_we_want_to_set, "load_density", "je_load_density"),
        help_links=(
            HelpLink("https://loaddensity.readthedocs.io/en/latest/",
                     "load_density_doc_label", "load_density_doc_tab_label"),
            HelpLink("https://github.com/Integration-Automation/LoadDensity",
                     "load_density_github_label", "load_density_github_tab_label"),
        ),
        create_project=safe_create_project(ui_we_want_to_set, "je_load_density"),
        create_project_label_key="load_density_create_project_label",
        gui_widget_factory=_load_density_gui,
        gui_label="LoadDensity GUI",
    ))
