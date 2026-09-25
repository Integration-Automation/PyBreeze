from __future__ import annotations

from typing import TYPE_CHECKING

from pybreeze.pybreeze_ui.menu.automation_menu.automation_menu_factory import (
    AutomationMenu, HelpLink, RunAction, build_automation_menu, safe_create_project
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow

from pybreeze.extend.process_executor.load_density.load_density_process import (
    call_load_density, call_load_density_with_send,
    call_load_density_multi_file, call_load_density_multi_file_and_send,
)


def _load_density_gui() -> QWidget:
    # Imported when its tab opens: the package brings locust and gevent, about
    # half a second of the IDE's start
    from je_load_density.gui.main_widget import LoadDensityWidget
    return LoadDensityWidget()


def set_load_density_menu(ui_we_want_to_set: PyBreezeMainWindow):
    build_automation_menu(ui_we_want_to_set, AutomationMenu(
        label_key="load_density_menu_label",
        run_actions=(
            RunAction("load_density_run_script_label",
                      lambda: call_load_density(ui_we_want_to_set)),
            RunAction("load_density_run_script_with_send_label",
                      lambda: call_load_density_with_send(ui_we_want_to_set)),
            RunAction("load_density_run_multi_script_label",
                      lambda: call_load_density_multi_file(ui_we_want_to_set)),
            RunAction("load_density_run_multi_script_with_send_label",
                      lambda: call_load_density_multi_file_and_send(ui_we_want_to_set)),
        ),
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
