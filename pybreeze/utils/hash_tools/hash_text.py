"""Compute common hash digests of a piece of text.

Handy for building or checking automation fixtures: content checksums, cache
keys, ETag comparisons, and the like. This is a general-purpose digest tool, not
a password or signature facility.

MD5 and SHA-1 are offered for interoperability with existing systems only. Every
digest is built through ``hashlib.new(name, ..., usedforsecurity=False)`` so the
weak algorithms are never used for a security decision here.
"""
from __future__ import annotations

import hashlib

# Text encoding used before hashing
_ENCODING = "utf-8"

# Supported algorithm names, strongest first (drives any UI listing).
_ALGORITHMS: tuple[str, ...] = ("sha256", "sha512", "sha1", "md5")


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
    if algorithm not in _ALGORITHMS:
        raise ValueError(f"unsupported hash algorithm: {algorithm}")
    # md5/sha1 are non-security interop digests only; usedforsecurity=False.
    digest = hashlib.new(  # nosemgrep
        algorithm, text.encode(_ENCODING), usedforsecurity=False)
    return digest.hexdigest()


def hash_all(text: str) -> dict[str, str]:
    """Return the hex digest of *text* under every supported algorithm.

    :param text: the text to hash
    :return: ``algorithm -> hex digest`` for each supported algorithm
    """
    return {name: hash_text(text, name) for name in _ALGORITHMS}
