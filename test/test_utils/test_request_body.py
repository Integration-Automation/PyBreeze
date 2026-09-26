"""How an imported request's body and form are sent: as JSON, as it was written, or as multipart."""
from __future__ import annotations

import pytest

from pybreeze.utils.curl_import.curl_parser import CurlRequest
from pybreeze.utils.curl_import.request_body import (
    _MAX_LITERAL_DEPTH,
    body_kind,
    form_entries,
    form_parts,
    sent_headers,
)

_JSON = {"Content-Type": "application/json"}


def _nested(levels: int) -> str:
    """A JSON body of lists *levels* deep around a 1: ``[[1]]`` is two."""
    return "[" * levels + "1" + "]" * levels


class TestBodyKind:
    def test_no_body_is_none(self):
        assert body_kind(CurlRequest(headers=dict(_JSON))) is None

    @pytest.mark.parametrize(("body", "parsed"), [
        ('{"a": 1.5, "b": [1, 2]}', {"a": 1.5, "b": [1, 2]}),
        ('{"n": 0.1}', {"n": 0.1}),
        ("[1, 2]", [1, 2]),
    ])
    def test_json_the_object_sends_back_unchanged_is_sent_as_json(self, body, parsed):
        assert body_kind(CurlRequest(headers=dict(_JSON), data_parts=[body])) == ("json", parsed)

    @pytest.mark.parametrize("body", [
        '{"n": 0.10000000000000000001}',   # more digits than a float holds, rounded down
        '{"n": 0.29999999999999999999}',   # and rounded up
        '{"n": 1e400}',                    # no float at all
        '{"n": NaN}',
        '{"a": 1, "a": 2}',                # the object keeps only the last
        "not json",
        _nested(100_000),                  # deeper than the parser goes
    ], ids=["digits down", "digits up", "overflow", "NaN", "repeated key", "text", "too deep to parse"])
    def test_json_that_would_come_back_changed_is_sent_as_written(self, body):
        assert body_kind(CurlRequest(headers=dict(_JSON), data_parts=[body])) == ("data", body)

    def test_a_body_nested_as_deep_as_a_script_takes_is_json_and_one_more_is_not(self):
        deepest = _nested(_MAX_LITERAL_DEPTH)
        too_deep = _nested(_MAX_LITERAL_DEPTH + 1)

        assert body_kind(CurlRequest(headers=dict(_JSON), data_parts=[deepest]))[0] == "json"
        assert body_kind(CurlRequest(headers=dict(_JSON), data_parts=[too_deep])) == ("data", too_deep)

    @pytest.mark.parametrize(("levels", "kind"), [(_MAX_LITERAL_DEPTH, "json"), (_MAX_LITERAL_DEPTH + 1, "data")])
    def test_objects_count_towards_the_depth_as_lists_do(self, levels, kind):
        body = '{"a": ' * levels + "1" + "}" * levels

        assert body_kind(CurlRequest(headers=dict(_JSON), data_parts=[body]))[0] == kind

    def test_without_a_json_content_type_it_is_sent_as_written(self):
        request = CurlRequest(headers={"Content-Type": "text/plain"}, data_parts=['{"a": 1}'])

        assert body_kind(request) == ("data", '{"a": 1}')


class TestForm:
    def test_fields_and_uploads_are_split_and_repeats_kept(self):
        request = CurlRequest(form_fields=["a=1", "f=@x.txt;type=text/plain", "a=2", "f=@y.bin", "novalue"],
                              form_strings=["s=@literal"])

        assert form_parts(request) == ({"a": ["1", "2"], "s": "@literal"}, {"f": ["x.txt", "y.bin"]})
        assert form_entries(request) == [
            ("a", False, "1"), ("a", False, "2"), ("s", False, "@literal"),
            ("f", True, "x.txt"), ("f", True, "y.bin"),
        ]


class TestSentHeaders:
    def test_a_form_s_multipart_content_type_is_left_to_requests(self):
        request = CurlRequest(headers={"Content-Type": " Multipart/form-data; boundary=x", "Accept": "*/*"},
                              form_fields=["a=1"])

        assert sent_headers(request) == {"Accept": "*/*"}

    def test_other_headers_of_a_form_are_kept(self):
        # Another media type, and a multipart value under names before and after Content-Type
        headers = {"Content-Type": "text/plain", "X-Note": "multipart/mixed", "Accept": "multipart/mixed"}

        assert sent_headers(CurlRequest(headers=dict(headers), form_fields=["a=1"])) == headers

    def test_without_a_form_every_header_is_kept(self):
        headers = {"Content-Type": "multipart/form-data"}

        assert sent_headers(CurlRequest(headers=dict(headers))) == headers


class TestAcceptEncoding:
    """The script decodes what it asks for: requests decodes br and zstd only with optional packages."""

    @pytest.mark.parametrize("value", [
        "gzip, deflate, br, zstd",
        "gzip, deflate, br",
        "br;q=1.0, gzip;q=0.8",
        "*",
        "zstd",
    ])
    def test_a_browsers_list_is_left_to_requests(self, value):
        # Sent as copied, a server answered in zstd, and a script run where
        # only requests is installed printed the compressed bytes
        for name in ("Accept-Encoding", "accept-encoding"):
            request = CurlRequest(headers={name: value, "Accept": "*/*"})

            assert sent_headers(request) == {"Accept": "*/*"}

    @pytest.mark.parametrize("value", ["gzip", "gzip, deflate", "identity", "x-gzip", "gzip, br;q=0", "deflate; q=0.5"])
    def test_one_asking_only_for_what_requests_decodes_is_kept(self, value):
        request = CurlRequest(headers={"Accept-Encoding": value})

        assert sent_headers(request) == {"Accept-Encoding": value}

    def test_the_generated_script_leaves_it_out(self):
        from pybreeze.utils.curl_import.curl_parser import parse_curl
        from pybreeze.utils.curl_import.request_codegen import to_requests_code

        code = to_requests_code(parse_curl(
            "curl https://api.example.test/items -H 'accept: application/json' "
            "-H 'accept-encoding: gzip, deflate, br, zstd'"))

        assert "accept-encoding" not in code.lower()
        assert '"accept": "application/json"' in code
