"""Tests for automation-module script templates generated from curl."""
from __future__ import annotations

import json

import pytest

from pybreeze.utils.curl_import.curl_parser import parse_curl
from pybreeze.utils.curl_import.request_body import body_kind, form_parts
from pybreeze.utils.curl_import.request_codegen import to_requests_code
from pybreeze.utils.curl_import.script_templates import (
    TEMPLATE_TARGETS,
    generate_template,
    to_apitestka_action_json,
    to_apitestka_python,
    to_loaddensity_python,
    to_pytest_test,
)
# Aliased so pytest does not collect this ``test_``-prefixed helper as a test.
from pybreeze.utils.curl_import.script_templates import (
    test_function_name as derive_test_function_name,
)


class TestBodyKind:
    def test_no_body(self):
        assert body_kind(parse_curl("curl https://x")) is None

    def test_json_body(self):
        request = parse_curl(
            "curl -H 'Content-Type: application/json' -d '{\"a\": 1}' https://x")
        assert body_kind(request) == ("json", {"a": 1})

    def test_non_json_body_is_data(self):
        assert body_kind(parse_curl("curl -d 'a=1&b=2' https://x")) == ("data", "a=1&b=2")

    def test_json_content_type_but_invalid_body_is_data(self):
        request = parse_curl("curl -H 'Content-Type: application/json' -d 'not json' https://x")
        assert body_kind(request) == ("data", "not json")

    @pytest.mark.parametrize("body", [
        '{"a": 1, "a": 2}',                  # the object kept only the last
        '{"p": 0.10000000000000000001}',     # the float wrote back 0.1
        '{"x": 1e400}',                      # inf
        '[NaN]',                             # not JSON
        "[" * 5000 + "]" * 5000,             # RecursionError out of the tab
        "[" * 102 + "]" * 102,               # too deep to write as a literal
    ], ids=["repeated-key", "long-float", "inf", "nan", "past-the-parser", "past-a-literal"])
    def test_a_body_the_object_would_not_send_back_as_it_was_goes_raw(self, body):
        request = parse_curl(f"curl -H 'Content-Type: application/json' -d '{body}' https://x")

        assert body_kind(request) == ("data", body)
        for target, _label in TEMPLATE_TARGETS:
            generate_template(target, request)
        compile(to_requests_code(request), "generated", "exec")

    def test_numbers_a_float_holds_still_go_as_json(self):
        request = parse_curl(
            "curl -H 'Content-Type: application/json' -d '{\"p\": 0.1, \"q\": 1E3, \"n\": 12345678901234567890}' https://x")

        assert body_kind(request) == ("json", {"p": 0.1, "q": 1000.0, "n": 12345678901234567890})


class TestFormParts:
    def test_plain_field(self):
        data, files = form_parts(parse_curl("curl -F 'name=widget' https://x"))
        assert data == {"name": "widget"}
        assert files == {}

    def test_file_field(self):
        data, files = form_parts(parse_curl("curl -F 'photo=@a.jpg' https://x"))
        assert data == {}
        assert files == {"photo": "a.jpg"}

    def test_file_type_suffix_stripped(self):
        data, files = form_parts(parse_curl("curl -F 'f=@a.png;type=image/png' https://x"))
        assert files == {"f": "a.png"}

    def test_mixed(self):
        data, files = form_parts(parse_curl("curl -F 'a=1' -F 'b=@f.txt' https://x"))
        assert data == {"a": "1"}
        assert files == {"b": "f.txt"}


class TestRequestsCodeForm:
    def test_every_form_field_goes_in_files(self):
        # data= made requests send a text-only form URL-encoded; curl sends multipart
        code = to_requests_code(parse_curl("curl -F 'name=x' -F 'photo=@a.jpg' https://up"))
        assert "data=data" not in code
        assert "files=files" in code
        assert '"name": (None, "x"),' in code
        assert 'open("a.jpg", "rb")' in code

    def test_form_code_is_valid_python(self):
        code = to_requests_code(parse_curl("curl -F 'name=x' -F 'photo=@a.jpg' https://up"))
        compile(code, "<generated>", "exec")

    def test_ignored_flag_url_correct_in_code(self):
        code = to_requests_code(parse_curl("curl --max-time 30 https://api.example.com/x"))
        assert 'url = "https://api.example.com/x"' in code


class TestRequestsCodeJsonFlagAndDataFile:
    def test_json_flag_uses_json_kwarg(self):
        code = to_requests_code(parse_curl("curl --json '{\"a\": 1}' https://x"))
        assert "json=json_body" in code
        assert "json_body = {" in code

    def test_data_file_reads_file(self):
        # As curl does for -d: the bytes, without carriage returns and newlines
        code = to_requests_code(parse_curl("curl -d @body.json https://x"))
        assert 'data = open("body.json", "rb").read().replace(b"\\r", b"").replace(b"\\n", b"")' in code
        assert "data=data" in code

    def test_data_file_code_is_valid_python(self):
        compile(to_requests_code(parse_curl("curl -d @body.json https://x")), "<g>", "exec")

    def test_apitestka_python_data_file(self):
        code = to_apitestka_python(parse_curl("curl -d @body.json https://x"))
        assert 'open("body.json", "rb").read()' in code
        compile(code, "<g>", "exec")


class TestApitestkaPython:
    def test_imports_and_calls(self):
        code = to_apitestka_python(parse_curl("curl https://example.com/api"))
        assert "from je_api_testka import test_api_method_requests" in code
        assert "test_api_method_requests(" in code
        assert 'test_url="https://example.com/api"' in code

    def test_method(self):
        code = to_apitestka_python(parse_curl("curl -X DELETE https://x"))
        assert '"DELETE"' in code

    def test_headers(self):
        code = to_apitestka_python(parse_curl("curl -H 'Accept: application/json' https://x"))
        assert "headers=" in code

    def test_json_body_uses_json_kwarg(self):
        code = to_apitestka_python(
            parse_curl("curl -H 'Content-Type: application/json' -d '{\"a\": 1}' https://x"))
        assert "json=" in code

    def test_form_body_uses_data_kwarg(self):
        code = to_apitestka_python(parse_curl("curl -d 'a=1' https://x"))
        assert "data=" in code

    def test_auth(self):
        code = to_apitestka_python(parse_curl("curl -u user:pass https://x"))
        assert "auth=(" in code

    def test_cookies(self):
        code = to_apitestka_python(parse_curl("curl -b 'a=1; b=2' https://x"))
        assert "cookies=" in code

    def test_params(self):
        code = to_apitestka_python(parse_curl("curl -G https://x -d 'a=1'"))
        assert "params=" in code

    def test_is_valid_python(self):
        command = (
            "curl -X POST https://example.com/api "
            "-H 'Content-Type: application/json' -d '{\"name\": \"a\"}'"
        )
        compile(to_apitestka_python(parse_curl(command)), "<generated>", "exec")

    def test_form_fields_and_files_go_in_files(self):
        code = to_apitestka_python(parse_curl("curl -F 'name=x' -F 'photo=@a.jpg' https://up"))
        assert "data=" not in code
        assert '"name": (None, "x")' in code
        assert 'open("a.jpg", "rb")' in code
        compile(code, "<generated>", "exec")


class TestApitestkaActionJson:
    def test_is_valid_json(self):
        action = json.loads(to_apitestka_action_json(parse_curl("curl https://x")))
        assert action == [["AT_test_api_method", {"http_method": "GET", "test_url": "https://x"}]]

    def test_headers_included(self):
        action = json.loads(
            to_apitestka_action_json(parse_curl("curl -H 'Accept: text/html' https://x")))
        assert action[0][1]["headers"] == {"Accept": "text/html"}

    def test_post_with_json_body(self):
        command = "curl -H 'Content-Type: application/json' -d '{\"a\": 1}' https://x"
        action = json.loads(to_apitestka_action_json(parse_curl(command)))
        params = action[0][1]
        assert params["http_method"] == "POST"
        assert params["json"] == {"a": 1}

    def test_form_body_uses_data_key(self):
        action = json.loads(to_apitestka_action_json(parse_curl("curl -d 'a=1' https://x")))
        assert action[0][1]["data"] == "a=1"

    def test_auth_as_list(self):
        action = json.loads(to_apitestka_action_json(parse_curl("curl -u user:pass https://x")))
        assert action[0][1]["auth"] == ["user", "pass"]

    def test_cookies_included(self):
        action = json.loads(to_apitestka_action_json(parse_curl("curl -b 'a=1' https://x")))
        assert action[0][1]["cookies"] == {"a": "1"}

    def test_get_flag_params(self):
        action = json.loads(to_apitestka_action_json(parse_curl("curl -G https://x -d 'a=1'")))
        assert action[0][1]["params"] == {"a": "1"}

    def test_form_text_fields_are_sent_as_multipart(self):
        action = json.loads(to_apitestka_action_json(parse_curl("curl -F 'name=x' -F 'a=b' https://up")))
        # [null, text] is requests' (None, text): a multipart field, as curl sends it
        assert action[0][1]["files"] == {"name": [None, "x"], "a": [None, "b"]}
        assert "data" not in action[0][1]

    @pytest.mark.parametrize("command", [
        "curl -F 'name=x' -F 'photo=@a.jpg' https://up",
        "curl -d @body.json -H 'Content-Type: application/json' https://up",
    ])
    def test_a_file_it_cannot_open_is_refused_not_left_out(self, command):
        # The upload, or the body read from a file, was left out without a word
        from pybreeze.utils.exception.exceptions import CurlParseException

        with pytest.raises(CurlParseException):
            to_apitestka_action_json(parse_curl(command))


class TestLoadDensityPython:
    def test_imports_and_calls_start_test(self):
        code = to_loaddensity_python(parse_curl("curl https://example.com/api"))
        assert "from je_load_density import start_test" in code
        assert "start_test(" in code

    def test_task_has_method_and_url(self):
        code = to_loaddensity_python(parse_curl("curl -X POST https://x/api -d 'a=1'"))
        assert '"post": {"request_url": "https://x/api"}' in code

    def test_get_method(self):
        code = to_loaddensity_python(parse_curl("curl https://x"))
        assert '"get": {"request_url": "https://x"}' in code

    def test_is_valid_python(self):
        compile(to_loaddensity_python(parse_curl("curl https://x")), "<generated>", "exec")

    def test_url_query_kept_in_request_url(self):
        code = to_loaddensity_python(parse_curl("curl 'https://x/api?a=1&b=2'"))
        assert '"request_url": "https://x/api?a=1&b=2"' in code

    def test_get_flag_params_kept_in_request_url(self):
        code = to_loaddensity_python(parse_curl("curl -G https://x/api -d 'a=1'"))
        assert '"request_url": "https://x/api?a=1"' in code


class TestTestFunctionName:
    def test_from_path(self):
        assert derive_test_function_name(parse_curl("curl https://x/v1/items")) == "test_get_v1_items"

    def test_method_prefix(self):
        assert derive_test_function_name(parse_curl("curl -X POST https://x/a")) == "test_post_a"

    def test_sanitises_non_identifier_chars(self):
        name = derive_test_function_name(parse_curl("curl 'https://x/a-b.c/d'"))
        assert name.isidentifier()
        assert name == "test_get_a_b_c_d"

    def test_no_path_uses_host(self):
        name = derive_test_function_name(parse_curl("curl https://api.example.com"))
        assert name == "test_get_api_example_com"


class TestToPytestTest:
    def test_defines_test_function(self):
        code = to_pytest_test(parse_curl("curl https://x/v1/items"))
        assert "def test_get_v1_items():" in code

    def test_imports_requests(self):
        assert "import requests" in to_pytest_test(parse_curl("curl https://x"))

    def test_asserts_status(self):
        assert "assert response.status_code == 200" in to_pytest_test(parse_curl("curl https://x"))

    def test_statements_are_indented(self):
        code = to_pytest_test(parse_curl("curl https://x"))
        assert "    url = " in code
        assert "    response = requests.request(" in code

    def test_is_valid_python(self):
        command = (
            "curl -X POST https://example.com/api "
            "-H 'Content-Type: application/json' -d '{\"name\": \"a\"}'"
        )
        compile(to_pytest_test(parse_curl(command)), "<generated>", "exec")

    def test_with_headers_and_auth(self):
        command = "curl -u user:pass -H 'Accept: application/json' https://x/data"
        code = to_pytest_test(parse_curl(command))
        assert "    headers = {" in code
        assert "    auth = (" in code
        compile(code, "<generated>", "exec")


class TestGenerateTemplate:
    def test_targets_are_registered(self):
        keys = [key for key, _label in TEMPLATE_TARGETS]
        assert keys == [
            "requests", "pytest", "apitestka_python", "apitestka_action", "loaddensity_python"]

    def test_pytest_target(self):
        code = generate_template("pytest", parse_curl("curl https://x"))
        assert "def test_" in code

    def test_loaddensity_target(self):
        code = generate_template("loaddensity_python", parse_curl("curl https://x"))
        assert "start_test" in code

    def test_requests_target(self):
        code = generate_template("requests", parse_curl("curl https://x"))
        assert "import requests" in code

    def test_apitestka_python_target(self):
        code = generate_template("apitestka_python", parse_curl("curl https://x"))
        assert "test_api_method_requests" in code

    def test_apitestka_action_target(self):
        code = generate_template("apitestka_action", parse_curl("curl https://x"))
        assert "AT_test_api_method" in code

    def test_unknown_target_falls_back_to_requests(self):
        code = generate_template("nope", parse_curl("curl https://x"))
        assert "import requests" in code


class TestMethodsInGeneratedCode:
    def test_a_method_that_is_not_a_token_is_refused(self):
        import pytest

        from pybreeze.utils.exception.exceptions import CurlParseException

        with pytest.raises(CurlParseException, match="not an HTTP method"):
            parse_curl("curl -X 'GET():\n    import os\ndef t' https://x/a")

    def test_a_method_with_a_hyphen_makes_a_valid_test_name(self):
        import ast

        from pybreeze.utils.curl_import.script_templates import to_pytest_test

        code = to_pytest_test(parse_curl("curl -X M-SEARCH https://x/a"))

        assert "def test_m_search_a():" in code
        ast.parse(code)


class TestJsonBodiesInGeneratedPython:
    """A JSON body is written as Python: true/false/null would be undefined names."""

    _COMMAND = (
        "curl https://x/api -H 'Content-Type: application/json' "
        "-d '{\"a\": true, \"b\": null, \"c\": [1.5, {\"d\": false}], \"e\": \"x\"}'"
    )

    def test_every_python_target_is_free_of_json_names(self):
        import ast

        from pybreeze.utils.curl_import.script_templates import generate_template

        request = parse_curl(self._COMMAND)
        for target in ("requests", "pytest", "apitestka_python"):
            tree = ast.parse(generate_template(target, request))
            names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
            assert not names & {"true", "false", "null"}, target

    def test_the_body_evaluates_to_what_was_sent(self):
        import ast

        code = to_requests_code(parse_curl(self._COMMAND))
        assignment = next(
            node for node in ast.parse(code).body
            if isinstance(node, ast.Assign) and node.targets[0].id == "json_body")

        assert ast.literal_eval(assignment.value) == {
            "a": True, "b": None, "c": [1.5, {"d": False}], "e": "x"}


def test_python_literal_round_trips_any_json_value():
    import ast

    from hypothesis import given, settings
    from hypothesis import strategies as st

    from pybreeze.utils.curl_import.request_codegen import python_literal

    scalars = st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False, allow_infinity=False) | st.text()
    values = st.recursive(
        scalars,
        lambda children: st.lists(children, max_size=4)
        | st.dictionaries(st.text(), children, max_size=4),
        max_leaves=20)

    @settings(max_examples=200, deadline=None)
    @given(values, st.booleans())
    def round_trip(value, inline):
        assert ast.literal_eval(python_literal(value, inline=inline)) == value

    round_trip()


def test_a_float_json_allows_but_python_cannot_write_is_spelled_out():
    from pybreeze.utils.curl_import.request_codegen import python_literal

    assert python_literal(float("inf")) == 'float("inf")'
    assert python_literal([float("-inf")], inline=True) == '[float("-inf")]'
    assert python_literal(float("nan")) == 'float("nan")'


def test_a_character_outside_the_bmp_stays_one_character():
    import ast

    from pybreeze.utils.curl_import.request_codegen import python_string

    text = "h\u00e9llo \U0001F600 \U00020000"
    assert ast.literal_eval(python_string(text)) == text
    assert "\\ud83d" not in python_string("\U0001F600")
    lone = "lone \ud800"
    assert ast.literal_eval(python_string(lone)) == lone

