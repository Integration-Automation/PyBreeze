from __future__ import annotations

import pytest

from pybreeze.pybreeze_ui.diagram_editor.diagram_net_utils import (
    _is_text_content_type,
    _parse_content_length,
)


class TestIsTextContentType:
    @pytest.mark.parametrize("content_type", [
        "text/html",
        "text/html; charset=utf-8",
        "text/plain",
        "TEXT/HTML",
    ])
    def test_text_types_rejected(self, content_type):
        assert _is_text_content_type(content_type) is True

    @pytest.mark.parametrize("content_type", [
        "image/png",
        "image/jpeg",
        "application/octet-stream",
        "",
    ])
    def test_non_text_types_allowed(self, content_type):
        assert _is_text_content_type(content_type) is False


class TestParseContentLength:
    @pytest.mark.parametrize("raw,expected", [
        ("0", 0),
        ("1024", 1024),
        ("20971520", 20 * 1024 * 1024),
    ])
    def test_valid_values(self, raw, expected):
        assert _parse_content_length(raw) == expected

    @pytest.mark.parametrize("raw", [
        None,          # header absent
        "abc",         # non-numeric
        "123abc",      # trailing junk
        "",            # empty
        "-5",          # negative
        "12.5",        # float-like
    ])
    def test_absent_or_malformed_returns_none(self, raw):
        assert _parse_content_length(raw) is None
