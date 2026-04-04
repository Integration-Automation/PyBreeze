import os
import sys
from os import environ
from pathlib import Path

environ["LOCUST_SKIP_MONKEY_PATCH"] = "1"

from PySide6.QtCore import QTimer, QCoreApplication
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QWidget
from je_editor import EditorMain, language_wrapper
from qt_material import apply_stylesheet

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.menu.build_menubar import add_menu_to_menubar
from pybreeze.pybreeze_ui.syntax.syntax_extend import \
    syntax_extend_package


EDITOR_EXTEND_TAB: dict[str, type[QWidget]] = {
}


class PyBreezeMainWindow(EditorMain):

    def __init__(self, debug_mode: bool = False, show_system_tray_ray: bool = False, extend: bool = False) -> None:
        super().__init__(debug_mode, show_system_tray_ray, extend=True)
        # Note: EditorMain.__init__ already calls load_external_plugins()
        # which auto-discovers jeditor_plugins/ in the current working directory.
        # Third-party plugins placed there will be loaded automatically.

        self.current_run_code_window: list[QWidget] = list()
        # Project compiler if user not choose this will use which to find
        self.python_compiler = None
        # Delete JEditor help
        if self.help_menu:
            self.help_menu.deleteLater()

        # Update language_dict
        update_language_dict()

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

        if debug_mode:
            close_timer = QTimer(self)
            close_timer.setInterval(10000)
            close_timer.timeout.connect(self.debug_close)
            close_timer.start()

    def closeEvent(self, event) -> None:
        for widget in self.current_run_code_window:
            widget.close()
        super().closeEvent(event)

    @staticmethod
    def debug_close() -> None:
        """
        Use to run CI test.
        :return: None
        """
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
        from pybreeze.utils.logging.logger import pybreeze_logger
        pybreeze_logger.error(f"Startup setting error: {error}")
    ret = new_ide.exec()
    os._exit(ret)
