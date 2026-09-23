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
from pybreeze.utils.curl_import.request_body import body_kind, form_entries, sent_headers
from pybreeze.utils.exception.exception_tags import action_cannot_read_files_error
from pybreeze.utils.exception.exceptions import CurlParseException
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.curl_import.request_codegen import (
    REQUESTS_IMPORT, cookie_file_notes, data_from_file_expr, form_has_repeats, form_value_expr, python_literal,
    python_string, request_statements, to_requests_code,
)

# APITestka action command that performs an HTTP request
_APITESTKA_ACTION = "AT_test_api_method"
# Import line each generated automation-module script starts with
APITESTKA_IMPORT = "from je_api_testka import test_api_method_requests"
LOADDENSITY_IMPORT = "from je_load_density import start_test"
# Default status asserted in a generated pytest test
_DEFAULT_EXPECTED_STATUS = 200
# Indentation for statements inside a generated test function
_TEST_INDENT = "    "


def _inline_json(value: object) -> str:
    """Render *value* as a compact one-line JSON literal for inline code."""
    return json.dumps(value, ensure_ascii=False)


def _inline_form(request: CurlRequest) -> str:
    """The ``files`` value, one line, every form field in it: a dict, or pairs when a field repeats."""
    entries = form_entries(request)
    values = [(python_string(entry[0]), form_value_expr(entry)) for entry in entries]
    if form_has_repeats(entries):
        return "[" + ", ".join(f"({name}, {value})" for name, value in values) + "]"
    return "{" + ", ".join(f"{name}: {value}" for name, value in values) + "}"


def _apitestka_payload_lines(request: CurlRequest) -> list[str]:
    """Return the inline ``data=`` / ``files=`` / ``json=`` kwargs for the payload."""
    if request.has_form:
        # Every field in files=, so the form is sent as multipart, as curl sends it
        return [f"    files={_inline_form(request)},"] if form_entries(request) else []
    if request.data_file_refs:
        return [f"    data={data_from_file_expr(request)},"]
    kind = body_kind(request)
    if kind is None:
        return []
    value = python_literal(kind[1], inline=True) if kind[0] == "json" else _inline_json(kind[1])
    return [f"    {kind[0]}={value},"]


def apitestka_call_block(request: CurlRequest) -> str:
    """Return the ``test_api_method_requests(...)`` call for *request*.

    The call is returned without the import, so several requests can be written
    into one script.

    :param request: the parsed request
    :return: the call statement, as one block
    """
    lines = cookie_file_notes(request) + [
        "response = test_api_method_requests(",
        f"    {_inline_json(request.method)},",
        f"    test_url={_inline_json(request.url)},",
    ]
    if sent_headers(request):
        lines.append(f"    headers={_inline_json(sent_headers(request))},")
    if request.params:
        lines.append(f"    params={_inline_json(request.params)},")
    if request.cookies:
        lines.append(f"    cookies={_inline_json(request.cookies)},")
    lines.extend(_apitestka_payload_lines(request))
    if request.username is not None:
        lines.append(
            f"    auth=({_inline_json(request.username)}, "
            f"{_inline_json(request.password or '')}),")
    lines.append(")")
    return "\n".join(lines)


def to_apitestka_python(request: CurlRequest) -> str:
    """Generate an APITestka Python snippet for *request*.

    :param request: the parsed curl request
    :return: Python source calling ``test_api_method_requests``
    """
    lines = [APITESTKA_IMPORT, "", apitestka_call_block(request), "", "print(response)"]
    return "\n".join(lines) + "\n"


def loaddensity_start_block(request: CurlRequest) -> str:
    """Return the ``start_test(...)`` call that load-tests *request*.

    The call is returned without the import, so several requests can be written
    into one script.

    :param request: the parsed request
    :return: the call statement, as one block
    """
    method_key = request.method.lower()
    # Drive by the full URL so query params (from the URL or -G) are not lost.
    task = f"{{{_inline_json(method_key)}: {{\"request_url\": {_inline_json(request.full_url)}}}}}"
    lines = [
        "start_test(",
        '    {"user": "fast_http_user"},',
        "    user_count=50,",
        "    spawn_rate=10,",
        "    test_time=60,",
        f"    tasks={task},",
        ")",
    ]
    return "\n".join(lines)


def to_loaddensity_python(request: CurlRequest) -> str:
    """Generate a LoadDensity (Locust) load-test snippet for *request*.

    The basic Locust task issues the request by URL; headers and bodies are noted
    but not sent, because the shared task template drives requests by URL only.

    :param request: the parsed curl request
    :return: Python source calling ``start_test``
    """
    lines = [
        LOADDENSITY_IMPORT,
        "",
        "# Load-test the endpoint captured from the curl command.",
        "# This basic task issues the request by URL; add headers/body in a custom",
        "# Locust task if the endpoint needs them.",
        loaddensity_start_block(request),
    ]
    return "\n".join(lines) + "\n"


def _apitestka_action_params(request: CurlRequest) -> dict:
    """Build the parameter dict for an ``AT_test_api_method`` action."""
    params: dict = {"http_method": request.method, "test_url": request.url}
    if sent_headers(request):
        params["headers"] = sent_headers(request)
    if request.params:
        params["params"] = request.params
    if request.cookies:
        params["cookies"] = request.cookies
    _apply_action_payload(request, params)
    if request.username is not None:
        params["auth"] = [request.username, request.password or ""]
    return params


def _apply_action_payload(request: CurlRequest, params: dict) -> None:
    """Add the body / form payload to an action's parameter dict.

    A form's text fields go in ``files`` as ``[null, text]``, which ``requests``
    reads as ``(None, text)``, so the form is sent as multipart, as curl sends
    it (``data`` sent it URL-encoded).

    :raises CurlParseException: for a file upload or a body read from a file.
        JSON cannot open a file, and the action was generated without them, as
        if the request had none.
    """
    if request.has_form:
        entries = form_entries(request)
        if any(is_file for _name, is_file, _value in entries):
            pybreeze_logger.error(action_cannot_read_files_error)
            raise CurlParseException(action_cannot_read_files_error)
        if form_has_repeats(entries):
            params["files"] = [[name, [None, value]] for name, _is_file, value in entries]
        elif entries:
            params["files"] = {name: [None, value] for name, _is_file, value in entries}
        return
    if request.data_file_refs or request.cookie_files:
        pybreeze_logger.error(action_cannot_read_files_error)
        raise CurlParseException(action_cannot_read_files_error)
    kind = body_kind(request)
    if kind is not None:
        params[kind[0]] = kind[1]


def to_apitestka_action(request: CurlRequest) -> list:
    """Return the single ``["AT_test_api_method", {...}]`` action for *request*.

    Returned as data rather than text so several requests can be collected into
    one action list.

    :param request: the parsed request
    :return: the action pair
    """
    return [_APITESTKA_ACTION, _apitestka_action_params(request)]


def to_apitestka_action_json(request: CurlRequest) -> str:
    """Generate an APITestka JSON action list for *request*.

    The result is a JSON document ``execute_files`` can run directly.

    :param request: the parsed curl request
    :return: a formatted JSON action list
    """
    return json.dumps([to_apitestka_action(request)], indent=4, ensure_ascii=False) + "\n"


def test_function_name(request: CurlRequest) -> str:
    """Derive a pytest function name from the request's method and URL path.

    :param request: the parsed curl request
    :return: a valid ``test_...`` identifier, e.g. ``test_get_v1_items``
    """
    parsed = urlparse(request.url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    slug_source = "_".join(segments) if segments else (parsed.hostname or "request")
    slug = re.sub(r"[^0-9A-Za-z]+", "_", slug_source).strip("_").lower()
    method = re.sub(r"[^0-9A-Za-z]+", "_", request.method).strip("_").lower()
    name = re.sub(r"_+", "_", f"test_{method}_{slug}").rstrip("_")
    return name or "test_request"


def _indent(block: str) -> str:
    """Indent every non-empty line of *block* for a function body."""
    return "\n".join(
        f"{_TEST_INDENT}{line}" if line else line for line in block.split("\n"))


def pytest_function(request: CurlRequest, name: str | None = None) -> str:
    """Return the pytest function for *request*, without the import line.

    :param request: the parsed request
    :param name: function name to use; derived from the request when omitted,
        which a caller writing several tests into one file overrides to keep the
        names unique
    :return: the function definition, as one block
    """
    lines = [f"def {name or test_function_name(request)}():"]
    lines.extend(_indent(statement) for statement in request_statements(request))
    lines.append(f"{_TEST_INDENT}assert response.status_code == {_DEFAULT_EXPECTED_STATUS}")
    lines.append(f"{_TEST_INDENT}# Add assertions on response.json() / response.text as needed")
    return "\n".join(lines)


def to_pytest_test(request: CurlRequest) -> str:
    """Generate a runnable pytest test that sends *request* and asserts the status.

    :param request: the parsed curl request
    :return: Python source defining a ``test_...`` function
    """
    return "\n".join([REQUESTS_IMPORT, "", "", pytest_function(request)]) + "\n"


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
