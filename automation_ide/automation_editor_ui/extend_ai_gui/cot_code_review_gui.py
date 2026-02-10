import sys

import requests
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QLineEdit, QComboBox, QMessageBox
)
from je_editor import language_wrapper

from automation_ide.automation_editor_ui.extend_ai_gui.ai_gui_global_variable import COT_TEMPLATE_FILES, \
    COT_TEMPLATE_RELATION
from automation_ide.automation_editor_ui.extend_ai_gui.prompt_edit_gui.cot_code_review_prompt_templates.global_rule import \
    build_global_rule_template
from automation_ide.automation_editor_ui.extend_multi_language.update_language_dict import update_language_dict


# Worker Thread 負責傳送資料
class SenderThread(QThread):
    update_response = Signal(str, str)  # (filename, response)

    def __init__(self, files: list, code: str, url: str):
        super().__init__()
        self.files = files
        self.code = code
        self.url = url

    def run(self):
        code = self.code
        first_code_review_result = None
        first_summary_result = None
        linter_result = None
        code_smell_result = None
        for file in self.files:
            match file:
                case "first_summary_prompt.md":
                    first_summary_prompt = COT_TEMPLATE_RELATION.get("first_summary_prompt.md")
                    prompt = build_global_rule_template(
                        prompt=first_summary_prompt.format(code_diff=code)
                    )
                case "first_code_review.md":
                    first_code_review_prompt = COT_TEMPLATE_RELATION.get("first_code_review.md")
                    prompt = build_global_rule_template(
                        prompt=first_code_review_prompt.format(code_diff=code)
                    )
                case "linter.md":
                    linter_prompt = COT_TEMPLATE_RELATION.get("linter.md")
                    prompt = build_global_rule_template(
                        prompt=linter_prompt.format(code_diff=code)
                    )
                case "code_smell_detector.md":
                    code_smell_detector_prompt = COT_TEMPLATE_RELATION.get("code_smell_detector.md")
                    prompt = build_global_rule_template(
                        prompt=code_smell_detector_prompt.format(code_diff=code)
                    )
                case "total_summary.md":
                    total_summary_prompt = COT_TEMPLATE_RELATION.get("total_summary.md")
                    prompt = build_global_rule_template(
                        prompt=total_summary_prompt.format(
                            first_code_review=first_code_review_result,
                            first_summary=first_summary_result,
                            linter_result=linter_result,
                            code_smell_result=code_smell_result,
                            code_diff=code,
                        )
                    )
                case _:
                    continue

            try:
                # 傳送到指定 URL
                resp = requests.post(self.url, json={"prompt": prompt})
                reply_text = resp.text
                match file:
                    case "first_summary_prompt.md":
                        first_summary_result = reply_text
                    case "first_code_review.md":
                        first_code_review_result = reply_text
                    case "linter.md":
                        linter_result = reply_text
                    case "code_smell_detector.md":
                        code_smell_result = reply_text
                    case _:
                        continue
            except Exception as e:
                reply_text = f"{language_wrapper.language_word_dict.get("cot_gui_error_sending")} {file} {e}"

            # 發送訊號更新 UI
            self.update_response.emit(file, reply_text)


class CoTCodeReviewGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(language_wrapper.language_word_dict.get("cot_gui_window_title"))

        # 檔案清單
        self.files = COT_TEMPLATE_FILES

        # UI 元件
        layout = QVBoxLayout()

        # URL 輸入框
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel(language_wrapper.language_word_dict.get("cot_gui_label_api_url")))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(language_wrapper.language_word_dict.get("cot_gui_placeholder_api_url"))
        url_layout.addWidget(self.url_input)
        layout.addLayout(url_layout)

        # 傳送資料區域
        self.code_paste_area = QTextEdit()
        self.code_paste_area.setPlaceholderText(
            language_wrapper.language_word_dict.get("cot_gui_placeholder_code_paste_area"))
        layout.addWidget(QLabel(language_wrapper.language_word_dict.get("cot_gui_label_prompt_area")))
        layout.addWidget(self.code_paste_area)

        # 回傳區域
        self.response_selector = QComboBox()  # 改用 ComboBox
        self.response_view = QTextEdit()
        self.response_view.setReadOnly(True)  # 可複製但不可編輯

        hbox_layout = QHBoxLayout()
        hbox_layout.addWidget(self.response_selector, 2)
        hbox_layout.addWidget(self.response_view, 5)

        layout.addWidget(QLabel(language_wrapper.language_word_dict.get("cot_gui_label_response_area")))
        layout.addLayout(hbox_layout)

        # 傳送按鈕
        self.send_button = QPushButton(language_wrapper.language_word_dict.get("cot_gui_button_send"))
        layout.addWidget(self.send_button)

        self.setLayout(layout)

        # 綁定事件
        self.response_selector.currentTextChanged.connect(self.show_response)
        self.send_button.clicked.connect(self.start_sending)

        # 儲存回覆
        self.responses = {}

    def show_response(self, filename):
        if filename in self.responses:
            self.response_view.setPlainText(self.responses[filename])

    def start_sending(self):
        # 取得 URL
        url = self.url_input.text().strip()
        if not url:
            message_box = QMessageBox()
            message_box.warning(self, "Warning", language_wrapper.language_word_dict.get("cot_gui_error_no_url"))
            message_box.exec_()
            return

        # 啟動傳送 Thread
        self.thread = SenderThread(files=self.files, code=self.code_paste_area.toPlainText(), url=url)
        self.thread.update_response.connect(self.handle_response)
        self.thread.start()

    def handle_response(self, filename, response):
        self.responses[filename] = response
        self.response_selector.addItem(filename)  # 加入 ComboBox
        # 自動顯示最新回覆
        self.response_selector.setCurrentText(filename)
