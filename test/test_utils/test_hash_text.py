"""Tests for the text hash utility."""
from __future__ import annotations

import hashlib

import pytest

from pybreeze.utils.hash_tools.hash_text import available_algorithms, hash_all, hash_text


class TestHashText:
    def test_sha256_matches_hashlib(self):
        assert hash_text("hello", "sha256") == hashlib.sha256(b"hello").hexdigest()

    def test_sha512_matches_hashlib(self):
        assert hash_text("hello", "sha512") == hashlib.sha512(b"hello").hexdigest()

    def test_md5_matches_hashlib(self):
        expected = hashlib.md5(b"hello", usedforsecurity=False).hexdigest()
        assert hash_text("hello", "md5") == expected

    def test_sha1_matches_hashlib(self):
        expected = hashlib.sha1(b"hello", usedforsecurity=False).hexdigest()
        assert hash_text("hello", "sha1") == expected

    def test_unicode_is_utf8_encoded(self):
        assert hash_text("測試", "sha256") == hashlib.sha256("測試".encode("utf-8")).hexdigest()

    def test_empty_text(self):
        assert hash_text("", "sha256") == hashlib.sha256(b"").hexdigest()

    def test_unknown_algorithm_raises(self):
        with pytest.raises(ValueError):
            hash_text("x", "crc32")

    def test_is_deterministic(self):
        # Hashing the same input twice must yield the same digest.
        first = hash_text("repeat", "sha256")
        second = hash_text("repeat", "sha256")
        assert first == second


class TestAvailableAlgorithms:
    def test_lists_strong_first(self):
        algorithms = available_algorithms()
        assert algorithms[0] == "sha256"
        assert set(algorithms) == {"sha256", "sha512", "sha1", "md5"}


class TestHashAll:
    def test_covers_every_algorithm(self):
        digests = hash_all("hello")
        assert set(digests) == set(available_algorithms())

    def test_values_match_individual(self):
        digests = hash_all("hello")
        assert digests["sha256"] == hash_text("hello", "sha256")

    def test_empty_text(self):
        digests = hash_all("")
        assert digests["md5"] == hashlib.md5(b"", usedforsecurity=False).hexdigest()
