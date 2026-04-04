from __future__ import annotations

from typing import TYPE_CHECKING

from je_load_density.gui.main_widget import LoadDensityWidget

from pybreeze.pybreeze_ui.menu.automation_menu.automation_menu_factory import (
    build_automation_menu, safe_create_project
)

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow

from pybreeze.extend.process_executor.load_density.load_density_process import (
    call_load_density, call_load_density_with_send,
    call_load_density_multi_file, call_load_density_multi_file_and_send,
)


def set_load_density_menu(ui_we_want_to_set: PyBreezeMainWindow):
    build_automation_menu(
        ui=ui_we_want_to_set,
        menu_label_key="load_density_menu_label",
        run_actions=[
            {"label_key": "load_density_run_script_label",
             "callback": lambda: call_load_density(ui_we_want_to_set)},
            {"label_key": "load_density_run_script_with_send_label",
             "callback": lambda: call_load_density_with_send(ui_we_want_to_set)},
            {"label_key": "load_density_run_multi_script_label",
             "callback": lambda: call_load_density_multi_file(ui_we_want_to_set)},
            {"label_key": "load_density_run_multi_script_with_send_label",
             "callback": lambda: call_load_density_multi_file_and_send(ui_we_want_to_set)},
        ],
        doc_url="https://loaddensity.readthedocs.io/en/latest/",
        doc_label_key="load_density_doc_label",
        doc_tab_label_key="load_density_doc_tab_label",
        github_url="https://github.com/Intergration-Automation-Testing/LoadDensity",
        github_label_key="load_density_github_label",
        github_tab_label_key="load_density_github_tab_label",
        create_project_func=safe_create_project("je_load_density"),
        create_project_label_key="load_density_create_project_label",
        gui_widget_class=LoadDensityWidget,
        gui_label="LoadDensity GUI",
    )
