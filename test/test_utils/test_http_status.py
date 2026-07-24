"""Tests for the HTTP status code reference."""
from __future__ import annotations

from pybreeze.utils.http_reference.status_codes import (
    all_statuses,
    lookup,
    search,
)


class TestAllStatuses:
    def test_includes_common_codes(self):
        codes = {info.code for info in all_statuses()}
        assert {200, 301, 404, 418, 500} <= codes

    def test_is_sorted_by_code(self):
        codes = [info.code for info in all_statuses()]
        assert codes == sorted(codes)

    def test_categories_assigned(self):
        by_code = {info.code: info for info in all_statuses()}
        assert by_code[200].category == "Success"
        assert by_code[404].category == "Client Error"
        assert by_code[500].category == "Server Error"
        assert by_code[301].category == "Redirection"


class TestLookup:
    def test_known_code(self):
        info = lookup(404)
        assert info is not None
        assert info.phrase == "Not Found"

    def test_unknown_code_returns_none(self):
        assert lookup(299) is None

    def test_teapot(self):
        assert lookup(418).phrase == "I'm a Teapot"


class TestSearch:
    def test_empty_returns_all(self):
        assert len(search("")) == len(all_statuses())

    def test_by_code_prefix(self):
        results = search("40")
        codes = {info.code for info in results}
        assert 404 in codes and 400 in codes
        assert all(str(info.code).startswith("40") for info in results)

    def test_by_exact_code(self):
        results = search("404")
        assert any(info.code == 404 for info in results)

    def test_by_phrase(self):
        results = search("not found")
        assert any(info.code == 404 for info in results)

    def test_case_insensitive(self):
        assert any(info.code == 404 for info in search("NOT FOUND"))

    def test_no_match(self):
        assert search("zzzzz nonexistent") == []

    def test_by_description_keyword(self):
        # 'Unauthorized' (401) description mentions authentication.
        results = search("unauthorized")
        assert any(info.code == 401 for info in results)
