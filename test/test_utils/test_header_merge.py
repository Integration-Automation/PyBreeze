"""Headers collected one at a time: a repeated name is combined, any other kept apart."""
from __future__ import annotations

from pybreeze.utils.header_tools.header_merge import (
    add_header,
    join_header_values,
    set_default_header,
    stored_header_name,
)


class TestStoredHeaderName:
    def test_found_in_any_casing_under_its_first_spelling(self):
        assert stored_header_name({"Content-Type": "a"}, "content-TYPE") == "Content-Type"

    def test_a_name_that_is_not_there_is_not_found(self):
        # Before or after the stored name in the alphabet, it is still another header
        headers = {"Mmm": "1"}

        assert stored_header_name(headers, "Aaa") is None
        assert stored_header_name(headers, "Zzz") is None


class TestAddHeader:
    def test_other_names_are_kept_apart(self):
        headers: dict[str, str] = {}
        for name in ("User-Agent", "Accept", "X-Trace"):
            add_header(headers, name, name.lower())

        assert headers == {"User-Agent": "user-agent", "Accept": "accept", "X-Trace": "x-trace"}

    def test_a_repeated_name_is_combined_under_its_first_spelling(self):
        headers: dict[str, str] = {}
        add_header(headers, "Accept", "text/html")
        add_header(headers, "accept", "application/json")

        assert headers == {"Accept": "text/html, application/json"}


class TestJoinHeaderValues:
    def test_cookies_are_joined_with_a_semicolon(self):
        assert join_header_values("Cookie", "a=1", "b=2") == "a=1; b=2"

    def test_any_other_header_with_a_comma(self):
        # Names after "cookie" in the alphabet as well as before it
        assert join_header_values("X-Tag", "a", "b") == "a, b"
        assert join_header_values("Accept", "a", "b") == "a, b"

    def test_an_empty_side_is_dropped(self):
        assert join_header_values("X-Tag", "", "b") == "b"
        assert join_header_values("X-Tag", "a", "") == "a"


def test_a_default_is_set_only_when_the_header_is_absent():
    headers = {"content-type": "text/plain"}

    set_default_header(headers, "Content-Type", "application/json")
    set_default_header(headers, "Accept", "*/*")

    assert headers == {"content-type": "text/plain", "Accept": "*/*"}
