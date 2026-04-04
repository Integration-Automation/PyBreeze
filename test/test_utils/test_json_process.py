import json

import pytest

from pybreeze.utils.json_format.json_process import reformat_json
from pybreeze.utils.exception.exceptions import ITEJsonException


class TestReformatJson:
    def test_valid_json_string(self):
        result = reformat_json('{"b": 2, "a": 1}')
        parsed = json.loads(result)
        assert parsed == {"a": 1, "b": 2}

    def test_sorted_keys(self):
        result = reformat_json('{"z": 1, "a": 2, "m": 3}')
        lines = result.strip().split("\n")
        # Keys should be sorted: a, m, z
        assert '"a"' in lines[1]
        assert '"m"' in lines[2]
        assert '"z"' in lines[3]

    def test_indentation(self):
        result = reformat_json('{"key": "value"}')
        assert "    " in result  # 4-space indent

    def test_nested_json(self):
        input_json = '{"outer": {"inner": "value"}}'
        result = reformat_json(input_json)
        parsed = json.loads(result)
        assert parsed["outer"]["inner"] == "value"

    def test_json_array(self):
        result = reformat_json('[1, 2, 3]')
        parsed = json.loads(result)
        assert parsed == [1, 2, 3]

    def test_invalid_json_raises_error(self):
        with pytest.raises((json.JSONDecodeError, ITEJsonException)):
            reformat_json("not valid json {{{")

    def test_empty_object(self):
        result = reformat_json("{}")
        assert json.loads(result) == {}

    def test_empty_array(self):
        result = reformat_json("[]")
        assert json.loads(result) == []

    def test_json_with_special_characters(self):
        result = reformat_json('{"key": "value with \\"quotes\\""}')
        parsed = json.loads(result)
        assert "quotes" in parsed["key"]

    def test_json_with_unicode(self):
        result = reformat_json('{"key": "中文"}')
        parsed = json.loads(result)
        assert parsed["key"] == "中文"
