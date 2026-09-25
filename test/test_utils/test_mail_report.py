"""Mailing a run's report: off the UI thread, and every failure logged rather than raised."""
from __future__ import annotations

import os
import sys
import threading
import time
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


@pytest.fixture
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


@pytest.fixture
def logger(monkeypatch) -> MagicMock:
    fake = MagicMock()
    monkeypatch.setattr(mail, "pybreeze_logger", fake)
    return fake


@pytest.fixture
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

        def slow_send(_path, *, not_before=None) -> None:
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
        reason = mail.send_report(str(tmp_path / "absent.html"))

        assert FakeSmtp.instances == []
        assert reason == "the run wrote no absent.html"
        assert reason in _logged(logger)

    def test_a_failed_login_is_logged_and_the_connection_closed(self, mail_thunder, logger, report, monkeypatch):
        monkeypatch.setattr(FakeSmtp, "logs_in", False)

        mail.send_report(report)

        (smtp,) = FakeSmtp.instances
        assert smtp.sent == []
        assert smtp.quit_called
        assert mail.send_html_exception_tag in _logged(logger)

    @pytest.mark.parametrize("error", [ConnectionRefusedError("refused"), MailThunderException("bad")])
    def test_a_failed_send_is_logged_and_the_connection_closed(
            self, mail_thunder, logger, report, error, monkeypatch):
        monkeypatch.setattr(FakeSmtp, "send_error", error)

        mail.send_report(report)

        assert FakeSmtp.instances[0].quit_called
        assert "Failed to send report" in _logged(logger)

    def test_an_unreachable_server_is_logged(self, mail_thunder, logger, report, monkeypatch):
        monkeypatch.setattr(FakeSmtp, "connect_error", TimeoutError("timed out"))

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


class TestAReportFromAnEarlierRun:
    """A run that wrote no report used to mail the one an earlier run left."""

    def test_a_report_older_than_the_run_is_not_sent(self, mail_thunder, logger, report):
        an_hour_ago = time.time() - 3600
        os.utime(report, (an_hour_ago, an_hour_ago))

        reason = mail.send_report(report, not_before=time.time())

        assert FakeSmtp.instances == []
        assert "earlier run" in reason

    def test_a_report_the_run_wrote_is_sent(self, mail_thunder, logger, report):
        assert mail.send_report(report, not_before=time.time() - 1) is None
        assert len(FakeSmtp.instances[0].sent) == 1

    def test_a_folder_in_its_place_is_not_sent(self, mail_thunder, logger, tmp_path):
        folder = tmp_path / "default_name.html"
        folder.mkdir()

        assert mail.send_report(str(folder)) == "default_name.html is not a file"


class TestTheAnswer:
    """What send_report says, for the run window: never a path, address or server reply."""

    def test_sent(self, mail_thunder, logger, report):
        assert mail.send_report(report) is None

    def test_no_user(self, mail_thunder, logger, report):
        mail_thunder.read_output_content = lambda: {}

        assert mail.send_report(report) == "no mail user is set"

    def test_login_failed(self, mail_thunder, logger, report, monkeypatch):
        monkeypatch.setattr(FakeSmtp, "logs_in", False)

        assert mail.send_report(report) == "the mail server login failed"

    def test_send_failed_names_only_the_error_kind(self, mail_thunder, logger, report, monkeypatch):
        monkeypatch.setattr(
            FakeSmtp, "send_error", ConnectionRefusedError("refused by mail.example.com for tester@example.com"))

        reason = mail.send_report(report)

        assert reason == "sending failed (ConnectionRefusedError)"

    def test_without_je_mail_thunder(self, monkeypatch, logger, report):
        monkeypatch.setitem(sys.modules, "je_mail_thunder", None)

        assert mail.send_report(report) == "je_mail_thunder is not installed"

    def test_the_answer_reaches_on_done(self, monkeypatch):
        answered = threading.Event()
        answers: list = []
        monkeypatch.setattr(mail, "send_report", lambda _path, *, not_before=None: "why")

        mail.send_after_test("report.html", on_done=lambda reason: (answers.append(reason), answered.set()))

        assert answered.wait(5)
        assert answers == ["why"]

    def test_anything_raised_while_sending_still_reaches_on_done(self, monkeypatch, logger):
        # The thread died with a traceback, and the run window never said a word
        answered = threading.Event()
        answers: list = []

        def breaks(_path, *, not_before=None):
            raise RuntimeError("inside je_mail_thunder")

        monkeypatch.setattr(mail, "send_report", breaks)

        mail.send_after_test("report.html", on_done=lambda reason: (answers.append(reason), answered.set()))

        assert answered.wait(5)
        assert answers == ["sending failed (RuntimeError)"]
        assert "inside je_mail_thunder" in _logged(logger)


class TestAMailSettingsFileThatCannotBeRead:
    """je_mail_thunder reads mail_thunder_content.json unguarded, in the locale's encoding."""

    @pytest.mark.parametrize("error", [
        ValueError("Expecting value"),
        UnicodeDecodeError("cp950", b"\xe5", 0, 1, "illegal multibyte sequence"),
        OSError("locked"),
    ])
    def test_it_is_reported_and_nothing_is_sent(self, mail_thunder, logger, report, error):
        def unreadable():
            raise error

        mail_thunder.read_output_content = unreadable

        assert mail.send_report(report) == (
            "the mail settings file (mail_thunder_content.json) could not be read")
        assert FakeSmtp.instances == []
        assert "could not be read" in _logged(logger)


class TestAServerThatStopsAnswering:
    """MailThunder's SMTPWrapper passes no timeout on: a server that took the connection and fell silent held the thread."""

    @staticmethod
    def _silent_server():
        import socket

        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        held: list = []

        def accept() -> None:
            try:
                connection, _address = listener.accept()
                held.append(connection)  # never says a word
            except OSError:
                return

        threading.Thread(target=accept, daemon=True).start()
        return listener, held

    def test_the_report_gives_up_on_it(self, mail_thunder, logger, report, monkeypatch):
        import smtplib

        listener, held = self._silent_server()
        port = listener.getsockname()[1]

        class SilentServerWrapper(smtplib.SMTP_SSL):
            """MailThunder's SMTPWrapper as it is, pointed at the silent server."""

            def __init__(self) -> None:
                super().__init__("127.0.0.1", port)
                self.login_state = False

        mail_thunder.SMTPWrapper = SilentServerWrapper
        monkeypatch.setattr(mail, "_SMTP_TIMEOUT_SECONDS", 1)
        outcome: list = []
        started = time.monotonic()
        sender = threading.Thread(target=lambda: outcome.append(mail.send_report(report)), daemon=True)
        sender.start()
        sender.join(15)
        try:
            assert outcome == ["sending failed (TimeoutError)"]
            assert time.monotonic() - started < 15
        finally:
            listener.close()
            for connection in held:
                connection.close()
