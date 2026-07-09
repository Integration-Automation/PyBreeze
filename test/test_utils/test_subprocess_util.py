from __future__ import annotations

import subprocess
import sys

from pybreeze.utils.subprocess_util import no_window_creationflags, utf8_subprocess_env


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
