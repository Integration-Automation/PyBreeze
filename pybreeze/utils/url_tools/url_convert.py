"""Parse a URL into its parts and rebuild one from those parts.

A companion to the query-string and cURL tools: paste a URL to see its scheme,
host, port, path, query and fragment as an editable JSON object, tweak any part,
then turn it back into a URL. Pure logic — no Qt and no network access.
"""
from __future__ import annotations

import json
from urllib.parse import SplitResult, urlsplit, urlunsplit

from pybreeze.utils.exception.exception_tags import (
    invalid_json_for_url_error,
    invalid_url_components_error,
    unreadable_url_error,
    url_port_out_of_range_error,
)
from pybreeze.utils.exception.exceptions import QueryConvertException, UrlConvertException
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.query_tools.query_convert import (
    coerce_scalar, encode_pairs, load_json_verbatim, query_round_trips, query_to_dict,
)

_MAX_PORT = 65535


def _safe_port(split: SplitResult) -> int | None:
    """Return the URL's port, or ``None`` when it is absent or out of range."""
    try:
        return split.port
    except ValueError:
        return None


def parse_url(url: str) -> dict:
    """Split *url* into its components as a JSON-friendly dict.

    :param url: the URL to parse (leading/trailing whitespace is ignored)
    :return: a dict with scheme, host, port, path, query and fragment, plus
        username/password when the URL carries credentials; the query is a dict
        of its values, or its text when that would not rebuild it as written
    """
    split = urlsplit(url.strip())
    components: dict = {
        "scheme": split.scheme,
        "host": split.hostname or "",
        "port": _safe_port(split),
        "path": split.path,
        "query": _query_component(split.query),
        "fragment": split.fragment,
    }
    if split.username is not None:
        components["username"] = split.username
    if split.password is not None:
        components["password"] = split.password
    return components


def _query_component(query: str) -> dict | str:
    """*query* as a dict of its values, or as its text when the dict would not rebuild it.

    A repeated key keeps every value, as a list, like the query tool. A query
    that decoding and encoding again would change stays the text it was:
    rebuilt, %zz became %25zz and a bare key gained "=". So does one whose
    repeated key comes back in another order: the dict groups ``a=1&b=2&a=3``
    into ``a=1&a=3&b=2``, which a signed URL does not survive.
    """
    if not query_round_trips(query):
        return query
    as_dict = query_to_dict(query)
    return as_dict if _build_query(as_dict) == query else query


def url_to_json(url: str) -> str:
    """Parse *url* and render its components as pretty-printed JSON.

    :param url: the URL to parse
    :return: a formatted JSON object of the URL's parts
    :raises UrlConvertException: when *url* cannot be split into parts at all
        (``http://[::1`` -- an unclosed IPv6 bracket -- is one), or names a
        port outside 0-65535
    """
    try:
        components = parse_url(url)
    except ValueError as error:
        pybreeze_logger.error(unreadable_url_error)
        raise UrlConvertException(unreadable_url_error) from error
    if components["port"] is None and _has_port_text(url):
        # parse_url leaves such a port out; shown that way, the URL built back
        # from these parts would silently lose it.
        pybreeze_logger.error(url_port_out_of_range_error)
        raise UrlConvertException(url_port_out_of_range_error)
    return json.dumps(components, indent=4, ensure_ascii=False)


def _has_port_text(url: str) -> bool:
    """Whether *url*'s authority names a port at all, readable or not.

    ``http://example.com:/`` names none: RFC 3986 allows the colon with an
    empty port, and it was refused as a port out of range.
    """
    host_and_port = urlsplit(url.strip()).netloc.rpartition("@")[2]
    return bool(host_and_port.rpartition("]")[2].partition(":")[2])


def _build_netloc(components: dict, host: str) -> str:
    """Assemble the ``user:pass@host:port`` authority from *components*."""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"  # bracket an IPv6 literal so the port stays separable
    netloc = host
    port = _port_text(components.get("port"))
    if port:
        netloc = f"{netloc}:{port}"
    username = components.get("username")
    if username is not None:
        password = components.get("password")
        credentials = str(username) if password is None else f"{username}:{password}"
        netloc = f"{credentials}@{netloc}"
    return netloc


def _port_text(port: object) -> str:
    """*port* as the URL writes it: empty for none, else a whole number from 0 to 65535.

    :raises UrlConvertException: for anything else; ``"abc"`` went into the URL as ``h:abc``
    """
    if port is None or port == "":
        return ""
    # ASCII digits only: "²".isdigit() holds, and int() then raised a
    # ValueError past the builder's error handling; "٣" became port 3
    if isinstance(port, str) and port.strip().isascii() and port.strip().isdigit():
        port = int(port)
    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= _MAX_PORT:
        pybreeze_logger.error(url_port_out_of_range_error)
        raise UrlConvertException(url_port_out_of_range_error)
    return str(port)


def _build_query(query: object) -> str:
    """Render the query component from a dict of pairs (or a raw string)."""
    if not query:
        return ""
    if isinstance(query, dict):
        # A list value is a key that repeats, one pair per value. Each value as
        # the query tool writes it: null is empty, not "None", and an object
        # has no query form.
        pairs: list[tuple[str, str]] = []
        try:
            for key, value in query.items():
                values = value if isinstance(value, list) else [value]
                pairs.extend((str(key), coerce_scalar(item)) for item in values)
            return encode_pairs(pairs)
        except QueryConvertException as error:
            raise UrlConvertException(str(error)) from error
    return str(query)


def build_url(components: dict) -> str:
    """Rebuild a URL from a components dict (the inverse of :func:`parse_url`).

    Missing parts default to empty, so a partial object still yields a URL.

    :param components: URL parts as produced by :func:`parse_url`
    :return: the assembled URL
    :raises UrlConvertException: for a port that is not a whole number from 0
        to 65535, or a query value that is an object or a list inside a list
    """
    scheme = _part(components, "scheme")
    host = _part(components, "host")
    netloc = _build_netloc(components, host)
    path = _part(components, "path")
    query = _build_query(components.get("query"))
    fragment = _part(components, "fragment")
    return urlunsplit((scheme, netloc, path, query, fragment))


def _part(components: dict, name: str) -> str:
    """The URL part *name* as text: a missing or null part is empty, not ``None``."""
    value = components.get(name)
    return "" if value is None else str(value)


def json_to_url(json_text: str) -> str:
    """Build a URL from a JSON object of URL parts.

    :param json_text: a JSON object as produced by :func:`url_to_json`
    :return: the assembled URL
    :raises UrlConvertException: when the input is not valid JSON or not an
        object, or holds a part :func:`build_url` refuses
    """
    try:
        # Numbers as written: a query value 1E3 went into the URL as 1000.0
        components = load_json_verbatim(json_text)
    # RecursionError: JSON nested deeper than the parser goes, which escaped
    # the tab's slot
    except (ValueError, RecursionError) as error:
        pybreeze_logger.error(invalid_json_for_url_error)
        raise UrlConvertException(invalid_json_for_url_error) from error
    if not isinstance(components, dict):
        pybreeze_logger.error(invalid_url_components_error)
        raise UrlConvertException(invalid_url_components_error)
    return build_url(components)
