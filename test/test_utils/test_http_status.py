"""Tests for the HTTP status code reference."""
from __future__ import annotations

import sys
from http import HTTPStatus

import pytest

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
        assert by_code[100].category == "Informational"


class TestStatusOf:
    def test_a_registered_code_is_the_registered_status(self):
        from pybreeze.utils.http_reference.status_codes import status_of

        assert status_of(404, "Gone Missing") == lookup(404)

    def test_a_code_nobody_registered_is_built_from_its_class_and_phrase(self):
        # A server may send one (599): its class still says what it means
        from pybreeze.utils.http_reference.status_codes import StatusInfo, status_of

        assert status_of(599, "Network Timeout") == StatusInfo(
            code=599, phrase="Network Timeout", description="", category="Server Error")
        assert status_of(199).category == "Informational"
        assert status_of(699).category == "Unknown"


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
        assert 404 in codes
        assert 400 in codes
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


class TestTheSameWordsOnEveryPython:
    """``http.HTTPStatus`` words statuses as the Python it runs on does; the reference does not vary."""

    @pytest.mark.parametrize(("code", "phrase"), [
        (413, "Content Too Large"),
        (414, "URI Too Long"),
        (416, "Range Not Satisfiable"),
        (422, "Unprocessable Content"),
    ])
    def test_a_status_rfc_9110_renamed_has_its_new_name(self, code, phrase):
        # Python before 3.13 gave the old names ("Unprocessable Entity")
        assert lookup(code).phrase == phrase

    def test_every_status_is_described(self):
        # Before 3.14, fourteen had no description (102, 422, 425, 507, ...)
        assert [info.code for info in all_statuses() if not info.description] == []

    @pytest.mark.parametrize(("former", "code"), [
        ("Unprocessable Entity", 422),
        ("request entity too large", 413),
        ("Request-URI Too Long", 414),
        ("Requested Range Not Satisfiable", 416),
    ])
    def test_a_status_is_found_by_its_former_name(self, former, code):
        assert code in {info.code for info in search(former)}

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="the table holds the words Python 3.14 gives")
    def test_the_table_is_what_python_gives_from_3_14(self):
        # A later Python rewording a status fails here, and the table follows it
        from pybreeze.utils.http_reference.status_codes import _CURRENT_WORDS

        assert {code: (HTTPStatus(code).phrase, HTTPStatus(code).description) for code in _CURRENT_WORDS} == _CURRENT_WORDS
