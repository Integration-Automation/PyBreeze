from __future__ import annotations

from typing import TYPE_CHECKING

from je_api_testka.gui.main_widget import APITestkaWidget

from pybreeze.pybreeze_ui.menu.automation_menu.automation_menu_factory import (
    build_automation_menu, safe_create_project
)

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow

from pybreeze.extend.process_executor.api_testka.api_testka_process import (
    call_api_testka, call_api_testka_with_send,
    call_api_testka_multi_file, call_api_testka_multi_file_and_send,
)


def set_apitestka_menu(ui_we_want_to_set: PyBreezeMainWindow):
    build_automation_menu(
        ui=ui_we_want_to_set,
        menu_label_key="apitestka_menu_label",
        run_actions=[
            {"label_key": "apitestka_run_script_label",
             "callback": lambda: call_api_testka(ui_we_want_to_set)},
            {"label_key": "apitestka_run_script_with_send_label",
             "callback": lambda: call_api_testka_with_send(ui_we_want_to_set)},
            {"label_key": "apitestka_run_multi_script_label",
             "callback": lambda: call_api_testka_multi_file(ui_we_want_to_set)},
            {"label_key": "apitestka_run_multi_script_with_send_label",
             "callback": lambda: call_api_testka_multi_file_and_send(ui_we_want_to_set)},
        ],
        doc_url="https://apitestka.readthedocs.io/en/latest/",
        doc_label_key="apitestka_doc_label",
        doc_tab_label_key="apitestka_doc_tab_label",
        github_url="https://github.com/Intergration-Automation-Testing/APITestka",
        github_label_key="apitestka_github_label",
        github_tab_label_key="apitestka_github_tab_label",
        create_project_func=safe_create_project("je_api_testka"),
        create_project_label_key="apitestka_create_project_label",
        gui_widget_class=APITestkaWidget,
        gui_label="APITestka GUI",
    )
