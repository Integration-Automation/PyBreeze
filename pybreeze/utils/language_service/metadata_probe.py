"""Ask an installed framework for its keywords, in a process of its own.

The keywords, their parameters and their documentation come from the package
that will run the script, not from a copy kept in the IDE. Reading them means
importing the package, and that is done in another process for three reasons:

- the IDE must not import ``je_auto_control`` as it runs (it changes how
  Windows scales the process), nor pay for locust and selenium at start;
- the scripts may run with another interpreter than the IDE's (the one chosen
  in the IDE, or a ``.venv`` in the project), with other versions installed;
- a package that fails to import, or hangs, costs its keywords and nothing
  else: the answer is a :class:`LanguageServiceException`, after a time limit.

The child runs a fixed script that needs only the standard library, from the
interpreter's own folder: the folder the IDE happens to be in (a project
someone opened) is not on its import path.
"""
from __future__ import annotations

import json
import shutil
import subprocess  # nosec B404 — a fixed argument list, never a shell
import sys
from pathlib import Path

from pybreeze.utils.exception.exception_tags import (
    language_probe_failed_error,
    language_probe_not_installed_error,
    language_probe_timeout_error,
)
from pybreeze.utils.exception.exceptions import LanguageServiceException
from pybreeze.utils.language_service.framework_profiles import FrameworkProfile
from pybreeze.utils.language_service.keyword_metadata import FrameworkMetadata, metadata_from_dict
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.subprocess_util import no_window_creationflags, utf8_subprocess_env

# How long a framework may take to import and describe itself
PROBE_TIMEOUT_SECONDS = 60.0
# What the line that carries the answer starts with: a package may print as it is imported
_MARKER = "pybreeze-keyword-metadata:"
# How much of what the child wrote to stderr is logged when it fails
_LOGGED_STDERR_CHARACTERS = 2000

# Runs in the interpreter that runs the scripts, which may be an older Python
# than the IDE's: the standard library only, and no syntax newer than 3.8
PROBE_SCRIPT = r'''
import builtins
import contextlib
import importlib
import inspect
import json
import sys

module_name, distribution, marker = sys.argv[1], sys.argv[2], sys.argv[3]
EMPTY = inspect.Parameter.empty
VARIADIC = (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)


def version():
    try:
        from importlib import metadata
        return metadata.version(distribution)
    except Exception:
        return ""


def annotation_text(annotation):
    if annotation is EMPTY:
        return ""
    return annotation if isinstance(annotation, str) else inspect.formatannotation(annotation)


def parameters(function):
    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError):
        return None
    return [{"name": parameter.name, "kind": parameter.kind.name,
             "required": parameter.default is EMPTY and parameter.kind not in VARIADIC,
             "default": "" if parameter.default is EMPTY else repr(parameter.default)[:80],
             "annotation": annotation_text(parameter.annotation)}
            for parameter in signature.parameters.values()]


def source(function):
    try:
        code = inspect.unwrap(function).__code__
        return code.co_filename, code.co_firstlineno
    except Exception:
        return "", 0


def describe(name, function):
    found = parameters(function)
    file, line = source(function)
    return {"name": name, "signature_known": found is not None, "parameters": found or [],
            "doc": inspect.getdoc(function) or "", "source_file": file, "source_line": line,
            "builtin": getattr(builtins, name, None) is function}


with contextlib.redirect_stdout(sys.stderr):
    events = importlib.import_module(module_name).executor.event_dict
    keywords = [describe(str(name), function) for name, function in events.items() if callable(function)]
sys.stdout.write(marker + json.dumps({
    "schema": 1, "framework": module_name.split(".")[0], "version": version(), "keywords": keywords}) + "\n")
'''


def probe_command(profile: FrameworkProfile, interpreter: str) -> list[str]:
    """The command that has *interpreter* describe *profile*'s framework."""
    return [interpreter, "-c", PROBE_SCRIPT, profile.executor_module, profile.distribution, _MARKER]


def _failure(profile: FrameworkProfile, stderr: str) -> LanguageServiceException:
    """Why the child gave no answer, from what it wrote to stderr.

    Only the exception's name is kept for the user: its message can carry a
    path. The rest goes to the log.
    """
    pybreeze_logger.info(
        "metadata_probe.py %s gave no keywords: %s", profile.framework, stderr[-_LOGGED_STDERR_CHARACTERS:])
    last_line = next((line for line in reversed(stderr.splitlines()) if line.strip()), "")
    missing = f"No module named '{profile.framework}" in last_line
    if missing:
        return LanguageServiceException(language_probe_not_installed_error.format(framework=profile.framework))
    reason = last_line.split(":", 1)[0].strip() or "no answer"
    return LanguageServiceException(language_probe_failed_error.format(framework=profile.framework, reason=reason))


def read_metadata(
        profile: FrameworkProfile, interpreter: str | None = None,
        timeout_seconds: float = PROBE_TIMEOUT_SECONDS) -> FrameworkMetadata:
    """The keywords of *profile*'s framework as *interpreter* has it installed.

    :param profile: the framework to ask
    :param interpreter: the Python that runs the scripts; the IDE's own when not given
    :param timeout_seconds: how long the framework may take
    :raises LanguageServiceException: when the framework is not installed there,
        fails to import, takes too long, or answers something that is not metadata
    """
    python = shutil.which(interpreter or sys.executable) or interpreter or sys.executable
    try:
        done = subprocess.run(  # nosec B603  # nosemgrep — fixed argument list, no shell
            probe_command(profile, python), capture_output=True, stdin=subprocess.DEVNULL, shell=False,
            timeout=timeout_seconds, env=utf8_subprocess_env(), cwd=Path(python).resolve().parent,
            creationflags=no_window_creationflags(), check=False)
    except subprocess.TimeoutExpired:
        raise LanguageServiceException(language_probe_timeout_error.format(
            framework=profile.framework, seconds=round(timeout_seconds))) from None
    except OSError as error:
        pybreeze_logger.info("metadata_probe.py %s could not be started: %r", python, error)
        raise LanguageServiceException(language_probe_failed_error.format(
            framework=profile.framework, reason=type(error).__name__)) from error
    answer = next((line for line in reversed(done.stdout.decode("utf-8", errors="replace").splitlines())
                   if line.startswith(_MARKER)), None)
    if answer is None:
        raise _failure(profile, done.stderr.decode("utf-8", errors="replace"))
    try:
        data = json.loads(answer[len(_MARKER):])
    except ValueError as error:
        raise LanguageServiceException(language_probe_failed_error.format(
            framework=profile.framework, reason=type(error).__name__)) from error
    return metadata_from_dict(data)
