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
