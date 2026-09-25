import logging
import os
import tempfile

from pybreeze.utils.logging.logger import PyBreezeLogger, pybreeze_logger


class TestPyBreezeLogger:
    def test_logger_exists(self):
        assert pybreeze_logger is not None
        assert pybreeze_logger.name == "Pybreeze"

    def test_logger_effective_level(self):
        assert pybreeze_logger.getEffectiveLevel() == logging.DEBUG

    def test_logger_has_handler(self):
        assert len(pybreeze_logger.handlers) > 0

    def test_does_not_reconfigure_root_logger(self):
        # A library must not force the root logger level or call basicConfig;
        # that would override the host application's logging configuration.
        import inspect

        from pybreeze.utils.logging import logger as logger_module

        source = inspect.getsource(logger_module)
        assert "root.setLevel" not in source
        assert "basicConfig" not in source

    def test_custom_handler_creation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            handler = PyBreezeLogger(filename=log_file, max_bytes=1024)
            # maxBytes is inherited from stdlib RotatingFileHandler; use getattr so
            # static analysers that don't follow stdlib inheritance stop flagging
            # the comparison as a type mismatch (SonarCloud S2159).
            assert getattr(handler, "maxBytes", None) == 1024
            handler.close()

    def test_custom_handler_writes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            handler = PyBreezeLogger(filename=log_file)
            test_logger = logging.getLogger("test_pybreeze")
            test_logger.addHandler(handler)
            test_logger.setLevel(logging.DEBUG)
            test_logger.info("test message")
            handler.flush()
            handler.close()
            with open(log_file) as f:
                content = f.read()
            assert "test message" in content

    def test_handler_formatter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            handler = PyBreezeLogger(filename=log_file)
            assert handler.formatter is not None
            handler.close()


class TestWhereTheLogGoes:
    """Importing writes nothing; the file is under the user's home, in UTF-8, appended."""

    def test_the_default_is_under_the_data_directory(self, monkeypatch):
        from pybreeze.utils.logging import logger as logger_module

        monkeypatch.delenv(logger_module.LOG_FILE_ENV, raising=False)

        path = logger_module.default_log_file()

        assert path.parts[-3:] == (".pybreeze", "logs", "PyBreeze.log")

    def test_the_environment_can_name_another_file(self, monkeypatch, tmp_path):
        from pybreeze.utils.logging import logger as logger_module

        monkeypatch.setenv(logger_module.LOG_FILE_ENV, str(tmp_path / "elsewhere.log"))

        assert logger_module.default_log_file() == tmp_path / "elsewhere.log"

    def test_a_data_folder_the_log_makes_is_its_owners_only(self, monkeypatch, tmp_path):
        # The log is often written first: it made ~/.pybreeze with the default
        # mode, and pybreeze_data_dir then left that folder as it was
        from pathlib import Path

        from pybreeze.utils.logging import logger as logger_module

        data = tmp_path / ".pybreeze"
        monkeypatch.setattr(logger_module, "pybreeze_data_path", lambda: data)
        modes: dict = {}
        made = Path.mkdir

        def record(path, mode=0o777, parents=False, exist_ok=False):
            modes.setdefault(Path(path), mode)
            made(path, mode=mode, parents=parents, exist_ok=exist_ok)

        monkeypatch.setattr(Path, "mkdir", record)
        handler = PyBreezeLogger(filename=str(data / "logs" / "PyBreeze.log"))
        handler.close()

        assert modes[data] == 0o700
        assert (data / "logs").is_dir()

    def test_the_package_handler_opens_nothing_at_import(self):
        from pybreeze.utils.logging.logger import file_handler

        # delay=True: no stream until the first record.
        assert file_handler.delay is True

    def test_text_outside_the_locale_code_page_is_kept(self, tmp_path):
        log_file = tmp_path / "unicode.log"
        handler = PyBreezeLogger(filename=str(log_file))
        test_logger = logging.getLogger("test_pybreeze_unicode")
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.DEBUG)

        test_logger.info("規則檢索 ÜÄÖ ключ")
        handler.close()
        test_logger.removeHandler(handler)

        assert "規則檢索 ÜÄÖ ключ" in log_file.read_text(encoding="utf-8")

    def test_a_second_process_appends_instead_of_wiping(self, tmp_path):
        log_file = tmp_path / "shared.log"
        for message in ("first run", "second run"):
            handler = PyBreezeLogger(filename=str(log_file))
            test_logger = logging.getLogger("test_pybreeze_append")
            test_logger.addHandler(handler)
            test_logger.setLevel(logging.DEBUG)
            test_logger.info(message)
            handler.close()
            test_logger.removeHandler(handler)

        text = log_file.read_text(encoding="utf-8")
        assert "first run" in text
        assert "second run" in text

    def test_a_file_that_cannot_be_opened_turns_logging_off_not_the_caller(self, tmp_path):
        import pytest

        blocked = tmp_path / "a_file_not_a_folder"
        blocked.write_text("", encoding="utf-8")
        handler = PyBreezeLogger(filename=str(blocked / "PyBreeze.log"), delay=True)
        test_logger = logging.getLogger("test_pybreeze_blocked")
        test_logger.addHandler(handler)

        with pytest.warns(RuntimeWarning):
            test_logger.error("goes nowhere")
        handler.close()
        test_logger.removeHandler(handler)


def _log_once(log_file, message: str) -> None:
    """Open a handler on *log_file* as a new process would, log *message*, close it."""
    handler = PyBreezeLogger(filename=str(log_file))
    test_logger = logging.getLogger("test_pybreeze_rotation")
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.DEBUG)
    try:
        test_logger.info(message)
    finally:
        handler.close()
        test_logger.removeHandler(handler)


class TestRotatingOnOpen:
    # A process moves a file past PYBREEZE_LOG_MAX_BYTES to <name>.1 as it
    # opens it: the log is appended to by every run and would grow for ever.
    def test_a_file_past_the_size_is_moved_aside(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PYBREEZE_LOG_MAX_BYTES", "10")
        log_file = tmp_path / "PyBreeze.log"
        log_file.write_text("an old run, longer than ten bytes\n", encoding="utf-8")
        (tmp_path / "PyBreeze.log.1").write_text("the run before that\n", encoding="utf-8")

        _log_once(log_file, "this run")

        assert (tmp_path / "PyBreeze.log.1").read_text(encoding="utf-8") == "an old run, longer than ten bytes\n"
        assert "this run" in log_file.read_text(encoding="utf-8")
        assert "an old run" not in log_file.read_text(encoding="utf-8")

    def test_a_file_within_the_size_is_appended_to(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PYBREEZE_LOG_MAX_BYTES", "1000")
        log_file = tmp_path / "PyBreeze.log"
        log_file.write_text("an old run\n", encoding="utf-8")

        _log_once(log_file, "this run")

        assert log_file.read_text(encoding="utf-8").startswith("an old run\n")
        assert not (tmp_path / "PyBreeze.log.1").exists()

    def test_a_size_of_zero_turns_it_off(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PYBREEZE_LOG_MAX_BYTES", "0")
        log_file = tmp_path / "PyBreeze.log"
        log_file.write_text("an old run\n", encoding="utf-8")

        _log_once(log_file, "this run")

        assert not (tmp_path / "PyBreeze.log.1").exists()

    def test_a_size_that_is_not_a_number_is_the_default(self, monkeypatch):
        from pybreeze.utils.logging import logger

        monkeypatch.setenv("PYBREEZE_LOG_MAX_BYTES", "100MB")

        assert logger._rotate_at_bytes() == logger.DEFAULT_MAX_LOG_BYTES

    def test_a_file_that_cannot_be_moved_is_still_logged_to(self, tmp_path, monkeypatch):
        # Windows refuses the rename while another process holds the file
        import pytest

        from pybreeze.utils.logging import logger

        def refused(_source, _target):
            raise PermissionError(13, "The file is in use")

        monkeypatch.setenv("PYBREEZE_LOG_MAX_BYTES", "10")
        monkeypatch.setattr(logger.os, "replace", refused)
        log_file = tmp_path / "PyBreeze.log"
        log_file.write_text("an old run, longer than ten bytes\n", encoding="utf-8")

        with pytest.warns(RuntimeWarning, match="not rotated"):
            _log_once(log_file, "this run")

        text = log_file.read_text(encoding="utf-8")
        assert text.startswith("an old run")
        assert "this run" in text
