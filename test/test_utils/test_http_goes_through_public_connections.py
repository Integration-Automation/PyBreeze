"""Every request the IDE sends goes through the connections that pin the checked address.

``validate_url`` alone checks one DNS answer and the request connects on
another. ``public_http`` connects to the address it checks as it connects; a
call straight to ``requests`` or ``urlopen`` would skip that.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pybreeze

_SOURCE = Path(pybreeze.__file__).parent
# Where the pinned session is built
_ALLOWED = {Path("utils/network/public_http.py")}
_REQUESTS_CALLS = {"get", "post", "put", "patch", "delete", "head", "options", "request", "Session", "session"}
_URLLIB_CALLS = {"urlopen"}


def _direct_calls(source: Path) -> list[str]:
    found: list[str] = []
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if isinstance(function, ast.Attribute) and isinstance(function.value, ast.Name):
            if function.value.id == "requests" and function.attr in _REQUESTS_CALLS:
                found.append(f"requests.{function.attr}")
            elif function.attr in _URLLIB_CALLS:
                found.append(function.attr)
        elif isinstance(function, ast.Name) and function.id in _URLLIB_CALLS:
            found.append(function.id)
    return found


def test_no_module_sends_a_request_around_the_pinned_connections():
    offenders = {
        str(source.relative_to(_SOURCE)): calls
        for source in sorted(_SOURCE.rglob("*.py"))
        if source.relative_to(_SOURCE) not in _ALLOWED and (calls := _direct_calls(source))
    }

    assert offenders == {}


def test_the_scan_finds_a_direct_call(tmp_path):
    sample = tmp_path / "sample.py"
    sample.write_text(
        "import requests\nfrom urllib.request import urlopen\n"
        "requests.post('https://x')\nurlopen('https://x')\n"
        "code = 'requests.request(\"GET\", url)'\n",
        encoding="utf-8",
    )

    # The string is generated code, not a call
    assert _direct_calls(sample) == ["requests.post", "urlopen"]
