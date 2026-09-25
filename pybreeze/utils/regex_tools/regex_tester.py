"""Test a regular expression against sample text and report the matches.

Automation work leans on regexes constantly — extracting values from responses,
building element locators, parsing log output. Being able to try a pattern
against real sample text inside the IDE shortens that loop.

This module is pure logic: it compiles the pattern and reports matches; it never
touches the UI or the network.
"""
from __future__ import annotations

import json
import multiprocessing
import re
import subprocess  # nosec B404 — runs this interpreter on a fixed script, never a shell
import sys
import threading
from dataclasses import dataclass, field

from pybreeze.utils.exception.exception_tags import (
    empty_regex_pattern_error,
    invalid_regex_pattern_error,
    regex_timeout_error,
    regex_worker_error,
)
from pybreeze.utils.exception.exceptions import RegexTesterException
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.subprocess_util import child_environment, no_window_creationflags

# Cap on reported matches, so a pattern that matches everywhere cannot flood
# the output. It bounds how many matches are reported, not how long one takes.
MAX_MATCHES = 1000

# How long a pattern may run, in its own process, before it is stopped.
MATCH_TIMEOUT_SECONDS = 5.0

# Groups nested past this overflow the C stack of ``re``'s parser on CPython
# 3.10 — a hard interpreter crash, not a catchable ``RecursionError`` — so the
# depth is checked here before the pattern ever reaches ``re.compile``.
MAX_GROUP_NESTING = 100

# Human-facing flag names mapped to their ``re`` values.
_FLAG_NAMES: dict[str, int] = {
    "IGNORECASE": re.IGNORECASE,
    "MULTILINE": re.MULTILINE,
    "DOTALL": re.DOTALL,
    "VERBOSE": re.VERBOSE,
}


@dataclass
class MatchResult:
    """One regex match and its captured groups.

    :param matched_text: the full matched substring
    :param start: match start offset in the text
    :param end: match end offset in the text
    :param groups: numbered capture groups (``None`` for groups that did not match)
    :param named_groups: named capture groups by name
    """

    matched_text: str
    start: int
    end: int
    groups: list[str | None] = field(default_factory=list)
    named_groups: dict[str, str | None] = field(default_factory=dict)


def available_flags() -> list[str]:
    """Return the supported flag names."""
    return list(_FLAG_NAMES)


def build_flags(flag_names: list[str] | set[str]) -> int:
    """Combine flag names into a single ``re`` flags integer.

    :param flag_names: names from :func:`available_flags` (unknown names ignored)
    :return: the combined flags value
    """
    combined = 0
    for name in flag_names:
        combined |= _FLAG_NAMES.get(name, 0)
    return combined


def _group_nesting_too_deep(pattern: str) -> bool:
    """Return whether *pattern* nests groups past :data:`MAX_GROUP_NESTING`.

    The scan is iterative, so it cannot itself overflow the stack. It skips
    escaped characters and the contents of character classes, where a
    parenthesis is a literal rather than a group.

    :param pattern: the regular expression to scan
    :return: ``True`` when the open-group nesting depth exceeds the cap
    """
    depth = 0
    in_class = False
    escaped = False
    for char in pattern:
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif in_class:
            if char == "]":
                in_class = False
        elif char == "[":
            in_class = True
        elif char == "(":
            depth += 1
            if depth > MAX_GROUP_NESTING:
                return True
        elif char == ")" and depth > 0:
            depth -= 1
    return False


def compile_pattern(pattern: str, flag_names: list[str] | set[str] | None = None) -> re.Pattern:
    """Compile *pattern*, raising a friendly error on failure.

    :param pattern: the regular expression
    :param flag_names: optional flag names to apply
    :return: the compiled pattern
    :raises RegexTesterException: when the pattern is empty or invalid
    """
    if pattern == "":
        pybreeze_logger.error(empty_regex_pattern_error)
        raise RegexTesterException(empty_regex_pattern_error)
    if _group_nesting_too_deep(pattern):
        message = invalid_regex_pattern_error.format(
            detail=f"groups nested more than {MAX_GROUP_NESTING} deep")
        pybreeze_logger.error(message)
        raise RegexTesterException(message)
    try:
        return re.compile(pattern, build_flags(flag_names or []))
    # OverflowError: a repeat count past what re takes (a{4294967296});
    # RecursionError: groups nested deeper than the compiler goes. Either
    # escaped the worker, and the tab stayed on "Running the pattern..."
    except (re.error, OverflowError, RecursionError) as error:
        message = invalid_regex_pattern_error.format(detail=str(error))
        pybreeze_logger.error(message)
        raise RegexTesterException(message) from error


def find_matches(
        pattern: str, text: str,
        flag_names: list[str] | set[str] | None = None) -> list[MatchResult]:
    """Find every match of *pattern* in *text*.

    :param pattern: the regular expression
    :param text: the sample text to search
    :param flag_names: optional flag names to apply
    :return: the matches, up to an internal cap
    :raises RegexTesterException: when the pattern is empty or invalid
    """
    compiled = compile_pattern(pattern, flag_names)
    results: list[MatchResult] = []
    for match in compiled.finditer(text):
        results.append(
            MatchResult(
                matched_text=match.group(0),
                start=match.start(),
                end=match.end(),
                groups=list(match.groups()),
                named_groups=dict(match.groupdict()),
            )
        )
        if len(results) >= MAX_MATCHES:
            break
    return results


# What the worker runs: the standard library only, so it needs nothing from the
# IDE's path. It reads the job as JSON on stdin and writes the matches as JSON.
_WORKER_SCRIPT = """
import json, re, sys
job = json.loads(sys.stdin.buffer.read().decode("utf-8"))
found = []
for match in re.compile(job["pattern"], job["flags"]).finditer(job["text"]):
    found.append([match.group(0), match.start(), match.end(), list(match.groups()), match.groupdict()])
    if len(found) >= job["limit"]:
        break
sys.stdout.buffer.write(json.dumps(found).encode("utf-8"))
"""

# The workers still running (Popen, or multiprocessing.Process in a packaged
# build), so closing the IDE can stop them: it exits with os._exit, and a child
# process outlives its parent on Windows
_RUNNING: set = set()
_RUNNING_LOCK = threading.Lock()
# How long to wait for a spawned worker to go once it is done or stopped
_JOIN_SECONDS = 2.0


def stop_running_workers() -> None:
    """Stop every pattern still running in a worker process."""
    with _RUNNING_LOCK:
        running = list(_RUNNING)
    for worker in running:
        still_running = worker.is_alive() if hasattr(worker, "is_alive") else worker.poll() is None
        if still_running:
            worker.kill()


def _register(worker) -> None:
    with _RUNNING_LOCK:
        _RUNNING.add(worker)


def _unregister(worker) -> None:
    with _RUNNING_LOCK:
        _RUNNING.discard(worker)


def find_matches_bounded(
        pattern: str, text: str, flag_names: list[str] | set[str] | None = None,
        timeout_seconds: float = MATCH_TIMEOUT_SECONDS) -> list[MatchResult]:
    """Like :func:`find_matches`, in a separate process stopped after *timeout_seconds*.

    Python's ``re`` cannot be interrupted once a match attempt starts, and a
    pattern with nested repetition backtracks exponentially: ``(a+)+$`` against
    26 ``a``'s and a ``b`` takes seconds, and each further character doubles it.
    Only a process can be stopped mid-match. The pattern is compiled here first,
    so a malformed one is reported without starting anything.

    The worker is this interpreter running a fixed script (``-I -S``), not a
    multiprocessing ``spawn`` child: that re-imports the script the IDE was
    started from, and one without a ``__main__`` guard (the README's own
    ``start_editor()`` example) opened a second IDE for every pattern, which
    then "timed out". A packaged build has no interpreter to run a script
    with (``sys.executable`` is the app), so there the worker is still a
    ``spawn`` child, which its guarded entry script and ``freeze_support()``
    handle.

    :param pattern: the regular expression
    :param text: the sample text to search
    :param flag_names: optional flag names to apply
    :param timeout_seconds: how long the pattern may run, process start included
    :return: the matches, up to an internal cap
    :raises RegexTesterException: when the pattern is empty or invalid, or ran too long
    """
    compile_pattern(pattern, flag_names)
    if getattr(sys, "frozen", False):
        return _find_in_spawned_process(pattern, text, list(flag_names or []), timeout_seconds)
    job = json.dumps({"pattern": pattern, "text": text, "flags": build_flags(flag_names or []),
                      "limit": MAX_MATCHES}).encode("utf-8")
    output = _run_worker(job, timeout_seconds)
    try:
        found = json.loads(output.decode("utf-8"))
    except ValueError as error:  # it died part-way (killed, or out of memory)
        raise _worker_failed(repr(error)) from error
    return [MatchResult(matched_text=text_, start=start, end=end, groups=groups, named_groups=named)
            for text_, start, end, groups, named in found]


def _run_worker(job: bytes, timeout_seconds: float) -> bytes:
    """Run the worker on *job*; its output, or ``RegexTesterException`` when it ran too long or failed."""
    try:
        process = subprocess.Popen(  # nosec B603 — fixed argument list, no shell
            [sys.executable, "-I", "-S", "-c", _WORKER_SCRIPT],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            shell=False, env=child_environment(), creationflags=no_window_creationflags())
    except OSError as error:
        raise _worker_failed(repr(error)) from error
    _register(process)
    try:
        output, _ = process.communicate(job, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        message = regex_timeout_error.format(seconds=timeout_seconds)
        pybreeze_logger.error(message)
        raise RegexTesterException(message) from None
    finally:
        _unregister(process)
    if process.returncode != 0:
        raise _worker_failed(f"exit code {process.returncode}")
    return output


def _worker_failed(detail: str) -> RegexTesterException:
    """The error for a worker that stopped without an answer."""
    message = regex_worker_error.format(detail=detail)
    pybreeze_logger.error(message)
    return RegexTesterException(message)


def _find_in_spawned_process(pattern: str, text: str, flag_names: list[str],
                             timeout_seconds: float) -> list[MatchResult]:
    """:func:`find_matches` in a ``spawn`` child stopped after *timeout_seconds* (packaged builds)."""
    context = multiprocessing.get_context("spawn")
    receiving, sending = context.Pipe(duplex=False)
    process = context.Process(
        target=_matches_into_pipe, args=(sending, pattern, text, flag_names), daemon=True)
    process.start()
    _register(process)
    sending.close()
    try:
        if not receiving.poll(timeout_seconds):
            message = regex_timeout_error.format(seconds=timeout_seconds)
            pybreeze_logger.error(message)
            raise RegexTesterException(message)
        kind, value = receiving.recv()
    except (EOFError, OSError) as error:
        raise _worker_failed(repr(error)) from error
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=_JOIN_SECONDS)
        receiving.close()
        _unregister(process)
    if kind == "error":
        raise RegexTesterException(value)
    return value


def _matches_into_pipe(sending, pattern: str, text: str, flag_names: list[str]) -> None:
    """Run :func:`find_matches` in the spawned worker and send back what happened."""
    try:
        sending.send(("matches", find_matches(pattern, text, flag_names)))
    except RegexTesterException as error:
        sending.send(("error", str(error)))
    finally:
        sending.close()
