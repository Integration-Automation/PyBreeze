"""Take secrets out of what is logged and reported about an MCP call.

A tool's arguments and a server's output go into the log and into the
execution report, and both outlive the session and get shared. Two things are
taken out before they get there:

- the value of anything named like a secret (``token``, ``password``,
  ``api_key``, ``Authorization``...), whatever the value is;
- every occurrence of a value the profile gave the server as an environment
  variable, wherever it turns up: a server that prints its own token in an
  error message has printed it into the report otherwise.

What the user is shown before a call (its real arguments, to confirm) is not
redacted: they typed them.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

REDACTED = "***"

# A key is a secret's when it holds one of these, whatever is around it:
# apiKey, X-Api-Key, access_token, client-secret, DB_PASSWORD
_SECRET_KEY = re.compile(
    r"pass(word|wd|phrase)?|secret|token|api[-_]?key|authori[sz]ation|credential|cookie|private[-_]?key|session[-_]?id",
    re.IGNORECASE)
# A value shorter than this is not searched for in text: "1" or "true" as an
# environment variable would blank half of every report
_SHORTEST_SECRET = 6
# Nesting deeper than this is not walked; what is there is replaced whole
_MAX_DEPTH = 64


def is_secret_name(name: object) -> bool:
    """Whether *name* reads like the name of a secret."""
    return isinstance(name, str) and _SECRET_KEY.search(name) is not None


def _usable(secrets: Iterable[str]) -> list[str]:
    """The secrets worth searching for, the longest first so that one holding another goes whole."""
    return sorted({secret for secret in secrets if isinstance(secret, str) and len(secret) >= _SHORTEST_SECRET},
                  key=len, reverse=True)


def redact_text(text: str, secrets: Iterable[str] = ()) -> str:
    """*text* with every occurrence of each of *secrets* replaced by ``***``."""
    for secret in _usable(secrets):
        text = text.replace(secret, REDACTED)
    return text


def redact(value: object, secrets: Iterable[str] = ()) -> object:
    """A copy of JSON-like *value* that holds no secret.

    :param value: what a call sent or got: objects, arrays, strings, numbers
    :param secrets: values known to be secret (the profile's environment); each
        is taken out of every string, key or value
    :return: the copy; *value* itself is left as it was
    """
    return _redacted(value, _usable(secrets), 0)


def _redacted(value: object, secrets: list[str], depth: int) -> object:
    if depth > _MAX_DEPTH:
        return REDACTED
    if isinstance(value, dict):
        return {
            redact_text(key, secrets) if isinstance(key, str) else key:
                REDACTED if is_secret_name(key) else _redacted(member, secrets, depth + 1)
            for key, member in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redacted(item, secrets, depth + 1) for item in value]
    if isinstance(value, str):
        return redact_text(value, secrets)
    return value
