from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QTextEdit, QPushButton, QGroupBox, QLabel, QMessageBox
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.extend_ai_gui.ai_gui_global_variable import COT_TEMPLATE_FILES, \
    COT_TEMPLATE_RELATION
from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.prompt_file_io import save_prompt_text
from pybreeze.pybreeze_ui.extend_ai_gui.prompt_store import prompt_dir, prompt_path


class CoTPromptEditor(QWidget):
    def __init__(self, prompt_files=None, parent=None):
        super().__init__(parent)
        self.prompt_files = prompt_files or COT_TEMPLATE_FILES

        # 對應檔案名稱與模板內容
        self.templates = COT_TEMPLATE_RELATION

        self.setWindowTitle(language_wrapper.language_word_dict.get(
            "cot_prompt_editor_window_title"
        ))  # 視窗標題：Prompt 編輯器

        # --- Layouts (版面配置) ---
        main_layout = QVBoxLayout(self)
        top_layout = QHBoxLayout()
        editor_layout = QHBoxLayout()
        bottom_layout = QHBoxLayout()

        # --- ComboBox for selecting files (下拉選單選擇檔案) ---
        self.file_selector = QComboBox()
        self.file_selector.addItems(self.prompt_files)
        self.file_selector.currentIndexChanged.connect(self.load_file_content)

        # --- Left Editable panel (左邊編輯區塊) ---
        self.middle_editor = QTextEdit()
        prompt_group = QGroupBox(language_wrapper.language_word_dict.get(
            "cot_prompt_editor_groupbox_edit_file_content"
        ))  # 左邊編輯檔案內容
        middle_layout = QVBoxLayout()
        middle_layout.addWidget(self.middle_editor)
        prompt_group.setLayout(middle_layout)

        editor_layout.addWidget(prompt_group, 1)

        # --- Buttons ---
        self.create_button = QPushButton(language_wrapper.language_word_dict.get(
            "cot_prompt_editor_button_create_file"
        ))
        self.create_button.clicked.connect(self.create_file)

        self.save_button = QPushButton(language_wrapper.language_word_dict.get(
            "cot_prompt_editor_button_save_file"
        ))
        self.save_button.clicked.connect(self.save_file)

        self.reload_button = QPushButton(language_wrapper.language_word_dict.get(
            "cot_prompt_editor_button_reload_file"
        ))
        self.reload_button.clicked.connect(lambda: self.load_file_content(self.file_selector.currentIndex()))

        bottom_layout.addWidget(self.file_selector)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.reload_button)
        bottom_layout.addWidget(self.save_button)
        bottom_layout.addWidget(self.create_button)

        # 這些檔案覆寫審查實際送出的 prompt，位置要讓人找得到
        # These files override what a review actually sends, so say where they are
        where = QLabel(
            f"{language_wrapper.language_word_dict.get('prompt_editor_stored_at_label')} "
            f"{prompt_dir()}")
        where.setWordWrap(True)

        # --- Combine layouts (組合版面配置) ---
        main_layout.addLayout(top_layout)
        main_layout.addLayout(editor_layout)
        main_layout.addWidget(where)
        main_layout.addLayout(bottom_layout)

        # --- FileSystemWatcher (檔案監控器) ---
        self.watcher = QFileSystemWatcher(
            [str(prompt_path(name)) for name in self.prompt_files])
        self.watcher.fileChanged.connect(self.on_file_changed)

        # 預設載入第一個檔案
        self.load_file_content(0)

    def load_file_content(self, index):
        """載入選擇的檔案內容到左邊編輯區"""
        filename = self.prompt_files[index]
        self.current_file = str(prompt_path(filename))
        path = Path(self.current_file)
        if path.is_file():
            self.middle_editor.setPlainText(path.read_text(encoding="utf-8"))
        else:
            self.middle_editor.setPlainText(language_wrapper.language_word_dict.get(
                "cot_prompt_editor_file_not_exist"
            ).format(filename=filename))

    def create_file(self):
        """建立目前選擇的檔案，若不存在則用模板內容建立"""
        filename = self.current_file
        if Path(filename).is_file():
            QMessageBox.information(
                self,
                language_wrapper.language_word_dict.get("cot_prompt_editor_msgbox_info_title"),
                language_wrapper.language_word_dict.get("cot_prompt_editor_msgbox_file_exists").format(filename=filename))
            return

        template_content = self.templates.get(Path(filename).name, "")
        if not save_prompt_text(
            self, filename, template_content,
            language_wrapper.language_word_dict.get("cot_prompt_editor_msgbox_error_title"),
        ):
            return

        # Only now does the file exist, so only now can it be watched for the
        # external edits this editor promises to pick up.
        self.watcher.addPath(filename)
        QMessageBox.information(
            self,
            language_wrapper.language_word_dict.get("cot_prompt_editor_msgbox_success_title"),
            language_wrapper.language_word_dict.get("cot_prompt_editor_msgbox_file_created").format(filename=filename))
        self.load_file_content(self.file_selector.currentIndex())

    def on_file_changed(self, path):
        """當檔案被外部修改時即時更新"""
        if path == self.current_file:
            self.load_file_content(self.file_selector.currentIndex())

    def save_file(self):
        """將左邊編輯區內容儲存到目前檔案"""
        if not hasattr(self, "current_file"):
            QMessageBox.warning(
                self,
                language_wrapper.language_word_dict.get("cot_prompt_editor_msgbox_error_title"),
                language_wrapper.language_word_dict.get("cot_prompt_editor_msgbox_no_file_selected"))
            return

        content = self.middle_editor.toPlainText()
        if not save_prompt_text(
            self, self.current_file, content,
            language_wrapper.language_word_dict.get("cot_prompt_editor_msgbox_error_title"),
        ):
            return
        QMessageBox.information(
            self,
            language_wrapper.language_word_dict.get("cot_prompt_editor_msgbox_success_title"),
            language_wrapper.language_word_dict.get("cot_prompt_editor_msgbox_file_saved").format(
                filename=self.current_file))
