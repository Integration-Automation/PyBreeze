"""Generate automation-module script templates from a parsed curl request.

Beyond plain ``requests`` code, an automation engineer usually wants the request
expressed in the framework they actually run. This module turns a
:class:`CurlRequest` into:

- an APITestka Python snippet (``test_api_method_requests(...)``), and
- an APITestka JSON *action* (the ``[["AT_test_api_method", {...}]]`` shape that
  ``execute_files`` runs).

Everything here is pure text generation; nothing is executed or sent.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from pybreeze.utils.curl_import.curl_parser import CurlRequest
from pybreeze.utils.curl_import.request_body import body_kind, form_parts
from pybreeze.utils.curl_import.request_codegen import (
    data_from_file_expr, request_statements, to_requests_code
)

# APITestka action command that performs an HTTP request
_APITESTKA_ACTION = "AT_test_api_method"
# Default status asserted in a generated pytest test
_DEFAULT_EXPECTED_STATUS = 200
# Indentation for statements inside a generated test function
_TEST_INDENT = "    "


def _inline_json(value: object) -> str:
    """Render *value* as a compact one-line JSON literal for inline code."""
    return json.dumps(value, ensure_ascii=False)


def _apitestka_payload_lines(request: CurlRequest) -> list[str]:
    """Return the inline ``data=`` / ``files=`` / ``json=`` kwargs for the payload."""
    if request.form_fields:
        data_fields, file_fields = form_parts(request)
        lines = []
        if data_fields:
            lines.append(f"    data={_inline_json(data_fields)},")
        if file_fields:
            uploads = ", ".join(
                f"{_inline_json(field)}: open({_inline_json(name)}, \"rb\")"
                for field, name in file_fields.items())
            lines.append(f"    files={{{uploads}}},")
        return lines
    if request.data_file_refs:
        return [f"    data={data_from_file_expr(request)},"]
    kind = body_kind(request)
    return [f"    {kind[0]}={_inline_json(kind[1])},"] if kind is not None else []


def to_apitestka_python(request: CurlRequest) -> str:
    """Generate an APITestka Python snippet for *request*.

    :param request: the parsed curl request
    :return: Python source calling ``test_api_method_requests``
    """
    lines = [
        "from je_api_testka import test_api_method_requests",
        "",
        "response = test_api_method_requests(",
        f"    {_inline_json(request.method)},",
        f"    test_url={_inline_json(request.url)},",
    ]
    if request.headers:
        lines.append(f"    headers={_inline_json(request.headers)},")
    if request.params:
        lines.append(f"    params={_inline_json(request.params)},")
    lines.extend(_apitestka_payload_lines(request))
    if request.username is not None:
        lines.append(
            f"    auth=({_inline_json(request.username)}, "
            f"{_inline_json(request.password or '')}),")
    lines.append(")")
    lines.append("")
    lines.append("print(response)")
    return "\n".join(lines) + "\n"


def to_loaddensity_python(request: CurlRequest) -> str:
    """Generate a LoadDensity (Locust) load-test snippet for *request*.

    The basic Locust task issues the request by URL; headers and bodies are noted
    but not sent, because the shared task template drives requests by URL only.

    :param request: the parsed curl request
    :return: Python source calling ``start_test``
    """
    method_key = request.method.lower()
    # Drive by the full URL so query params (from the URL or -G) are not lost.
    task = f"{{{_inline_json(method_key)}: {{\"request_url\": {_inline_json(request.full_url)}}}}}"
    lines = [
        "from je_load_density import start_test",
        "",
        "# Load-test the endpoint captured from the curl command.",
        "# This basic task issues the request by URL; add headers/body in a custom",
        "# Locust task if the endpoint needs them.",
        "start_test(",
        '    {"user": "fast_http_user"},',
        "    user_count=50,",
        "    spawn_rate=10,",
        "    test_time=60,",
        f"    tasks={task},",
        ")",
    ]
    return "\n".join(lines) + "\n"


def _apitestka_action_params(request: CurlRequest) -> dict:
    """Build the parameter dict for an ``AT_test_api_method`` action."""
    params: dict = {"http_method": request.method, "test_url": request.url}
    if request.headers:
        params["headers"] = request.headers
    if request.params:
        params["params"] = request.params
    _apply_action_payload(request, params)
    if request.username is not None:
        params["auth"] = [request.username, request.password or ""]
    return params


def _apply_action_payload(request: CurlRequest, params: dict) -> None:
    """Add the body / form payload to an action's parameter dict.

    JSON cannot carry file handles, so multipart file uploads are not represented
    here; only the plain form fields are. Use a Python target for file uploads.
    """
    if request.form_fields:
        data_fields, _file_fields = form_parts(request)
        if data_fields:
            params["data"] = data_fields
        return
    kind = body_kind(request)
    if kind is not None:
        params[kind[0]] = kind[1]


def to_apitestka_action_json(request: CurlRequest) -> str:
    """Generate an APITestka JSON action list for *request*.

    The result is a JSON document ``execute_files`` can run directly.

    :param request: the parsed curl request
    :return: a formatted JSON action list
    """
    action = [[_APITESTKA_ACTION, _apitestka_action_params(request)]]
    return json.dumps(action, indent=4, ensure_ascii=False) + "\n"


def test_function_name(request: CurlRequest) -> str:
    """Derive a pytest function name from the request's method and URL path.

    :param request: the parsed curl request
    :return: a valid ``test_...`` identifier, e.g. ``test_get_v1_items``
    """
    parsed = urlparse(request.url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    slug_source = "_".join(segments) if segments else (parsed.hostname or "request")
    slug = re.sub(r"[^0-9A-Za-z]+", "_", slug_source).strip("_").lower()
    name = f"test_{request.method.lower()}_{slug}".rstrip("_")
    return name or "test_request"


def _indent(block: str) -> str:
    """Indent every non-empty line of *block* for a function body."""
    return "\n".join(
        f"{_TEST_INDENT}{line}" if line else line for line in block.split("\n"))


def to_pytest_test(request: CurlRequest) -> str:
    """Generate a runnable pytest test that sends *request* and asserts the status.

    :param request: the parsed curl request
    :return: Python source defining a ``test_...`` function
    """
    lines = ["import requests", "", "", f"def {test_function_name(request)}():"]
    lines.extend(_indent(statement) for statement in request_statements(request))
    lines.append(f"{_TEST_INDENT}assert response.status_code == {_DEFAULT_EXPECTED_STATUS}")
    lines.append(f"{_TEST_INDENT}# Add assertions on response.json() / response.text as needed")
    return "\n".join(lines) + "\n"


# Target key -> (i18n label key, generator). The first entry is the default.
# Only HTTP-oriented modules are offered: a curl command is an HTTP request, which
# maps to APITestka and LoadDensity but not to browser (WebRunner) or desktop-GUI
# (AutoControl) automation.
TEMPLATE_TARGETS: list[tuple[str, str]] = [
    ("requests", "curl_import_target_requests"),
    ("pytest", "curl_import_target_pytest"),
    ("apitestka_python", "curl_import_target_apitestka_python"),
    ("apitestka_action", "curl_import_target_apitestka_action"),
    ("loaddensity_python", "curl_import_target_loaddensity_python"),
]

_GENERATORS = {
    "requests": to_requests_code,
    "pytest": to_pytest_test,
    "apitestka_python": to_apitestka_python,
    "apitestka_action": to_apitestka_action_json,
    "loaddensity_python": to_loaddensity_python,
}


def generate_template(target: str, request: CurlRequest) -> str:
    """Generate the template for *target*, falling back to ``requests`` code.

    :param target: a target key from :data:`TEMPLATE_TARGETS`
    :param request: the parsed curl request
    :return: the generated template text
    """
    generator = _GENERATORS.get(target, to_requests_code)
    return generator(request)
