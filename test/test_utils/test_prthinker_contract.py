"""PyBreeze's side of the prthinker command line, checked against the real prthinker.

prthinker is not on PyPI and needs Python 3.12 or newer, so these run only where
an interpreter with prthinker installed is at hand: the one running the tests
(CI's 3.12 leg installs it), or one named by ``PYBREEZE_PRTHINKER_PYTHON``.

Each case runs the real CLI with the arguments and the environment PyBreeze
builds, with the backend and the forge pointed at a closed local port. Reaching
the network (``ConnectError``) means prthinker accepted every argument and every
variable. A rename on either side stops it earlier instead, with
"unrecognized arguments", "is required" or "is not a valid".
"""
from __future__ import annotations

import importlib.util
import json
import os
import socket
import subprocess
import sys

import pytest

from pybreeze.extend.prthinker_extend.prthinker_setting import (
    BACKENDS, DEFAULT_SETTING, PRTHINKER_PACKAGE, environment_for, review_file_arguments,
    review_pr_arguments
)
from pybreeze.utils.subprocess_util import utf8_subprocess_env

_RUN_TIMEOUT_SECONDS = 120
_REJECTIONS = ("unrecognized arguments", "is required", "is not a valid", "invalid choice")


def _prthinker_python() -> str | None:
    named = os.environ.get("PYBREEZE_PRTHINKER_PYTHON")
    if named:
        return named
    if importlib.util.find_spec(PRTHINKER_PACKAGE) is not None:
        return sys.executable
    return None


PRTHINKER_PYTHON = _prthinker_python()
pytestmark = pytest.mark.skipif(
    PRTHINKER_PYTHON is None,
    reason="prthinker is not installed here (set PYBREEZE_PRTHINKER_PYTHON to run these)")


@pytest.fixture
def closed_url() -> str:
    """An address on this machine where nothing listens."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    return f"http://127.0.0.1:{port}"


def _run(arguments: list[str], setting: dict, cwd) -> subprocess.CompletedProcess:
    # The same environment TaskProcessManager gives the child.
    environment = {**utf8_subprocess_env("utf-8"), **environment_for(setting)}
    return subprocess.run(  # noqa: S603 — fixed interpreter and argv built by the code under test
        [PRTHINKER_PYTHON, "-m", PRTHINKER_PACKAGE, *arguments],
        cwd=cwd, env=environment, stdin=subprocess.DEVNULL, capture_output=True,
        timeout=_RUN_TIMEOUT_SECONDS, check=False, shell=False,
    )


def _assert_accepted(completed: subprocess.CompletedProcess) -> None:
    errors = completed.stderr.decode("utf-8", "replace")
    rejected = [phrase for phrase in _REJECTIONS if phrase in errors]
    assert not rejected, f"prthinker rejected what PyBreeze sent ({rejected}):\n{errors[-2000:]}"
    assert "ConnectError" in errors, f"prthinker stopped before the network:\n{errors[-2000:]}"


def test_every_backend_pybreeze_offers_is_one_prthinker_knows():
    completed = subprocess.run(  # noqa: S603 — fixed interpreter and a literal script
        [PRTHINKER_PYTHON, "-c",
         "import json; from prthinker.config import BackendKind; "
         "print(json.dumps([kind.value for kind in BackendKind]))"],
        capture_output=True, timeout=_RUN_TIMEOUT_SECONDS, check=True, shell=False,
    )
    known = set(json.loads(completed.stdout))
    assert set(BACKENDS) <= known, f"offered but unknown to prthinker: {set(BACKENDS) - known}"


@pytest.mark.parametrize("backend", ["openai", "remote"])
def test_reviewing_a_file_is_accepted(tmp_path, closed_url, backend):
    source = tmp_path / "main.py"
    source.write_text("print(1)\n", encoding="utf-8")
    setting = {
        **DEFAULT_SETTING,
        "backend": backend,
        "model_name": "any-model",
        "remote_url": closed_url,
        "openai_base_url": f"{closed_url}/v1",
        "openai_api_key": "not-a-real-key",
        "extra_arguments": "--max-new-tokens 16",
    }
    _assert_accepted(_run(review_file_arguments(str(source), setting), setting, tmp_path))


def test_rule_retrieval_through_the_server_is_accepted(tmp_path, closed_url):
    # An installed prthinker has no local RAG index: were the variable that
    # asks for the server's /rag not read, it would stop on that import instead.
    source = tmp_path / "main.py"
    source.write_text("print(1)\n", encoding="utf-8")
    setting = {
        **DEFAULT_SETTING,
        "backend": "remote",
        "remote_url": closed_url,
        "rag": "remote",
        "extra_arguments": "--max-new-tokens 16",
    }
    _assert_accepted(_run(review_file_arguments(str(source), setting), setting, tmp_path))


# Build prthinker's review configuration the way its command line does, from the
# environment alone, and report the backend and the model it settled on.
# ``_build_parser`` and ``_build_config`` are in ``prthinker.cli.__all__``.
_REPORT_BACKEND_AND_MODEL = """
import json
from prthinker.cli import _build_config, _build_parser
args = _build_parser().parse_args(["review-file", "main.py"])
config = _build_config(args)
kind = getattr(config.backend, "value", config.backend)
chosen = getattr(config, kind.replace("-", "_"))
for attribute in ("model", "model_name"):
    if hasattr(chosen, attribute):
        model = getattr(chosen, attribute)
        break
else:
    # The remote server picks its own model; prthinker only reports this one.
    model = args.model_name
print(json.dumps({"backend": kind, "model": model}))
"""


@pytest.mark.parametrize("backend", BACKENDS)
def test_the_model_reaches_the_backend_it_was_set_for(closed_url, backend):
    setting = {
        **DEFAULT_SETTING,
        "backend": backend,
        "model_name": "pybreeze-contract-model",
        "remote_url": closed_url,
        "openai_api_key": "not-a-real-key",
        "anthropic_api_key": "not-a-real-key",
    }
    environment = {
        **utf8_subprocess_env("utf-8"),
        # The three keys PyBreeze has no field for: prthinker reads them from
        # the environment the IDE was started in.
        "PRTHINKER_GEMINI_API_KEY": "not-a-real-key",
        "PRTHINKER_COHERE_API_KEY": "not-a-real-key",
        "PRTHINKER_MISTRAL_API_KEY": "not-a-real-key",
        **environment_for(setting),
    }
    completed = subprocess.run(  # noqa: S603 — fixed interpreter and a literal script
        [PRTHINKER_PYTHON, "-c", _REPORT_BACKEND_AND_MODEL],
        env=environment, capture_output=True, timeout=_RUN_TIMEOUT_SECONDS, check=False,
        shell=False,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")[-2000:]
    assert json.loads(completed.stdout) == {
        "backend": backend, "model": "pybreeze-contract-model"}


def test_reviewing_a_pull_request_is_accepted(tmp_path, closed_url):
    setting = {
        **DEFAULT_SETTING,
        "backend": "openai",
        "openai_base_url": f"{closed_url}/v1",
        "openai_api_key": "not-a-real-key",
        "platform": "github",
        "platform_base_url": closed_url,
        "repository": "owner/name",
        "platform_token": "not-a-real-token",
    }
    _assert_accepted(_run(review_pr_arguments(12, setting), setting, tmp_path))
