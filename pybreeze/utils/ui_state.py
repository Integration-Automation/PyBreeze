"""What the user last did with the IDE's own panels, kept from one run to the next.

A panel closed on purpose should stay closed. This is the one small file that
remembers such things (``~/.pybreeze/ui_state.json``); the editor's own
settings stay with JEditor.
"""
from __future__ import annotations

import json

from pybreeze.utils.app_dirs import pybreeze_data_dir, pybreeze_data_path
from pybreeze.utils.file_process.replace_file import replace_text
from pybreeze.utils.logging.logger import pybreeze_logger

_FILE_NAME = "ui_state.json"


def read_ui_state() -> dict:
    """Everything remembered, by name; nothing when the file is not there or cannot be read.

    Reading creates nothing: a first start leaves no file behind.
    """
    try:
        state = json.loads((pybreeze_data_path() / _FILE_NAME).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        # A damaged file costs what it remembered, not the start of the IDE
        pybreeze_logger.debug("ui_state.py could not be read: %r", error)
        return {}
    return state if isinstance(state, dict) else {}


def remember(name: str, value: object) -> None:
    """Keep *value* under *name* for the next run.

    A file that cannot be written is logged and nothing more: where a panel
    was is not worth a message box.

    :param name: what is remembered
    :param value: JSON-compatible
    """
    state = read_ui_state()
    state[name] = value
    try:
        replace_text(pybreeze_data_dir() / _FILE_NAME, json.dumps(state, indent=4, ensure_ascii=False) + "\n")
    except OSError as error:
        pybreeze_logger.error("ui_state.py could not be written: %r", error)
