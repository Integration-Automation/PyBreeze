from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit, QComboBox, QPushButton, \
    QMessageBox
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.extend_ai_gui.ai_gui_global_variable import COT_TEMPLATE_FILES
from pybreeze.pybreeze_ui.extend_ai_gui.code_review.code_review_thread import SenderThread
from pybreeze.pybreeze_ui.thread_keeper import let_run_out


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
        self.thread = None

    def show_response(self, filename):
        if filename in self.responses:
            self.response_view.setPlainText(self.responses[filename])

    def start_sending(self):
        # 取得 URL
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Warning", language_wrapper.language_word_dict.get("cot_gui_error_no_url"))
            return
        # The URL is checked by the worker, which reports a refusal as the
        # "error" answer: checked here too, its DNS lookup froze the IDE.

        # Ignore re-submits while a run is in flight so we never drop a running
        # QThread or interleave two review passes into the same response store.
        if self.thread is not None and self.thread.isRunning():
            return

        # A new run starts from nothing: answers about the previous code, or its
        # "error", must not sit beside this run's.
        self.responses.clear()
        self.response_selector.clear()
        self.response_view.clear()

        # 啟動傳送 Thread
        self.send_button.setEnabled(False)
        self.thread = SenderThread(files=self.files, code=self.code_paste_area.toPlainText(), url=url)
        self.thread.update_response.connect(self.handle_response)
        self.thread.finished.connect(self._enable_send)
        self.thread.start()

    def _enable_send(self) -> None:
        """Let the next request be sent, however this one ended.

        A bound method, not a lambda: the thread's connection holding a lambda
        that held the panel kept both alive after the panel was closed and
        deleted, a cycle through Qt that Python's collector cannot see.
        """
        self.send_button.setEnabled(True)

    def handle_response(self, filename, response):
        self.responses[filename] = response
        if self.response_selector.findText(filename) == -1:
            self.response_selector.addItem(filename)
        # 自動顯示最新回覆
        self.response_selector.setCurrentText(filename)
        self.show_response(filename)

    def closeEvent(self, event):
        """Ask a review still going to stop after its current request, without waiting.

        A request can take its whole read timeout, so waiting here froze the IDE
        that long. The thread is cut off from this widget and kept until it
        ends: a QThread destroyed while running aborts the process.
        """
        thread = self.thread
        if thread is not None and thread.isRunning():
            thread.requestInterruption()
            let_run_out(thread, thread.update_response)
        event.accept()
