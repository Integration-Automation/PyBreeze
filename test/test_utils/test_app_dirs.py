from __future__ import annotations

from pathlib import Path

from pybreeze.utils.app_dirs import pybreeze_data_dir


class TestPybreezeDataDir:
    def test_under_home_and_created(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        result = pybreeze_data_dir()
        assert result == tmp_path / ".pybreeze"
        assert result.is_dir()

    def test_idempotent_when_already_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        first = pybreeze_data_dir()
        second = pybreeze_data_dir()
        assert first == second
        assert second.is_dir()
