import os

from PySide6.QtCore import QFileSystemWatcher
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QTextEdit, QPushButton, QGroupBox, QMessageBox
)
from je_editor import language_wrapper

from automation_ide.automation_editor_ui.extend_ai_gui.ai_gui_global_variable import SKILLS_TEMPLATE_FILES, \
    SKILLS_TEMPLATE_RELATION


class SkillPromptEditor(QWidget):
    def __init__(self, skill_files=None, parent=None):
        super().__init__(parent)
        self.skill_files = skill_files or SKILLS_TEMPLATE_FILES

        # 對應檔案名稱與模板內容
        self.templates = SKILLS_TEMPLATE_RELATION

        self.setWindowTitle(language_wrapper.language_word_dict.get(
            "skill_prompt_editor_window_title"
        ))  # 視窗標題：Skill Prompt 編輯器

        # --- Layouts ---
        main_layout = QVBoxLayout(self)
        editor_layout = QHBoxLayout()
        bottom_layout = QHBoxLayout()

        # --- ComboBox for selecting files ---
        self.file_selector = QComboBox()
        self.file_selector.addItems(self.skill_files)
        self.file_selector.currentIndexChanged.connect(self.load_file_content)

        # --- Editable panel ---
        self.middle_editor = QTextEdit()
        skill_group = QGroupBox(language_wrapper.language_word_dict.get(
            "skill_prompt_editor_groupbox_edit_file_content"
        ))
        middle_layout = QVBoxLayout()
        middle_layout.addWidget(self.middle_editor)
        skill_group.setLayout(middle_layout)

        editor_layout.addWidget(skill_group, 1)

        # --- Buttons ---
        self.create_button = QPushButton(language_wrapper.language_word_dict.get(
            "skill_prompt_editor_button_create_file"
        ))
        self.create_button.clicked.connect(self.create_file)

        self.save_button = QPushButton(language_wrapper.language_word_dict.get(
            "skill_prompt_editor_button_save_file"
        ))
        self.save_button.clicked.connect(self.save_file)

        self.reload_button = QPushButton(language_wrapper.language_word_dict.get(
            "skill_prompt_editor_button_reload_file"
        ))
        self.reload_button.clicked.connect(lambda: self.load_file_content(self.file_selector.currentIndex()))

        bottom_layout.addWidget(self.file_selector)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.reload_button)
        bottom_layout.addWidget(self.save_button)
        bottom_layout.addWidget(self.create_button)

        # --- Combine layouts ---
        main_layout.addLayout(editor_layout)
        main_layout.addLayout(bottom_layout)

        # --- FileSystemWatcher ---
        self.watcher = QFileSystemWatcher(self.skill_files)
        self.watcher.fileChanged.connect(self.on_file_changed)

        # 預設載入第一個檔案
        self.load_file_content(0)

    def load_file_content(self, index):
        """載入選擇的檔案內容到編輯區"""
        filename = self.skill_files[index]
        self.current_file = filename
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read()
            self.middle_editor.setPlainText(content)
        else:
            self.middle_editor.setPlainText(language_wrapper.language_word_dict.get(
                "skill_prompt_editor_file_not_exist"
            ).format(filename=filename))

    def create_file(self):
        """建立目前選擇的檔案，若不存在則用模板內容建立"""
        filename = self.current_file
        if os.path.exists(filename):
            QMessageBox.information(
                self,
                language_wrapper.language_word_dict.get("skill_prompt_editor_msgbox_info_title"),
                language_wrapper.language_word_dict.get("skill_prompt_editor_msgbox_file_exists").format(
                    filename=filename))
            return

        template_content = self.templates.get(filename, "")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(template_content)

        QMessageBox.information(
            self,
            language_wrapper.language_word_dict.get("skill_prompt_editor_msgbox_success_title"),
            language_wrapper.language_word_dict.get("skill_prompt_editor_msgbox_file_created").format(
                filename=filename))
        self.load_file_content(self.file_selector.currentIndex())

    def on_file_changed(self, path):
        """當檔案被外部修改時即時更新"""
        if path == self.current_file:
            self.load_file_content(self.file_selector.currentIndex())

    def save_file(self):
        """將編輯區內容儲存到目前檔案"""
        if not hasattr(self, "current_file"):
            QMessageBox.warning(
                self,
                language_wrapper.language_word_dict.get("skill_prompt_editor_msgbox_error_title"),
                language_wrapper.language_word_dict.get("skill_prompt_editor_msgbox_no_file_selected"))
            return

        content = self.middle_editor.toPlainText()
        with open(self.current_file, "w", encoding="utf-8") as f:
            f.write(content)
        QMessageBox.information(
            self,
            language_wrapper.language_word_dict.get("skill_prompt_editor_msgbox_success_title"),
            language_wrapper.language_word_dict.get("skill_prompt_editor_msgbox_file_saved").format(
                filename=self.current_file))
