"""Read a HAR export and turn each recorded request into a :class:`CurlRequest`.

"Copy as cURL" captures one request; **Save all as HAR** captures the whole
session. This module parses that export so the rest of PyBreeze can treat every
recorded call exactly like an imported curl command — same structure, same code
generators, same tools.

A HAR is JSON, so nothing beyond the standard library is needed, and nothing here
is ever executed or replayed.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from urllib.parse import urlparse

from pybreeze.utils.curl_import.curl_parser import CurlRequest, parse_query_pairs
from pybreeze.utils.exception.exception_tags import (
    empty_har_error,
    invalid_har_json_error,
    no_entries_in_har_error,
    not_a_har_document_error,
)
from pybreeze.utils.exception.exceptions import HarParseException
from pybreeze.utils.header_tools.header_merge import add_header, stored_header_name
from pybreeze.utils.logging.logger import pybreeze_logger

# Media type of a URL-encoded form body
_FORM_MEDIA_TYPE = "application/x-www-form-urlencoded"
# Media type prefix of a multipart form body
_MULTIPART_MEDIA_TYPE = "multipart/form-data"
# Header carrying the request body's media type
_CONTENT_TYPE_HEADER = "content-type"
# Header carrying the request's cookies
_COOKIE_HEADER = "cookie"

# Response media types that are page furniture rather than an API call
_STATIC_MEDIA_TYPES = (
    "text/css", "text/javascript", "image/", "font/", "video/", "audio/",
    "application/javascript", "application/x-javascript", "application/font",
)
# File extensions that mark a static asset regardless of the media type sent
_STATIC_EXTENSIONS = (
    ".css", ".js", ".mjs", ".map", ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".webp", ".avif", ".ico", ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".mp4", ".webm", ".mp3", ".wav",
)


@dataclass
class HarEntry:
    """One request recorded in a HAR export.

    :param request: the recorded request, in the same shape a curl command parses
        into, so every existing generator and tool accepts it
    :param status: the recorded response status, or ``None`` when absent
    :param response_media_type: the response's media type, or an empty string
    :param started: the recorded start time, as written in the export
    """

    request: CurlRequest
    status: int | None = None
    response_media_type: str = ""
    started: str = ""

    @property
    def path(self) -> str:
        """The request's path (with query), for display in a compact list."""
        parsed = urlparse(self.request.full_url)
        return f"{parsed.path or '/'}{'?' + parsed.query if parsed.query else ''}"

    @property
    def host(self) -> str:
        """The request's host, or an empty string when the URL has none."""
        return urlparse(self.request.url).hostname or ""

    def summary(self) -> str:
        """A one-line description: method, path, status and media type."""
        parts = [self.request.method, self.path]
        if self.status is not None:
            parts.append(str(self.status))
        if self.response_media_type:
            parts.append(self.response_media_type)
        return "  ".join(parts)


def _header_pairs(raw_headers: object) -> list[tuple[str, str]]:
    """Return the ``(name, value)`` pairs of a HAR header/query/cookie list.

    HTTP/2 pseudo-headers (``:method``, ``:authority``) are dropped: they are
    frame metadata, not headers a client sets, and passing them on would produce
    code that fails.
    """
    if not isinstance(raw_headers, list):
        return []
    pairs: list[tuple[str, str]] = []
    for item in raw_headers:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name or name.startswith(":"):
            continue
        pairs.append((name, str(item.get("value", ""))))
    return pairs


def _apply_headers(request: CurlRequest, raw_request: dict) -> None:
    """Collect the entry's headers, combining any repeated name."""
    for name, value in _header_pairs(raw_request.get("headers")):
        add_header(request.headers, name, value)


def _apply_cookies(request: CurlRequest, raw_request: dict) -> None:
    """Collect the entry's cookies, and drop the header that duplicates them.

    A HAR records cookies both as a structured list and inside the ``Cookie``
    header. Keeping both would send every cookie twice, so the structured list
    wins — it is the one the generated code can edit.
    """
    for name, value in _header_pairs(raw_request.get("cookies")):
        request.cookies[name] = value
    if not request.cookies:
        return
    stored = stored_header_name(request.headers, _COOKIE_HEADER)
    if stored is not None:
        del request.headers[stored]


def _apply_query(request: CurlRequest, raw_request: dict, query: str) -> None:
    """Collect the query parameters from the URL, then from ``queryString``.

    The URL is authoritative because it is what was actually sent; the recorded
    ``queryString`` list only fills in what the URL did not carry.
    """
    for key, value in parse_query_pairs(query.split("&")).items():
        request.params.setdefault(key, value)
    for name, value in _header_pairs(raw_request.get("queryString")):
        request.params.setdefault(name, value)


def _multipart_fields(params: list[tuple[str, str, str]]) -> list[str]:
    """Render multipart params in curl's ``-F`` syntax so form handling is shared."""
    return [
        f"{name}=@{file_name}" if file_name else f"{name}={value}"
        for name, value, file_name in params
    ]


def _post_params(raw_post: dict) -> list[tuple[str, str, str]]:
    """Return the ``(name, value, fileName)`` triples of a recorded form body."""
    raw_params = raw_post.get("params")
    if not isinstance(raw_params, list):
        return []
    triples: list[tuple[str, str, str]] = []
    for item in raw_params:
        if isinstance(item, dict) and item.get("name"):
            triples.append((
                str(item["name"]), str(item.get("value", "")), str(item.get("fileName", ""))))
    return triples


def _apply_body(request: CurlRequest, raw_request: dict) -> None:
    """Collect the recorded request body as data parts or form fields."""
    raw_post = raw_request.get("postData")
    if not isinstance(raw_post, dict):
        return
    media_type = str(raw_post.get("mimeType", "")).lower()
    params = _post_params(raw_post)
    if params and media_type.startswith(_MULTIPART_MEDIA_TYPE):
        request.form_fields.extend(_multipart_fields(params))
        return
    if params and _FORM_MEDIA_TYPE in media_type:
        request.data_parts.extend(f"{name}={value}" for name, value, _file in params)
        return
    text = raw_post.get("text")
    if text:
        request.data_parts.append(str(text))


def _entry_request(raw_request: dict) -> CurlRequest:
    """Build a :class:`CurlRequest` from a HAR entry's ``request`` object."""
    url = str(raw_request.get("url", ""))
    base, _separator, query = url.partition("?")
    request = CurlRequest(
        method=str(raw_request.get("method", "GET")).upper(), url=base)
    _apply_headers(request, raw_request)
    _apply_cookies(request, raw_request)
    _apply_query(request, raw_request, query)
    _apply_body(request, raw_request)
    return request


def _response_details(raw_response: object) -> tuple[int | None, str]:
    """Return the recorded ``(status, media type)`` of an entry's response."""
    if not isinstance(raw_response, dict):
        return None, ""
    status = raw_response.get("status")
    content = raw_response.get("content")
    media_type = ""
    if isinstance(content, dict):
        media_type = str(content.get("mimeType", "")).split(";")[0].strip()
    return (status if isinstance(status, int) and status > 0 else None), media_type


def _load_entries(text: str) -> list[dict]:
    """Return the raw entry list of a HAR document.

    :raises HarParseException: when the text is empty, is not JSON, or has no
        ``log.entries`` list
    """
    if not text.strip():
        pybreeze_logger.error(empty_har_error)
        raise HarParseException(empty_har_error)
    try:
        document = json.loads(text)
    except ValueError as error:
        pybreeze_logger.error(invalid_har_json_error)
        raise HarParseException(invalid_har_json_error) from error
    log = document.get("log") if isinstance(document, dict) else None
    entries = log.get("entries") if isinstance(log, dict) else None
    if not isinstance(entries, list):
        pybreeze_logger.error(not_a_har_document_error)
        raise HarParseException(not_a_har_document_error)
    return [entry for entry in entries if isinstance(entry, dict)]


def parse_har(text: str) -> list[HarEntry]:
    """Parse a HAR export into one entry per recorded request.

    :param text: the contents of a ``.har`` file
    :return: the recorded requests, in the order they were captured
    :raises HarParseException: when the text is not a HAR export, or records no
        request with a URL
    """
    entries: list[HarEntry] = []
    for raw_entry in _load_entries(text):
        raw_request = raw_entry.get("request")
        if not isinstance(raw_request, dict) or not raw_request.get("url"):
            continue
        status, media_type = _response_details(raw_entry.get("response"))
        entries.append(HarEntry(
            request=_entry_request(raw_request),
            status=status,
            response_media_type=media_type,
            started=str(raw_entry.get("startedDateTime", "")),
        ))
    if not entries:
        pybreeze_logger.error(no_entries_in_har_error)
        raise HarParseException(no_entries_in_har_error)
    return entries


def is_api_like(entry: HarEntry) -> bool:
    """Whether *entry* looks like an API call rather than a page asset.

    A recorded session is mostly stylesheets, images and fonts; those are not
    worth generating a test for. An entry is treated as an asset when its
    response media type or its path extension says so.

    :param entry: the recorded entry
    :return: ``True`` when the entry is worth generating code for
    """
    media_type = entry.response_media_type.lower()
    if media_type.startswith(_STATIC_MEDIA_TYPES):
        return False
    path = urlparse(entry.request.url).path.lower()
    return not path.endswith(_STATIC_EXTENSIONS)


def api_entries(entries: list[HarEntry]) -> list[HarEntry]:
    """Return only the entries that look like API calls.

    :param entries: the parsed entries
    :return: the subset worth generating code for
    """
    return [entry for entry in entries if is_api_like(entry)]


@dataclass
class HarSummary:
    """Counts describing what a parsed export contains.

    :param total: every recorded request
    :param api: those that look like API calls
    :param hosts: the distinct hosts contacted, in first-seen order
    """

    total: int = 0
    api: int = 0
    hosts: list[str] = field(default_factory=list)


def summarize(entries: list[HarEntry]) -> HarSummary:
    """Summarise a parsed export for display above the entry list.

    :param entries: the parsed entries
    :return: the counts and the hosts involved
    """
    hosts: list[str] = []
    for entry in entries:
        host = entry.host
        if host and host not in hosts:
            hosts.append(host)
    return HarSummary(total=len(entries), api=len(api_entries(entries)), hosts=hosts)
