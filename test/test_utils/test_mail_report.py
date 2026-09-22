"""Mailing a run's report: off the UI thread, and every failure logged rather than raised."""
from __future__ import annotations

import sys
import threading
import types
from unittest.mock import MagicMock

import pytest

from pybreeze.extend.mail_thunder_extend import mail_thunder_setting as mail


class FakeSmtp:
    """SMTPWrapper's surface, recording what happens to it."""

    instances: list[FakeSmtp] = []
    connect_error: Exception | None = None
    logs_in = True
    send_error: Exception | None = None

    def __init__(self) -> None:
        if FakeSmtp.connect_error is not None:
            raise FakeSmtp.connect_error
        self.login_state = False
        self.sent: list = []
        self.quit_called = False
        FakeSmtp.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        self.quit_called = True

    def later_init(self) -> None:
        self.login_state = FakeSmtp.logs_in

    def create_message_with_attach(self, html, settings, path, use_html) -> dict:
        return {"html": html, **settings, "path": path, "use_html": use_html}

    def send_message(self, message) -> None:
        if FakeSmtp.send_error is not None:
            raise FakeSmtp.send_error
        self.sent.append(message)


class MailThunderException(Exception):
    pass


@pytest.fixture()
def mail_thunder(monkeypatch):
    """A stand-in je_mail_thunder with a user in its content file."""
    FakeSmtp.instances = []
    FakeSmtp.connect_error = None
    FakeSmtp.logs_in = True
    FakeSmtp.send_error = None
    package = types.ModuleType("je_mail_thunder")
    package.SMTPWrapper = FakeSmtp
    package.read_output_content = lambda: {"user": "tester@example.com"}
    package.get_mail_thunder_os_environ = lambda: {}
    exceptions = types.ModuleType("je_mail_thunder.utils.exception.exceptions")
    exceptions.MailThunderException = MailThunderException
    monkeypatch.setitem(sys.modules, "je_mail_thunder", package)
    monkeypatch.setitem(sys.modules, "je_mail_thunder.utils.exception.exceptions", exceptions)
    return package


@pytest.fixture()
def logger(monkeypatch) -> MagicMock:
    fake = MagicMock()
    monkeypatch.setattr(mail, "pybreeze_logger", fake)
    return fake


@pytest.fixture()
def report(tmp_path) -> str:
    path = tmp_path / "report.html"
    path.write_text("<html>ok</html>", encoding="utf-8")
    return str(path)


def _logged(logger: MagicMock) -> str:
    return " ".join(str(arg) for call in logger.error.call_args_list for arg in call.args)


class TestSendAfterTest:
    def test_it_returns_before_the_mail_is_sent(self, monkeypatch):
        sending = threading.Event()
        release = threading.Event()

        def slow_send(_path) -> None:
            sending.set()
            release.wait(5)

        monkeypatch.setattr(mail, "send_report", slow_send)

        mail.send_after_test("report.html")  # the mail server has not answered

        assert sending.wait(5)
        release.set()


class TestSendReport:
    def test_the_report_goes_to_the_user(self, mail_thunder, logger, report):
        mail.send_report(report)

        (smtp,) = FakeSmtp.instances
        assert smtp.sent == [{
            "html": "<html>ok</html>", "Subject": "Test Report",
            "To": "tester@example.com", "From": "tester@example.com",
            "path": report, "use_html": True,
        }]
        assert smtp.quit_called
        logger.error.assert_not_called()

    def test_the_user_can_come_from_the_environment(self, mail_thunder, logger, report):
        mail_thunder.read_output_content = lambda: None
        mail_thunder.get_mail_thunder_os_environ = lambda: {"mail_thunder_user": "env@example.com"}

        mail.send_report(report)

        assert FakeSmtp.instances[0].sent[0]["To"] == "env@example.com"

    def test_no_user_means_no_connection(self, mail_thunder, logger, report):
        mail_thunder.read_output_content = lambda: {}

        mail.send_report(report)

        assert FakeSmtp.instances == []
        assert "mail user" in _logged(logger)

    def test_a_missing_report_means_no_connection(self, mail_thunder, logger, tmp_path):
        mail.send_report(str(tmp_path / "absent.html"))

        assert FakeSmtp.instances == []
        assert "not found" in _logged(logger)

    def test_a_failed_login_is_logged_and_the_connection_closed(self, mail_thunder, logger, report):
        FakeSmtp.logs_in = False

        mail.send_report(report)

        (smtp,) = FakeSmtp.instances
        assert smtp.sent == [] and smtp.quit_called
        assert mail.send_html_exception_tag in _logged(logger)

    @pytest.mark.parametrize("error", [ConnectionRefusedError("refused"), MailThunderException("bad")])
    def test_a_failed_send_is_logged_and_the_connection_closed(self, mail_thunder, logger, report, error):
        FakeSmtp.send_error = error

        mail.send_report(report)

        assert FakeSmtp.instances[0].quit_called
        assert "Failed to send report" in _logged(logger)

    def test_an_unreachable_server_is_logged(self, mail_thunder, logger, report):
        FakeSmtp.connect_error = TimeoutError("timed out")

        mail.send_report(report)

        assert "timed out" in _logged(logger)

    def test_a_report_that_is_not_utf8_is_logged(self, mail_thunder, logger, tmp_path):
        path = tmp_path / "report.html"
        path.write_bytes(b"\xff\xfe\x00bad")

        mail.send_report(str(path))

        assert FakeSmtp.instances == []
        assert "Failed to send report" in _logged(logger)

    def test_without_je_mail_thunder_it_is_logged(self, monkeypatch, logger, report):
        monkeypatch.setitem(sys.modules, "je_mail_thunder", None)  # makes the import fail

        mail.send_report(report)

        assert "je_mail_thunder" in _logged(logger)
