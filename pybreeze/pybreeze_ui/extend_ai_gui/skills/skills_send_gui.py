from __future__ import annotations

import requests
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit,
    QTextEdit, QPushButton, QLabel, QComboBox, QMessageBox
)
from PySide6.QtCore import QThread, Signal
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.extend_ai_gui.ai_gui_global_variable import (
    SKILLS_TEMPLATE_FILES, SKILLS_TEMPLATE_RELATION
)
from pybreeze.pybreeze_ui.extend_ai_gui.prompt_store import load_prompt
from pybreeze.pybreeze_ui.thread_keeper import let_run_out
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.network.http_client import (
    ResponseTooLargeError, read_capped_text, CONNECT_TIMEOUT, describe_request_error, succeeded,
    truncate_for_display,
)
from pybreeze.utils.network.public_http import public_session
from pybreeze.utils.network.url_validation import UnsafeURLError, validate_url


# Where a skill template wants the code; the user puts it there before sending
CODE_PLACEHOLDER = "{code_diff}"


class RequestThread(QThread):
    # Not "finished": that is QThread's own end-of-thread signal, and hiding it
    # left nothing to re-enable the send button when run() ended some other way.
    answered = Signal(str)   # 成功或錯誤訊息 / the answer, or a status to show
    error = Signal(str)

    def __init__(self, api_url, code_text):
        super().__init__()
        self.api_url = api_url
        self.code_text = code_text

    def run(self):
        try:
            validate_url(self.api_url)
            with public_session() as session:
                response = session.post(
                    self.api_url, json={"code": self.code_text},
                    timeout=(CONNECT_TIMEOUT, 30), allow_redirects=False, stream=True,
                )
                body = read_capped_text(response)
            if succeeded(response):
                self.answered.emit(body)
                return
            is_error, text = describe_failed_status(response, body)
            message = language_wrapper.language_word_dict.get("skills_error_status").format(
                status_code=response.status_code, text=text)
            (self.error if is_error else self.answered).emit(message)
        except (requests.RequestException, ResponseTooLargeError, UnsafeURLError) as e:
            # Not %r: a requests error carries the whole URL, which may hold a token.
            pybreeze_logger.error("Skills send request failed: %s", type(e).__name__)
            self.error.emit(language_wrapper.language_word_dict.get("skills_exception").format(error=describe_request_error(e)))


def describe_failed_status(response, body: str) -> tuple[bool, str]:
    """Say what a non-2xx answer means: whether it is an error, and in what words.

    A redirect (not followed) and an ordinary client error are shown as the
    answer; a refused request and a server error are errors.
    """
    if response.is_redirect:
        return False, f"Redirect to {response.headers.get('Location', 'unknown')}"
    if response.status_code in (401, 403):
        return True, "Authentication/Authorization failed"
    if response.status_code >= 500:
        return True, f"Server error: {truncate_for_display(body)}"
    return False, truncate_for_display(body)


class SkillsSendGUI(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        # API URL 輸入框
        self.api_url_label = QLabel(language_wrapper.language_word_dict.get("skills_api_url_label"))
        self.api_url_input = QLineEdit()
        self.api_url_input.setPlaceholderText(language_wrapper.language_word_dict.get("skills_api_url_placeholder"))
        layout.addWidget(self.api_url_label)
        layout.addWidget(self.api_url_input)

        # Prompt 選擇下拉選單
        self.prompt_select_label = QLabel(language_wrapper.language_word_dict.get("skills_prompt_select_label"))
        self.prompt_select = QComboBox()
        self.prompt_select.addItems(SKILLS_TEMPLATE_FILES)
        self.prompt_select.currentTextChanged.connect(self.load_selected_prompt)
        layout.addWidget(self.prompt_select_label)
        layout.addWidget(self.prompt_select)

        # Prompt 輸入區域
        self.prompt_label = QLabel(language_wrapper.language_word_dict.get("skills_prompt_label"))
        self.prompt_input = QTextEdit()
        layout.addWidget(self.prompt_label)
        layout.addWidget(self.prompt_input)

        # 傳送按鈕
        self.send_button = QPushButton(language_wrapper.language_word_dict.get("skills_send_button"))
        self.send_button.clicked.connect(self.send_prompt)
        layout.addWidget(self.send_button)

        # 回傳結果顯示區域
        self.response_label = QLabel(language_wrapper.language_word_dict.get("skills_response_label"))
        self.response_output = QTextEdit()
        self.response_output.setReadOnly(True)
        layout.addWidget(self.response_label)
        layout.addWidget(self.response_output)

        self.setLayout(layout)

        self.thread = None  # 保存執行緒
        # 編輯區裡是哪個模板：換模板被拒時選單要回到這裡
        # The template in the edit area: where the selector goes back to when a switch is refused
        self._shown_template = self.prompt_select.currentText()
        # 開啟時就把選到的那個模板載進來，選單才不是擺著好看
        # Load the selected template on open, so the selector does something
        self.load_selected_prompt(self.prompt_select.currentText())

    def load_selected_prompt(self, name: str) -> None:
        """
        把選到的 skill 模板載進編輯區
        Put the selected skill template in the edit area.

        以編輯過的檔案為準，沒有就用內建的；載進來以後仍然可以改，送出的是編輯區的內容。
        The edited file wins over the built-in one. What lands here stays
        editable: what is sent is whatever the edit area holds.

        :param name: 模板檔名 / the template's file name
        """
        built_in = SKILLS_TEMPLATE_RELATION.get(name)
        if built_in is None:
            return
        if self.prompt_input.document().isModified() and not self._may_replace_edits(name):
            # 選單回到編輯區裡的模板，不再觸發一次
            # Put the selector back on the template being edited, without coming here again
            self.prompt_select.blockSignals(True)
            self.prompt_select.setCurrentText(self._shown_template)
            self.prompt_select.blockSignals(False)
            return
        self.prompt_input.setPlainText(load_prompt(name, built_in))
        self.prompt_input.document().setModified(False)
        self._shown_template = name

    def _may_replace_edits(self, name: str) -> bool:
        """
        編輯區有修改時，問使用者能不能換掉；以前一換模板，貼上的程式碼就沒了
        Ask whether the edited prompt may be replaced: switching templates used
        to throw away the code the user had pasted into it.
        """
        reply = QMessageBox.question(
            self, language_wrapper.language_word_dict.get("skills_prompt_select_label"),
            language_wrapper.language_word_dict.get("skills_switch_over_edits").format(name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        return reply == QMessageBox.StandardButton.Yes

    def send_prompt(self):
        # Ignore re-submits while a request is in flight: reassigning self.thread
        # here would drop a still-running QThread (risking "destroyed while
        # running") and let a stale worker overwrite the panel.
        if self.thread is not None and self.thread.isRunning():
            return

        api_url = self.api_url_input.text().strip()
        prompt_text = self.prompt_input.toPlainText().strip()

        if not api_url or not prompt_text:
            self.response_output.setPlainText(language_wrapper.language_word_dict.get("skills_missing_input"))
            return
        if CODE_PLACEHOLDER in prompt_text:
            # 模板原封不動送出，端點收到的是一份沒有程式碼的審查請求
            # Sent as it is, the template asked for a review of no code at all
            self.response_output.setPlainText(language_wrapper.language_word_dict.get("skills_code_missing"))
            return

        # 顯示「產生中」
        self.response_output.setPlainText(language_wrapper.language_word_dict.get("skills_generating"))

        # 啟動 QThread
        self.send_button.setEnabled(False)
        self.thread = RequestThread(api_url, prompt_text)
        self.thread.answered.connect(self.on_finished)
        self.thread.error.connect(self.on_error)
        # However run() ends -- including an exception outside its handler --
        # the button comes back.
        self.thread.finished.connect(lambda: self.send_button.setEnabled(True))
        self.thread.start()

    def on_finished(self, result):
        self.response_output.setPlainText(result)
        self.send_button.setEnabled(True)

    def on_error(self, error_msg):
        self.response_output.setPlainText(error_msg)
        self.send_button.setEnabled(True)

    def closeEvent(self, event):
        """Let a request still in flight finish on its own, without this panel.

        Its answers are cut off from the panel, and the thread is kept
        referenced until it ends, so it is never destroyed while running. The
        panel does not wait for it: the request can take the whole read timeout,
        and waiting froze the IDE for that long.
        """
        thread = self.thread
        if thread is not None and thread.isRunning():
            let_run_out(thread, thread.answered, thread.error)
        event.accept()
