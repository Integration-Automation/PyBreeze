from __future__ import annotations

import subprocess
import sys

import pytest

from pybreeze.utils.subprocess_util import (
    IDE_ONLY, child_environment, no_window_creationflags, utf8_subprocess_env,
)


class TestUtf8SubprocessEnv:
    def test_sets_pythonioencoding(self):
        env = utf8_subprocess_env("utf-8")
        assert env["PYTHONIOENCODING"] == "utf-8"

    def test_honours_custom_encoding(self):
        assert utf8_subprocess_env("cp950")["PYTHONIOENCODING"] == "cp950"

    def test_preserves_existing_environment(self, monkeypatch):
        monkeypatch.setenv("PYBREEZE_TEST_MARKER", "kept")
        env = utf8_subprocess_env()
        assert env.get("PYBREEZE_TEST_MARKER") == "kept"

    def test_child_actually_uses_the_encoding(self):
        # A real child must report the pinned stdout encoding.
        result = subprocess.run(
            [sys.executable, "-c", "import sys; print(sys.stdout.encoding)"],
            capture_output=True, text=True, env=utf8_subprocess_env("utf-8"),
        )
        assert result.stdout.strip().replace("-", "").lower() == "utf8"


class TestWhatTheIdeSetsForItself:
    """A variable the IDE sets for its own process only stays out of the processes it starts."""

    @staticmethod
    def _set_for_the_ide(monkeypatch, name: str) -> None:
        monkeypatch.setenv(name, IDE_ONLY)  # restored when the test ends

    def test_a_child_does_not_get_it(self, monkeypatch):
        self._set_for_the_ide(monkeypatch, "PYBREEZE_TEST_IDE_ONLY")

        assert "PYBREEZE_TEST_IDE_ONLY" not in child_environment()
        assert "PYBREEZE_TEST_IDE_ONLY" not in utf8_subprocess_env()

    def test_one_the_user_set_is_passed_on(self, monkeypatch):
        monkeypatch.setenv("PYBREEZE_TEST_IDE_ONLY", "1")

        assert child_environment()["PYBREEZE_TEST_IDE_ONLY"] == "1"

    def test_it_is_known_by_its_value_not_by_the_object(self, monkeypatch):
        # The same text built anew, as one inherited from a parent process would be
        monkeypatch.setenv("PYBREEZE_TEST_IDE_ONLY", "".join(list(IDE_ONLY)))

        assert "PYBREEZE_TEST_IDE_ONLY" not in child_environment()

    # Values sorting before and after the marker
    @pytest.mark.parametrize("value", ["0", "zzz"])
    def test_any_other_value_is_passed_on(self, monkeypatch, value):
        monkeypatch.setenv("PYBREEZE_TEST_IDE_ONLY", value)

        assert child_environment()["PYBREEZE_TEST_IDE_ONLY"] == value


    def test_a_real_child_runs_without_it(self, monkeypatch):
        self._set_for_the_ide(monkeypatch, "PYBREEZE_TEST_IDE_ONLY")

        result = subprocess.run(
            [sys.executable, "-c", "import os; print(os.environ.get('PYBREEZE_TEST_IDE_ONLY'))"],
            capture_output=True, text=True, env=utf8_subprocess_env(), timeout=60, check=True,
        )

        assert result.stdout.strip() == "None"


class TestNoWindowCreationflags:
    def test_returns_int(self):
        assert isinstance(no_window_creationflags(), int)

    def test_matches_platform(self):
        flags = no_window_creationflags()
        if sys.platform == "win32":
            assert flags == subprocess.CREATE_NO_WINDOW
        else:
            assert flags == 0

    def test_is_a_noop_when_or_combined_on_posix_semantics(self):
        # OR-ing the flag with other creationflags must never lose existing bits.
        base = 0x4
        assert base | no_window_creationflags() >= base


class TestStoppingATree:
    """Stopping a run stops what it started: ``go run`` and a web run start the program as a grandchild."""

    _GRANDCHILD = (
        "import sys, time\n"
        "deadline = time.monotonic() + 30\n"
        "while time.monotonic() < deadline:\n"
        "    open(sys.argv[1], 'w').write(str(time.monotonic()))\n"
        "    time.sleep(0.05)\n"
    )

    def test_the_program_a_launcher_started_stops_too(self, tmp_path):
        import time

        from pybreeze.utils.subprocess_util import own_session_options, stop_tree

        heartbeat = tmp_path / "beat"
        grandchild = tmp_path / "grandchild.py"
        grandchild.write_text(self._GRANDCHILD, encoding="utf-8")
        launcher = subprocess.Popen(  # noqa: S603 — this interpreter and a script the test wrote
            [sys.executable, "-c",
             "import subprocess, sys, time\n"
             f"subprocess.Popen([sys.executable, {str(grandchild)!r}, {str(heartbeat)!r}])\n"
             "time.sleep(30)\n"],
            creationflags=no_window_creationflags(), **own_session_options())
        deadline = time.monotonic() + 20
        while not heartbeat.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert heartbeat.exists(), "the grandchild never started"

        stop_tree(launcher)
        launcher.wait(10)
        time.sleep(0.5)
        last = heartbeat.read_text(encoding="utf-8")
        time.sleep(0.5)

        assert heartbeat.read_text(encoding="utf-8") == last, "the grandchild is still running"

    def test_on_windows_taskkill_is_run_as_a_list_without_a_shell(self, monkeypatch):
        # A fixed argument list, no shell, no window, its output kept, bounded in time
        from pybreeze.utils import subprocess_util

        monkeypatch.setattr(subprocess_util.sys, "platform", "win32")
        monkeypatch.setenv("SystemRoot", "C:\\Windows")
        calls: list = []
        monkeypatch.setattr(subprocess_util.subprocess, "run", lambda args, **options: calls.append((args, options)))

        class Running:
            pid = 4242

            def poll(self):
                return None if not calls else 0

            def terminate(self):
                raise AssertionError("taskkill ended it")

        subprocess_util.stop_tree(Running())

        ((args, options),) = calls
        assert args[1:] == ["/T", "/F", "/PID", "4242"]
        assert args[0].lower().endswith("taskkill.exe")
        assert {name: options[name] for name in ("capture_output", "timeout", "check", "shell")} == {
            "capture_output": True, "timeout": 10, "check": False, "shell": False}

    def test_a_process_that_has_ended_is_left_alone(self, monkeypatch):
        from pybreeze.utils import subprocess_util

        class Ended:
            pid = 1

            def poll(self):
                return 0

            def terminate(self):
                raise AssertionError("an ended process was terminated")

        monkeypatch.setattr(subprocess_util.subprocess, "run", lambda *a, **k: pytest.fail("taskkill was run"))
        subprocess_util.stop_tree(Ended())

    def test_when_the_tree_cannot_be_stopped_the_child_still_is(self, monkeypatch):
        from pybreeze.utils import subprocess_util

        class Running:
            pid = 4242
            terminated = False

            def poll(self):
                return 0 if self.terminated else None

            def terminate(self):
                self.terminated = True

        def refuse(*_args, **_kwargs):
            raise OSError("taskkill is not there")

        monkeypatch.setattr(subprocess_util.subprocess, "run", refuse)
        monkeypatch.setattr(subprocess_util.os, "killpg", refuse, raising=False)
        child = Running()

        subprocess_util.stop_tree(child)

        assert child.terminated


class TestOnPosix:
    """What the POSIX branches do, run on any platform with ``sys.platform`` stood in for (CI is Windows)."""

    @pytest.fixture
    def posix(self, monkeypatch):
        from types import SimpleNamespace

        from pybreeze.utils import subprocess_util

        monkeypatch.setattr(subprocess_util, "sys", SimpleNamespace(platform="linux"))
        return subprocess_util

    def test_a_child_gets_no_window_flag_and_a_session_of_its_own(self, posix):
        assert posix.no_window_creationflags() == 0
        assert posix.own_session_options() == {"start_new_session": True}

    def test_stopping_a_tree_signals_the_process_group(self, posix, monkeypatch):
        import signal

        signalled: list = []

        class Running:
            pid = 4242

            def poll(self):
                return 0 if signalled else None

            def terminate(self):
                raise AssertionError("the group was signalled; the child needs no terminate")

        monkeypatch.setattr(posix.os, "killpg", lambda pid, sig: signalled.append((pid, sig)), raising=False)
        monkeypatch.setattr(posix.subprocess, "run", lambda *a, **k: pytest.fail("taskkill was run"))

        posix.stop_tree(Running())

        assert signalled == [(4242, signal.SIGTERM)]


class TestOwnSessionOptions:
    """A child gets a process group of its own on POSIX, for stop_tree; Windows needs none."""

    @pytest.mark.parametrize(("platform", "options"), [
        ("win32", {}), ("linux", {"start_new_session": True}), ("darwin", {"start_new_session": True}),
    ])
    def test_by_platform(self, monkeypatch, platform, options):
        from pybreeze.utils import subprocess_util

        monkeypatch.setattr(subprocess_util.sys, "platform", platform)

        assert subprocess_util.own_session_options() == options
