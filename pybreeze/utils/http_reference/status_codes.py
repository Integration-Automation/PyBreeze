"""A searchable reference of HTTP status codes.

Debugging an API test constantly raises "what does 409 mean again?". This module
answers that from the standard library's ``http.HTTPStatus`` table, in the words
Python 3.14 gives on every version (``_CURRENT_WORDS``).
"""
from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus

# The class of a status is its first digit (1xx..5xx).
_CLASS_DIVISOR = 100

# ``HTTPStatus`` words a status as the Python it runs on does: RFC 9110 renamed
# four in 2022, which Python took in 3.13, and 3.14 described fourteen it had
# left blank. The reference read differently from one version to the next
# ("Unprocessable Entity" with no description before 3.13). These are 3.14's
# words, for the statuses whose words changed since 3.10.
_CURRENT_WORDS: dict[int, tuple[str, str]] = {
    102: ("Processing", "Server is processing the request"),
    103: ("Early Hints", "Headers sent to prepare for the response"),
    207: ("Multi-Status", "Response contains multiple statuses in the body"),
    208: ("Already Reported", "Operation has already been reported"),
    226: ("IM Used", "Request completed using instance manipulations"),
    413: ("Content Too Large", "Content is too large"),
    414: ("URI Too Long", "URI is too long"),
    416: ("Range Not Satisfiable", "Cannot satisfy request range"),
    418: ("I'm a Teapot", "Server refuses to brew coffee because it is a teapot"),
    422: ("Unprocessable Content", "Server is not able to process the contained instructions"),
    423: ("Locked", "Resource of a method is locked"),
    424: ("Failed Dependency", "Dependent action of the request failed"),
    425: ("Too Early", "Server refuses to process a request that might be replayed"),
    426: ("Upgrade Required", "Server refuses to perform the request using the current protocol"),
    506: ("Variant Also Negotiates", "Server has an internal configuration error"),
    507: ("Insufficient Storage", "Server is not able to store the representation"),
    508: ("Loop Detected", "Server encountered an infinite loop while processing a request"),
    510: ("Not Extended", "Request does not meet the resource access policy"),
}
# The names RFC 9110 replaced, which a search still finds its status by
_FORMER_PHRASES: dict[int, str] = {
    413: "Request Entity Too Large",
    414: "Request-URI Too Long",
    416: "Requested Range Not Satisfiable",
    422: "Unprocessable Entity",
}


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
    """Convert an ``HTTPStatus`` member into a :class:`StatusInfo`, in 3.14's words."""
    phrase, description = _CURRENT_WORDS.get(int(status), (status.phrase, status.description))
    return StatusInfo(
        code=int(status),
        phrase=phrase,
        description=description,
        category=_category_for(int(status)),
    )


def all_statuses() -> list[StatusInfo]:
    """Return every known status, ordered by code."""
    return [_to_info(status) for status in sorted(HTTPStatus, key=int)]


def status_of(code: int, phrase: str = "") -> StatusInfo:
    """The status for *code*: the registered one, else one built from its class.

    A server may send a code nobody registered (``299``, ``599``); what it
    means is still its class, and *phrase* -- the reason phrase from its
    status line -- is what it called it.

    :param code: the numeric status code
    :param phrase: the reason phrase the response gave, if any
    """
    return lookup(code) or StatusInfo(code=code, phrase=phrase, description="", category=_category_for(code))


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
    starts with the query digits, or the query text appears in its phrase, its
    description or the name RFC 9110 replaced (case-insensitive).

    :param query: the search text (digits or words)
    :return: the matching statuses, ordered by code
    """
    stripped = query.strip().lower()
    if not stripped:
        return all_statuses()
    matches: list[StatusInfo] = []
    for info in all_statuses():
        haystack = f"{info.phrase} {info.description} {_FORMER_PHRASES.get(info.code, '')}".lower()
        if str(info.code).startswith(stripped) or stripped in haystack:
            matches.append(info)
    return matches
