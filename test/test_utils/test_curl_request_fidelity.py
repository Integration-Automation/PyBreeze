"""The request a curl command imports as is the request curl would send."""
from __future__ import annotations

import pytest

from pybreeze.utils.curl_import.curl_parser import parse_curl
from pybreeze.utils.curl_import.request_body import form_parts
from pybreeze.utils.curl_import.request_codegen import to_requests_code
from pybreeze.utils.curl_import.script_templates import apitestka_call_block
from pybreeze.utils.har_import.har_parser import parse_har


class TestHead:
    @pytest.mark.parametrize("command", [
        "curl -I https://x", "curl --head https://x", "curl -sI https://x",
    ])
    def test_it_is_a_head_request(self, command):
        # -I was skipped as a display flag, and the code sent a GET.
        assert parse_curl(command).method == "HEAD"

    def test_an_explicit_method_wins(self):
        assert parse_curl("curl -I -X OPTIONS https://x").method == "OPTIONS"


class TestOauth2Bearer:
    def test_it_becomes_the_authorization_header(self):
        # The token was consumed and thrown away.
        assert parse_curl("curl --oauth2-bearer T0K https://x").headers == {
            "Authorization": "Bearer T0K"}

    @pytest.mark.parametrize("command", [
        "curl --oauth2-bearer T0K -H 'Authorization: Basic eg==' https://x",
        "curl -H 'Authorization: Basic eg==' --oauth2-bearer T0K https://x",
    ])
    def test_an_explicit_authorization_header_wins(self, command):
        assert parse_curl(command).headers == {"Authorization": "Basic eg=="}


class TestFragment:
    def test_it_is_not_sent(self):
        request = parse_curl("curl 'https://x/a?b=1#frag'")

        # It became part of the last query value: b="1#frag".
        assert request.params == {"b": "1"}
        assert request.full_url == "https://x/a?b=1"

    def test_a_fragment_without_a_query_is_dropped_too(self):
        assert parse_curl("curl 'https://x/a#top'").url == "https://x/a"


class TestRepeatedFormFields:
    COMMAND = "curl -F f=@a.txt -F f=@b.txt -F k=1 -F k=2 https://x/up"

    def test_every_value_is_kept(self):
        # A dict kept only the last: one file uploaded out of two.
        assert form_parts(parse_curl(self.COMMAND)) == (
            {"k": ["1", "2"]}, {"f": ["a.txt", "b.txt"]})

    def test_the_requests_code_uploads_both_files(self):
        code = to_requests_code(parse_curl(self.COMMAND))

        assert '("f", open("a.txt", "rb")),' in code
        assert '("f", open("b.txt", "rb")),' in code

    def test_the_apitestka_call_uploads_both_files(self):
        block = apitestka_call_block(parse_curl(self.COMMAND))

        assert 'files=[("f", open("a.txt", "rb")), ("f", open("b.txt", "rb"))],' in block

    def test_a_field_given_once_is_written_as_before(self):
        assert 'files={"f": open("a.txt", "rb")},' in apitestka_call_block(
            parse_curl("curl -F f=@a.txt https://x/up"))

    def test_a_recorded_multipart_upload_keeps_both_files(self):
        import json

        har = json.dumps({"log": {"entries": [{"request": {
            "method": "POST", "url": "https://x/up",
            "postData": {"mimeType": "multipart/form-data; boundary=z", "params": [
                {"name": "f", "fileName": "a.txt"}, {"name": "f", "fileName": "b.txt"}]},
        }}]}})

        (entry,) = parse_har(har)

        assert form_parts(entry.request)[1] == {"f": ["a.txt", "b.txt"]}
