from __future__ import annotations

import os
import threading

from pybreeze.utils.exception.exception_tags import send_html_exception_tag
from pybreeze.utils.exception.exceptions import ITESendHtmlReportException
from pybreeze.utils.logging.logger import pybreeze_logger

DEFAULT_REPORT_PATH = "default_name.html"


def send_after_test(html_report_path: str | None = None) -> None:
    """Mail a finished run's HTML report, on a thread of its own.

    This is a run's done-hook, called on the UI thread as the run ends. The
    SMTP connect (made when the client is built), the login and the send take
    as long as the mail server does, and the IDE used to be frozen for all of
    it. Whatever goes wrong is logged by that thread, never raised.

    :param html_report_path: the report to send; ``default_name.html`` when None
    """
    threading.Thread(
        target=send_report, args=(html_report_path,), name="pybreeze-report-mail", daemon=True
    ).start()


def send_report(html_report_path: str | None = None) -> None:
    """Mail the HTML report to the configured mail user, and log what went wrong.

    Blocks for as long as the mail server takes; ``send_after_test`` runs it
    off the UI thread.

    :param html_report_path: the report to send; ``default_name.html`` when None
    """
    try:
        from je_mail_thunder import SMTPWrapper, get_mail_thunder_os_environ, read_output_content
        from je_mail_thunder.utils.exception.exceptions import MailThunderException
    except ImportError as error:
        pybreeze_logger.error("Cannot send the report without je_mail_thunder: %r", error)
        return

    report_path = html_report_path if html_report_path is not None else DEFAULT_REPORT_PATH
    if not os.path.isfile(report_path):
        pybreeze_logger.error("Report file not found: %s", report_path)
        return
    user = _mail_user(read_output_content, get_mail_thunder_os_environ)
    if user is None:
        pybreeze_logger.error("Cannot determine mail user for sending report")
        return
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
    # OSError covers the socket and every smtplib error; ValueError a report
    # that is not UTF-8
    except (OSError, ValueError, MailThunderException) as error:
        pybreeze_logger.error("Failed to send report: %r", error)


def _mail_user(read_output_content, get_mail_thunder_os_environ) -> str | None:
    """The address to send to: the saved content file's user, else the environment's."""
    user_info = read_output_content()
    if isinstance(user_info, dict) and user_info.get("user") is not None:
        return user_info["user"]
    return get_mail_thunder_os_environ().get("mail_thunder_user")
