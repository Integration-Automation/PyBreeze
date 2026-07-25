"""Tests for automation-module script templates generated from curl."""
from __future__ import annotations

import json

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
    def test_form_uses_data_and_files(self):
        code = to_requests_code(parse_curl("curl -F 'name=x' -F 'photo=@a.jpg' https://up"))
        assert "data=data" in code
        assert "files=files" in code
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
        code = to_requests_code(parse_curl("curl -d @body.json https://x"))
        assert 'data = open("body.json", encoding="utf-8").read()' in code
        assert "data=data" in code

    def test_data_file_code_is_valid_python(self):
        compile(to_requests_code(parse_curl("curl -d @body.json https://x")), "<g>", "exec")

    def test_apitestka_python_data_file(self):
        code = to_apitestka_python(parse_curl("curl -d @body.json https://x"))
        assert 'open("body.json", encoding="utf-8").read()' in code
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

    def test_form_data_and_files(self):
        code = to_apitestka_python(parse_curl("curl -F 'name=x' -F 'photo=@a.jpg' https://up"))
        assert "data=" in code
        assert "files=" in code
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

    def test_form_data_fields_included(self):
        action = json.loads(
            to_apitestka_action_json(parse_curl("curl -F 'name=x' -F 'photo=@a.jpg' https://up")))
        # Plain form fields go under "data"; file uploads are omitted (no file handles in JSON).
        assert action[0][1]["data"] == {"name": "x"}


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
