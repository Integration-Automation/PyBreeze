from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit, QComboBox, QPushButton, \
    QMessageBox
from je_editor import language_wrapper

from automation_ide.automation_editor_ui.extend_ai_gui.ai_gui_global_variable import COT_TEMPLATE_FILES
from automation_ide.automation_editor_ui.extend_ai_gui.code_review.code_review_thread import SenderThread


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
