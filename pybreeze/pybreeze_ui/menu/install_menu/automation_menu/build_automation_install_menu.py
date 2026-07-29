from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QMessageBox
from je_editor import language_wrapper

from pybreeze.extend.prthinker_extend.prthinker_setting import (
    install_target, load_setting, save_setting
)
from pybreeze.pybreeze_ui.menu.install_menu.install_utils import install_package

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow


def build_automation_install_menu(ui_we_want_to_set: PyBreezeMainWindow):
    ui_we_want_to_set.install_automation_menu = ui_we_want_to_set.install_menu.addMenu(
        language_wrapper.language_word_dict.get("automation_menu_label"))
    # Try to install AutoControl
    ui_we_want_to_set.install_autocontrol_action = QAction(
        language_wrapper.language_word_dict.get("install_menu_autocontrol"))
    ui_we_want_to_set.install_autocontrol_action.triggered.connect(
        lambda: install_autocontrol(ui_we_want_to_set)
    )
    ui_we_want_to_set.install_automation_menu.addAction(ui_we_want_to_set.install_autocontrol_action)
    # Try to install APITestka
    ui_we_want_to_set.install_api_testka = QAction(
        language_wrapper.language_word_dict.get("install_menu_apitestka"))
    ui_we_want_to_set.install_api_testka.triggered.connect(
        lambda: install_api_testka(ui_we_want_to_set)
    )
    ui_we_want_to_set.install_automation_menu.addAction(ui_we_want_to_set.install_api_testka)
    # Try to install LoadDensity
    ui_we_want_to_set.install_load_density_action = QAction(
        language_wrapper.language_word_dict.get("install_menu_loaddensity"))
    ui_we_want_to_set.install_load_density_action.triggered.connect(
        lambda: install_load_density(ui_we_want_to_set)
    )
    ui_we_want_to_set.install_automation_menu.addAction(ui_we_want_to_set.install_load_density_action)
    # Try to install WebRunner
    ui_we_want_to_set.install_web_runner_action = QAction(
        language_wrapper.language_word_dict.get("install_menu_webrunner"))
    ui_we_want_to_set.install_web_runner_action.triggered.connect(
        lambda: install_web_runner(ui_we_want_to_set)
    )
    ui_we_want_to_set.install_automation_menu.addAction(ui_we_want_to_set.install_web_runner_action)
    # Try to install Automation File
    ui_we_want_to_set.install_automation_file_action = QAction(
        language_wrapper.language_word_dict.get("install_menu_automation_file"))
    ui_we_want_to_set.install_automation_file_action.triggered.connect(
        lambda: install_automation_file(ui_we_want_to_set)
    )
    ui_we_want_to_set.install_automation_menu.addAction(ui_we_want_to_set.install_automation_file_action)
    # Try to install MailThunder
    ui_we_want_to_set.install_mail_thunder_action = QAction(
        language_wrapper.language_word_dict.get("install_menu_mail_thunder"))
    ui_we_want_to_set.install_mail_thunder_action.triggered.connect(
        lambda: install_mail_thunder_file(ui_we_want_to_set)
    )
    ui_we_want_to_set.install_automation_menu.addAction(ui_we_want_to_set.install_mail_thunder_action)
    # Try to install prthinker
    ui_we_want_to_set.install_prthinker_action = QAction(
        language_wrapper.language_word_dict.get("install_menu_prthinker"))
    ui_we_want_to_set.install_prthinker_action.triggered.connect(
        lambda: install_prthinker(ui_we_want_to_set)
    )
    ui_we_want_to_set.install_automation_menu.addAction(ui_we_want_to_set.install_prthinker_action)


def install_autocontrol(ui_we_want_to_set: PyBreezeMainWindow) -> None:
    install_package("je_auto_control", ui_we_want_to_set)


def install_api_testka(ui_we_want_to_set: PyBreezeMainWindow) -> None:
    install_package("je_api_testka", ui_we_want_to_set)


def install_load_density(ui_we_want_to_set: PyBreezeMainWindow) -> None:
    install_package("je_load_density", ui_we_want_to_set)


def install_web_runner(ui_we_want_to_set: PyBreezeMainWindow) -> None:
    install_package("je_web_runner", ui_we_want_to_set)


def install_automation_file(ui_we_want_to_set: PyBreezeMainWindow) -> None:
    install_package("automation_file", ui_we_want_to_set)


def install_mail_thunder_file(ui_we_want_to_set: PyBreezeMainWindow) -> None:
    install_package("je_mail_thunder", ui_we_want_to_set)


def install_prthinker(ui_we_want_to_set: PyBreezeMainWindow) -> None:
    """Install the code review framework from its own source folder.

    prthinker is installed from source rather than from PyPI, so the folder is
    asked for once and then remembered in the prthinker settings.
    """
    setting = load_setting()
    target = install_target(setting.get("source_path", ""))
    if not target:
        chosen = QFileDialog(parent=ui_we_want_to_set).getExistingDirectory(
            caption=language_wrapper.language_word_dict.get(
                "prthinker_choose_source_path_label"))
        target = install_target(chosen or "")
        if not target:
            messagebox = QMessageBox(ui_we_want_to_set)
            messagebox.setWindowTitle(
                language_wrapper.language_word_dict.get("install_menu_prthinker"))
            messagebox.setText(
                language_wrapper.language_word_dict.get(
                    "prthinker_need_source_path_message"))
            messagebox.exec()
            return
        setting["source_path"] = chosen
        save_setting(setting)
    install_package(target, ui_we_want_to_set)
