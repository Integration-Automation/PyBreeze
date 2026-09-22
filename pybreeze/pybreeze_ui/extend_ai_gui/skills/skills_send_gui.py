from __future__ import annotations

import requests
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit,
    QTextEdit, QPushButton, QLabel, QComboBox
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
    ResponseTooLargeError, read_capped_text, CONNECT_TIMEOUT, succeeded, truncate_for_display,
)
from pybreeze.utils.network.url_validation import UnsafeURLError, validate_url


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
            response = requests.post(
                self.api_url, json={"code": self.code_text},
                timeout=(CONNECT_TIMEOUT, 30), allow_redirects=False, stream=True,
            )
            body = read_capped_text(response)
            if succeeded(response):
                self.answered.emit(body)
            elif response.is_redirect:
                self.answered.emit(
                    language_wrapper.language_word_dict.get(
                        "skills_error_status").format(
                        status_code=response.status_code,
                        text=f"Redirect to {response.headers.get('Location', 'unknown')}"))
            elif response.status_code in (401, 403):
                self.error.emit(
                    language_wrapper.language_word_dict.get(
                        "skills_error_status").format(
                        status_code=response.status_code,
                        text="Authentication/Authorization failed"))
            elif response.status_code >= 500:
                self.error.emit(
                    language_wrapper.language_word_dict.get(
                        "skills_error_status").format(
                        status_code=response.status_code,
                        text=f"Server error: {truncate_for_display(body)}"))
            else:
                self.answered.emit(
                    language_wrapper.language_word_dict.get(
                        "skills_error_status").format(
                        status_code=response.status_code, text=truncate_for_display(body)))
        except (requests.RequestException, ResponseTooLargeError, UnsafeURLError) as e:
            pybreeze_logger.error("Skills send request failed: %r", e)
            self.error.emit(language_wrapper.language_word_dict.get("skills_exception").format(error=str(e)))


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
        self.prompt_input.setPlainText(load_prompt(name, built_in))

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
