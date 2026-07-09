from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qt_app():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        try:
            app = QApplication([])
        except Exception as exc:  # pragma: no cover - no usable Qt platform
            pytest.skip(f"Cannot start QApplication: {exc}")
    return app


class TestCodeWindowScrollbackCap:
    def test_block_count_is_capped(self, qt_app):
        from pybreeze.pybreeze_ui.show_code_window.code_window import (
            MAX_OUTPUT_BLOCKS,
            CodeWindow,
        )

        window = CodeWindow()
        assert window.code_result.document().maximumBlockCount() == MAX_OUTPUT_BLOCKS

    def test_old_lines_dropped_once_capped(self, qt_app):
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        window = CodeWindow()
        window.code_result.document().setMaximumBlockCount(50)
        cursor = window.code_result.textCursor()
        for i in range(500):
            cursor.insertText(f"line {i}")
            cursor.insertBlock()

        assert window.code_result.document().blockCount() <= 50
        text = window.code_result.toPlainText()
        assert "line 499" in text       # newest kept
        assert "line 0\n" not in text   # oldest dropped
