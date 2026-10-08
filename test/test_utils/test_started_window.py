"""The child-IDE harness itself: a modal dialog in the child is named, not waited on for two minutes."""
from __future__ import annotations

import time

import pytest

from test_utils.started_window import run_started_window

_A_MODAL_WARNING = """
from PySide6.QtWidgets import QMessageBox
QMessageBox.warning(window, "Stuck", "nobody answers")
result = {"went_on": True}
"""


def test_a_modal_dialog_in_the_ide_fails_the_test_and_names_itself(tmp_path):
    started = time.monotonic()

    with pytest.raises(AssertionError, match="Stuck: nobody answers"):
        run_started_window(tmp_path, _A_MODAL_WARNING)

    assert time.monotonic() - started < 100  # not the two-minute timeout
