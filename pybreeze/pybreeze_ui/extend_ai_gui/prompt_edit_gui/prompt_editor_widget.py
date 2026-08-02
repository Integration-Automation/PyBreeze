"""One prompt editor, shared by the CoT and the Skill template editors.

The two differ in exactly two things: which templates they list, and which
language keys label them. Everything else — loading the selected file, creating
it from its built-in template, saving, and picking up an external edit — was
written twice, line for line. It lives here once instead.

The language keys arrive as a :class:`PromptEditorLabels` of literal strings
rather than being built from a prefix, so a key that does not exist can still be
caught by a test reading the source rather than only at runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher
from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QTextEdit, QVBoxLayout, QWidget
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.prompt_file_io import save_prompt_text
from pybreeze.pybreeze_ui.extend_ai_gui.prompt_store import prompt_dir, prompt_path


@dataclass(frozen=True)
class PromptEditorLabels:
    """The language keys one editor labels itself with."""

    window_title: str
    edit_group: str
    create_button: str
    save_button: str
    reload_button: str
    file_not_exist: str
    info_title: str
    error_title: str
    success_title: str
    file_exists: str
    file_created: str
    file_saved: str
    no_file_selected: str


class PromptEditorWidget(QWidget):
    """Edit the prompt files that override the built-in templates."""

    def __init__(self, files: list[str], templates: dict[str, str],
                 labels: PromptEditorLabels, parent=None) -> None:
        """
        :param files: the template file names this editor offers, in order
        :param templates: file name -> the template compiled into the source tree
        :param labels: the language keys this editor is labelled with
        """
        super().__init__(parent)
        self.prompt_files = files
        self.templates = templates
        self._labels = labels
        self.current_file: str | None = None

        word = language_wrapper.language_word_dict
        self.setWindowTitle(word.get(labels.window_title))

        self.file_selector = QComboBox()
        self.file_selector.addItems(self.prompt_files)
        self.file_selector.currentIndexChanged.connect(self.load_file_content)

        self.middle_editor = QTextEdit()
        group = QGroupBox(word.get(labels.edit_group))
        group_layout = QVBoxLayout()
        group_layout.addWidget(self.middle_editor)
        group.setLayout(group_layout)

        self.reload_button = QPushButton(word.get(labels.reload_button))
        self.reload_button.clicked.connect(
            lambda: self.load_file_content(self.file_selector.currentIndex()))
        self.save_button = QPushButton(word.get(labels.save_button))
        self.save_button.clicked.connect(self.save_file)
        self.create_button = QPushButton(word.get(labels.create_button))
        self.create_button.clicked.connect(self.create_file)

        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.file_selector)
        bottom_layout.addStretch()
        for button in (self.reload_button, self.save_button, self.create_button):
            bottom_layout.addWidget(button)

        # 這些檔案覆寫實際送出的 prompt，位置要讓人找得到
        # These files override the prompt that is sent, so say where they are
        where = QLabel(f"{word.get('prompt_editor_stored_at_label')} {prompt_dir()}")
        where.setWordWrap(True)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(group)
        main_layout.addWidget(where)
        main_layout.addLayout(bottom_layout)

        # 檔案監控器：外部改動即時反映 / Pick up edits made outside the editor
        self.watcher = QFileSystemWatcher(
            [str(prompt_path(name)) for name in self.prompt_files])
        self.watcher.fileChanged.connect(self.on_file_changed)

        if self.prompt_files:
            self.load_file_content(0)

    def load_file_content(self, index: int) -> None:
        """載入選擇的檔案內容 / Show the selected file, or say it is not there yet."""
        name = self.prompt_files[index]
        self.current_file = str(prompt_path(name))
        path = Path(self.current_file)
        if path.is_file():
            self.middle_editor.setPlainText(path.read_text(encoding="utf-8"))
            return
        self.middle_editor.setPlainText(
            language_wrapper.language_word_dict.get(
                self._labels.file_not_exist).format(filename=name))

    def create_file(self) -> None:
        """用內建模板建立目前選擇的檔案 / Create the selected file from its built-in template."""
        word = language_wrapper.language_word_dict
        if self.current_file is None:
            return
        if Path(self.current_file).is_file():
            QMessageBox.information(
                self, word.get(self._labels.info_title),
                word.get(self._labels.file_exists).format(filename=self.current_file))
            return

        content = self.templates.get(Path(self.current_file).name, "")
        if not save_prompt_text(
                self, self.current_file, content, word.get(self._labels.error_title)):
            return

        # Only now does the file exist, so only now can it be watched for the
        # external edits this editor promises to pick up.
        self.watcher.addPath(self.current_file)
        QMessageBox.information(
            self, word.get(self._labels.success_title),
            word.get(self._labels.file_created).format(filename=self.current_file))
        self.load_file_content(self.file_selector.currentIndex())

    def on_file_changed(self, path: str) -> None:
        """外部改動時重新載入 / Reload when the file changes underneath us."""
        if path == self.current_file:
            self.load_file_content(self.file_selector.currentIndex())

    def save_file(self) -> None:
        """把編輯區內容存回檔案 / Write the edit area back to the file."""
        word = language_wrapper.language_word_dict
        if self.current_file is None:
            QMessageBox.warning(
                self, word.get(self._labels.error_title),
                word.get(self._labels.no_file_selected))
            return

        if not save_prompt_text(
                self, self.current_file, self.middle_editor.toPlainText(),
                word.get(self._labels.error_title)):
            return
        self.watcher.addPath(self.current_file)
        QMessageBox.information(
            self, word.get(self._labels.success_title),
            word.get(self._labels.file_saved).format(filename=self.current_file))
