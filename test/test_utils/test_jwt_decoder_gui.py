"""Tests for the JWT decoder tool widget."""
from __future__ import annotations

import base64
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict


def _make_jwt(header: dict, payload: dict, signature: str = "sig") -> str:
    def seg(obj):
        raw = json.dumps(obj).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return f"{seg(header)}.{seg(payload)}.{signature}"


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture()
def widget(app):
    from pybreeze.pybreeze_ui.tools_gui.jwt_decoder_gui import JwtDecoderGUI
    gui = JwtDecoderGUI()
    yield gui
    gui.close()
    gui.deleteLater()


class TestJwtDecoderGUI:
    def test_decode_shows_claims(self, widget):
        widget.input_edit.setPlainText(_make_jwt({"alg": "HS256"}, {"sub": "42"}))
        widget.decode()
        output = widget.output_edit.toPlainText()
        assert '"sub": "42"' in output
        assert '"alg": "HS256"' in output

    def test_decode_shows_timestamps(self, widget):
        widget.input_edit.setPlainText(_make_jwt({"alg": "HS256"}, {"exp": 1609459200}))
        widget.decode()
        assert "2021-01-01T00:00:00" in widget.output_edit.toPlainText()

    def test_invalid_token_shows_error(self, widget):
        widget.input_edit.setPlainText("only.two")
        widget.decode()
        assert '"sub"' not in widget.output_edit.toPlainText()
        assert widget.output_edit.toPlainText() != ""

    def test_empty_input_shows_hint(self, widget):
        widget.input_edit.setPlainText("   ")
        widget.decode()
        assert widget.output_edit.toPlainText() != ""

    def test_copy_output(self, app, widget):
        widget.input_edit.setPlainText(_make_jwt({"alg": "HS256"}, {"sub": "42"}))
        widget.decode()
        widget.actions.copy()
        assert '"sub": "42"' in QApplication.clipboard().text()

    def test_build_decoded_text_without_timestamps(self, app):
        from pybreeze.pybreeze_ui.tools_gui.jwt_decoder_gui import build_decoded_text
        from pybreeze.utils.jwt_tools.jwt_decoder import DecodedJwt
        text = build_decoded_text(DecodedJwt(header={"alg": "none"}, payload={"a": 1}, signature="s"))
        assert '"a": 1' in text

    def test_initial_token_is_decoded_on_open(self, app):
        from pybreeze.pybreeze_ui.tools_gui.jwt_decoder_gui import JwtDecoderGUI
        token = _make_jwt({"alg": "HS256"}, {"sub": "seed"})
        gui = JwtDecoderGUI(initial_token=token)
        assert '"sub": "seed"' in gui.output_edit.toPlainText()
        gui.close()
        gui.deleteLater()
