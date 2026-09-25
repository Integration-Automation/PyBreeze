from __future__ import annotations

import os
import sys
from os import environ
from pathlib import Path

from pybreeze.utils.subprocess_util import IDE_ONLY

# locust patches the whole process with gevent as it imports unless this is set,
# and the IDE imports it: the Load Density GUI, or a user in JEditor's
# in-process console. IDE_ONLY keeps it out of the processes the IDE starts (a
# load test needs the patching to run its users at once); a value the user set
# is kept, for both.
environ["LOCUST_SKIP_MONKEY_PATCH"] = environ.get("LOCUST_SKIP_MONKEY_PATCH") or IDE_ONLY

from PySide6.QtCore import QTimer, QCoreApplication
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QWidget
from je_editor import EditorMain, EditorWidget, language_wrapper
from je_editor.pyside_ui.main_ui.dock.destroy_dock import DestroyDock
from je_editor.pyside_ui.main_ui.save_settings.user_setting_file import user_setting_dict
from qt_material import apply_stylesheet

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.code_result_logs import show_only_warnings_in_code_result
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

# The theme until one is picked from UI Style, as JEditor has it
DEFAULT_THEME = "dark_amber.xml"

# Shipped beside this module (package data): it was read from the working
# folder, which a started IDE never has, and the window had no icon
_ICON_PATH = Path(__file__).with_name("pybreeze_icon.ico")


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
        show_only_warnings_in_code_result()
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
            self.icon_path = _ICON_PATH
            self.icon = QIcon(str(self.icon_path))
            if not self.icon.isNull():
                self.setWindowIcon(self.icon)

        # Menu
        add_menu_to_menubar(self)
        syntax_extend_package(self)
        # JEditor's Stop All Program stops what its own menus started; PyBreeze's runs join it
        self.run_menu.stop_all_program_action.triggered.connect(self.stop_all_runs)

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

        A tool tab is deleted once it is closed. ``removeTab`` keeps the page,
        so every tool tab ever closed stayed in memory until the IDE exited,
        a diagram with its scene and an SSH panel among them; a docked one is
        already deleted as its dock closes. JEditor's own editor tabs are left
        to JEditor.
        """
        widget = self.tab_widget.widget(index)
        if not may_close(widget):
            return
        super().close_tab(index)
        if widget is not None and not isinstance(widget, EditorWidget) and self.tab_widget.indexOf(widget) == -1:
            widget.deleteLater()

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

    def stop_all_runs(self) -> None:
        """Stop the run in every run window: an automation script, a package install, a Run with... run.

        Connected to Run > Stop All Program, which stopped only the programs
        JEditor's own menus started. The windows stay open with their output;
        one whose stop fails is logged and the others are still stopped.
        """
        # Over a copy: a window that ends its run may drop itself from the list
        for run_window in tuple(self.current_run_code_window):
            _close_guarded(run_window, run_window.stop_runner)

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


def start_editor(debug_mode: bool = False, theme: str | None = None, **kwargs) -> None:
    """
    Start editor instance
    :param debug_mode: enable debug mode with auto-close timer
    :param theme: qt_material theme name (e.g. "dark_teal.xml", "light_blue.xml"). It replaces
        the theme picked from UI Style, and is kept as the picked one. ``None`` starts with the
        picked theme, ``dark_amber.xml`` until one is picked
    :return: None
    """
    new_ide = QCoreApplication.instance()
    if new_ide is None:
        new_ide = QApplication(sys.argv)
    # Workers allocate enough to trigger a collection, which then destroyed
    # Qt objects on the worker and crashed the IDE later
    collect_garbage_on_gui_thread(new_ide)
    # Held until the application ends: the window is nobody else's
    _window = open_main_window(new_ide, debug_mode=debug_mode, theme=theme, **kwargs)
    ret = new_ide.exec()
    os._exit(ret)


def open_main_window(app: QApplication, debug_mode: bool = False, theme: str | None = None,
                     **kwargs) -> PyBreezeMainWindow:
    """Build the main window, style it, show it and apply the saved settings.

    :param app: the running application, which the theme is applied to
    :param debug_mode: close by itself after a while, as the startup tests need
    :param theme: qt_material theme name, which replaces the one picked from UI Style and is
        kept as the picked one; ``None`` keeps the picked one
    :return: the window, which the caller keeps for as long as the IDE runs
    """
    window = PyBreezeMainWindow(debug_mode=debug_mode, **kwargs)
    # startup_setting() applies the picked theme, over any applied before it:
    # a theme given here was never seen until it became the picked one
    if theme is not None:
        user_setting_dict["ui_style"] = theme
    apply_stylesheet(app, theme=user_setting_dict.get("ui_style", DEFAULT_THEME))
    window.showMaximized()
    try:
        window.startup_setting()
    # The user's saved settings, and the files they reopen, can be anything:
    # a bad one is logged and the IDE starts without it.
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        pybreeze_logger.error("Startup setting error: %r", error)
    return window
