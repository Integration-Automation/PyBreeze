"""The text boxes that hold code show it in the fixed-pitch font.

In the interface's proportional font, indentation and the columns of a diff did
not line up.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.fixed_pitch import fixed_pitch_font


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


def _diff():
    from pybreeze.pybreeze_ui.tools_gui.diff_gui import DiffGUI
    return DiffGUI(None)


def _curl():
    from pybreeze.pybreeze_ui.tools_gui.curl_import_gui import CurlImportGUI
    return CurlImportGUI(None)


def _har():
    from pybreeze.pybreeze_ui.tools_gui.har_import_gui import HarImportGUI
    return HarImportGUI(None)


def _json_format():
    from pybreeze.pybreeze_ui.tools_gui.json_format_gui import JsonFormatGUI
    return JsonFormatGUI(None)


def _ai_code_review():
    from pybreeze.pybreeze_ui.connect_gui.url.ai_code_review_gui import AICodeReviewClient
    return AICodeReviewClient()


CODE_BOXES = [
    (_diff, "left_edit"), (_diff, "right_edit"), (_diff, "output_edit"),
    (_curl, "input_edit"), (_curl, "output_edit"),
    (_har, "output_edit"),
    (_json_format, "input_edit"), (_json_format, "output_edit"),
    (_ai_code_review, "code_input"),
]


@pytest.mark.parametrize(("build", "box"), CODE_BOXES,
                         ids=[f"{build.__name__[1:]}.{box}" for build, box in CODE_BOXES])
def test_the_box_uses_the_fixed_pitch_font(app, build, box):
    widget = build()
    view = getattr(widget, box)
    family = fixed_pitch_font().family()

    assert view.font().family() == family
    # In the view's own sheet too: the theme's sheet overrides setFont
    assert family in view.styleSheet()
    widget.close()
