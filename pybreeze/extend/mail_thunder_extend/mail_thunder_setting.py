from __future__ import annotations

import os
import threading
from collections.abc import Callable

from pybreeze.utils.exception.exception_tags import (
    mail_login_failed_error,
    mail_no_user_error,
    mail_not_installed_error,
    mail_send_failed_error,
    mail_settings_unreadable_error,
    report_missing_error,
    report_not_a_file_error,
    report_stale_error,
    send_html_exception_tag,
)
from pybreeze.utils.exception.exceptions import ITESendHtmlReportException
from pybreeze.utils.logging.logger import pybreeze_logger

DEFAULT_REPORT_PATH = "default_name.html"

# How much older than the run a report may look and still be its own: file
# systems keep modification times to a second or two
_MTIME_SLACK_SECONDS = 2.0


def send_after_test(
        html_report_path: str | None = None,
        *,
        not_before: float | None = None,
        on_done: Callable[[str | None], None] | None = None,
) -> None:
    """Mail a finished run's HTML report, on a thread of its own.

    This is a run's done-hook, called on the UI thread as the run ends. The
    SMTP connect (made when the client is built), the login and the send take
    as long as the mail server does, and the IDE used to be frozen for all of
    it. Whatever goes wrong is logged by that thread, never raised.

    :param html_report_path: the report to send; ``default_name.html`` when None
    :param not_before: see ``send_report``
    :param on_done: called on the mail thread with ``send_report``'s answer
    """
    def send() -> None:
        try:
            outcome = send_report(html_report_path, not_before=not_before)
        # The last stop on this thread: anything je_mail_thunder raises past
        # send_report must still reach on_done, or the run window never says
        except Exception as error:  # noqa: BLE001 — logged, and reported to the run window
            pybreeze_logger.error("Sending the report failed: %r", error)
            outcome = f"sending failed ({type(error).__name__})"
        if on_done is not None:
            on_done(outcome)

    threading.Thread(target=send, name="pybreeze-report-mail", daemon=True).start()


def send_report(html_report_path: str | None = None, *, not_before: float | None = None) -> str | None:
    """Mail the HTML report to the configured mail user, and log what went wrong.

    Blocks for as long as the mail server takes; ``send_after_test`` runs it
    off the UI thread.

    :param html_report_path: the report to send; ``default_name.html`` when None
    :param not_before: when the run started (``time.time()``). A report last
        written before then is an earlier run's, left behind by a run that
        wrote none, and is not sent.
    :return: None once the report is sent, else why it was not, in words for
        the run window (no path, address or server reply: those are logged)
    """
    try:
        from je_mail_thunder import SMTPWrapper, get_mail_thunder_os_environ, read_output_content
        from je_mail_thunder.utils.exception.exceptions import MailThunderException
    except ImportError as error:
        pybreeze_logger.error("Cannot send the report without je_mail_thunder: %r", error)
        return mail_not_installed_error

    report_path = html_report_path if html_report_path is not None else DEFAULT_REPORT_PATH
    problem = _report_problem(report_path, not_before)
    if problem is not None:
        pybreeze_logger.error("Report not sent (%s): %s", problem, report_path)
        return problem
    try:
        user = _mail_user(read_output_content, get_mail_thunder_os_environ)
    # je_mail_thunder reads mail_thunder_content.json in the locale's encoding
    # and parses it unguarded: a broken file, or UTF-8 text on a cp950
    # system, raised out of the mail thread
    except (OSError, ValueError, MailThunderException) as error:
        pybreeze_logger.error("The mail settings file could not be read: %r", error)
        return mail_settings_unreadable_error
    if user is None:
        pybreeze_logger.error("Cannot determine mail user for sending report")
        return mail_no_user_error
    try:
        with open(report_path, encoding="utf-8") as file:
            html_string = file.read()
        # The client connects when it is built, and quits when the block ends
        # however it ends.
        with SMTPWrapper() as mail_thunder_smtp:
            mail_thunder_smtp.later_init()
            if not mail_thunder_smtp.login_state:
                raise ITESendHtmlReportException
            message = mail_thunder_smtp.create_message_with_attach(
                html_string,
                {"Subject": "Test Report", "To": user, "From": user},
                report_path, use_html=True)
            mail_thunder_smtp.send_message(message)
    except ITESendHtmlReportException as error:
        pybreeze_logger.error("%r %s", error, send_html_exception_tag)
        return mail_login_failed_error
    # OSError covers the socket and every smtplib error; ValueError a report
    # that is not UTF-8
    except (OSError, ValueError, MailThunderException) as error:
        pybreeze_logger.error("Failed to send report: %r", error)
        return mail_send_failed_error.format(kind=type(error).__name__)
    return None


def _report_problem(report_path: str, not_before: float | None) -> str | None:
    """Why *report_path* is not this run's report to send, or None when it is."""
    name = os.path.basename(report_path)
    try:
        written = os.stat(report_path)
    except OSError:
        return report_missing_error.format(name=name)
    if not os.path.isfile(report_path):
        return report_not_a_file_error.format(name=name)
    if not_before is not None and written.st_mtime < not_before - _MTIME_SLACK_SECONDS:
        return report_stale_error.format(name=name)
    return None


def _mail_user(read_output_content, get_mail_thunder_os_environ) -> str | None:
    """The address to send to: the saved content file's user, else the environment's."""
    user_info = read_output_content()
    if isinstance(user_info, dict) and user_info.get("user") is not None:
        return user_info["user"]
    return get_mail_thunder_os_environ().get("mail_thunder_user")
