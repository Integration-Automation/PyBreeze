"""Collect HTTP headers the way a receiver collects repeated field lines.

The curl parser and the HAR importer both gather headers one at a time from a
source that may repeat a name — two ``-H`` flags, two entries in a HAR header
list — so the rule for combining them lives here once rather than in each.

Names are compared case-insensitively, as HTTP defines them, and the spelling
first seen is the one kept.
"""
from __future__ import annotations

# Header whose repeated values are joined with "; " rather than ", "
_COOKIE_HEADER = "cookie"
# How repeated header lines are combined into a single value
_HEADER_JOINER = ", "
_COOKIE_JOINER = "; "


def stored_header_name(headers: dict[str, str], name: str) -> str | None:
    """Return the spelling *name* is already stored under, or ``None``.

    :param headers: the headers collected so far
    :param name: the header name to look for, in any casing
    :return: the stored spelling, or ``None`` when the header is absent
    """
    lowered = name.lower()
    for stored in headers:
        if stored.lower() == lowered:
            return stored
    return None


def join_header_values(name: str, previous: str, value: str) -> str:
    """Combine a repeated header's values the way HTTP combines field lines.

    :param name: the header name (decides the separator)
    :param previous: the value collected so far
    :param value: the value to append
    :return: the combined value; an empty side is dropped rather than joined
    """
    if not previous:
        return value
    if not value:
        return previous
    joiner = _COOKIE_JOINER if name.lower() == _COOKIE_HEADER else _HEADER_JOINER
    return joiner.join((previous, value))


def add_header(headers: dict[str, str], name: str, value: str) -> None:
    """Record ``name: value`` in *headers*, combining repeats of the same name.

    :param headers: the headers to add to, modified in place
    :param name: the header name
    :param value: the header value
    """
    stored = stored_header_name(headers, name)
    if stored is None:
        headers[name] = value
        return
    headers[stored] = join_header_values(stored, headers[stored], value)


def set_default_header(headers: dict[str, str], name: str, value: str) -> None:
    """Set ``name: value`` only when no header of that name is present.

    :param headers: the headers to add to, modified in place
    :param name: the header name
    :param value: the value to use when the header is absent
    """
    if stored_header_name(headers, name) is None:
        headers[name] = value
