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


class TestReplaceWritten:
    def test_the_writer_gets_a_file_with_the_same_extension(self, tmp_path):
        from pybreeze.utils.file_process.replace_file import replace_written

        given: list = []

        def write(target):
            given.append(target)
            target.write_bytes(b"new")

        replace_written(tmp_path / "out.png", write)

        assert given[0].suffix == ".png"
        assert given[0].parent == tmp_path
        assert (tmp_path / "out.png").read_bytes() == b"new"
        assert list(tmp_path.iterdir()) == [tmp_path / "out.png"]

    def test_a_writer_that_fails_leaves_the_old_file_and_nothing_else(self, tmp_path):
        import pytest

        from pybreeze.utils.file_process.replace_file import replace_written

        old = tmp_path / "out.svg"
        old.write_bytes(b"old")

        def write(target):
            target.write_bytes(b"ha")
            raise OSError("disk full")

        with pytest.raises(OSError):
            replace_written(old, write)

        assert old.read_bytes() == b"old"
        assert list(tmp_path.iterdir()) == [old]

    def test_a_writer_that_fails_otherwise_leaves_nothing_behind_either(self, tmp_path):
        from pybreeze.utils.file_process.replace_file import replace_written

        old = tmp_path / "out.svg"
        old.write_bytes(b"old")

        def write(target):
            target.write_bytes(b"ha")
            raise ValueError("not an image")

        with pytest.raises(ValueError):
            replace_written(old, write)

        assert old.read_bytes() == b"old"
        assert list(tmp_path.iterdir()) == [old]


def test_text_utf8_cannot_encode_leaves_the_file_and_nothing_else(tmp_path):
    # UnicodeEncodeError is no OSError: the partial <name>.saving stayed
    target = tmp_path / "f.txt"
    target.write_text("old", encoding="utf-8")

    with pytest.raises(UnicodeEncodeError):
        replace_text(target, "x" + chr(0xD800))

    assert target.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize(("options", "mode"), [({}, 0o666), ({"private": True}, 0o600)])
def test_the_mode_the_file_is_created_with_is_private_only_when_asked(tmp_path, monkeypatch, options, mode):
    # Recorded as os.open is asked, so it runs where the permission bits do not (CI is Windows)
    modes: list = []
    opened = replace_file.os.open

    def record(path, flags, requested=0o777):
        modes.append(requested)
        return opened(path, flags, requested)

    monkeypatch.setattr(replace_file.os, "open", record)

    replace_text(tmp_path / "file.txt", "x", **options)

    assert modes == [mode]
