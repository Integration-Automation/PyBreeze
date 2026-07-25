"""Parse a URL into its parts and rebuild one from those parts.

A companion to the query-string and cURL tools: paste a URL to see its scheme,
host, port, path, query and fragment as an editable JSON object, tweak any part,
then turn it back into a URL. Pure logic — no Qt and no network access.
"""
from __future__ import annotations

import json
from urllib.parse import SplitResult, parse_qsl, urlencode, urlsplit, urlunsplit

from pybreeze.utils.exception.exception_tags import (
    invalid_json_for_url_error,
    invalid_url_components_error,
)
from pybreeze.utils.exception.exceptions import UrlConvertException
from pybreeze.utils.logging.logger import pybreeze_logger


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
        username/password when the URL carries credentials
    """
    split = urlsplit(url.strip())
    components: dict = {
        "scheme": split.scheme,
        "host": split.hostname or "",
        "port": _safe_port(split),
        "path": split.path,
        "query": dict(parse_qsl(split.query, keep_blank_values=True)),
        "fragment": split.fragment,
    }
    if split.username is not None:
        components["username"] = split.username
    if split.password is not None:
        components["password"] = split.password
    return components


def url_to_json(url: str) -> str:
    """Parse *url* and render its components as pretty-printed JSON.

    :param url: the URL to parse
    :return: a formatted JSON object of the URL's parts
    """
    return json.dumps(parse_url(url), indent=4, ensure_ascii=False)


def _build_netloc(components: dict, host: str) -> str:
    """Assemble the ``user:pass@host:port`` authority from *components*."""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"  # bracket an IPv6 literal so the port stays separable
    netloc = host
    port = components.get("port")
    if port is not None and port != "":
        netloc = f"{netloc}:{port}"
    username = components.get("username")
    if username is not None:
        password = components.get("password")
        credentials = username if password is None else f"{username}:{password}"
        netloc = f"{credentials}@{netloc}"
    return netloc


def _build_query(query: object) -> str:
    """Render the query component from a dict of pairs (or a raw string)."""
    if not query:
        return ""
    if isinstance(query, dict):
        return urlencode(query)
    return str(query)


def build_url(components: dict) -> str:
    """Rebuild a URL from a components dict (the inverse of :func:`parse_url`).

    Missing parts default to empty, so a partial object still yields a URL.

    :param components: URL parts as produced by :func:`parse_url`
    :return: the assembled URL
    """
    scheme = str(components.get("scheme", ""))
    host = str(components.get("host", ""))
    netloc = _build_netloc(components, host)
    path = str(components.get("path", ""))
    query = _build_query(components.get("query"))
    fragment = str(components.get("fragment", ""))
    return urlunsplit((scheme, netloc, path, query, fragment))


def json_to_url(json_text: str) -> str:
    """Build a URL from a JSON object of URL parts.

    :param json_text: a JSON object as produced by :func:`url_to_json`
    :return: the assembled URL
    :raises UrlConvertException: when the input is not valid JSON or not an object
    """
    try:
        components = json.loads(json_text)
    except ValueError as error:
        pybreeze_logger.error(invalid_json_for_url_error)
        raise UrlConvertException(invalid_json_for_url_error) from error
    if not isinstance(components, dict):
        pybreeze_logger.error(invalid_url_components_error)
        raise UrlConvertException(invalid_url_components_error)
    return build_url(components)
