"""The WebRunner import target, and the normalized request it is written from."""
from __future__ import annotations

import json

import pytest

from pybreeze.utils.curl_import.curl_parser import CurlRequest, parse_curl
from pybreeze.utils.har_import.har_parser import parse_har
from pybreeze.utils.import_targets.builtin_targets import IMPORT_TARGETS
from pybreeze.utils.import_targets.normalized_request import NormalizedRequest, Payload, PayloadKind, normalize
from pybreeze.utils.import_targets.target_registry import RequestPart
from pybreeze.utils.import_targets.webrunner_target import (
    to_webrunner_action_json,
    webrunner_action_script,
    webrunner_actions,
)

_URL = "https://x.example/items"
_START = ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}]
_QUIT = ["WR_quit"]


def _go(url: str) -> list:
    return ["WR_to_url", {"url": url}]


class TestNormalize:
    def test_a_bare_get(self):
        assert normalize(parse_curl(f"curl {_URL}")) == NormalizedRequest(method="GET", url=_URL)

    def test_the_url_is_whole_with_the_query_from_the_command_too(self):
        sent = normalize(parse_curl(f"curl -G '{_URL}?a=1' -d b=2"))

        assert sent.method == "GET"
        assert sent.url == f"{_URL}?a=1&b=2"
        assert sent.payload == Payload()

    def test_headers_and_cookies_are_what_goes_out(self):
        sent = normalize(parse_curl(f"curl {_URL} -H 'X-A: 1' -H 'Accept-Encoding: br' -b 'a=1; b=2'"))

        # requests names the codings it can decode itself (request_body.sent_headers)
        assert sent.headers == (("X-A", "1"),)
        assert sent.cookies == (("a", "1"), ("b", "2"))

    def test_a_raw_body(self):
        sent = normalize(parse_curl(f"curl {_URL} -d 'a=1' -d 'b=2'"))

        assert sent.method == "POST"
        assert sent.payload == Payload(PayloadKind.RAW, text="a=1&b=2")

    def test_a_json_body_is_kept_as_text_and_as_what_it_says(self):
        sent = normalize(parse_curl(f"curl {_URL} -H 'Content-Type: application/json' -d '{{\"a\": [1, true]}}'"))

        assert sent.payload == Payload(PayloadKind.JSON, text='{"a": [1, true]}', value={"a": [1, True]})

    def test_a_form_holds_each_field_and_whether_it_is_a_file(self):
        sent = normalize(parse_curl(f"curl {_URL} -F 'name=text' -F 'file=@up.bin' -d ignored"))

        assert sent.payload == Payload(
            PayloadKind.FORM, fields=(("name", False, "text"), ("file", True, "up.bin")))

    def test_a_body_read_from_files_names_them_in_order(self):
        sent = normalize(parse_curl(f"curl {_URL} -d @one.txt -d a=1 --data-binary @two.bin"))

        assert sent.payload.kind is PayloadKind.FILES
        assert sent.payload.files == ("one.txt", "two.bin")
        assert sent.payload.text == "a=1"

    def test_credentials_a_time_limit_and_cookie_files(self):
        sent = normalize(parse_curl(f"curl {_URL} -u alice -m 2.5 -b jar.txt"))

        assert (sent.username, sent.password) == ("alice", "")
        assert sent.timeout == pytest.approx(2.5)
        assert sent.cookie_files == ("jar.txt",)

    def test_a_request_without_them_has_none(self):
        sent = normalize(parse_curl(f"curl {_URL}"))

        assert (sent.username, sent.timeout, sent.cookie_files) == (None, None, ())

    def test_a_har_entry_normalizes_like_a_command(self):
        har = json.dumps({"log": {"entries": [{
            "request": {
                "method": "POST", "url": f"{_URL}?a=1",
                "headers": [{"name": "Content-Type", "value": "application/json"}],
                "cookies": [{"name": "sid", "value": "s1"}],
                "postData": {"mimeType": "application/json", "text": "{\"k\": 1}"}},
            "response": {"status": 200}}]}})
        from_har = normalize(parse_har(har)[0].request)
        from_curl = normalize(parse_curl(
            f"curl -X POST '{_URL}?a=1' -H 'Content-Type: application/json' -b 'sid=s1' -d '{{\"k\": 1}}'"))

        assert from_har == from_curl

    def test_it_cannot_be_changed(self):
        sent = normalize(parse_curl(f"curl {_URL}"))

        with pytest.raises(AttributeError):
            sent.url = "https://elsewhere.example"


class TestActions:
    def test_a_get_is_a_visit(self):
        assert webrunner_actions([parse_curl(f"curl '{_URL}?a=1&b=2'")]) == [
            _START, _go(f"{_URL}?a=1&b=2"), _QUIT]

    def test_a_query_that_would_not_come_back_as_written_is_visited_as_written(self):
        # A signed URL must not be re-encoded (curl_parser._split_url_query)
        assert webrunner_actions([parse_curl(f"curl '{_URL}?sig=a%2Fb&b=two words'")]) == [
            _START, _go(f"{_URL}?sig=a%2Fb&b=two words"), _QUIT]

    def test_cookies_are_set_on_the_site_and_the_page_loaded_again(self):
        actions = webrunner_actions([parse_curl(f"curl {_URL} -b 'sid=s1; theme=dark'")])

        assert actions == [
            _START, _go(_URL),
            ["WR_add_cookie", {"cookie_dict": {"name": "sid", "value": "s1"}}],
            ["WR_add_cookie", {"cookie_dict": {"name": "theme", "value": "dark"}}],
            _go(_URL), _QUIT]

    @pytest.mark.parametrize(("limit", "seconds"), [("7", 7), ("2.1", 3), ("0.2", 1)])
    def test_a_time_limit_is_the_page_load_timeout_in_whole_seconds(self, limit, seconds):
        actions = webrunner_actions([parse_curl(f"curl {_URL} -m {limit}")])

        assert actions == [_START, ["WR_set_page_load_timeout", {"time_to_wait": seconds}], _go(_URL), _QUIT]

    def test_no_limit_sets_none(self):
        # curl's -m 0 means no limit
        assert webrunner_actions([parse_curl(f"curl {_URL} -m 0")]) == [_START, _go(_URL), _QUIT]

    def test_what_a_browser_cannot_do_is_not_written(self):
        request = parse_curl(
            f"curl -X PUT {_URL} -H 'X-Secret: h3ader' -u user:pa55 -d 'b0dy=1' -b jar.txt")

        text = to_webrunner_action_json(request)

        assert json.loads(text) == [_START, _go(_URL), _QUIT]
        for left_out in ("PUT", "h3ader", "pa55", "b0dy", "jar.txt"):
            assert left_out not in text

    def test_several_requests_share_one_browser(self):
        requests = [parse_curl(f"curl {_URL}/1"), parse_curl(f"curl {_URL}/2 -b a=1"), parse_curl(f"curl {_URL}/3")]

        actions = json.loads(webrunner_action_script(requests))

        assert actions == [
            _START, _go(f"{_URL}/1"), _go(f"{_URL}/2"),
            ["WR_add_cookie", {"cookie_dict": {"name": "a", "value": "1"}}], _go(f"{_URL}/2"),
            _go(f"{_URL}/3"), _QUIT]

    def test_no_requests_is_a_browser_opened_and_closed(self):
        assert webrunner_actions([]) == [_START, _QUIT]

    def test_the_text_is_indented_json_ending_in_a_line_break(self):
        text = to_webrunner_action_json(parse_curl(f"curl {_URL}"))

        assert text.startswith("[\n    [\n        \"WR_get_webdriver_manager\",")
        assert text.endswith("]\n")

    def test_a_character_a_text_box_would_not_give_back_is_escaped(self):
        text = to_webrunner_action_json(CurlRequest(url=f"{_URL}?q= "))

        assert "\\u2028" in text
        assert json.loads(text)[1] == _go(f"{_URL}?q= ")


class TestTheRegisteredTarget:
    def test_it_is_offered_last_as_json(self):
        target = IMPORT_TARGETS.targets()[-1]

        assert (target.key, target.extension) == ("webrunner_action", "json")
        assert target.carries == {RequestPart.COOKIES, RequestPart.TIMEOUT}

    def test_one_request_and_several_through_the_registry(self):
        one = [parse_curl(f"curl {_URL}/1")]
        two = [*one, parse_curl(f"curl {_URL}/2")]

        assert json.loads(IMPORT_TARGETS.generate("webrunner_action", one)) == [_START, _go(f"{_URL}/1"), _QUIT]
        assert json.loads(IMPORT_TARGETS.generate("webrunner_action", two)) == [
            _START, _go(f"{_URL}/1"), _go(f"{_URL}/2"), _QUIT]

    def test_it_says_what_of_a_post_it_leaves_out(self):
        target = IMPORT_TARGETS.target("webrunner_action")
        request = parse_curl(f"curl {_URL} -H 'X-A: 1' -d a=1 -b c=1 -m 3")

        assert target.unrepresented(request) == [RequestPart.METHOD, RequestPart.HEADERS, RequestPart.BODY]
