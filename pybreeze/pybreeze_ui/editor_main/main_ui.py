from __future__ import annotations

import os
import sys
from os import environ
from pathlib import Path

environ["LOCUST_SKIP_MONKEY_PATCH"] = "1"

from PySide6.QtCore import QTimer, QCoreApplication
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QWidget
from je_editor import EditorMain, EditorWidget, language_wrapper
from je_editor.pyside_ui.main_ui.dock.destroy_dock import DestroyDock
from qt_material import apply_stylesheet

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.editor_main.file_tree_context_menu import setup_file_tree_context_menu
from pybreeze.pybreeze_ui.menu.build_menubar import add_menu_to_menubar
from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow
from pybreeze.pybreeze_ui.syntax.syntax_extend import \
    syntax_extend_package
from pybreeze.utils.logging.logger import pybreeze_logger


EDITOR_EXTEND_TAB: dict[str, type[QWidget]] = {
}


class PyBreezeMainWindow(EditorMain):

    def __init__(self, debug_mode: bool = False, show_system_tray_ray: bool = False, extend: bool = False) -> None:
        # PyBreeze's strings must be in JEditor's word dicts before EditorMain.__init__
        # picks the startup language: for any language but English it builds the
        # dictionary it reads from as a merged copy, so strings added afterwards are
        # missing from it, and a menu given a None title crashes Qt.
        update_language_dict()
        super().__init__(debug_mode, show_system_tray_ray, extend=True)
        # Note: EditorMain.__init__ already calls load_external_plugins()
        # which auto-discovers jeditor_plugins/ in the current working directory.
        # Third-party plugins placed there will be loaded automatically.

        self.current_run_code_window: list[CodeWindow] = []
        # Project compiler if user not choose this will use which to find
        self.python_compiler = None
        # Delete JEditor help
        if self.help_menu:
            self.help_menu.deleteLater()

        # Title
        self.setWindowTitle(language_wrapper.language_word_dict.get("application_name"))
        self.setToolTip(language_wrapper.language_word_dict.get("application_name"))

        # Windows 系統專用：設定應用程式 ID
        # Windows only: set application ID
        if not extend:
            self.id = language_wrapper.language_word_dict.get("application_name")
            if sys.platform in ["win32", "cygwin", "msys"]:
                from ctypes import windll
                windll.shell32.SetCurrentProcessExplicitAppUserModelID(self.id)

        # Icon
        if not extend:
            self.icon_path = Path(os.getcwd()) / "pybreeze_icon.ico"
            self.icon = QIcon(str(self.icon_path))
            if not self.icon.isNull():
                self.setWindowIcon(self.icon)

        # Menu
        add_menu_to_menubar(self)
        syntax_extend_package(self)

        # Tab
        for widget_name, widget in EDITOR_EXTEND_TAB.items():
            self.tab_widget.addTab(widget(), widget_name)

        # File tree context menu (right-click)
        setup_file_tree_context_menu(self)

        if debug_mode:
            close_timer = QTimer(self)
            close_timer.setInterval(10000)
            close_timer.timeout.connect(self.debug_close)
            close_timer.start()

    def closeEvent(self, event) -> None:
        # A run's child outlives the IDE unless stopped here: it is a separate
        # process, and without a console nobody would see it still running.
        # Over a copy: a window that closes drops itself from the list.
        for run_window in tuple(self.current_run_code_window):
            run_window.stop_runner()
            run_window.close()
        self._close_tool_tabs_and_docks()
        super().closeEvent(event)

    def _close_tool_tabs_and_docks(self) -> None:
        """Close PyBreeze's own tabs and docks so each can stop what it started.

        JEditor's ``closeEvent`` closes editor tabs only, and PyBreeze's tabs and
        docks own processes and sessions of their own -- a JupyterLab server, an
        SSH session, a diagram's downloads. Without this, ``start_editor``'s
        ``os._exit`` leaves them running.
        """
        for index in range(self.tab_widget.count() - 1, -1, -1):
            widget = self.tab_widget.widget(index)
            if widget is not None and not isinstance(widget, EditorWidget):
                widget.close()
        for dock in self.findChildren(DestroyDock):
            dock.close()

    def debug_close(self) -> None:
        """Close the window and leave the event loop. Used by the startup tests.

        Closing first means the same cleanup as a user closing the IDE --
        stopping any run still going, saving the settings -- which quitting
        the application on its own would skip.
        """
        self.close()
        app = QApplication.instance()
        if app is not None:
            app.quit()


def start_editor(debug_mode: bool = False, theme: str = "dark_amber.xml", **kwargs) -> None:
    """
    Start editor instance
    :param debug_mode: enable debug mode with auto-close timer
    :param theme: qt_material theme name (e.g. "dark_amber.xml", "dark_teal.xml", "light_blue.xml")
    :return: None
    """
    new_ide = QCoreApplication.instance()
    if new_ide is None:
        new_ide = QApplication(sys.argv)
    window = PyBreezeMainWindow(debug_mode=debug_mode, **kwargs)
    apply_stylesheet(new_ide, theme=theme)
    window.showMaximized()
    try:
        window.startup_setting()
    except Exception as error:
        pybreeze_logger.error(f"Startup setting error: {error}")
    ret = new_ide.exec()
    os._exit(ret)
