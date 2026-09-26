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
        text = _har()
        with pytest.raises(HarParseException):
            parse_har(text)

    def test_an_entry_with_a_malformed_url_is_skipped(self):
        # Listing it raised ValueError out of the tab, which kept showing the
        # previous file's requests, and "Generate all" generated those.
        entries = parse_har(_har(_entry(url="http://[::1/api"), _entry()))

        assert [entry.request.url for entry in entries] == ["https://api.example.com/v1/items"]


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

    def test_cookies_sharing_a_name_all_go_as_the_header(self):
        # Two paths, two sid cookies: a dict would keep only the last
        entry = parse_har(_har(_entry(
            headers=[{"name": "cookie", "value": "sid=1; sid=2"}],
            cookies=[{"name": "sid", "value": "1"}, {"name": "sid", "value": "2"}])))[0]
        assert entry.request.cookies == {}
        assert entry.request.headers == {"cookie": "sid=1; sid=2"}

    def test_cookies_sharing_a_name_without_a_header_make_one(self):
        entry = parse_har(_har(_entry(
            cookies=[{"name": "sid", "value": "1"}, {"name": "sid", "value": "2"}])))[0]
        assert entry.request.cookies == {}
        assert entry.request.headers == {"Cookie": "sid=1; sid=2"}

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
        assert entry.request.form_strings == ["note=hi"]
        assert entry.request.form_fields == ["file=@a.png"]

    def test_a_text_field_starting_with_at_is_not_a_file(self):
        from pybreeze.utils.curl_import.request_body import form_parts

        entry = parse_har(_har(_entry(method="POST", post_data={
            "mimeType": "multipart/form-data; boundary=x",
            "params": [{"name": "handle", "value": "@alice"}]})))[0]

        assert form_parts(entry.request) == ({"handle": "@alice"}, {})

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
        assert "GET" in line
        assert "/api/items?a=1" in line
        assert "200" in line


class TestUniqueTestNames:
    def test_distinct_paths_keep_their_names(self):
        requests = [e.request for e in parse_har(_har(
            _entry(url="https://x/api/items"), _entry(url="https://x/api/users")))]
        assert unique_test_names(requests) == ["test_get_api_items", "test_get_api_users"]

    def test_repeated_endpoint_is_numbered(self):
        requests = [e.request for e in parse_har(_har(
            _entry(url="https://x/api/items"), _entry(url="https://x/api/items")))]
        assert unique_test_names(requests) == ["test_get_api_items", "test_get_api_items_2"]

    @pytest.mark.parametrize("paths", [("a", "a", "a/2"), ("a/2", "a", "a"), ("a", "a/2", "a", "a", "a/3")])
    def test_a_number_never_takes_another_requests_own_name(self, paths):
        requests = [e.request for e in parse_har(_har(*[_entry(url=f"https://x/{p}") for p in paths]))]

        names = unique_test_names(requests)

        assert len(set(names)) == len(names)
        assert "test_get_a_2" in names

    @pytest.mark.parametrize(("paths", "expected"), [
        (("a", "a", "a/2"), ["test_get_a", "test_get_a_3", "test_get_a_2"]),
        (("a", "a", "a", "a"), ["test_get_a", "test_get_a_2", "test_get_a_3", "test_get_a_4"]),
    ])
    def test_the_numbers_given(self, paths, expected):
        requests = [e.request for e in parse_har(_har(*[_entry(url=f"https://x/{p}") for p in paths]))]

        assert unique_test_names(requests) == expected


class TestGenerateHarScript:
    def _requests(self, *urls: str):
        return [e.request for e in parse_har(_har(*[_entry(url=url) for url in urls]))]

    def test_no_requests_yields_empty_text(self):
        assert generate_har_script("requests", []) == ""

    @pytest.mark.parametrize("target", ["pytest", "requests", "apitestka_python", "loaddensity_python"])
    def test_single_request_matches_the_curl_importer(self, target):
        from pybreeze.utils.curl_import.script_templates import generate_template
        requests = self._requests("https://x/api/items")
        assert generate_har_script(target, requests) == generate_template(target, requests[0])

    @pytest.mark.parametrize("target", ["requests", "apitestka_python", "loaddensity_python"])
    def test_the_blocks_are_numbered_from_one(self, target):
        code = generate_har_script(target, self._requests("https://x/one", "https://x/two"))

        assert "# 1. GET https://x/one" in code
        assert "# 2. GET https://x/two" in code

    def test_requests_script_covers_every_request(self):
        code = generate_har_script("requests", self._requests("https://x/one", "https://x/two"))
        assert code.count("import requests") == 1
        assert "https://x/one" in code
        assert "https://x/two" in code

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
        assert "https://x/api/a" in code
        assert "https://x/api/b" in code

    def test_unknown_target_falls_back_to_requests(self):
        code = generate_har_script("nonsense", self._requests("https://x/one", "https://x/two"))
        assert "import requests" in code


class TestQueryValuesFromTheUrl:
    """A value in the recorded URL is percent-encoded; params hold it decoded, once."""

    def test_an_encoded_value_is_decoded(self):
        entry = parse_har(_har(_entry(url="https://x/api?q=hello+world&tag=a%2Bb")))[0]

        assert entry.request.params == {"q": "hello world", "tag": "a+b"}

    def test_the_rebuilt_url_is_encoded_once(self):
        entry = parse_har(_har(_entry(url="https://x/api?q=hello+world")))[0]

        assert entry.request.full_url == "https://x/api?q=hello+world"

    def test_a_query_that_would_not_come_back_as_written_stays_as_recorded(self):
        # Decoded and encoded again, %20 became + and a bare key gained =
        entry = parse_har(_har(_entry(url="https://x/api?q=hello%20world&flag")))[0]

        assert entry.request.params == {}
        assert entry.request.full_url == "https://x/api?q=hello%20world&flag"


class TestWhatReachesTheGeneratedCode:
    """A recording's method and URL end up in code; nothing in them may become code."""

    def test_a_method_that_is_not_a_token_is_refused(self):
        text = _har(_entry(method="GET():\n    __import__('os').system('calc')\ndef t"))
        with pytest.raises(HarParseException, match="not an HTTP method"):
            parse_har(text)

    @pytest.mark.parametrize("bad", [
        {"url": "https://x/a?q=\ud800"},
        {"url": "https://x/a", "query": [{"name": "q", "value": "\ud800"}]},
        {"url": "https://x/a", "headers": [{"name": "X", "value": "\udfff"}]},
    ])
    def test_an_entry_with_half_a_character_is_skipped_and_the_rest_load(self, bad):
        # JSON's "\ud800" escape: encoding it raised UnicodeEncodeError out of the tab
        entries = parse_har(_har(_entry(**bad), _entry(url="https://x/b")))

        assert [entry.request.url for entry in entries] == ["https://x/b"]

    def test_an_entry_with_a_bad_method_is_skipped_and_the_rest_load(self):
        entries = parse_har(_har(_entry(url="https://x/a", method=""), _entry(url="https://x/b")))

        assert [entry.request.url for entry in entries] == ["https://x/b"]

    def test_a_line_break_in_a_url_stays_inside_the_comment(self):
        import ast

        url = "https://x/a\nimport os; os.system('calc')  #"
        requests = [e.request for e in parse_har(_har(_entry(url=url), _entry()))]

        code = generate_har_script("requests", requests)

        imports = [node for node in ast.parse(code).body if isinstance(node, ast.Import)]
        assert [alias.name for node in imports for alias in node.names] == ["requests"]
        assert "\x0a" in code


class TestRepeatedQueryKeys:
    def test_every_value_in_the_url_is_kept_once(self):
        entry = parse_har(_har(_entry(
            url="https://api.example.com/v1/items?id=1&id=2",
            query=[{"name": "id", "value": "1"}, {"name": "id", "value": "2"}])))[0]

        assert entry.request.params == {"id": ["1", "2"]}

    def test_a_recorded_name_the_url_lacks_keeps_all_its_values(self):
        entry = parse_har(_har(_entry(
            url="https://api.example.com/v1/items?q=a",
            query=[{"name": "q", "value": "a"},
                   {"name": "tag", "value": "x"}, {"name": "tag", "value": "y"}])))[0]

        assert entry.request.params == {"q": "a", "tag": ["x", "y"]}


def test_json_nested_too_deep_is_reported_not_raised_out_of_the_tab():
    from pybreeze.utils.exception.exceptions import HarParseException
    from pybreeze.utils.har_import.har_parser import parse_har

    # json.loads raises RecursionError, which the tab did not catch
    with pytest.raises(HarParseException):
        parse_har("[" * 100000)


def test_a_header_entry_that_is_not_an_object_is_skipped():
    # A HAR another tool wrote with a stray string among the headers
    entry = parse_har(_har(_entry(headers=["X-Stray", {"name": "Accept", "value": "text/plain"}])))[0]

    assert entry.request.headers == {"Accept": "text/plain"}


def test_a_form_parameter_without_a_name_is_left_out():
    post = {"mimeType": "application/x-www-form-urlencoded",
            "params": [{"value": "orphan"}, "not a parameter", {"name": "kept", "value": "1"}]}
    entry = parse_har(_har(_entry(method="POST", post_data=post)))[0]

    assert entry.request.data_parts == ["kept=1"]


def test_a_body_with_no_text_sends_nothing():
    entry = parse_har(_har(_entry(method="POST", post_data={"mimeType": "text/plain", "text": ""})))[0]

    assert entry.request.data_parts == []
