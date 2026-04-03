from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.jupyter_lab_gui.jupyter_lab_widget import JupyterLabWidget
from pybreeze.utils.logging.logger import pybreeze_logger

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow

def extend_tab_tools_menu(ui_we_want_to_set: PyBreezeMainWindow):
    jeditor_tab_menu: QMenu = ui_we_want_to_set.tab_menu.tools_menu

    jeditor_tab_menu.add_jupyterlab_action = QAction(
        language_wrapper.language_word_dict.get("tab_menu_jupyterlab_tab_name"))
    jeditor_tab_menu.add_jupyterlab_action.triggered.connect(
        lambda: add_jupyterlab_tab(ui_we_want_to_set)
    )
    jeditor_tab_menu.addAction(jeditor_tab_menu.add_jupyterlab_action)

def add_jupyterlab_tab(ui_we_want_to_set: PyBreezeMainWindow):
    pybreeze_logger.info(f"jupyter_lab_tab.py add jupyter tab ui_we_want_to_set: {ui_we_want_to_set}")
    ui_we_want_to_set.tab_widget.addTab(
        JupyterLabWidget(),
        f"{language_wrapper.language_word_dict.get('tab_menu_jupyterlab_tab_name')} "
        f"{ui_we_want_to_set.tab_widget.count()}")
