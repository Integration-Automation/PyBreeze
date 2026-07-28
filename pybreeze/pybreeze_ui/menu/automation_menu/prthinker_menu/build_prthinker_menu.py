"""
prthinker 程式碼審查的選單
The menu for prthinker code review.

兩種用法：審查目前開著的檔案，或審查一個 Pull Request。兩者共用同一份設定，設定裡填
的是後端與權杖。
Two ways in: review the file currently open, or review a pull request. Both use
the same settings, which is where the backend and the token are filled in.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QInputDialog, QMessageBox
from je_editor import language_wrapper

from pybreeze.extend.process_executor.prthinker.prthinker_process import (
    review_current_file, review_pull_request
)
from pybreeze.pybreeze_ui.dialog.prthinker_setting_dialog import PRThinkerSettingDialog
from pybreeze.pybreeze_ui.menu.menu_utils import open_web_browser

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow

# PR 編號的範圍，第一個 PR 是 1 / The range a pull request number falls in, the first being 1
FIRST_PULL_REQUEST_NUMBER = 1
LAST_PULL_REQUEST_NUMBER = 1000000

DOCUMENT_URL = "https://code-review-framework.readthedocs.io/en/latest/"
GITHUB_URL = "https://github.com/JE-Chen/Code-Review-Framework-Combining-Large-Language-Models-and-Chain-of-Thought-Reasoning"


def set_prthinker_menu(ui_we_want_to_set: PyBreezeMainWindow) -> None:
    """
    建立 prthinker 選單
    Build the prthinker menu.

    :param ui_we_want_to_set: 要加選單的主視窗 / the main window to add the menu to
    """
    lang = language_wrapper.language_word_dict
    ui_we_want_to_set.prthinker_menu = ui_we_want_to_set.automation_menu.addMenu(
        lang.get("prthinker_menu_label"))

    ui_we_want_to_set.prthinker_review_file_action = QAction(
        lang.get("prthinker_review_current_file_label"))
    ui_we_want_to_set.prthinker_review_file_action.triggered.connect(
        lambda: _review_current_file(ui_we_want_to_set))
    ui_we_want_to_set.prthinker_menu.addAction(
        ui_we_want_to_set.prthinker_review_file_action)

    ui_we_want_to_set.prthinker_review_pr_action = QAction(
        lang.get("prthinker_review_pull_request_label"))
    ui_we_want_to_set.prthinker_review_pr_action.triggered.connect(
        lambda: _review_pull_request(ui_we_want_to_set))
    ui_we_want_to_set.prthinker_menu.addAction(
        ui_we_want_to_set.prthinker_review_pr_action)

    ui_we_want_to_set.prthinker_setting_action = QAction(
        lang.get("prthinker_setting_label"))
    ui_we_want_to_set.prthinker_setting_action.triggered.connect(
        lambda: _open_setting(ui_we_want_to_set))
    ui_we_want_to_set.prthinker_menu.addAction(
        ui_we_want_to_set.prthinker_setting_action)

    help_menu = ui_we_want_to_set.prthinker_menu.addMenu(lang.get("help_label"))
    ui_we_want_to_set.prthinker_doc_action = QAction(lang.get("prthinker_doc_label"))
    ui_we_want_to_set.prthinker_doc_action.triggered.connect(
        lambda: open_web_browser(
            ui_we_want_to_set, DOCUMENT_URL, lang.get("prthinker_doc_tab_label")))
    help_menu.addAction(ui_we_want_to_set.prthinker_doc_action)
    ui_we_want_to_set.prthinker_github_action = QAction(lang.get("prthinker_github_label"))
    ui_we_want_to_set.prthinker_github_action.triggered.connect(
        lambda: open_web_browser(
            ui_we_want_to_set, GITHUB_URL, lang.get("prthinker_github_tab_label")))
    help_menu.addAction(ui_we_want_to_set.prthinker_github_action)


def _review_current_file(ui_we_want_to_set: PyBreezeMainWindow) -> None:
    """審查目前的檔案，沒有存檔就說一聲 / Review the current file, saying so when there is none."""
    if not review_current_file(ui_we_want_to_set):
        _tell(ui_we_want_to_set, "prthinker_need_saved_file_message")


def _review_pull_request(ui_we_want_to_set: PyBreezeMainWindow) -> None:
    """問要審哪個 PR，再開始審查 / Ask which pull request, then start the review."""
    lang = language_wrapper.language_word_dict
    number, chosen = QInputDialog.getInt(
        ui_we_want_to_set,
        lang.get("prthinker_review_pull_request_label"),
        lang.get("prthinker_pull_request_number_label"),
        FIRST_PULL_REQUEST_NUMBER, FIRST_PULL_REQUEST_NUMBER, LAST_PULL_REQUEST_NUMBER)
    if not chosen:
        return
    if not review_pull_request(ui_we_want_to_set, number):
        _tell(ui_we_want_to_set, "prthinker_need_repository_message")


def _open_setting(ui_we_want_to_set: PyBreezeMainWindow) -> None:
    """開設定視窗 / Open the settings window."""
    dialog = PRThinkerSettingDialog(ui_we_want_to_set)
    dialog.exec()


def _tell(ui_we_want_to_set: PyBreezeMainWindow, message_key: str) -> None:
    """把一句話說給使用者聽 / Put one sentence in front of the user."""
    lang = language_wrapper.language_word_dict
    messagebox = QMessageBox(ui_we_want_to_set)
    messagebox.setWindowTitle(lang.get("prthinker_menu_label"))
    messagebox.setText(lang.get(message_key))
    messagebox.exec()
