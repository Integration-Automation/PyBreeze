"""The main window shows PyBreeze's icon wherever the IDE is started from."""
from __future__ import annotations

from pathlib import Path

from test_utils.started_window import run_started_window

_ICON = """
result = {"has_icon": not window.windowIcon().isNull(),
          "sizes": [size.width() for size in window.windowIcon().availableSizes()]}
"""


def test_the_window_has_pybreezes_icon_whatever_the_working_folder(tmp_path):
    # It was read from pybreeze_icon.ico in the working folder, which a started
    # IDE (python -m pybreeze, an installed package) never has: the window had
    # no icon. The child here runs in an empty temporary folder.
    seen = run_started_window(tmp_path, _ICON)

    assert seen["has_icon"]
    assert seen["sizes"]


def test_the_icon_is_package_data():
    # Shipped inside the package, beside the module that loads it
    from pybreeze.pybreeze_ui.editor_main import main_ui

    icon = Path(main_ui.__file__).with_name("pybreeze_icon.ico")
    assert icon.is_file()
    assert icon.read_bytes()[:4] == b"\x00\x00\x01\x00"  # an .ico file's header
