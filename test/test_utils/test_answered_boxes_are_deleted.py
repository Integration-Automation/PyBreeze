"""A message box or dialog made for the main window is deleted once answered.

Built with the main window as its parent and never deleted, each one stayed a
child of the window until the IDE exited, one more every time it was shown.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

import pybreeze  # noqa: E402

_BOX = re.compile(r"^(\s*)(\w+) = (?:QMessageBox|PRThinkerSettingDialog)\(", re.M)


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    from pybreeze.extend_multi_language.update_language_dict import update_language_dict

    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


def test_every_box_built_in_the_package_is_deleted_on_close():
    missing = []
    for path in Path(pybreeze.__file__).parent.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in _BOX.finditer(text):
            following = text[match.end():].split("\n", 3)[:3]
            wanted = f"{match.group(2)}.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)"
            if not any(wanted in line for line in following):
                missing.append(f"{path.name}: {match.group(2)}")
    assert not missing, f"Boxes kept after they are answered: {missing}"


def test_an_answered_about_box_is_gone(app):
    from PySide6.QtCore import QCoreApplication, QEvent, QTimer
    from PySide6.QtWidgets import QApplication, QWidget

    from pybreeze.pybreeze_ui.menu.plugin_menu import build_plugin_menu

    window = QWidget()

    def answer() -> None:
        QApplication.activeModalWidget().accept()

    QTimer.singleShot(50, answer)
    build_plugin_menu._make_about_callback(window, "Go", "1", "someone")()
    # Only the box's delete: others still posted belong to earlier tests
    for child in window.children():
        QCoreApplication.sendPostedEvents(child, QEvent.Type.DeferredDelete)

    assert window.children() == []
