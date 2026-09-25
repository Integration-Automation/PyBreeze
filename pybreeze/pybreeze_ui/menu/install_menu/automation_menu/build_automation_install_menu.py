from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QMessageBox
from je_editor import language_wrapper

from pybreeze.extend.prthinker_extend.prthinker_setting import (
    install_target, load_setting, save_setting
)
from pybreeze.pybreeze_ui.menu.install_menu.install_utils import install_package

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow

# The entries installed from PyPI, in menu order: the language key of each
# label and the package it installs
PYPI_PACKAGES: tuple[tuple[str, str], ...] = (
    ("install_menu_autocontrol", "je_auto_control"),
    ("install_menu_apitestka", "je_api_testka"),
    ("install_menu_loaddensity", "je_load_density"),
    ("install_menu_webrunner", "je_web_runner"),
    ("install_menu_automation_file", "automation_file"),
    ("install_menu_mail_thunder", "je_mail_thunder"),
    ("install_menu_test_pioneer", "test_pioneer"),
)


def build_automation_install_menu(ui_we_want_to_set: PyBreezeMainWindow):
    """Add the Automation submenu of Install: one entry per package, then prthinker."""
    words = language_wrapper.language_word_dict
    menu = ui_we_want_to_set.install_menu.addMenu(words.get("automation_menu_label"))
    ui_we_want_to_set.install_automation_menu = menu
    for label_key, package in PYPI_PACKAGES:
        # The menu is the action's parent: a menu does not own what is added to it
        action = QAction(words.get(label_key), menu)
        action.triggered.connect(
            lambda _checked=False, name=package: install_package(name, ui_we_want_to_set))
        menu.addAction(action)
    prthinker_action = QAction(words.get("install_menu_prthinker"), menu)
    prthinker_action.triggered.connect(lambda: install_prthinker(ui_we_want_to_set))
    menu.addAction(prthinker_action)


def install_prthinker(ui_we_want_to_set: PyBreezeMainWindow) -> None:
    """Install the code review framework from its own source folder.

    prthinker is installed from source rather than from PyPI, so the folder is
    asked for once and then remembered in the prthinker settings.
    """
    setting = load_setting()
    target = install_target(setting.get("source_path", ""))
    if not target:
        # Static: called through an instance, the dialog had no parent and
        # could open behind the main window.
        chosen = QFileDialog.getExistingDirectory(
            ui_we_want_to_set,
            language_wrapper.language_word_dict.get("prthinker_choose_source_path_label"))
        target = install_target(chosen or "")
        if not target:
            messagebox = QMessageBox(ui_we_want_to_set)
            messagebox.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
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
