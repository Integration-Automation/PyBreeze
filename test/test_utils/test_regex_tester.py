"""Tests for the regular expression tester."""
from __future__ import annotations

import pytest

from pybreeze.utils.exception.exceptions import RegexTesterException
from pybreeze.utils.regex_tools.regex_tester import (
    available_flags,
    build_flags,
    compile_pattern,
    find_matches,
)


class TestBuildFlags:
    def test_no_flags(self):
        assert build_flags([]) == 0

    def test_ignorecase(self):
        import re
        assert build_flags(["IGNORECASE"]) & re.IGNORECASE

    def test_multiple(self):
        import re
        combined = build_flags(["IGNORECASE", "DOTALL"])
        assert combined & re.IGNORECASE and combined & re.DOTALL

    def test_unknown_ignored(self):
        assert build_flags(["NOPE"]) == 0

    def test_available_flags(self):
        assert set(available_flags()) == {"IGNORECASE", "MULTILINE", "DOTALL", "VERBOSE"}


class TestCompilePattern:
    def test_valid(self):
        assert compile_pattern(r"\d+").pattern == r"\d+"

    def test_empty_raises(self):
        with pytest.raises(RegexTesterException):
            compile_pattern("")

    def test_invalid_raises(self):
        with pytest.raises(RegexTesterException):
            compile_pattern("(")


class TestFindMatches:
    def test_simple(self):
        matches = find_matches(r"\d+", "a1 b22 c333")
        assert [m.matched_text for m in matches] == ["1", "22", "333"]

    def test_offsets(self):
        matches = find_matches(r"b", "abc")
        assert (matches[0].start, matches[0].end) == (1, 2)

    def test_numbered_groups(self):
        matches = find_matches(r"(\d)(\d)", "12")
        assert matches[0].groups == ["1", "2"]

    def test_named_groups(self):
        matches = find_matches(r"(?P<year>\d{4})", "2021")
        assert matches[0].named_groups == {"year": "2021"}

    def test_no_matches(self):
        assert find_matches(r"z", "abc") == []

    def test_ignorecase_flag(self):
        assert len(find_matches(r"abc", "ABC abc", ["IGNORECASE"])) == 2

    def test_multiline_flag(self):
        matches = find_matches(r"^\d", "1\n2\n3", ["MULTILINE"])
        assert len(matches) == 3

    def test_dotall_flag(self):
        assert find_matches(r"a.b", "a\nb", ["DOTALL"])[0].matched_text == "a\nb"

    def test_invalid_pattern_raises(self):
        with pytest.raises(RegexTesterException):
            find_matches("(", "text")

    def test_empty_pattern_raises(self):
        with pytest.raises(RegexTesterException):
            find_matches("", "text")

    def test_group_that_did_not_match_is_none(self):
        matches = find_matches(r"(a)|(b)", "a")
        assert matches[0].groups == ["a", None]

    def test_match_cap(self):
        from pybreeze.utils.regex_tools import regex_tester
        # More potential matches than the cap; result is capped, not unbounded.
        text = "a" * (regex_tester.MAX_MATCHES + 50)
        assert len(find_matches("a", text)) == regex_tester.MAX_MATCHES


class TestABoundedRun:
    """find_matches_bounded runs the pattern in a process it can stop."""

    def test_it_finds_what_find_matches_finds(self):
        from pybreeze.utils.regex_tools.regex_tester import find_matches, find_matches_bounded

        assert find_matches_bounded(r"\d+", "a1 b22") == find_matches(r"\d+", "a1 b22")

    def test_a_malformed_pattern_is_reported_before_any_process(self, monkeypatch):
        from pybreeze.utils.exception.exceptions import RegexTesterException
        from pybreeze.utils.regex_tools import regex_tester

        monkeypatch.setattr(
            regex_tester.subprocess, "Popen",
            lambda *_a, **_k: pytest.fail("a process was started for a pattern that cannot compile"))

        with pytest.raises(RegexTesterException):
            regex_tester.find_matches_bounded("(", "abc")

    def test_catastrophic_backtracking_is_stopped(self):
        import time

        from pybreeze.utils.exception.exceptions import RegexTesterException
        from pybreeze.utils.regex_tools.regex_tester import find_matches_bounded

        started = time.monotonic()
        with pytest.raises(RegexTesterException, match="still running"):
            find_matches_bounded("(a+)+$", "a" * 40 + "b", timeout_seconds=2.0)

        assert time.monotonic() - started < 10


class TestPatternsTheCompilerCannotTake:
    """They escaped the worker, and the tab stayed on "Running the pattern..."."""

    def test_a_repeat_count_too_large_is_reported(self):
        from pybreeze.utils.exception.exceptions import RegexTesterException
        from pybreeze.utils.regex_tools.regex_tester import compile_pattern

        with pytest.raises(RegexTesterException):
            compile_pattern("a{4294967296}")

    def test_groups_nested_too_deep_are_reported(self):
        from pybreeze.utils.exception.exceptions import RegexTesterException
        from pybreeze.utils.regex_tools.regex_tester import compile_pattern

        with pytest.raises(RegexTesterException):
            compile_pattern("(" * 5000 + "a" + ")" * 5000)


class TestTheWorkerProcess:
    def test_an_unguarded_launch_script_runs_once(self, tmp_path):
        # A spawn child re-imported it: the README's start_editor() script
        # opened a second IDE for every pattern, which then "timed out"
        import subprocess
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        script = tmp_path / "launch.py"
        script.write_text(
            "import sys\n"
            f"sys.path.insert(0, {str(root)!r})\n"
            "print('STARTED', flush=True)\n"
            "from pybreeze.utils.regex_tools.regex_tester import find_matches_bounded\n"
            "print('FOUND', len(find_matches_bounded(r'\\d', 'a1 b2')), flush=True)\n",
            encoding="utf-8")

        result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                                timeout=60, check=False)

        assert result.stdout.count("STARTED") == 1, result.stderr
        assert "FOUND 2" in result.stdout

    def test_a_running_pattern_can_be_stopped(self):
        # Closing the IDE ends with os._exit, which left the worker running
        import threading
        import time

        from pybreeze.utils.exception.exceptions import RegexTesterException
        from pybreeze.utils.regex_tools import regex_tester

        failures: list = []

        def run() -> None:
            try:
                regex_tester.find_matches_bounded("(a+)+$", "a" * 60 + "b", timeout_seconds=60)
            except RegexTesterException as error:
                failures.append(error)

        worker = threading.Thread(target=run)
        worker.start()
        deadline = time.monotonic() + 20
        while not regex_tester._RUNNING and time.monotonic() < deadline:
            time.sleep(0.05)
        started = time.monotonic()
        regex_tester.stop_running_workers()
        worker.join(20)

        assert failures and time.monotonic() - started < 10
        assert not regex_tester._RUNNING

    def test_the_packaged_builds_spawned_worker_finds_matches(self):
        # A packaged build has no interpreter to run a script with; it keeps the
        # spawn child. (Setting sys.frozen here would make multiprocessing hand
        # this interpreter the frozen app's arguments.)
        from pybreeze.utils.regex_tools import regex_tester

        found = regex_tester._find_in_spawned_process(r"\d+", "a1 b22", [], 30)

        assert found == regex_tester.find_matches(r"\d+", "a1 b22")
        assert not regex_tester._RUNNING

    def test_the_packaged_builds_worker_is_stopped_when_it_runs_too_long(self):
        import time

        from pybreeze.utils.exception.exceptions import RegexTesterException
        from pybreeze.utils.regex_tools import regex_tester

        started = time.monotonic()
        with pytest.raises(RegexTesterException, match="still running"):
            regex_tester._find_in_spawned_process("(a+)+$", "a" * 40 + "b", [], 3.0)

        assert time.monotonic() - started < 20
        assert not regex_tester._RUNNING

    def test_the_packaged_builds_worker_reports_a_pattern_it_cannot_run(self):
        from pybreeze.utils.exception.exceptions import RegexTesterException
        from pybreeze.utils.regex_tools import regex_tester

        with pytest.raises(RegexTesterException):
            regex_tester._find_in_spawned_process("(", "abc", [], 30)

        assert not regex_tester._RUNNING


class TestWhatTheSpawnedWorkerSends:
    """_matches_into_pipe, run here with a stand-in for its end of the pipe."""

    class _Pipe:
        def __init__(self) -> None:
            self.sent: list = []
            self.closed = False

        def send(self, message) -> None:
            self.sent.append(message)

        def close(self) -> None:
            self.closed = True

    def test_the_matches(self):
        from pybreeze.utils.regex_tools.regex_tester import _matches_into_pipe

        pipe = self._Pipe()
        _matches_into_pipe(pipe, r"\d+", "a1 b22", [])

        assert pipe.sent == [("matches", find_matches(r"\d+", "a1 b22"))]
        assert [match.matched_text for match in pipe.sent[0][1]] == ["1", "22"]
        assert pipe.closed

    def test_the_error_for_a_pattern_that_does_not_compile(self):
        from pybreeze.utils.regex_tools.regex_tester import _matches_into_pipe

        pipe = self._Pipe()
        _matches_into_pipe(pipe, "(", "abc", [])

        ((kind, message),) = pipe.sent
        assert kind == "error" and message
        assert pipe.closed
