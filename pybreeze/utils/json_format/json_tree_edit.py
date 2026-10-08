"""Editing a JSON tree: a value put in, taken out, renamed, moved or replaced.

A visual editor does not type JSON, it changes a tree: add a member here,
delete that item, move this one up. Each such change is a function here that
takes a tree and a place in it and gives back a new tree. The tree given is
never changed, so the one a document holds stays whole until the new one is
handed to it (``JsonDocument.set_tree``), and an edit that is refused has
changed nothing.

A place is a *path*: the keys and indexes to follow from the root, ``()`` being
the root itself and ``("servers", 0, "port")`` the port of the first server.

Pure logic: no widget, and nothing is read or written.
"""
from __future__ import annotations

from collections.abc import Callable
from enum import Enum

from pybreeze.utils.exception.exception_tags import (
    json_edit_key_exists_error,
    json_edit_no_such_place_error,
    json_edit_not_a_boolean_error,
    json_edit_not_a_container_error,
    json_edit_not_a_number_error,
    json_edit_root_error,
)
from pybreeze.utils.exception.exceptions import ITEJsonException
from pybreeze.utils.json_format.json_document import JsonNumber, JsonValue

# The keys and indexes that lead from the root to a value
JsonPath = tuple[str | int, ...]


class JsonKind(Enum):
    """What a value is."""

    OBJECT = "object"
    ARRAY = "array"
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    NULL = "null"


class JsonEditError(ITEJsonException):
    """An edit that cannot be made: the tree is as it was."""


def kind_of(value: JsonValue) -> JsonKind:
    """What *value* is."""
    if isinstance(value, dict):
        return JsonKind.OBJECT
    if isinstance(value, list):
        return JsonKind.ARRAY
    if isinstance(value, bool):
        return JsonKind.BOOLEAN
    if isinstance(value, str):
        return JsonKind.STRING
    return JsonKind.NULL if value is None else JsonKind.NUMBER


def empty_value(kind: JsonKind) -> JsonValue:
    """A new value of *kind*, holding nothing: ``{}``, ``[]``, ``""``, ``0``, ``false`` or ``null``."""
    made: dict[JsonKind, Callable[[], JsonValue]] = {
        JsonKind.OBJECT: dict, JsonKind.ARRAY: list, JsonKind.STRING: str,
        JsonKind.NUMBER: lambda: JsonNumber("0"), JsonKind.BOOLEAN: bool, JsonKind.NULL: lambda: None,
    }
    return made[kind]()


def children(value: JsonValue) -> list[tuple[str | int, JsonValue]]:
    """What *value* holds, each with its key or index, in order; nothing for a value that holds none."""
    if isinstance(value, dict):
        return list(value.items())
    if isinstance(value, list):
        return list(enumerate(value))
    return []


def _child(container: JsonValue, step: str | int) -> JsonValue:
    """The value *step* leads to in *container*.

    :raises JsonEditError: when it leads nowhere
    """
    # A bool is an int to Python and would index an array
    if isinstance(container, dict) and isinstance(step, str) and step in container:
        return container[step]
    if (isinstance(container, list) and isinstance(step, int) and not isinstance(step, bool)
            and 0 <= step < len(container)):
        return container[step]
    raise JsonEditError(json_edit_no_such_place_error)


def value_at(tree: JsonValue, path: JsonPath) -> JsonValue:
    """The value at *path* in *tree*.

    :raises JsonEditError: when *path* leads nowhere
    """
    value = tree
    for step in path:
        value = _child(value, step)
    return value


def _rebuilt(tree: JsonValue, path: JsonPath, change: Callable[[JsonValue], JsonValue]) -> JsonValue:
    """A new tree in which the value at *path* is ``change(that value)``.

    Every container on the way is copied and the rest is shared with *tree*,
    which is left as it was. Done without recursion: a path can be as long as
    the document is deep.
    """
    containers = []
    value = tree
    for step in path:
        containers.append(value)
        value = _child(value, step)
    value = change(value)
    for container, step in zip(reversed(containers), reversed(path)):
        copy = dict(container) if isinstance(container, dict) else list(container)
        copy[step] = value
        value = copy
    return value


def _own(path: JsonPath) -> tuple[JsonPath, str | int]:
    """*path* as the place that holds it and its own key or index.

    :raises JsonEditError: for the root, which nothing holds
    """
    if not path:
        raise JsonEditError(json_edit_root_error)
    return path[:-1], path[-1]


def set_value(tree: JsonValue, path: JsonPath, value: JsonValue) -> JsonValue:
    """*tree* with *value* at *path*, in place of what was there.

    :raises JsonEditError: when *path* leads nowhere
    """
    return _rebuilt(tree, path, lambda _old: value)


def insert(tree: JsonValue, parent: JsonPath, key: str | int, value: JsonValue) -> JsonValue:
    """*tree* with *value* put into the object or array at *parent*.

    :param key: for an object, the new member's name, which goes last; for an
        array, the index to put the item at (its length puts it last)
    :raises JsonEditError: when *parent* leads nowhere or holds no values, the
        object has a member of that name already, or the index is outside the array
    """
    def put(container: JsonValue) -> JsonValue:
        if isinstance(container, dict) and isinstance(key, str):
            if key in container:
                raise JsonEditError(json_edit_key_exists_error.format(key=key))
            return {**container, key: value}
        if isinstance(container, list) and isinstance(key, int) and not isinstance(key, bool):
            if not 0 <= key <= len(container):
                raise JsonEditError(json_edit_no_such_place_error)
            return [*container[:key], value, *container[key:]]
        raise JsonEditError(
            json_edit_not_a_container_error if not isinstance(container, (dict, list))
            else json_edit_no_such_place_error)

    return _rebuilt(tree, parent, put)


def delete(tree: JsonValue, path: JsonPath) -> JsonValue:
    """*tree* without the value at *path*.

    :raises JsonEditError: for the root, or when *path* leads nowhere
    """
    parent, own = _own(path)

    def drop(container: JsonValue) -> JsonValue:
        _child(container, own)
        if isinstance(container, dict):
            return {name: member for name, member in container.items() if name != own}
        return [item for index, item in enumerate(container) if index != own]

    return _rebuilt(tree, parent, drop)


def rename(tree: JsonValue, path: JsonPath, new_key: str) -> JsonValue:
    """*tree* with the object member at *path* called *new_key*, where it stood.

    :raises JsonEditError: for the root or an array's item (which has no name),
        when *path* leads nowhere, or when the object has a member of that name already
    """
    parent, own = _own(path)

    def call(container: JsonValue) -> JsonValue:
        _child(container, own)
        if not isinstance(container, dict):
            raise JsonEditError(json_edit_not_a_container_error)
        if new_key == own:
            return container
        if new_key in container:
            raise JsonEditError(json_edit_key_exists_error.format(key=new_key))
        return {(new_key if name == own else name): member for name, member in container.items()}

    return _rebuilt(tree, parent, call)


def move(tree: JsonValue, path: JsonPath, position: int) -> tuple[JsonValue, JsonPath]:
    """*tree* with the value at *path* at *position* among those beside it.

    :param position: where it goes, from 0; one outside the container is the nearest end
    :return: the new tree, and the path the value now has (an array's item
        changes its index; an object's member keeps its name)
    :raises JsonEditError: for the root, or when *path* leads nowhere
    """
    parent, own = _own(path)
    moved_to: list[str | int] = [own]

    def reorder(container: JsonValue) -> JsonValue:
        _child(container, own)
        entries = children(container)
        current = next(index for index, (name, _value) in enumerate(entries) if name == own)
        entry = entries.pop(current)
        target = max(0, min(position, len(entries)))
        entries.insert(target, entry)
        if isinstance(container, dict):
            return dict(entries)
        moved_to[0] = target
        return [item for _index, item in entries]

    rebuilt = _rebuilt(tree, parent, reorder)
    return rebuilt, (*parent, moved_to[0])


def position_of(tree: JsonValue, path: JsonPath) -> int:
    """Where the value at *path* stands among those beside it, from 0.

    :raises JsonEditError: for the root, or when *path* leads nowhere
    """
    parent, own = _own(path)
    names = [name for name, _value in children(value_at(tree, parent))]
    if own not in names:
        raise JsonEditError(json_edit_no_such_place_error)
    return names.index(own)

# How a boolean is written, and what each spelling means
_BOOLEANS = {"true": True, "false": False}


def scalar_text(value: JsonValue) -> str:
    """A value that holds no others as the text a cell shows and takes back: a string as it is, the rest as JSON."""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, JsonNumber):
        return value.text
    return "null"


def value_from_text(kind: JsonKind, text: str) -> JsonValue:
    """The value of *kind* that *text* writes, as typed into a cell.

    A string is taken as it is, spaces and all. A number and a boolean are
    read without the spaces around them. An object, an array and null are not
    typed: whatever *text* is, the answer is the empty value of that kind.

    :raises JsonEditError: when *text* is not a number or a boolean of JSON's
    """
    if kind is JsonKind.STRING:
        return text
    written = text.strip()
    if kind is JsonKind.NUMBER:
        try:
            return JsonNumber(written)
        except ValueError:
            raise JsonEditError(json_edit_not_a_number_error.format(text=text)) from None
    if kind is JsonKind.BOOLEAN and written.lower() in _BOOLEANS:
        return _BOOLEANS[written.lower()]
    if kind is JsonKind.BOOLEAN:
        raise JsonEditError(json_edit_not_a_boolean_error.format(text=text))
    return empty_value(kind)


def converted(value: JsonValue, kind: JsonKind) -> JsonValue:
    """*value* as a value of *kind*: the same thing said another way where there is one, else an empty one.

    A number or a boolean becomes the string that writes it, and a string
    that writes a number or a boolean becomes it. Anything else has nothing
    in common with the new kind and starts empty (:func:`empty_value`).
    """
    if kind_of(value) is kind:
        return value
    if isinstance(value, (dict, list)) or value is None:
        return empty_value(kind)
    if kind is JsonKind.STRING:
        return scalar_text(value)
    if isinstance(value, str) and kind in (JsonKind.NUMBER, JsonKind.BOOLEAN):
        try:
            return value_from_text(kind, value)
        except JsonEditError:
            return empty_value(kind)
    return empty_value(kind)
