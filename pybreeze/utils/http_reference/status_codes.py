"""A searchable reference of HTTP status codes.

Debugging an API test constantly raises "what does 409 mean again?". This module
answers that from the standard library's ``http.HTTPStatus`` table, so the list
stays correct and maintained without a hand-written mapping.
"""
from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus

# The class of a status is its first digit (1xx..5xx).
_CLASS_DIVISOR = 100


@dataclass(frozen=True)
class StatusInfo:
    """One HTTP status code.

    :param code: the numeric status code (e.g. ``404``)
    :param phrase: the reason phrase (e.g. ``Not Found``)
    :param description: a short description of the status
    :param category: the status class label (e.g. ``Client Error``)
    """

    code: int
    phrase: str
    description: str
    category: str


_CATEGORY_BY_CLASS: dict[int, str] = {
    1: "Informational",
    2: "Success",
    3: "Redirection",
    4: "Client Error",
    5: "Server Error",
}


def _category_for(code: int) -> str:
    """Return the human label for a status code's class."""
    return _CATEGORY_BY_CLASS.get(code // _CLASS_DIVISOR, "Unknown")


def _to_info(status: HTTPStatus) -> StatusInfo:
    """Convert an ``HTTPStatus`` member into a :class:`StatusInfo`."""
    return StatusInfo(
        code=int(status),
        phrase=status.phrase,
        description=status.description,
        category=_category_for(int(status)),
    )


def all_statuses() -> list[StatusInfo]:
    """Return every known status, ordered by code."""
    return [_to_info(status) for status in sorted(HTTPStatus, key=int)]


def lookup(code: int) -> StatusInfo | None:
    """Return the status for an exact *code*, or ``None`` if unknown.

    :param code: the numeric status code
    :return: the matching status, or ``None``
    """
    try:
        return _to_info(HTTPStatus(code))
    except ValueError:
        return None


def search(query: str) -> list[StatusInfo]:
    """Search statuses by code prefix or phrase/description substring.

    An empty query returns every status. Otherwise a status matches when its code
    starts with the query digits, or the query text appears in its phrase or
    description (case-insensitive).

    :param query: the search text (digits or words)
    :return: the matching statuses, ordered by code
    """
    stripped = query.strip().lower()
    if not stripped:
        return all_statuses()
    matches: list[StatusInfo] = []
    for info in all_statuses():
        haystack = f"{info.phrase} {info.description}".lower()
        if str(info.code).startswith(stripped) or stripped in haystack:
            matches.append(info)
    return matches
