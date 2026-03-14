import sys
import requests
import os
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QTextEdit, QComboBox, QLabel, QSizePolicy
)
from je_editor import language_wrapper


class AICodeReviewClient(QWidget):
    def __init__(self):
        super().__init__()
        self.word_dict = language_wrapper.language_word_dict
        self.setWindowTitle(self.word_dict.get(
            "ai_code_review_gui_window_title"
        ))

        # 記錄接受/拒絕次數
        self.accept_count = 0
        self.reject_count = 0
        self.stats_file = "response_stats.txt"
        self.url_file = "urls.txt"

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
        """Send HTTP request and display result"""
        url = self.url_input.text().strip()
        method = self.method_box.currentText()
        code_content = self.code_input.toPlainText().strip()

        if not url:
            self.response_panel.setPlainText(
                self.word_dict.get("ai_code_review_gui_message_enter_valid_url"))
            return

        # 檢查 URL 是否已紀錄
        if os.path.exists(self.url_file):
            with open(self.url_file, "r", encoding="utf-8") as f:
                urls = [line.strip() for line in f.readlines()]
        else:
            urls = []

        if url in urls:
            self.response_panel.setPlainText(
                self.word_dict.get("ai_code_review_gui_message_url_already_recorded"))
        else:
            with open(self.url_file, "a", encoding="utf-8") as f:
                f.write(url + "\n")
            self.response_panel.setPlainText(
                self.word_dict.get("ai_code_review_gui_message_new_url_recorded"))

        try:
            if method == "GET":
                response = requests.get(url)
            elif method == "POST":
                response = requests.post(url, data={"code": code_content})
            elif method == "PUT":
                response = requests.put(url, data={"code": code_content})
            elif method == "DELETE":
                response = requests.delete(url)
            else:
                self.response_panel.setPlainText(
                    self.word_dict.get("ai_code_review_gui_message_unsupported_http_method"))
                return

            self.response_panel.append(response.text)

        except Exception as e:
            self.response_panel.setPlainText(f"{self.word_dict.get('ai_code_review_gui_message_error')}: {e}")

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