"""Editing a JSON tree by path: every edit gives a new tree and leaves the old one whole."""
from __future__ import annotations

import copy

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pybreeze.utils.json_format.json_document import JsonNumber, parse_json
from pybreeze.utils.json_format.json_tree_edit import (
    JsonEditError,
    JsonKind,
    children,
    converted,
    delete,
    empty_value,
    insert,
    kind_of,
    move,
    position_of,
    rename,
    scalar_text,
    set_value,
    value_at,
    value_from_text,
)

SERVERS = '{"name": "demo", "servers": [{"port": 80}, {"port": 443}], "on": true, "note": null}'


@pytest.fixture
def tree():
    return parse_json(SERVERS)


# ----------------------------------------------------------------------
# What a value is
# ----------------------------------------------------------------------

@pytest.mark.parametrize(("value", "kind"), [
    ({}, JsonKind.OBJECT), ([], JsonKind.ARRAY), ("", JsonKind.STRING), (JsonNumber("0"), JsonKind.NUMBER),
    (True, JsonKind.BOOLEAN), (False, JsonKind.BOOLEAN), (None, JsonKind.NULL),
])
def test_every_value_has_a_kind(value, kind):
    assert kind_of(value) is kind


@pytest.mark.parametrize("kind", list(JsonKind))
def test_an_empty_value_is_of_the_kind_asked_for(kind):
    assert kind_of(empty_value(kind)) is kind


def test_an_empty_container_is_a_new_one_each_time():
    assert empty_value(JsonKind.OBJECT) is not empty_value(JsonKind.OBJECT)
    assert empty_value(JsonKind.ARRAY) is not empty_value(JsonKind.ARRAY)


def test_children_are_named_by_key_or_index(tree):
    assert [name for name, _value in children(tree)] == ["name", "servers", "on", "note"]
    assert [name for name, _value in children(tree["servers"])] == [0, 1]
    assert children("text") == [] and children(None) == []


# ----------------------------------------------------------------------
# Finding a value
# ----------------------------------------------------------------------

def test_the_empty_path_is_the_document(tree):
    assert value_at(tree, ()) is tree


def test_a_path_is_followed_through_objects_and_arrays(tree):
    assert value_at(tree, ("servers", 1, "port")) == JsonNumber("443")


@pytest.mark.parametrize("path", [
    ("missing",), ("servers", 2), ("servers", -1), ("servers", "0"), ("name", 0), (0,), ("servers", True),
])
def test_a_path_that_leads_nowhere_is_refused(tree, path):
    with pytest.raises(JsonEditError):
        value_at(tree, path)


# ----------------------------------------------------------------------
# Edits
# ----------------------------------------------------------------------

def test_a_value_is_replaced_and_the_old_tree_is_left_as_it_was(tree):
    before = copy.deepcopy(tree)

    edited = set_value(tree, ("servers", 0, "port"), JsonNumber("8080"))

    assert value_at(edited, ("servers", 0, "port")) == JsonNumber("8080")
    assert tree == before


def test_what_an_edit_does_not_touch_is_shared_not_copied(tree):
    edited = set_value(tree, ("servers", 0, "port"), JsonNumber("8080"))

    assert edited["servers"][1] is tree["servers"][1]
    assert edited["servers"] is not tree["servers"]


def test_the_document_itself_can_be_replaced(tree):
    assert set_value(tree, (), []) == []


def test_a_member_added_to_an_object_goes_last(tree):
    edited = insert(tree, (), "port", JsonNumber("1"))

    assert list(edited) == ["name", "servers", "on", "note", "port"]
    assert "port" not in tree


def test_a_member_whose_name_is_taken_is_refused_by_name(tree):
    with pytest.raises(JsonEditError, match="'name'"):
        insert(tree, (), "name", None)


@pytest.mark.parametrize(("index", "expected"), [(0, ["x", 80, 443]), (1, [80, "x", 443]), (2, [80, 443, "x"])])
def test_an_item_is_put_into_an_array_at_its_index(tree, index, expected):
    edited = insert(tree, ("servers",), index, "x")

    ports = [item if item == "x" else int(item["port"].text) for item in edited["servers"]]
    assert ports == expected


@pytest.mark.parametrize(("parent", "key"), [
    (("servers",), 3), (("servers",), -1), (("servers",), "name"), ((), 0), (("servers",), True), (("missing",), "a"),
])
def test_an_insert_with_no_place_to_go_is_refused(tree, parent, key):
    with pytest.raises(JsonEditError):
        insert(tree, parent, key, None)


def test_only_an_object_or_an_array_takes_a_value(tree):
    with pytest.raises(JsonEditError, match="object or an array"):
        insert(tree, ("name",), "a", None)


def test_a_member_is_deleted(tree):
    assert list(delete(tree, ("on",))) == ["name", "servers", "note"]


def test_an_item_is_deleted_and_those_after_it_move_up(tree):
    edited = delete(tree, ("servers", 0))

    assert edited["servers"] == [{"port": JsonNumber("443")}]
    assert len(tree["servers"]) == 2


@pytest.mark.parametrize("edit", [
    lambda tree: delete(tree, ()),
    lambda tree: rename(tree, (), "a"),
    lambda tree: move(tree, (), 0),
    lambda tree: position_of(tree, ()),
])
def test_the_document_itself_is_not_deleted_renamed_or_moved(tree, edit):
    with pytest.raises(JsonEditError, match="document itself"):
        edit(tree)


@pytest.mark.parametrize("edit", [
    lambda tree: delete(tree, ("missing",)),
    lambda tree: rename(tree, ("missing",), "a"),
    lambda tree: move(tree, ("servers", 5), 0),
    lambda tree: position_of(tree, ("missing",)),
])
def test_an_edit_of_what_is_not_there_is_refused(tree, edit):
    with pytest.raises(JsonEditError):
        edit(tree)


def test_a_renamed_member_stays_where_it_stood(tree):
    edited = rename(tree, ("servers",), "hosts")

    assert list(edited) == ["name", "hosts", "on", "note"]
    assert edited["hosts"] is tree["servers"]


def test_renaming_a_member_to_its_own_name_changes_nothing(tree):
    assert rename(tree, ("name",), "name") == tree


def test_a_member_is_not_renamed_to_a_name_that_is_taken(tree):
    with pytest.raises(JsonEditError, match="'on'"):
        rename(tree, ("name",), "on")


def test_an_item_of_an_array_has_no_name_to_change(tree):
    with pytest.raises(JsonEditError):
        rename(tree, ("servers", 0), "first")


def test_a_moved_item_has_a_new_index(tree):
    edited, path = move(tree, ("servers", 1), 0)

    assert path == ("servers", 0)
    assert [item["port"].text for item in edited["servers"]] == ["443", "80"]


def test_a_moved_member_keeps_its_name(tree):
    edited, path = move(tree, ("note",), 0)

    assert path == ("note",)
    assert list(edited) == ["note", "name", "servers", "on"]


@pytest.mark.parametrize(("position", "expected"), [(-5, ["on", "name", "servers", "note"]),
                                                    (99, ["name", "servers", "note", "on"])])
def test_a_position_outside_is_the_nearest_end(tree, position, expected):
    edited, _path = move(tree, ("on",), position)

    assert list(edited) == expected


def test_a_value_knows_where_it_stands(tree):
    assert position_of(tree, ("on",)) == 2
    assert position_of(tree, ("servers", 1)) == 1


def test_a_path_as_long_as_the_document_is_deep_is_followed_without_recursion():
    depth = 20000
    deep: list = []
    for _level in range(depth):
        deep = [deep]
    path = (0,) * depth

    edited = set_value(deep, path, "bottom")

    assert value_at(edited, path) == "bottom"
    assert value_at(deep, path) == []


# ----------------------------------------------------------------------
# A value typed into a cell
# ----------------------------------------------------------------------

@pytest.mark.parametrize(("value", "text"), [
    ("as it is ", "as it is "), (True, "true"), (False, "false"), (JsonNumber("-12.50"), "-12.50"), (None, "null"),
])
def test_a_value_is_shown_as_the_text_that_writes_it(value, text):
    assert scalar_text(value) == text


def test_a_string_is_taken_as_typed_spaces_and_all():
    assert value_from_text(JsonKind.STRING, "  12 ") == "  12 "


@pytest.mark.parametrize("text", ["12", "-0.5", "1e3", "1.0", " 7 "])
def test_a_number_is_kept_as_it_was_typed(text):
    assert value_from_text(JsonKind.NUMBER, text) == JsonNumber(text.strip())


@pytest.mark.parametrize("text", ["", "abc", "01", "1.", ".5", "0x10", "NaN", "Infinity", "1,000", "+1"])
def test_what_is_not_a_json_number_is_refused(text):
    with pytest.raises(JsonEditError, match="not a JSON number"):
        value_from_text(JsonKind.NUMBER, text)


@pytest.mark.parametrize(("text", "value"), [("true", True), ("False", False), (" TRUE ", True)])
def test_a_boolean_is_read_whatever_its_capitals(text, value):
    assert value_from_text(JsonKind.BOOLEAN, text) is value


@pytest.mark.parametrize("text", ["", "yes", "1", "truee"])
def test_what_is_not_a_boolean_is_refused(text):
    with pytest.raises(JsonEditError, match="true or false"):
        value_from_text(JsonKind.BOOLEAN, text)


@pytest.mark.parametrize("kind", [JsonKind.OBJECT, JsonKind.ARRAY, JsonKind.NULL])
def test_a_kind_that_is_not_typed_gives_its_empty_value(kind):
    assert value_from_text(kind, "anything") == empty_value(kind)


# ----------------------------------------------------------------------
# A value given another kind
# ----------------------------------------------------------------------

@pytest.mark.parametrize(("value", "kind", "expected"), [
    (JsonNumber("1.50"), JsonKind.STRING, "1.50"),
    (True, JsonKind.STRING, "true"),
    ("1.50", JsonKind.NUMBER, JsonNumber("1.50")),
    ("true", JsonKind.BOOLEAN, True),
    ("not a number", JsonKind.NUMBER, JsonNumber("0")),
    ("maybe", JsonKind.BOOLEAN, False),
    (JsonNumber("1"), JsonKind.BOOLEAN, False),
    (True, JsonKind.NUMBER, JsonNumber("0")),
    (None, JsonKind.STRING, ""),
    ({"a": 1}, JsonKind.ARRAY, []),
    ([1], JsonKind.STRING, ""),
    ("text", JsonKind.OBJECT, {}),
    ("text", JsonKind.NULL, None),
])
def test_a_value_says_the_same_in_its_new_kind_where_it_can(value, kind, expected):
    assert converted(value, kind) == expected
    assert kind_of(converted(value, kind)) is kind


def test_a_value_given_its_own_kind_is_the_same_value():
    members = {"a": "b"}

    assert converted(members, JsonKind.OBJECT) is members


# ----------------------------------------------------------------------
# Whatever the document
# ----------------------------------------------------------------------

_SCALARS = st.one_of(
    st.none(), st.booleans(), st.text(max_size=5),
    st.integers(min_value=-999, max_value=999).map(lambda number: JsonNumber(str(number))))
_TREES = st.recursive(
    _SCALARS,
    lambda inner: st.one_of(st.lists(inner, max_size=4), st.dictionaries(st.text(max_size=3), inner, max_size=4)),
    max_leaves=12)


def _paths(tree, path=()):
    """Every path in *tree*, the document's own first."""
    found = [path]
    for name, child in children(tree):
        found.extend(_paths(child, (*path, name)))
    return found


@given(tree=_TREES, data=st.data())
def test_an_edit_never_changes_the_tree_it_was_given(tree, data):
    before = copy.deepcopy(tree)
    path = data.draw(st.sampled_from(_paths(tree)))

    set_value(tree, path, "new")
    if path:
        delete(tree, path)
        move(tree, path, 0)
    if isinstance(value_at(tree, path), list):
        insert(tree, path, 0, "new")

    assert tree == before


@given(tree=_TREES, data=st.data())
def test_deleting_what_was_just_added_gives_the_tree_back(tree, data):
    containers = [path for path in _paths(tree) if isinstance(value_at(tree, path), (dict, list))]
    if not containers:
        return
    parent = data.draw(st.sampled_from(containers))
    holder = value_at(tree, parent)
    if isinstance(holder, list):
        key = data.draw(st.integers(min_value=0, max_value=len(holder)))
    else:
        key = data.draw(st.text(max_size=4).filter(lambda name: name not in holder))

    added = insert(tree, parent, key, "new")

    assert value_at(added, (*parent, key)) == "new"
    assert delete(added, (*parent, key)) == tree
    # An object's members are compared in order too: the new one went last
    assert [name for name, _value in children(delete(added, (*parent, key)))] == [
        name for name, _value in children(tree)]


@given(tree=_TREES, data=st.data())
def test_a_value_moved_and_moved_back_is_where_it_was(tree, data):
    places = [path for path in _paths(tree) if path]
    if not places:
        return
    path = data.draw(st.sampled_from(places))
    was_at = position_of(tree, path)
    beside = len(children(value_at(tree, path[:-1])))
    target = data.draw(st.integers(min_value=0, max_value=beside - 1))

    moved, new_path = move(tree, path, target)
    back, old_path = move(moved, new_path, was_at)

    assert position_of(moved, new_path) == target
    assert old_path == path
    assert back == tree
    assert [name for name, _value in children(value_at(back, path[:-1]))] == [
        name for name, _value in children(value_at(tree, path[:-1]))]


@given(tree=_TREES, data=st.data(), new_name=st.text(max_size=4))
def test_a_member_renamed_and_renamed_back_is_as_it_was(tree, data, new_name):
    members = [path for path in _paths(tree) if path and isinstance(path[-1], str)]
    if not members:
        return
    path = data.draw(st.sampled_from(members))
    holder = value_at(tree, path[:-1])
    if new_name in holder and new_name != path[-1]:
        with pytest.raises(JsonEditError):
            rename(tree, path, new_name)
        return

    renamed = rename(tree, path, new_name)
    back = rename(renamed, (*path[:-1], new_name), path[-1])

    assert position_of(renamed, (*path[:-1], new_name)) == position_of(tree, path)
    assert list(value_at(back, path[:-1])) == list(holder)
    assert back == tree
