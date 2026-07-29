"""Generate one script covering several recorded requests.

The cURL importer generates a script for a single request; a HAR export holds a
whole session, so the same targets need a form that carries many requests at
once — one pytest file of several tests, one APITestka action list that replays
the flow in order, one ``requests`` script that walks through it.

Each target is built from the same per-request blocks the single-request
templates use, so the two paths cannot drift apart.
"""
from __future__ import annotations

import json
from collections.abc import Callable

from pybreeze.utils.curl_import.curl_parser import CurlRequest
from pybreeze.utils.curl_import.request_codegen import REQUESTS_IMPORT, request_statements
from pybreeze.utils.curl_import.script_templates import (
    APITESTKA_IMPORT,
    LOADDENSITY_IMPORT,
    apitestka_call_block,
    generate_template,
    loaddensity_start_block,
    pytest_function,
    test_function_name,
    to_apitestka_action,
)

# Blank lines between two top-level definitions in generated Python
_BETWEEN_FUNCTIONS = "\n\n\n"


def unique_test_names(requests: list[CurlRequest]) -> list[str]:
    """Derive one pytest function name per request, keeping them unique.

    Two recorded calls to the same endpoint would otherwise define the same
    function twice, and the second would silently replace the first.

    :param requests: the requests to name, in order
    :return: a name per request, suffixed ``_2``, ``_3`` … on a repeat
    """
    names: list[str] = []
    seen: dict[str, int] = {}
    for request in requests:
        base = test_function_name(request)
        seen[base] = seen.get(base, 0) + 1
        names.append(base if seen[base] == 1 else f"{base}_{seen[base]}")
    return names


def _numbered_comment(index: int, request: CurlRequest) -> str:
    """Return the comment introducing one request's block."""
    return f"# {index}. {request.method} {request.full_url}"


def _requests_script(requests: list[CurlRequest]) -> str:
    """Write every request as ``requests`` statements in one script."""
    lines = [REQUESTS_IMPORT]
    for index, request in enumerate(requests, start=1):
        lines.append("")
        lines.append(_numbered_comment(index, request))
        lines.extend(request_statements(request))
        lines.append("print(response.status_code)")
    return "\n".join(lines) + "\n"


def _pytest_script(requests: list[CurlRequest]) -> str:
    """Write every request as its own test in one pytest file."""
    functions = [
        pytest_function(request, name)
        for request, name in zip(requests, unique_test_names(requests), strict=True)
    ]
    return "\n".join([REQUESTS_IMPORT, "", "", _BETWEEN_FUNCTIONS.join(functions)]) + "\n"


def _apitestka_python_script(requests: list[CurlRequest]) -> str:
    """Write every request as an APITestka call in one script."""
    lines = [APITESTKA_IMPORT]
    for index, request in enumerate(requests, start=1):
        lines.append("")
        lines.append(_numbered_comment(index, request))
        lines.append(apitestka_call_block(request))
        lines.append("print(response)")
    return "\n".join(lines) + "\n"


def _apitestka_action_script(requests: list[CurlRequest]) -> str:
    """Collect every request into one action list, replayed in capture order."""
    actions = [to_apitestka_action(request) for request in requests]
    return json.dumps(actions, indent=4, ensure_ascii=False) + "\n"


def _loaddensity_script(requests: list[CurlRequest]) -> str:
    """Write one load test per request.

    The shared Locust task template holds one URL per HTTP method, so merging
    the requests into a single ``tasks`` dict would quietly drop all but the last
    ``GET``. Each request therefore gets its own run to edit or delete.
    """
    lines = [
        LOADDENSITY_IMPORT,
        "",
        "# One run per captured request: the shared task template drives one URL",
        "# per HTTP method, so merging them would drop all but the last of each.",
    ]
    for index, request in enumerate(requests, start=1):
        lines.append("")
        lines.append(_numbered_comment(index, request))
        lines.append(loaddensity_start_block(request))
    return "\n".join(lines) + "\n"


# Target key -> the generator that writes several requests into one script.
_BATCH_GENERATORS: dict[str, Callable[[list[CurlRequest]], str]] = {
    "requests": _requests_script,
    "pytest": _pytest_script,
    "apitestka_python": _apitestka_python_script,
    "apitestka_action": _apitestka_action_script,
    "loaddensity_python": _loaddensity_script,
}


def generate_har_script(target: str, requests: list[CurlRequest]) -> str:
    """Generate one script for *target* covering every request in *requests*.

    A single request produces exactly what the cURL importer would produce for
    it, so the two tools agree.

    :param target: a target key from ``TEMPLATE_TARGETS``
    :param requests: the requests to write, in capture order
    :return: the generated script, or an empty string when there is nothing to write
    """
    if not requests:
        return ""
    if len(requests) == 1:
        return generate_template(target, requests[0])
    generator = _BATCH_GENERATORS.get(target, _requests_script)
    return generator(requests)
