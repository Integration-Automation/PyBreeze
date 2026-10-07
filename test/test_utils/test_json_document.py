"""The JSON document: one copy, a text and a tree, edited from either side."""
from __future__ import annotations

import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pybreeze.utils.exception.exceptions import ITEJsonException
from pybreeze.utils.json_format.json_document import (
    JsonDocument,
    JsonNumber,
    JsonProblem,
    SerializationOptions,
    StaleRevisionError,
    parse_json,
    serialize_json,
)
from pybreeze.utils.json_format.json_process import pretty_json_or_none

_ONE_LINE = SerializationOptions(indent=None)


class TestJsonNumber:
    @pytest.mark.parametrize("text", ["0", "-0", "12", "-12.50", "1e400", "1E+2", "0.1e-7", "12345678901234567890123"])
    def test_a_json_number_is_kept_as_written(self, text):
        assert JsonNumber(text).text == text

    @pytest.mark.parametrize("text", ["", "01", "+1", "1.", ".5", "0x10", "1e", "NaN", "Infinity", "1 ", "１"])
    def test_anything_else_is_refused(self, text):
        with pytest.raises(ValueError, match="not a JSON number"):
            JsonNumber(text)


class TestParse:
    def test_every_kind_of_value(self):
        tree = parse_json('{"s": "x", "n": 1.0, "t": true, "f": false, "z": null, "a": [1, {}], "o": {"k": []}}')

        assert tree == {
            "s": "x", "n": JsonNumber("1.0"), "t": True, "f": False, "z": None,
            "a": [JsonNumber("1"), {}], "o": {"k": []}}

    def test_an_object_keeps_its_members_in_order(self):
        assert list(parse_json('{"b": 1, "a": 2, "c": 3}')) == ["b", "a", "c"]

    def test_a_number_a_float_cannot_hold_keeps_its_text(self):
        assert parse_json("[1e400, 0.10000000000000000001]") == [
            JsonNumber("1e400"), JsonNumber("0.10000000000000000001")]

    def test_a_syntax_error_says_where(self):
        with pytest.raises(JsonProblem) as refused:
            parse_json('{\n  "a": 1,\n  "b" 2\n}')

        assert (refused.value.line, refused.value.column) == (3, 7)
        assert str(refused.value) == "can't parse JSON"

    def test_a_key_given_twice_is_named(self):
        with pytest.raises(JsonProblem, match="the key 'a' twice") as refused:
            parse_json('{"a": 1, "a": 2}')

        assert refused.value.line is None

    @pytest.mark.parametrize("text", ["[NaN]", "[Infinity]", "[-Infinity]", "", "   ", "[" * 100_000],
                             ids=["nan", "infinity", "minus-infinity", "empty", "blank", "too-deep"])
    def test_what_is_not_json_is_a_problem(self, text):
        with pytest.raises(JsonProblem):
            parse_json(text)

    def test_a_problem_is_a_json_exception(self):
        # What already catches the JSON tools' error catches this one
        assert issubclass(JsonProblem, ITEJsonException)


class TestSerialize:
    _TREE = {"b": JsonNumber("1.0"), "a": ["é", True, None]}

    def test_indented_by_four_keys_in_their_order(self):
        assert serialize_json(self._TREE) == (
            '{\n    "b": 1.0,\n    "a": [\n        "é",\n        true,\n        null\n    ]\n}')

    def test_on_one_line(self):
        assert serialize_json(self._TREE, _ONE_LINE) == '{"b": 1.0, "a": ["é", true, null]}'

    def test_with_another_indent(self):
        assert serialize_json({"a": []}, SerializationOptions(indent=2)) == '{\n  "a": []\n}'

    def test_ascii_only(self):
        assert serialize_json(["é"], SerializationOptions(indent=None, ensure_ascii=True)) == '["\\u00e9"]'

    def test_ending_with_a_line_break(self):
        assert serialize_json([], SerializationOptions(trailing_newline=True)) == "[]\n"

    @pytest.mark.parametrize("character", [" ", " ", "\x85", "﷐", "\ud83d"])
    def test_a_character_a_text_view_would_not_give_back_is_escaped(self, character):
        text = serialize_json([character], _ONE_LINE)

        assert text == f'["\\u{ord(character):04x}"]'
        assert parse_json(text) == [character]

    def test_a_string_that_looks_like_a_number_stays_a_string(self):
        assert serialize_json(["1.0", JsonNumber("1.0")], _ONE_LINE) == '["1.0", 1.0]'

    @pytest.mark.parametrize("tree", [[object()], [float("nan")], [{1, 2}]], ids=["an-object", "nan", "a-set"])
    def test_what_is_not_json_is_a_problem(self, tree):
        with pytest.raises(JsonProblem):
            serialize_json(tree)

    def test_a_tree_nested_past_the_writer_is_a_problem(self):
        tree: list = []
        for _level in range(100_000):
            tree = [tree]

        with pytest.raises(JsonProblem):
            serialize_json(tree, _ONE_LINE)


# JSON text as someone might type it: numbers in several spellings, any nesting
_number_texts = st.one_of(
    st.integers().map(str),
    st.floats(allow_nan=False, allow_infinity=False).map(repr),
    st.sampled_from(["1.0", "-0", "1e400", "0.10000000000000000001", "1E2", "12345678901234567890123"]))
_strings = st.text(max_size=6)


def _json_texts() -> st.SearchStrategy[str]:
    scalars = st.one_of(
        st.sampled_from(["true", "false", "null"]), _number_texts, _strings.map(json.dumps))
    return st.recursive(
        scalars,
        lambda inner: st.one_of(
            st.lists(inner, max_size=3).map(lambda items: "[" + ", ".join(items) + "]"),
            st.dictionaries(_strings, inner, max_size=3).map(
                lambda members: "{" + ", ".join(
                    f"{json.dumps(key)}: {value}" for key, value in members.items()) + "}")),
        max_leaves=8)


@given(text=_json_texts())
def test_a_tree_written_and_read_again_is_the_same_tree(text):
    tree = parse_json(text)

    assert parse_json(serialize_json(tree)) == tree
    assert parse_json(serialize_json(tree, _ONE_LINE)) == tree


@given(text=_json_texts())
def test_the_default_layout_is_the_json_tools_layout(text):
    # JSON Format, the Response Inspector and the JWT decoder lay JSON out this way
    assert serialize_json(parse_json(text)) == pretty_json_or_none(text)


class TestDocument:
    def test_a_new_document_holds_its_text_and_tree(self):
        document = JsonDocument('{"a": 1}')

        assert document.text == '{"a": 1}'
        assert document.tree == {"a": JsonNumber("1")}
        assert document.problem is None
        assert document.revision == 0

    def test_an_empty_document_is_not_json_yet(self):
        document = JsonDocument()

        assert document.text == ""
        assert document.tree is None
        assert isinstance(document.problem, JsonProblem)

    def test_text_that_is_not_json_is_kept_and_explained(self):
        document = JsonDocument('{"a": 1}')

        revision = document.set_text('{"a": 1, ', document.revision)

        assert revision == document.revision == 1
        assert document.text == '{"a": 1, '
        assert document.tree is None
        assert (document.problem.line, document.problem.column) == (1, 10)

    def test_text_that_parses_again_has_a_tree_again(self):
        document = JsonDocument("{")

        document.set_text("[null]", document.revision)

        assert document.tree == [None]
        assert document.problem is None

    def test_the_text_null_has_a_tree_of_none_and_no_problem(self):
        document = JsonDocument("null")

        assert document.tree is None
        assert document.problem is None

    def test_a_tree_edit_writes_the_text_with_the_documents_options(self):
        document = JsonDocument("{}", SerializationOptions(indent=2, trailing_newline=True))

        revision = document.set_tree({"a": [JsonNumber("2.50")]}, document.revision)

        assert revision == 1
        assert document.text == '{\n  "a": [\n    2.50\n  ]\n}\n'
        assert document.tree == {"a": [JsonNumber("2.50")]}
        assert document.options == SerializationOptions(indent=2, trailing_newline=True)

    def test_a_tree_edit_replaces_text_that_was_not_json(self):
        document = JsonDocument("{")

        document.set_tree([], document.revision)

        assert document.text == "[]"
        assert document.problem is None

    def test_the_tree_handed_in_stays_the_callers(self):
        document = JsonDocument("[]")
        mine = {"a": []}

        document.set_tree(mine, document.revision)
        mine["a"].append("changed afterwards")

        assert document.tree == {"a": []}

    def test_an_edit_against_an_older_revision_is_refused(self):
        document = JsonDocument("[]")
        seen = document.revision
        document.set_text("[1]", seen)

        with pytest.raises(StaleRevisionError) as refused:
            document.set_tree([JsonNumber("2")], seen)

        assert (refused.value.base, refused.value.current) == (0, 1)
        assert document.text == "[1]"
        assert document.revision == 1

    def test_a_text_edit_against_an_older_revision_is_refused_too(self):
        document = JsonDocument("[]")
        seen = document.revision
        document.set_tree([JsonNumber("1")], seen)

        with pytest.raises(StaleRevisionError):
            document.set_text("[2]", seen)

        assert document.tree == [JsonNumber("1")]

    def test_a_tree_that_is_not_json_leaves_the_document_as_it_was(self):
        document = JsonDocument("[1]")

        with pytest.raises(JsonProblem):
            document.set_tree([object()], document.revision)

        assert document.text == "[1]"
        assert document.tree == [JsonNumber("1")]
        assert document.revision == 0

    def test_text_through_the_tree_and_back_says_the_same(self):
        document = JsonDocument('{"n": 1.0, "s": "\\u2028"}')

        document.set_tree(document.tree, document.revision)

        assert parse_json(document.text) == {"n": JsonNumber("1.0"), "s": " "}
