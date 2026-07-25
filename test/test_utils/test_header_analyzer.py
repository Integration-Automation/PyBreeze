"""Tests for the HTTP header analyzer's pure logic."""
from __future__ import annotations

from pybreeze.utils.header_tools.header_analyzer import (
    LEVEL_INFO,
    LEVEL_WARNING,
    analyze_headers,
    parse_headers,
)


def _codes(text: str) -> set[str]:
    return {finding.code for finding in analyze_headers(text).findings}


def _finding(text: str, code: str):
    return next(f for f in analyze_headers(text).findings if f.code == code)


class TestParseHeaders:
    def test_plain_block(self):
        fields = parse_headers("Content-Type: application/json\nAccept: */*")
        assert [(f.name, f.value) for f in fields] == [
            ("Content-Type", "application/json"), ("Accept", "*/*")]

    def test_status_line_is_skipped(self):
        fields = parse_headers("HTTP/1.1 200 OK\nServer: nginx")
        assert [f.name for f in fields] == ["Server"]

    def test_request_line_is_skipped(self):
        fields = parse_headers("GET /api?a=1 HTTP/1.1\nHost: example.com")
        assert [f.name for f in fields] == ["Host"]

    def test_body_after_blank_line_is_not_parsed(self):
        fields = parse_headers("Content-Type: text/plain\n\nnot-a-header: really")
        assert [f.name for f in fields] == ["Content-Type"]

    def test_value_with_colon_is_kept_whole(self):
        fields = parse_headers("Host: example.com:8080")
        assert fields[0].value == "example.com:8080"

    def test_crlf_line_endings(self):
        fields = parse_headers("A: 1\r\nB: 2\r\n")
        assert [f.name for f in fields] == ["A", "B"]

    def test_duplicates_are_kept(self):
        fields = parse_headers("Set-Cookie: a=1\nSet-Cookie: b=2")
        assert len(fields) == 2

    def test_empty_text(self):
        assert parse_headers("") == []


class TestDuplicates:
    def test_repeated_name_is_counted_and_reported(self):
        analysis = analyze_headers("X-Trace: 1\nx-trace: 2")
        assert analysis.duplicates == {"x-trace": 2}
        assert "duplicate_header" in {f.code for f in analysis.findings}

    def test_repeatable_header_is_counted_but_not_reported(self):
        analysis = analyze_headers("Set-Cookie: a=1; Secure; HttpOnly; SameSite=Lax\n"
                                   "Set-Cookie: b=2; Secure; HttpOnly; SameSite=Lax")
        assert analysis.duplicates == {"set-cookie": 2}
        assert "duplicate_header" not in {f.code for f in analysis.findings}

    def test_duplicate_detail_carries_the_count(self):
        assert _finding("A: 1\nA: 2\nA: 3", "duplicate_header").detail == "3"


class TestSecurityHeaderValues:
    def test_content_type_options_nosniff_is_clean(self):
        assert "content_type_options_not_nosniff" not in _codes(
            "X-Content-Type-Options: nosniff")

    def test_content_type_options_other_value_is_flagged(self):
        assert "content_type_options_not_nosniff" in _codes("X-Content-Type-Options: sniff")

    def test_long_hsts_is_clean(self):
        assert "hsts_weak_max_age" not in _codes(
            "Strict-Transport-Security: max-age=31536000; includeSubDomains")

    def test_short_hsts_is_flagged(self):
        assert _finding("Strict-Transport-Security: max-age=600", "hsts_weak_max_age").detail == "600"

    def test_hsts_without_max_age_is_flagged_as_zero(self):
        assert _finding(
            "Strict-Transport-Security: includeSubDomains", "hsts_weak_max_age").detail == "0"

    def test_csp_unsafe_inline_is_flagged(self):
        finding = _finding("Content-Security-Policy: default-src 'self' 'unsafe-inline'",
                           "csp_unsafe_directive")
        assert finding.detail == "unsafe-inline"

    def test_csp_without_unsafe_directives_is_clean(self):
        assert "csp_unsafe_directive" not in _codes("Content-Security-Policy: default-src 'self'")

    def test_wildcard_cors_is_noted(self):
        assert "cors_wildcard_origin" in _codes("Access-Control-Allow-Origin: *")

    def test_specific_cors_origin_is_clean(self):
        assert "cors_wildcard_origin" not in _codes("Access-Control-Allow-Origin: https://a.com")

    def test_wildcard_cors_with_credentials_is_a_warning(self):
        finding = _finding(
            "Access-Control-Allow-Origin: *\nAccess-Control-Allow-Credentials: true",
            "cors_wildcard_with_credentials")
        assert finding.level == LEVEL_WARNING

    def test_specific_origin_with_credentials_is_clean(self):
        assert "cors_wildcard_with_credentials" not in _codes(
            "Access-Control-Allow-Origin: https://a.com\nAccess-Control-Allow-Credentials: true")


class TestCookieFlags:
    def test_hardened_cookie_is_clean(self):
        codes = _codes("Set-Cookie: sid=abc; Path=/; Secure; HttpOnly; SameSite=Strict")
        assert not codes & {"cookie_not_secure", "cookie_not_httponly", "cookie_no_samesite"}

    def test_bare_cookie_reports_every_missing_flag(self):
        codes = _codes("Set-Cookie: sid=abc; Path=/")
        assert {"cookie_not_secure", "cookie_not_httponly", "cookie_no_samesite"} <= codes

    def test_finding_names_the_cookie_not_its_value(self):
        finding = _finding("Set-Cookie: sid=secret-value; Path=/", "cookie_not_secure")
        assert finding.detail == "sid"

    def test_samesite_is_only_informational(self):
        assert _finding(
            "Set-Cookie: sid=a; Secure; HttpOnly", "cookie_no_samesite").level == LEVEL_INFO


class TestOtherFindings:
    def test_sensitive_header_never_reports_its_value(self):
        finding = _finding("Authorization: Bearer super-secret", "sensitive_header")
        assert finding.detail == ""
        assert "super-secret" not in str(finding)

    def test_server_banner_is_noted(self):
        assert _finding("Server: nginx/1.25.3", "server_banner").detail == "nginx/1.25.3"

    def test_empty_banner_is_ignored(self):
        assert "server_banner" not in _codes("Server:")

    def test_deprecated_header_is_noted(self):
        assert "deprecated_header" in _codes("X-XSS-Protection: 1; mode=block")

    def test_text_type_without_charset_is_noted(self):
        assert "content_type_no_charset" in _codes("Content-Type: text/html")

    def test_text_type_with_charset_is_clean(self):
        assert "content_type_no_charset" not in _codes("Content-Type: text/html; charset=utf-8")

    def test_json_type_is_not_asked_for_a_charset(self):
        assert "content_type_no_charset" not in _codes("Content-Type: application/json")


class TestMissingResponseHeaders:
    def test_response_reports_missing_security_headers(self):
        codes = _codes("HTTP/1.1 200 OK\nContent-Type: text/html; charset=utf-8")
        assert {"missing_hsts", "missing_csp", "missing_content_type_options",
                "missing_frame_options", "missing_referrer_policy"} <= codes

    def test_request_block_is_not_audited_for_response_headers(self):
        codes = _codes("GET /api HTTP/1.1\nHost: example.com\nAccept: */*")
        assert not {code for code in codes if code.startswith("missing_")}

    def test_response_only_header_marks_the_block_as_a_response(self):
        assert analyze_headers("Set-Cookie: a=1").looks_like_response

    def test_present_header_is_not_reported_missing(self):
        assert "missing_csp" not in _codes(
            "HTTP/1.1 200 OK\nContent-Security-Policy: default-src 'self'")


class TestAnalysisShape:
    def test_warnings_come_before_info(self):
        analysis = analyze_headers(
            "HTTP/1.1 200 OK\nServer: nginx\nX-Content-Type-Options: sniff")
        levels = [finding.level for finding in analysis.findings]
        assert levels == sorted(levels, key=lambda level: 0 if level == LEVEL_WARNING else 1)
        assert LEVEL_WARNING in levels

    def test_empty_input_yields_empty_analysis(self):
        analysis = analyze_headers("")
        assert analysis.fields == []
        assert analysis.findings == []
        assert not analysis.looks_like_response

    def test_text_without_headers_yields_no_fields(self):
        assert analyze_headers("just some prose").fields == []
