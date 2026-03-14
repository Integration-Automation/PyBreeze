import sys
import requests
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLineEdit,
    QTextEdit, QPushButton, QLabel, QComboBox
)
from PySide6.QtCore import QThread, Signal
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.extend_ai_gui.ai_gui_global_variable import SKILLS_TEMPLATE_FILES


class RequestThread(QThread):
    finished = Signal(str)   # 成功或錯誤訊息
    error = Signal(str)

    def __init__(self, api_url, code_text):
        super().__init__()
        self.api_url = api_url
        self.code_text = code_text

    def run(self):
        try:
            response = requests.post(self.api_url, json={"code": self.code_text})
            if response.status_code == 200:
                self.finished.emit(response.text)
            else:
                self.finished.emit(
                    language_wrapper.language_word_dict.get(
                        "skills_error_status").format(status_code=response.status_code, text=response.text))
        except Exception as e:
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

    def send_prompt(self):
        api_url = self.api_url_input.text().strip()
        prompt_text = self.prompt_input.toPlainText().strip()

        if not api_url or not prompt_text:
            self.response_output.setPlainText(language_wrapper.language_word_dict.get("skills_missing_input"))
            return

        # 顯示「產生中」
        self.response_output.setPlainText(language_wrapper.language_word_dict.get("skills_generating"))

        # 啟動 QThread
        self.thread = RequestThread(api_url, prompt_text)
        self.thread.finished.connect(self.on_finished)
        self.thread.error.connect(self.on_error)
        self.thread.start()

    def on_finished(self, result):
        self.response_output.setPlainText(result)

    def on_error(self, error_msg):
        self.response_output.setPlainText(error_msg)
