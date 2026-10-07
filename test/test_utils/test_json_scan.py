"""Where things are in a JSON text, and what the cursor is in the middle of."""
from __future__ import annotations

import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pybreeze.utils.language_service.json_scan import (
    ARRAY,
    OBJECT,
    SCALAR,
    STRING,
    Frame,
    LineIndex,
    context_at,
    locate,
    tokens,
)
from pybreeze.utils.language_service.service_adapter import Position, Range

SCRIPT = '[\n  ["WR_to_url", {"url": "https://example.com"}],\n  ["WR_quit"]\n]\n'


# ----------------------------------------------------------------------
# Pieces
# ----------------------------------------------------------------------

def test_a_text_is_cut_into_its_pieces_without_the_space_between():
    assert [(token.kind, token.text) for token in tokens('{"a": [1, true]}')] == [
        ("punctuation", "{"), ("string", '"a"'), ("punctuation", ":"), ("punctuation", "["), ("scalar", "1"),
        ("punctuation", ","), ("scalar", "true"), ("punctuation", "]"), ("punctuation", "}")]


def test_each_piece_knows_where_it_is():
    text = '  ["ab"]'
    piece = tokens(text)[1]

    assert text[piece.start:piece.end] == '"ab"'


def test_a_string_that_is_not_closed_ends_at_its_line():
    pieces = tokens('["abc\n, "d"]')

    assert [(piece.kind, piece.text) for piece in pieces][1] == ("open_string", '"abc')
    assert pieces[-2].text == '"d"'


def test_an_escaped_quote_does_not_end_a_string():
    assert [token.text for token in tokens(r'["a\"b"]')] == ["[", r'"a\"b"', "]"]


# ----------------------------------------------------------------------
# Every value with its place
# ----------------------------------------------------------------------

def test_a_script_is_read_into_values_that_know_their_place():
    root = locate(SCRIPT)

    assert root.kind == ARRAY and len(root.items) == 2
    first = root.items[0]
    assert SCRIPT[first.start:first.end] == '["WR_to_url", {"url": "https://example.com"}]'
    name, arguments = first.items
    assert (name.kind, name.value, SCRIPT[name.start:name.end]) == (STRING, "WR_to_url", '"WR_to_url"')
    key, value = arguments.members[0]
    assert arguments.kind == OBJECT and key.value == "url" and value.value == "https://example.com"
    assert SCRIPT[key.start:key.end] == '"url"'


def test_scalars_keep_what_was_written():
    root = locate('[1.50, true, null]')

    assert [(item.kind, item.value) for item in root.items] == [(SCALAR, "1.50"), (SCALAR, "true"), (SCALAR, "null")]


def test_a_string_says_what_its_escapes_mean():
    assert locate(r'"a\nbé"').value == "a\nbé"


def test_a_value_holds_the_offsets_at_both_its_ends():
    name = locate('["ab"]').items[0]

    assert name.holds(1) and name.holds(5)
    assert not name.holds(0) and not name.holds(6)


@pytest.mark.parametrize(("text", "expected"), [
    ('[["WR_to', ["WR_to"]),
    ('[["WR_to_url", {"url": "x"}], ["WR_', ["WR_to_url", "WR_"]),
    ('{"webdriver_wrapper": [["WR_quit"]', ["WR_quit"]),
])
def test_a_script_being_typed_is_read_as_far_as_it_goes(text, expected):
    root = locate(text)
    actions = root.members[0][1] if root.kind == OBJECT else root

    assert [action.items[0].value for action in actions.items] == expected


@pytest.mark.parametrize("text", ["", "   \n", "]", "}}"])
def test_text_with_no_value_in_it_gives_none(text):
    assert locate(text) is None


def test_a_document_as_deep_as_it_likes_is_read_without_recursion():
    depth = 20000

    root = locate("[" * depth + "]" * depth)

    assert root.kind == ARRAY and (root.start, root.end) == (0, 2 * depth)


_JSON = st.recursive(
    st.one_of(st.none(), st.booleans(), st.integers(-99, 99), st.text(max_size=6)),
    lambda inner: st.one_of(st.lists(inner, max_size=3), st.dictionaries(st.text(max_size=3), inner, max_size=3)),
    max_leaves=10)


def _meaning(located):
    """What a located value means, as ``json.loads`` gives it."""
    if located.kind == ARRAY:
        return [_meaning(item) for item in located.items]
    if located.kind == OBJECT:
        return {key.value: _meaning(value) for key, value in located.members}
    return located.value if located.kind == STRING else json.loads(located.value)


@given(value=_JSON, indent=st.sampled_from([None, 0, 2]))
def test_whatever_the_json_every_value_is_found_where_it_is_written(value, indent):
    text = json.dumps(value, indent=indent, ensure_ascii=False)

    root = locate(text)

    assert _meaning(root) == value
    assert (root.start, root.end) == (0, len(text))
    assert json.loads(text[root.start:root.end]) == value


# ----------------------------------------------------------------------
# What the cursor is in the middle of
# ----------------------------------------------------------------------

def _context(marked: str):
    """The context at the ``|`` of *marked*."""
    offset = marked.index("|")
    return context_at(marked.replace("|", ""), offset)


def test_the_cursor_in_an_actions_name_is_in_a_string_first_in_a_list_in_a_list():
    context = _context('[["WR_to|')

    assert context.in_string and context.typed == "WR_to"
    assert context.frames == (Frame(ARRAY), Frame(ARRAY))
    assert context.start == 2


def test_later_actions_count_the_ones_before_them():
    context = _context('[["WR_quit"], ["WR_|')

    assert context.frames == (Frame(ARRAY, index=1), Frame(ARRAY))


def test_the_cursor_where_an_arguments_name_goes_knows_the_keyword_and_the_names_given():
    context = _context('[["WR_get_webdriver_manager", {"webdriver_name": "chrome", "|')

    assert context.in_string and context.typed == ""
    assert context.frames == (
        Frame(ARRAY), Frame(ARRAY, index=1, first="WR_get_webdriver_manager"),
        Frame(OBJECT, index=1, key=None, keys=("webdriver_name",)))


def test_the_cursor_in_an_arguments_value_is_under_its_key():
    context = _context('[["WR_to_url", {"url": "https://|')

    assert context.frames[-1] == Frame(OBJECT, key="url", keys=("url",))
    assert context.typed == "https://"


def test_under_a_frameworks_key_the_outermost_frame_names_it():
    context = _context('{"auto_control": [["AC_|')

    assert context.frames[0] == Frame(OBJECT, key="auto_control", keys=("auto_control",))


def test_outside_a_string_nothing_is_typed():
    context = _context('[[|')

    assert not context.in_string and context.typed == ""
    assert context.frames == (Frame(ARRAY), Frame(ARRAY))
    assert context.start == 2


def test_what_is_closed_before_the_cursor_is_no_longer_open():
    assert _context('[["WR_quit"], {"a": [1, 2]}, |').frames == (Frame(ARRAY, index=2),)


def test_text_after_the_cursor_is_not_read():
    assert _context('[["WR_|"], ["WR_quit"]]').frames == (Frame(ARRAY), Frame(ARRAY))


def test_a_string_left_open_on_an_earlier_line_is_not_the_one_being_typed():
    context = _context('[["WR_to_url\n, {"|')

    assert context.in_string and context.typed == ""
    assert context.frames[1].first == "WR_to_url"


@pytest.mark.parametrize("marked", ["|", "|[]", "]|", "}}|[", '"a|'])
def test_a_cursor_in_no_object_or_array_has_no_frames(marked):
    assert _context(marked).frames == ()


def test_a_cursor_before_the_text_is_at_its_start():
    assert context_at("[]", -5).frames == ()


@given(text=st.text(alphabet='[]{},:" \nab\\1', max_size=40), offset=st.integers(0, 40))
def test_any_text_can_be_read_at_any_cursor(text, offset):
    context = context_at(text, offset)

    assert all(frame.kind in (OBJECT, ARRAY) for frame in context.frames)
    assert locate(text) is None or locate(text).start >= 0


# ----------------------------------------------------------------------
# Offsets and positions
# ----------------------------------------------------------------------

def test_an_offset_is_a_line_and_a_character():
    index = LineIndex("ab\ncd\n")

    assert index.position(0) == Position(0, 0)
    assert index.position(4) == Position(1, 1)
    assert index.position(6) == Position(2, 0)
    assert index.span(3, 5) == Range(Position(1, 0), Position(1, 2))


@pytest.mark.parametrize("text", ["ab\r\ncd", "ab\rcd", "ab\ncd"])
def test_every_kind_of_line_break_ends_a_line(text):
    index = LineIndex(text)

    assert index.position(text.index("c")) == Position(1, 0)
    assert index.offset(Position(1, 1)) == text.index("d")


def test_a_character_outside_the_basic_plane_counts_as_two():
    text = '["\U0001F600x"]'
    index = LineIndex(text)

    assert index.position(text.index("x")) == Position(0, 4)
    assert index.offset(Position(0, 4)) == text.index("x")


@pytest.mark.parametrize(("position", "offset"), [
    (Position(-1, 0), 0), (Position(9, 0), 5), (Position(0, 99), 2), (Position(1, 99), 5),
])
def test_a_position_outside_the_text_is_its_nearest_end(position, offset):
    assert LineIndex("ab\ncd").offset(position) == offset


@given(text=st.text(alphabet="ab\n\r\U0001F600é", max_size=30), data=st.data())
def test_a_position_leads_back_to_its_offset(text, data):
    index = LineIndex(text)
    offset = data.draw(st.integers(0, len(text)))
    # Between the two characters of a \r\n there is no position of its own
    if 0 < offset < len(text) and text[offset - 1] == "\r" and text[offset] == "\n":
        return

    assert index.offset(index.position(offset)) == offset
