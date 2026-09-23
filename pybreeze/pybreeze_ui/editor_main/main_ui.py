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
from pybreeze.pybreeze_ui.closing import AskingDock, may_close
from pybreeze.pybreeze_ui.editor_main.file_tree_context_menu import setup_file_tree_context_menu
from pybreeze.pybreeze_ui.gui_thread_gc import collect_garbage_on_gui_thread
from pybreeze.pybreeze_ui.menu.build_menubar import add_menu_to_menubar
from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow
from pybreeze.pybreeze_ui.syntax.syntax_extend import \
    syntax_extend_package
from pybreeze.utils.logging.logger import pybreeze_logger


EDITOR_EXTEND_TAB: dict[str, type[QWidget]] = {
}


def _close_guarded(widget: QWidget, *steps) -> None:
    """Run *widget*'s closing *steps*, logging a failure instead of raising it.

    The IDE's close runs every tab's and dock's close before JEditor's own, and
    some of them are third-party (``EDITOR_EXTEND_TAB``) or plugin widgets. One
    that raised stopped the rest: JEditor's close never ran, so the open files
    were not recorded, the settings not written and the editors' auto-save
    threads not stopped.
    """
    for step in steps:
        try:
            step()
        except Exception as error:  # noqa: BLE001 — any widget may raise on close; the IDE must still close the rest
            pybreeze_logger.error("%s did not close cleanly: %r", type(widget).__name__, error)


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
        self._add_extend_tabs()

        # File tree context menu (right-click)
        setup_file_tree_context_menu(self)

        if debug_mode:
            close_timer = QTimer(self)
            close_timer.setInterval(10000)
            close_timer.timeout.connect(self.debug_close)
            close_timer.start()

    def _add_extend_tabs(self) -> None:
        """Add every registered ``EDITOR_EXTEND_TAB`` widget as a tab.

        The registry is open to third parties, so one widget whose constructor
        raises must cost only its own tab: unguarded, it took down the whole
        window before anything was shown, and the user got a traceback instead
        of an IDE.
        """
        for widget_name, widget in EDITOR_EXTEND_TAB.items():
            try:
                self.tab_widget.addTab(widget(), widget_name)
            except Exception as error:  # noqa: BLE001 — a registered third-party tab may raise anything; the IDE must still start
                pybreeze_logger.error("Extend tab %r could not be built: %r", widget_name, error)

    def close_tab(self, index: int) -> None:
        """Close the tab at *index*, unless it has unsaved work the user keeps.

        JEditor asks about its own editor tabs only, and closes any other tab
        whatever its ``closeEvent`` says: a prompt or a diagram being edited
        was lost. A tab with a ``may_close()`` is asked first.
        """
        if not may_close(self.tab_widget.widget(index)):
            return
        super().close_tab(index)

    def _tool_tabs_may_close(self) -> bool:
        """Whether every PyBreeze tab and docked widget agrees to close (each may ask)."""
        widgets = [self.tab_widget.widget(index) for index in range(self.tab_widget.count())]
        widgets += [dock.widget() for dock in self.findChildren(DestroyDock)]
        agreed = all(may_close(widget) for widget in widgets if not isinstance(widget, EditorWidget))
        if agreed:
            # Asked once here: a dock that asks on close must not ask again
            for dock in self.findChildren(AskingDock):
                dock.already_asked = True
        return agreed

    def closeEvent(self, event) -> None:
        # Asked before anything is stopped: a No keeps the IDE open as it was
        if not self._tool_tabs_may_close():
            event.ignore()
            return
        # A run's child outlives the IDE unless stopped here: it is a separate
        # process, and without a console nobody would see it still running.
        # Over a copy: a window that closes drops itself from the list.
        for run_window in tuple(self.current_run_code_window):
            _close_guarded(run_window, run_window.stop_runner, run_window.close)
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
                _close_guarded(widget, widget.close)
        for dock in self.findChildren(DestroyDock):
            _close_guarded(dock, dock.close)

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
    # Workers allocate enough to trigger a collection, which then destroyed
    # Qt objects on the worker and crashed the IDE later
    collect_garbage_on_gui_thread(new_ide)
    window = PyBreezeMainWindow(debug_mode=debug_mode, **kwargs)
    apply_stylesheet(new_ide, theme=theme)
    window.showMaximized()
    try:
        window.startup_setting()
    # The user's saved settings, and the files they reopen, can be anything:
    # a bad one is logged and the IDE starts without it.
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        pybreeze_logger.error("Startup setting error: %r", error)
    ret = new_ide.exec()
    os._exit(ret)
