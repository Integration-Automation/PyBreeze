"""Tests for the HAR export parser and its multi-request code generation."""
from __future__ import annotations

import json

import pytest

from pybreeze.utils.exception.exceptions import HarParseException
from pybreeze.utils.har_import.har_codegen import generate_har_script, unique_test_names
from pybreeze.utils.har_import.har_parser import (
    api_entries,
    is_api_like,
    parse_har,
    summarize,
)


def _har(*entries: dict) -> str:
    """Wrap raw entry dicts in a minimal HAR document."""
    return json.dumps({"log": {"version": "1.2", "entries": list(entries)}})


def _entry(
        url: str = "https://api.example.com/v1/items",
        method: str = "GET",
        headers: list | None = None,
        cookies: list | None = None,
        query: list | None = None,
        post_data: dict | None = None,
        status: int = 200,
        mime: str = "application/json",
        started: str = "2026-07-25T00:00:00.000Z") -> dict:
    """Build one HAR entry, with only the parts a test cares about filled in."""
    request: dict = {"method": method, "url": url, "headers": headers or []}
    if cookies is not None:
        request["cookies"] = cookies
    if query is not None:
        request["queryString"] = query
    if post_data is not None:
        request["postData"] = post_data
    return {
        "startedDateTime": started,
        "request": request,
        "response": {"status": status, "content": {"mimeType": mime}},
    }


class TestParseHarBasics:
    def test_method_and_url(self):
        entry = parse_har(_har(_entry()))[0]
        assert entry.request.method == "GET"
        assert entry.request.url == "https://api.example.com/v1/items"

    def test_method_is_uppercased(self):
        assert parse_har(_har(_entry(method="post")))[0].request.method == "POST"

    def test_response_details_are_kept(self):
        entry = parse_har(_har(_entry(status=404, mime="application/json; charset=utf-8")))[0]
        assert entry.status == 404
        assert entry.response_media_type == "application/json"

    def test_started_time_is_kept(self):
        assert parse_har(_har(_entry()))[0].started == "2026-07-25T00:00:00.000Z"

    def test_entries_keep_capture_order(self):
        document = _har(_entry(url="https://x/one"), _entry(url="https://x/two"))
        assert [e.request.url for e in parse_har(document)] == ["https://x/one", "https://x/two"]

    def test_entry_without_url_is_skipped(self):
        document = _har({"request": {"method": "GET"}}, _entry())
        assert len(parse_har(document)) == 1

    def test_missing_response_leaves_status_none(self):
        document = _har({"request": {"method": "GET", "url": "https://x/a"}})
        assert parse_har(document)[0].status is None


class TestParseHarErrors:
    def test_empty_text(self):
        with pytest.raises(HarParseException):
            parse_har("   ")

    def test_not_json(self):
        with pytest.raises(HarParseException):
            parse_har("not json at all")

    def test_json_without_log_entries(self):
        with pytest.raises(HarParseException):
            parse_har('{"log": {"version": "1.2"}}')

    def test_json_array(self):
        with pytest.raises(HarParseException):
            parse_har("[1, 2, 3]")

    def test_no_usable_entries(self):
        with pytest.raises(HarParseException):
            parse_har(_har())


class TestHeadersAndCookies:
    def test_headers_are_collected(self):
        entry = parse_har(_har(_entry(headers=[
            {"name": "Accept", "value": "application/json"},
            {"name": "X-Token", "value": "abc"},
        ])))[0]
        assert entry.request.headers == {"Accept": "application/json", "X-Token": "abc"}

    def test_repeated_header_is_combined(self):
        entry = parse_har(_har(_entry(headers=[
            {"name": "Accept", "value": "text/html"},
            {"name": "accept", "value": "application/json"},
        ])))[0]
        assert entry.request.headers == {"Accept": "text/html, application/json"}

    def test_http2_pseudo_headers_are_dropped(self):
        entry = parse_har(_har(_entry(headers=[
            {"name": ":method", "value": "GET"},
            {"name": ":authority", "value": "api.example.com"},
            {"name": "Accept", "value": "*/*"},
        ])))[0]
        assert entry.request.headers == {"Accept": "*/*"}

    def test_cookies_become_a_dict(self):
        entry = parse_har(_har(_entry(cookies=[
            {"name": "sid", "value": "abc"}, {"name": "theme", "value": "dark"},
        ])))[0]
        assert entry.request.cookies == {"sid": "abc", "theme": "dark"}

    def test_cookie_header_is_dropped_when_cookies_were_recorded(self):
        # Keeping both would send every cookie twice.
        entry = parse_har(_har(_entry(
            headers=[{"name": "Cookie", "value": "sid=abc"}],
            cookies=[{"name": "sid", "value": "abc"}])))[0]
        assert entry.request.cookies == {"sid": "abc"}
        assert "Cookie" not in entry.request.headers

    def test_cookie_header_is_kept_when_no_cookies_were_recorded(self):
        entry = parse_har(_har(_entry(headers=[{"name": "Cookie", "value": "sid=abc"}])))[0]
        assert entry.request.headers["Cookie"] == "sid=abc"


class TestQueryParameters:
    def test_url_query_moves_into_params(self):
        entry = parse_har(_har(_entry(url="https://x/api?a=1&b=2")))[0]
        assert entry.request.url == "https://x/api"
        assert entry.request.params == {"a": "1", "b": "2"}

    def test_query_string_list_fills_in_what_the_url_lacks(self):
        entry = parse_har(_har(_entry(
            url="https://x/api", query=[{"name": "page", "value": "2"}])))[0]
        assert entry.request.params == {"page": "2"}

    def test_url_wins_over_the_recorded_list(self):
        entry = parse_har(_har(_entry(
            url="https://x/api?page=1", query=[{"name": "page", "value": "9"}])))[0]
        assert entry.request.params == {"page": "1"}

    def test_full_url_rebuilds_the_address(self):
        entry = parse_har(_har(_entry(url="https://x/api?a=1")))[0]
        assert entry.request.full_url == "https://x/api?a=1"


class TestRequestBody:
    def test_raw_text_body(self):
        entry = parse_har(_har(_entry(method="POST", post_data={
            "mimeType": "application/json", "text": '{"a": 1}'})))[0]
        assert entry.request.body == '{"a": 1}'

    def test_urlencoded_params_become_body_pairs(self):
        entry = parse_har(_har(_entry(method="POST", post_data={
            "mimeType": "application/x-www-form-urlencoded",
            "params": [{"name": "a", "value": "1"}, {"name": "b", "value": "2"}]})))[0]
        assert entry.request.body == "a=1&b=2"

    def test_multipart_params_become_form_fields(self):
        entry = parse_har(_har(_entry(method="POST", post_data={
            "mimeType": "multipart/form-data; boundary=x",
            "params": [
                {"name": "note", "value": "hi"},
                {"name": "file", "value": "", "fileName": "a.png"},
            ]})))[0]
        assert entry.request.form_fields == ["note=hi", "file=@a.png"]

    def test_no_post_data_leaves_no_body(self):
        assert not parse_har(_har(_entry()))[0].request.has_body


class TestApiFiltering:
    def test_json_response_is_api_like(self):
        assert is_api_like(parse_har(_har(_entry()))[0])

    def test_stylesheet_is_not_api_like(self):
        entry = parse_har(_har(_entry(url="https://x/app.css", mime="text/css")))[0]
        assert not is_api_like(entry)

    def test_image_is_not_api_like(self):
        entry = parse_har(_har(_entry(url="https://x/logo.png", mime="image/png")))[0]
        assert not is_api_like(entry)

    def test_asset_extension_without_media_type_is_not_api_like(self):
        entry = parse_har(_har(_entry(url="https://x/app.js", mime="")))[0]
        assert not is_api_like(entry)

    def test_api_entries_keeps_only_calls(self):
        document = _har(
            _entry(url="https://x/api/items"),
            _entry(url="https://x/app.css", mime="text/css"),
            _entry(url="https://x/logo.png", mime="image/png"))
        assert [e.request.url for e in api_entries(parse_har(document))] == ["https://x/api/items"]


class TestSummary:
    def test_counts_and_hosts(self):
        document = _har(
            _entry(url="https://a.com/api/items"),
            _entry(url="https://a.com/app.css", mime="text/css"),
            _entry(url="https://b.com/api/users"))
        summary = summarize(parse_har(document))
        assert summary.total == 3
        assert summary.api == 2
        assert summary.hosts == ["a.com", "b.com"]

    def test_entry_summary_line(self):
        line = parse_har(_har(_entry(url="https://x/api/items?a=1")))[0].summary()
        assert "GET" in line and "/api/items?a=1" in line and "200" in line


class TestUniqueTestNames:
    def test_distinct_paths_keep_their_names(self):
        requests = [e.request for e in parse_har(_har(
            _entry(url="https://x/api/items"), _entry(url="https://x/api/users")))]
        assert unique_test_names(requests) == ["test_get_api_items", "test_get_api_users"]

    def test_repeated_endpoint_is_numbered(self):
        requests = [e.request for e in parse_har(_har(
            _entry(url="https://x/api/items"), _entry(url="https://x/api/items")))]
        assert unique_test_names(requests) == ["test_get_api_items", "test_get_api_items_2"]


class TestGenerateHarScript:
    def _requests(self, *urls: str):
        return [e.request for e in parse_har(_har(*[_entry(url=url) for url in urls]))]

    def test_no_requests_yields_empty_text(self):
        assert generate_har_script("requests", []) == ""

    def test_single_request_matches_the_curl_importer(self):
        from pybreeze.utils.curl_import.script_templates import generate_template
        requests = self._requests("https://x/api/items")
        assert generate_har_script("pytest", requests) == generate_template("pytest", requests[0])

    def test_requests_script_covers_every_request(self):
        code = generate_har_script("requests", self._requests("https://x/one", "https://x/two"))
        assert code.count("import requests") == 1
        assert "https://x/one" in code and "https://x/two" in code

    def test_pytest_script_defines_one_test_per_request(self):
        code = generate_har_script("pytest", self._requests("https://x/api/a", "https://x/api/b"))
        assert "def test_get_api_a():" in code
        assert "def test_get_api_b():" in code
        assert code.count("import requests") == 1

    def test_pytest_script_never_defines_the_same_test_twice(self):
        code = generate_har_script("pytest", self._requests("https://x/api/a", "https://x/api/a"))
        assert "def test_get_api_a():" in code
        assert "def test_get_api_a_2():" in code

    def test_apitestka_action_script_is_one_action_list(self):
        code = generate_har_script(
            "apitestka_action", self._requests("https://x/api/a", "https://x/api/b"))
        actions = json.loads(code)
        assert [action[0] for action in actions] == ["AT_test_api_method"] * 2
        assert [action[1]["test_url"] for action in actions] == [
            "https://x/api/a", "https://x/api/b"]

    def test_apitestka_python_script_imports_once(self):
        code = generate_har_script(
            "apitestka_python", self._requests("https://x/api/a", "https://x/api/b"))
        assert code.count("from je_api_testka import") == 1
        assert code.count("test_api_method_requests(") == 2

    def test_loaddensity_script_keeps_every_request(self):
        # Merging into one tasks dict would drop all but the last GET.
        code = generate_har_script(
            "loaddensity_python", self._requests("https://x/api/a", "https://x/api/b"))
        assert code.count("start_test(") == 2
        assert "https://x/api/a" in code and "https://x/api/b" in code

    def test_unknown_target_falls_back_to_requests(self):
        code = generate_har_script("nonsense", self._requests("https://x/one", "https://x/two"))
        assert "import requests" in code
