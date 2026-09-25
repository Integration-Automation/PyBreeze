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

    def test_invalid_json_raises_ite_exception(self):
        # reformat_json must surface a single documented exception type, not a
        # raw json.JSONDecodeError leaking through.
        with pytest.raises(ITEJsonException):
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


class TestInputNestedTooDeep:
    """The json module recurses per level; deep nesting is a RecursionError, not a crash."""

    _DEEP = "[" * 100_000 + "]" * 100_000

    def test_reformat_reports_it_as_bad_json(self):
        from pybreeze.utils.exception.exceptions import ITEJsonException
        from pybreeze.utils.json_format.json_process import reformat_json

        with pytest.raises(ITEJsonException):
            reformat_json(self._DEEP)

    def test_minify_reports_it_as_bad_json(self):
        from pybreeze.utils.exception.exceptions import ITEJsonException
        from pybreeze.utils.json_format.json_process import minify_json

        with pytest.raises(ITEJsonException):
            minify_json(self._DEEP)


def test_an_integer_past_the_conversion_limit_comes_back_as_written():
    # Converted to int, it raised ValueError past Python's 4300-digit limit;
    # it is valid JSON, and the number is now kept as its own text
    from pybreeze.utils.json_format.json_process import minify_json

    digits = "9" * 5000
    assert minify_json('{"n": ' + digits + "}") == '{"n":' + digits + "}"
    assert digits in reformat_json('{"n": ' + digits + "}")


class TestTheDataIsNotChanged:
    """Format and Minify re-lay the JSON out; what it says stays the same."""

    @pytest.mark.parametrize("number", [
        "1e400", "12345678901234567890123.0", "0.10000000000000000555", "1.50", "2E3", "-0.0", "1e-400"])
    def test_a_number_is_written_as_it_was(self, number):
        from pybreeze.utils.json_format.json_process import minify_json

        # float() made 1e400 Infinity, which is not JSON, and rounded the rest
        assert minify_json(f"[{number}]") == f"[{number}]"
        assert f"    {number}\n" in reformat_json(f"[{number}]")

    def test_characters_are_written_as_they_were(self):
        from pybreeze.utils.json_format.json_process import minify_json

        assert minify_json('{"n": "中文"}') == '{"n":"中文"}'
        assert '"中文"' in reformat_json('{"n": "中文"}')

    def test_a_string_that_looks_like_a_placeholder_stays_a_string(self):
        from pybreeze.utils.json_format.json_process import minify_json

        assert minify_json('["\\u0000abc:0\\u0000", 5]') == '["\\u0000abc:0\\u0000",5]'

    def test_a_key_given_twice_is_reported_not_dropped(self):
        from pybreeze.utils.json_format.json_process import minify_json

        with pytest.raises(ITEJsonException) as raised:
            minify_json('{"a": 1, "a": 2}')
        assert "'a'" in str(raised.value)
        with pytest.raises(ITEJsonException):
            reformat_json('{"a": 1, "a": 2}')

    def test_the_same_key_in_two_objects_is_fine(self):
        from pybreeze.utils.json_format.json_process import minify_json

        assert minify_json('[{"a": 1}, {"a": 2}]') == '[{"a":1},{"a":2}]'

    @pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
    def test_nan_and_infinity_are_not_json(self, constant):
        from pybreeze.utils.json_format.json_process import minify_json

        with pytest.raises(ITEJsonException):
            minify_json(f"[{constant}]")


class TestLoneSurrogates:
    """Written out raw, the text view dropped them: an escaped lone surrogate came out as ""."""

    def test_reformat_keeps_the_escape(self):
        result = reformat_json(r'{"a": "\ud83d"}')

        assert r'"\ud83d"' in result
        assert json.loads(result) == {"a": "\ud83d"}

    def test_minify_keeps_the_escape_and_a_pair_stays_one_character(self):
        from pybreeze.utils.json_format.json_process import minify_json

        assert minify_json(r'{"a": "\ud83d", "b": "\ud83d\ude00"}') == '{"a":"\\ud83d","b":"\U0001f600"}'


class TestWhatCannotBeWrittenBack:
    def test_a_value_already_parsed_is_laid_out(self):
        assert reformat_json({"b": 1, "a": [1]}) == '{\n    "a": [\n        1\n    ],\n    "b": 1\n}'

    def test_a_value_json_cannot_hold_is_refused(self):
        with pytest.raises(ITEJsonException):
            reformat_json({1, 2})

    @pytest.mark.parametrize("operation", ["reformat_json", "minify_json"])
    def test_text_that_parses_but_is_too_deep_to_write_is_refused(self, operation, monkeypatch):
        # On Python 3.14 a list nested ~16,000 deep parses and then cannot be
        # written; the depth depends on the version, so the writer is made to fail
        from pybreeze.utils.json_format import json_process

        def too_deep(*_args, **_kwargs):
            raise RecursionError("maximum recursion depth exceeded")

        monkeypatch.setattr(json_process, "dumps", too_deep)

        with pytest.raises(ITEJsonException):
            getattr(json_process, operation)("[[1]]")


class TestPrettyJsonOrNone:
    """For text that may be anything (a response body, a token's segment): laid out, or None."""

    def test_laid_out_by_four_with_characters_and_numbers_as_written(self):
        from pybreeze.utils.json_format.json_process import pretty_json_or_none

        shown = pretty_json_or_none('{"名稱": 1e400, "b": [1]}')

        assert shown == '{\n    "名稱": 1e400,\n    "b": [\n        1\n    ]\n}'

    def test_the_keys_are_sorted_only_when_asked(self):
        from pybreeze.utils.json_format.json_process import pretty_json_or_none

        assert pretty_json_or_none('{"b": 1, "a": 2}', sort_keys=True) == '{\n    "a": 2,\n    "b": 1\n}'
        assert pretty_json_or_none('{"b": 1, "a": 2}') == '{\n    "b": 1,\n    "a": 2\n}'

    @pytest.mark.parametrize("text", [
        "not json",
        '{"a": 1, "a": 2}',          # a key repeated
        "NaN",
        "[" * 100_000 + "]" * 100_000,  # nested past the recursion limit
    ], ids=["text", "repeated key", "NaN", "too deep"])
    def test_what_is_not_json_it_accepts_is_none(self, text):
        from pybreeze.utils.json_format.json_process import pretty_json_or_none

        assert pretty_json_or_none(text) is None
