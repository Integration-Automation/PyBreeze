"""Tests for query-string <-> JSON conversion."""
from __future__ import annotations

import json

import pytest

from pybreeze.utils.exception.exceptions import QueryConvertException
from pybreeze.utils.query_tools.query_convert import (
    json_to_query,
    query_to_dict,
    query_to_json,
)


class TestQueryToDict:
    def test_simple_pairs(self):
        assert query_to_dict("a=1&b=2") == {"a": "1", "b": "2"}

    def test_leading_question_mark_ignored(self):
        assert query_to_dict("?a=1") == {"a": "1"}

    def test_url_decoding(self):
        assert query_to_dict("q=a%20b%2Fc") == {"q": "a b/c"}

    def test_repeated_key_becomes_list(self):
        assert query_to_dict("a=1&a=2&a=3") == {"a": ["1", "2", "3"]}

    def test_blank_value_kept(self):
        assert query_to_dict("a=&b=2") == {"a": "", "b": "2"}

    def test_empty_string(self):
        assert query_to_dict("") == {}


class TestQueryToJson:
    def test_produces_json(self):
        result = query_to_json("a=1&b=2")
        assert json.loads(result) == {"a": "1", "b": "2"}

    def test_is_pretty_printed(self):
        assert "\n" in query_to_json("a=1&b=2")

    def test_repeated_key_is_array(self):
        assert json.loads(query_to_json("a=1&a=2")) == {"a": ["1", "2"]}


class TestJsonToQuery:
    def test_simple_object(self):
        assert json_to_query('{"a": "1", "b": "2"}') == "a=1&b=2"

    def test_url_encoding(self):
        assert json_to_query('{"q": "a b/c"}') == "q=a+b%2Fc"

    def test_list_becomes_repeated_key(self):
        assert json_to_query('{"a": [1, 2]}') == "a=1&a=2"

    def test_numbers_coerced_to_strings(self):
        assert json_to_query('{"n": 42}') == "n=42"

    def test_bool_coerced(self):
        assert json_to_query('{"ok": true}') == "ok=true"

    def test_invalid_json_raises(self):
        with pytest.raises(QueryConvertException):
            json_to_query("not json")

    def test_non_object_json_raises(self):
        with pytest.raises(QueryConvertException):
            json_to_query("[1, 2, 3]")


class TestRoundTrip:
    def test_query_json_query(self):
        assert json_to_query(query_to_json("a=1&b=2")) == "a=1&b=2"

    def test_repeated_key_round_trip(self):
        assert json_to_query(query_to_json("a=1&a=2")) == "a=1&a=2"
