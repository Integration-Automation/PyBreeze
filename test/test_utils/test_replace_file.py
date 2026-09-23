"""A file written through replace_text is either the old one or the new one, never half."""
from __future__ import annotations

import os
import sys

import pytest

from pybreeze.utils.file_process import replace_file
from pybreeze.utils.file_process.replace_file import replace_text


def test_the_text_is_written(tmp_path):
    target = tmp_path / "settings.json"

    replace_text(target, "new text\n")

    assert target.read_text(encoding="utf-8") == "new text\n"


def test_a_failure_part_way_leaves_the_old_file_and_no_partial_one(tmp_path, monkeypatch):
    target = tmp_path / "settings.json"
    target.write_text("old text", encoding="utf-8")

    def disk_full(*_args, **_kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(replace_file.os, "replace", disk_full)

    with pytest.raises(OSError):
        replace_text(target, "new text")

    assert target.read_text(encoding="utf-8") == "old text"
    assert [path.name for path in tmp_path.iterdir()] == ["settings.json"]


def test_a_partial_file_left_by_an_earlier_failure_is_replaced(tmp_path):
    target = tmp_path / "settings.json"
    (tmp_path / "settings.json.saving").write_text("half of an old save", encoding="utf-8")

    replace_text(target, "new text")

    assert target.read_text(encoding="utf-8") == "new text"
    assert not (tmp_path / "settings.json.saving").exists()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_a_private_file_is_readable_by_its_owner_only(tmp_path):
    target = tmp_path / "keys.json"

    replace_text(target, "{}", private=True)

    assert os.stat(target).st_mode & 0o777 == 0o600
