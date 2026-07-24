"""Compute common hash digests of a piece of text.

Handy for building or checking automation fixtures: content checksums, cache
keys, ETag comparisons, and the like. This is a general-purpose digest tool, not
a password or signature facility.

MD5 and SHA-1 are offered for interoperability with existing systems only. They
are constructed with ``usedforsecurity=False`` so static analysis knows they are
never used for a security decision here.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable

# Text encoding used before hashing
_ENCODING = "utf-8"

# Ordered so the strong algorithms appear first in any UI listing.
_ALGORITHMS: dict[str, Callable[[bytes], "hashlib._Hash"]] = {
    "sha256": hashlib.sha256,
    "sha512": hashlib.sha512,
    "sha1": lambda data: hashlib.sha1(data, usedforsecurity=False),
    "md5": lambda data: hashlib.md5(data, usedforsecurity=False),
}


def available_algorithms() -> list[str]:
    """Return the supported algorithm names, strongest first."""
    return list(_ALGORITHMS)


def hash_text(text: str, algorithm: str) -> str:
    """Return the hex digest of *text* under *algorithm*.

    :param text: the text to hash (encoded as UTF-8)
    :param algorithm: one of :func:`available_algorithms`
    :return: the lower-case hex digest
    :raises ValueError: when *algorithm* is not supported
    """
    constructor = _ALGORITHMS.get(algorithm)
    if constructor is None:
        raise ValueError(f"unsupported hash algorithm: {algorithm}")
    return constructor(text.encode(_ENCODING)).hexdigest()


def hash_all(text: str) -> dict[str, str]:
    """Return the hex digest of *text* under every supported algorithm.

    :param text: the text to hash
    :return: ``algorithm -> hex digest`` for each supported algorithm
    """
    return {name: hash_text(text, name) for name in _ALGORITHMS}
