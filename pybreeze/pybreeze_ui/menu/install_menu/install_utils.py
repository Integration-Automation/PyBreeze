from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from pybreeze.extend.process_executor.process_executor_utils import build_task_process

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow


def install_packages(packages: Sequence[str], ui_we_want_to_set: PyBreezeMainWindow) -> None:
    """Install *packages* with one ``pip install -U``, in a run window of its own.

    pip runs as ``python -m pip`` with the interpreter chosen in the IDE (and
    the same fallbacks as any run), from an argument list with no shell. The
    install used to go through JEditor's shell runner, which hands the command
    to ``cmd.exe``: a target can be a folder the user chose, and a folder name
    holding ``&`` or ``|`` split the command there. Several packages go to one
    pip, not one pip each -- those ran at the same time against the same
    environment.

    :param packages: what pip is asked to install (names, or a path with extras)
    :param ui_we_want_to_set: the main window
    """
    process = build_task_process(ui_we_want_to_set)
    process.start_module_process("pip", ["install", "-U", *packages])


def install_package(package_text: str, ui_we_want_to_set: PyBreezeMainWindow) -> None:
    """Install one package; see :func:`install_packages`."""
    install_packages([package_text], ui_we_want_to_set)
