from __future__ import annotations

import sys
from pathlib import Path

import requests
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QTextEdit, QComboBox, QLabel, QSizePolicy
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.thread_keeper import let_run_out
from pybreeze.utils.app_dirs import pybreeze_data_dir
from pybreeze.utils.hash_tools.hash_text import hash_text
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.network.http_client import (
    ResponseTooLargeError, read_capped_text, CONNECT_TIMEOUT,
)
from pybreeze.utils.network.url_validation import UnsafeURLError, validate_url


# What the "seen this URL before" file keeps. An API URL can carry a token in
# its query, and this project treats one as a credential, so only a fingerprint
# of the URL is written to disk.
_FINGERPRINT_ALGORITHM = "sha256"
_FINGERPRINT_LENGTH = 64


def url_fingerprint(url: str) -> str:
    """Return the fingerprint recorded for *url* instead of the URL itself."""
    return hash_text(url, _FINGERPRINT_ALGORITHM)


def looks_like_a_fingerprint(line: str) -> bool:
    """Whether *line* is already a fingerprint rather than a URL."""
    return len(line) == _FINGERPRINT_LENGTH and all(c in "0123456789abcdef" for c in line)

# The methods the panel offers / 面板提供的方法
SUPPORTED_METHODS = ("GET", "POST", "PUT", "DELETE")
# The methods that carry the code in a body / 會把程式碼放進 body 的方法
METHODS_WITH_A_BODY = ("POST", "PUT")


class ReviewRequestThread(QThread):
    """One review request, off the UI thread.

    The IDE must stay usable while an endpoint thinks: the request can take the
    connect timeout plus 30 s per read, and the body is streamed under a cap
    after that. Only these two signals touch the UI, and they are delivered on
    the UI thread.
    """

    answered = Signal(str)
    failed = Signal(str)

    def __init__(self, method: str, url: str, code_text: str) -> None:
        super().__init__()
        self._method = method
        self._url = url
        self._code_text = code_text

    def run(self) -> None:
        try:
            validate_url(self._url)
            response = self._send()
            body = read_capped_text(response)
            if response.ok:
                self.answered.emit(body)
            else:
                # Without this a 302 (redirects are not followed) or a 500 with
                # an empty body would leave the panel looking like a success.
                self.answered.emit(f"HTTP {response.status_code} {response.reason}\n{body}")
        except (requests.RequestException, ResponseTooLargeError, UnsafeURLError) as error:
            # Not %r: a requests error carries the whole URL, which may hold a token.
            pybreeze_logger.error("AI code review request failed: %s", type(error).__name__)
            self.failed.emit(str(error))

    def _send(self) -> requests.Response:
        """Send the request with the chosen method, code in the body where there is one."""
        send = getattr(requests, self._method.lower())
        options = {"timeout": (CONNECT_TIMEOUT, 30), "allow_redirects": False, "stream": True}
        if self._method in METHODS_WITH_A_BODY:
            return send(self._url, data={"code": self._code_text}, **options)
        return send(self._url, **options)


class AICodeReviewClient(QWidget):
    def __init__(self):
        super().__init__()
        self.word_dict = language_wrapper.language_word_dict
        self.setWindowTitle(self.word_dict.get(
            "ai_code_review_gui_window_title"
        ))

        # 目前在飛的請求 / The request in flight, if any
        self.request_thread: ReviewRequestThread | None = None
        # 記錄接受/拒絕次數
        self.accept_count = 0
        self.reject_count = 0
        # Store under the user's home (like the SSH known_hosts) so the data is
        # stable regardless of which directory the IDE was launched from.
        data_dir = pybreeze_data_dir()
        self.stats_file = str(data_dir / "response_stats.txt")
        self.url_file = str(data_dir / "urls.txt")

        # 主佈局 (垂直)
        main_layout = QVBoxLayout()

        # -------------------------------
        # 上方：URL 與 Method
        # -------------------------------
        top_layout = QHBoxLayout()

        # URL
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel(self.word_dict.get("ai_code_review_gui_label_url")))
        self.url_input = QLineEdit()
        url_layout.addWidget(self.url_input)
        top_layout.addLayout(url_layout)

        # Method
        method_layout = QHBoxLayout()
        method_layout.addWidget(QLabel(self.word_dict.get("ai_code_review_gui_label_method")))
        self.method_box = QComboBox()
        self.method_box.addItems(["GET", "POST", "PUT", "DELETE"])
        method_layout.addWidget(self.method_box)
        top_layout.addLayout(method_layout)

        main_layout.addLayout(top_layout)

        # -------------------------------
        # 中間：左右顯示框 (同樣高)
        # -------------------------------
        middle_layout = QHBoxLayout()

        # 左邊：程式碼輸入
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel(
            self.word_dict.get("ai_code_review_gui_label_code_to_send")))
        self.code_input = QTextEdit()
        self.code_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_layout.addWidget(self.code_input)

        # 右邊：回傳顯示
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel(self.word_dict.get("ai_code_review_gui_label_response")))
        self.response_panel = QTextEdit()
        self.response_panel.setReadOnly(True)
        self.response_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_layout.addWidget(self.response_panel)

        # 放入中間佈局
        middle_layout.addLayout(left_layout, 1)
        middle_layout.addLayout(right_layout, 1)

        main_layout.addLayout(middle_layout)

        # -------------------------------
        # 最下面：發送按鈕
        # -------------------------------
        self.send_button = QPushButton(
            self.word_dict.get("ai_code_review_gui_button_send_request"))
        self.send_button.clicked.connect(self.send_request)
        main_layout.addWidget(self.send_button)

        # -------------------------------
        # 最下面：接受/不接受按鈕
        # -------------------------------
        bottom_layout = QHBoxLayout()
        self.accept_button = QPushButton(
            self.word_dict.get("ai_code_review_gui_button_accept_response"))
        self.reject_button = QPushButton(
            self.word_dict.get("ai_code_review_gui_button_reject_response"))

        # 綁定事件
        self.accept_button.clicked.connect(self.accept_response)
        self.reject_button.clicked.connect(self.reject_response)

        bottom_layout.addWidget(self.accept_button)
        bottom_layout.addWidget(self.reject_button)

        main_layout.addLayout(bottom_layout)

        self.setLayout(main_layout)

    def send_request(self):
        """Start a review request; the answer reaches the panel when it arrives.

        Nothing is sent while one is in flight: replacing a running QThread here
        would risk destroying it mid-run and let a stale answer overwrite a newer
        one.
        """
        if self.request_thread is not None and self.request_thread.isRunning():
            return
        url = self.url_input.text().strip()
        method = self.method_box.currentText()
        code_content = self.code_input.toPlainText().strip()

        if not url:
            self.response_panel.setPlainText(
                self.word_dict.get("ai_code_review_gui_message_enter_valid_url"))
            return
        if method not in SUPPORTED_METHODS:
            self.response_panel.setPlainText(
                self.word_dict.get("ai_code_review_gui_message_unsupported_http_method"))
            return

        # 這個 URL 之前送過嗎 / Has this URL been sent before?
        if self.record_url(url):
            self.response_panel.setPlainText(
                self.word_dict.get("ai_code_review_gui_message_new_url_recorded"))
        else:
            self.response_panel.setPlainText(
                self.word_dict.get("ai_code_review_gui_message_url_already_recorded"))

        self.send_button.setEnabled(False)
        self.request_thread = ReviewRequestThread(method, url, code_content)
        self.request_thread.answered.connect(self.on_answered)
        self.request_thread.failed.connect(self.on_failed)
        self.request_thread.start()

    def on_answered(self, body: str) -> None:
        """Show what came back and let the next request be sent."""
        self.response_panel.append(body)
        self.send_button.setEnabled(True)

    def on_failed(self, message: str) -> None:
        """Show why nothing came back and let the next request be sent."""
        self.response_panel.setPlainText(
            f"{self.word_dict.get('ai_code_review_gui_message_error')}: {message}")
        self.send_button.setEnabled(True)

    def closeEvent(self, event) -> None:
        """Let a request still in flight run out without this panel.

        Waiting for it froze the IDE for as long as the request took; it is cut
        off from the panel instead and kept until it ends, so it is never
        destroyed while running.
        """
        thread = self.request_thread
        if thread is not None and thread.isRunning():
            let_run_out(thread, thread.answered, thread.failed)
        super().closeEvent(event)

    def record_url(self, url: str) -> bool:
        """Record *url* as sent, and say whether it had not been sent before.

        Only a fingerprint is stored. A file still holding URLs from an older
        version is rewritten as fingerprints, so the tokens they may carry stop
        sitting in the user's home directory.
        """
        path = Path(self.url_file)
        lines = []
        if path.is_file():
            lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
                     if line.strip()]
        seen = {line if looks_like_a_fingerprint(line) else url_fingerprint(line)
                for line in lines}
        fingerprint = url_fingerprint(url)
        is_new = fingerprint not in seen
        if is_new or any(not looks_like_a_fingerprint(line) for line in lines):
            seen.add(fingerprint)
            path.write_text("\n".join(sorted(seen)) + "\n", encoding="utf-8")
        return is_new

    def accept_response(self):
        """Accept response code and save"""
        self.accept_count += 1
        self.response_panel.append(f"\n{self.word_dict.get('ai_code_review_gui_status_accepted')}")
        self.save_stats()

    def reject_response(self):
        """Reject response code and save"""
        self.reject_count += 1
        self.response_panel.append(f"\n{self.word_dict.get('ai_code_review_gui_status_rejected')}")
        self.save_stats()

    def save_stats(self):
        """Save accept/reject counts"""
        try:
            with open(self.stats_file, "w", encoding="utf-8") as f:
                f.write(f"Accepted: {self.accept_count}\n")
                f.write(f"Rejected: {self.reject_count}\n")
        except Exception as e:
            self.response_panel.append(f"\n[{self.word_dict.get('ai_code_review_gui_status_save_failed')}: {e}]")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AICodeReviewClient()
    window.showMaximized()
    sys.exit(app.exec())
