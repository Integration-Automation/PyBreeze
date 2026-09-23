from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QMessageBox
from je_editor import language_wrapper
from test_pioneer import create_template_dir

from pybreeze.extend.process_executor.test_pioneer.test_pioneer_process_manager import \
    init_and_start_test_pioneer_process
from pybreeze.utils.logging.logger import pybreeze_logger

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow


# A TestPioneer script is YAML, under either of YAML's extensions
_YAML_SUFFIXES = (".yml", ".yaml")
_YAML_FILTER = "YAML (*.yml *.yaml)"
# Where TestPioneer puts its template, under the project directory
_TEMPLATE_DIR = ".TestPioneer"


def set_test_pioneer_menu(ui_we_want_to_set: PyBreezeMainWindow):
    """
    Build menu include Test Pioneer feature.
    :param ui_we_want_to_set: main window to add menu.
    :return: None
    """
    ui_we_want_to_set.test_pioneer_menu = ui_we_want_to_set.automation_menu.addMenu(
        language_wrapper.language_word_dict.get("test_pioneer_label"))
    # Create test pioneer template
    ui_we_want_to_set.create_template_action = QAction(
        language_wrapper.language_word_dict.get("test_pioneer_create_template_label"))
    ui_we_want_to_set.create_template_action.triggered.connect(
        lambda: create_template(ui_we_want_to_set)
    )
    ui_we_want_to_set.test_pioneer_menu.addAction(
        ui_we_want_to_set.create_template_action
    )
    # Run test pioneer yaml
    ui_we_want_to_set.run_yaml_action = QAction(
        language_wrapper.language_word_dict.get("test_pioneer_run_yaml"))
    ui_we_want_to_set.run_yaml_action.triggered.connect(
        lambda: check_file(ui_we_want_to_set)
    )
    ui_we_want_to_set.test_pioneer_menu.addAction(
        ui_we_want_to_set.run_yaml_action
    )


def create_template(ui_we_want_to_set: PyBreezeMainWindow) -> None:
    """Create TestPioneer's template in the project directory, asking before replacing one.

    TestPioneer rewrites ``.TestPioneer/.TestPioneer.yml`` whenever the folder
    exists, so a second click used to wipe an edited template without a word.
    The project directory is the IDE's working directory, falling back to the
    process's, and a failure to write is reported rather than raised from the
    menu slot.
    """
    word = language_wrapper.language_word_dict
    title = word.get("test_pioneer_create_template_label")
    project = Path(getattr(ui_we_want_to_set, "working_dir", None) or Path.cwd())
    template = project / _TEMPLATE_DIR / f"{_TEMPLATE_DIR}.yml"
    if template.exists():
        reply = QMessageBox.question(
            ui_we_want_to_set, title,
            word.get("test_pioneer_template_exists").format(path=template),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
    try:
        create_template_dir(project_path=str(project), parent_name=_TEMPLATE_DIR)
    except Exception as error:  # noqa: BLE001 — TestPioneer raises its unexported ProjectException, a bare Exception subclass, for a write it could not make; it is logged and reported
        pybreeze_logger.error("TestPioneer template not created in %s: %r", project, error)
        QMessageBox.warning(
            ui_we_want_to_set, title,
            word.get("test_pioneer_template_failed").format(path=template, error=error))
        return
    QMessageBox.information(
        ui_we_want_to_set, title, word.get("test_pioneer_template_created").format(path=template))


def check_file(ui_we_want_to_set: PyBreezeMainWindow):
    """Ask for a TestPioneer YAML file and run it, or say why it cannot be run."""
    # getOpenFileName is static: the filter has to be passed to it, not set on
    # a dialog instance that is never shown. It returns (filename,
    # selected_filter); the tuple is always truthy, so check the filename -- an
    # empty one means the user cancelled.
    file_path = QFileDialog.getOpenFileName(
        ui_we_want_to_set, filter=_YAML_FILTER)[0]
    show_messagebox = False
    if file_path:
        if Path(file_path).is_file() and Path(file_path).suffix.lower() in _YAML_SUFFIXES:
            init_and_start_test_pioneer_process(ui_we_want_to_set, file_path)
        else:
            show_messagebox = True
    if show_messagebox:
        messagebox = QMessageBox(ui_we_want_to_set)
        messagebox.setWindowTitle(language_wrapper.language_word_dict.get("test_pioneer_not_choose_yaml"))
        messagebox.setText(language_wrapper.language_word_dict.get("test_pioneer_not_choose_yaml"))
        messagebox.exec()
