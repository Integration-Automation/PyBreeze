from __future__ import annotations

import os
from email.mime.multipart import MIMEMultipart

from pybreeze.utils.exception.exception_tags import send_html_exception_tag
from pybreeze.utils.exception.exceptions import ITESendHtmlReportException
from pybreeze.utils.logging.logger import pybreeze_logger


def send_after_test(html_report_path: str | None = None) -> None:
    try:
        from je_mail_thunder import SMTPWrapper, read_output_content, get_mail_thunder_os_environ
        mail_thunder_smtp: SMTPWrapper = SMTPWrapper()
        mail_thunder_smtp.later_init()

        if not mail_thunder_smtp.login_state:
            raise ITESendHtmlReportException

        # Determine which report file to use
        report_path = html_report_path if html_report_path is not None else "default_name.html"

        if not os.path.isfile(report_path):
            pybreeze_logger.error(f"Report file not found: {report_path}")
            return

        # Resolve user from content file or environment variables
        user: str | None = None
        user_info = read_output_content()
        if user_info is not None and isinstance(user_info, dict):
            user = user_info.get("user")
        if user is None:
            env_info = get_mail_thunder_os_environ()
            user = env_info.get("mail_thunder_user")
        if user is None:
            pybreeze_logger.error("Cannot determine mail user for sending report")
            return

        with open(report_path, encoding="utf-8") as file:
            html_string: str = file.read()
        message: MIMEMultipart = mail_thunder_smtp.create_message_with_attach(
            html_string,
            {"Subject": "Test Report", "To": user, "From": user},
            report_path, use_html=True)
        mail_thunder_smtp.send_message(message)
        mail_thunder_smtp.quit()
    except ITESendHtmlReportException as error:
        pybreeze_logger.error(f"{repr(error)} {send_html_exception_tag}")
    except FileNotFoundError as error:
        pybreeze_logger.error(f"Report file not found: {error}")
    except Exception as error:
        pybreeze_logger.error(f"Failed to send report: {error}")
