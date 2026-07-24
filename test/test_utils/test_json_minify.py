"""Tests for JSON minify (pretty-printing is covered by test_json_process)."""
from __future__ import annotations

import json

import pytest

from pybreeze.utils.exception.exceptions import ITEJsonException
from pybreeze.utils.json_format.json_process import minify_json


class TestMinifyJson:
    def test_removes_whitespace(self):
        assert minify_json('{ "a" : 1 , "b" : 2 }') == '{"a":1,"b":2}'

    def test_nested(self):
        assert minify_json('{"a": [1, 2, {"b": 3}]}') == '{"a":[1,2,{"b":3}]}'

    def test_round_trips_semantically(self):
        original = '{"x": [1, 2], "y": {"z": true}}'
        assert json.loads(minify_json(original)) == json.loads(original)

    def test_preserves_unicode(self):
        # ensure_ascii default keeps non-ASCII as escapes; content must round-trip.
        assert json.loads(minify_json('{"n": "測試"}')) == {"n": "測試"}

    def test_invalid_raises(self):
        with pytest.raises(ITEJsonException):
            minify_json("{not valid}")

    def test_empty_object(self):
        assert minify_json("{}") == "{}"
