from __future__ import annotations

# Worker Thread 負責傳送資料
import requests
from PySide6.QtCore import QThread, Signal
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.extend_ai_gui.code_review.cot_chain import (
    CODE_DIFF, STEP_RESULT_KEY, build_prompt
)
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.network.http_client import (
    ResponseTooLargeError, read_capped_text, CONNECT_TIMEOUT,
)
from pybreeze.utils.network.url_validation import UnsafeURLError, validate_url


class SenderThread(QThread):
    update_response = Signal(str, str)  # (filename, response)

    def __init__(self, files: list, code: str, url: str):
        super().__init__()
        self.files = files
        self.code = code
        self.url = url

    def run(self):
        try:
            validate_url(self.url)
        except UnsafeURLError as error:
            pybreeze_logger.error("CoT code review URL rejected: %r", error)
            self.update_response.emit("error", str(error))
            return
        # One session reuses a single TCP/TLS connection across all the
        # sequential per-template POSTs to the same endpoint.
        session = requests.Session()
        try:
            self._run_templates(session, self.code)
        finally:
            session.close()

    def _run_templates(self, session: requests.Session, code: str) -> None:
        # Answers accumulate here as the chain runs; a later step quotes whichever
        # of them its template asks for. See cot_chain for the wiring.
        results: dict[str, str] = {CODE_DIFF: code}
        for file in self.files:
            # Stop promptly if the widget is closing instead of firing off the
            # remaining per-template POSTs.
            if self.isInterruptionRequested():
                return
            prompt = build_prompt(file, results)
            if prompt is None:
                continue
            reply_text, answered = self._ask(session, file, prompt)
            result_key = STEP_RESULT_KEY.get(file)
            # A failure message is shown but never stored: a later step must not
            # quote "could not send" back to the model as if it were a review.
            if answered and result_key is not None:
                results[result_key] = reply_text
            # 發送訊號更新 UI
            self.update_response.emit(file, reply_text)

    def _ask(self, session: requests.Session, file: str, prompt: str) -> tuple[str, bool]:
        """Send one step's prompt; return its answer and whether it arrived."""
        try:
            # 傳送到指定 URL（重用 session 連線）
            resp = session.post(
                self.url, json={"prompt": prompt},
                timeout=(CONNECT_TIMEOUT, 60), allow_redirects=False, stream=True,
            )
            return read_capped_text(resp), True
        except (requests.RequestException, ResponseTooLargeError) as error:
            pybreeze_logger.error("CoT code review send failed for %s: %r", file, error)
            word = language_wrapper.language_word_dict
            return f"{word.get('cot_gui_error_sending')} {file} {error}", False
