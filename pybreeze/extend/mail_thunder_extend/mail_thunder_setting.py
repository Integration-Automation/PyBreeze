from __future__ import annotations

import sys
from email.mime.multipart import MIMEMultipart

from pybreeze.utils.exception.exception_tags import send_html_exception_tag
from pybreeze.utils.exception.exceptions import ITESendHtmlReportException


def send_after_test(html_report_path: str | None = None) -> None:
    try:
        from je_mail_thunder import SMTPWrapper
        mail_thunder_smtp: SMTPWrapper = SMTPWrapper()
        if html_report_path is None and mail_thunder_smtp.login_state:
            user: str = mail_thunder_smtp.user
            with open("default_name.html") as file:
                html_string: str = file.read()
            message = mail_thunder_smtp.create_message_with_attach(
                html_string,
                {"Subject": "Test Report", "To": user, "From": user},
                "default_name.html", use_html=True)
            mail_thunder_smtp.send_message(message)
            mail_thunder_smtp.quit()
        elif mail_thunder_smtp.login_state:
            user: str = mail_thunder_smtp.user
            with open(html_report_path) as file:
                html_string: str = file.read()
            message: MIMEMultipart = mail_thunder_smtp.create_message_with_attach(
                html_string,
                {"Subject": "Test Report", "To": user, "From": user},
                html_report_path, use_html=True)
            mail_thunder_smtp.send_message(message)
            mail_thunder_smtp.quit()
        else:
            raise ITESendHtmlReportException
    except ITESendHtmlReportException as error:
        print(repr(error), file=sys.stderr)
        print(send_html_exception_tag, file=sys.stderr)
