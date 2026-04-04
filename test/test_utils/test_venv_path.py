import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from pybreeze.extend.process_executor.python_task_process_manager import find_venv_path


class TestFindVenvPath:
    def test_returns_path_object(self):
        result = find_venv_path()
        assert isinstance(result, Path)

    def test_prefers_venv_over_dot_venv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create both venv and .venv
            if sys.platform in ["win32", "cygwin", "msys"]:
                venv_dir = os.path.join(tmpdir, "venv", "Scripts")
                dot_venv_dir = os.path.join(tmpdir, ".venv", "Scripts")
            else:
                venv_dir = os.path.join(tmpdir, "venv", "bin")
                dot_venv_dir = os.path.join(tmpdir, ".venv", "bin")
            os.makedirs(venv_dir)
            os.makedirs(dot_venv_dir)

            with patch.object(Path, "cwd", return_value=Path(tmpdir)):
                result = find_venv_path()
                assert "venv" in str(result)
                assert ".venv" not in str(result)

    def test_falls_back_to_dot_venv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            if sys.platform in ["win32", "cygwin", "msys"]:
                dot_venv_dir = os.path.join(tmpdir, ".venv", "Scripts")
            else:
                dot_venv_dir = os.path.join(tmpdir, ".venv", "bin")
            os.makedirs(dot_venv_dir)

            with patch.object(Path, "cwd", return_value=Path(tmpdir)):
                result = find_venv_path()
                assert ".venv" in str(result)

    def test_returns_first_candidate_when_none_exist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "cwd", return_value=Path(tmpdir)):
                result = find_venv_path()
                # Should return the first candidate (venv) even if it doesn't exist
                assert "venv" in str(result)

    def test_platform_specific_subdirectory(self):
        result = find_venv_path()
        if sys.platform in ["win32", "cygwin", "msys"]:
            assert str(result).endswith("Scripts")
        else:
            assert str(result).endswith("bin")
