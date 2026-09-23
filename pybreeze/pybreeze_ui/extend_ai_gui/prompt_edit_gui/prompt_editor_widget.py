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
from pybreeze.pybreeze_ui.extend_ai_gui.prompt_store import (
    prompt_dir, prompt_path, read_prompt_file
)
from pybreeze.utils.logging.logger import pybreeze_logger


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
        # The template whose file is in the edit area, to go back to when the
        # user keeps their edits rather than switch away from them.
        self._shown_index = -1

        word = language_wrapper.language_word_dict
        self.setWindowTitle(word.get(labels.window_title))

        self.file_selector = QComboBox()
        self.file_selector.addItems(self.prompt_files)
        self.file_selector.currentIndexChanged.connect(self._on_template_chosen)

        self.middle_editor = QTextEdit()
        group = QGroupBox(word.get(labels.edit_group))
        group_layout = QVBoxLayout()
        group_layout.addWidget(self.middle_editor)
        group.setLayout(group_layout)

        self.reload_button = QPushButton(word.get(labels.reload_button))
        self.reload_button.clicked.connect(self._on_reload_clicked)
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
        # Parented to the editor so it goes with it: an orphan watcher outlived a
        # closed editor and delivered the next change on disk to a deleted widget.
        self.watcher = QFileSystemWatcher(
            [str(prompt_path(name)) for name in self.prompt_files], self)
        self.watcher.fileChanged.connect(self.on_file_changed)

        if self.prompt_files:
            self.load_file_content(0)

    def _on_template_chosen(self, index: int) -> None:
        """Show the chosen template, unless that would throw away unsaved edits."""
        if index == self._shown_index:
            return
        if not self._may_discard_edits(
                "prompt_editor_switch_over_edits", self._shown_name()):
            # Put the selector back without coming here again.
            self.file_selector.blockSignals(True)
            self.file_selector.setCurrentIndex(self._shown_index)
            self.file_selector.blockSignals(False)
            return
        self.load_file_content(index)

    def _on_reload_clicked(self) -> None:
        """Reload the file from disk, asking first when that loses edits."""
        if self._may_discard_edits("prompt_editor_reload_button_over_edits", self._shown_name()):
            self.load_file_content(self.file_selector.currentIndex())

    def _shown_name(self) -> str:
        """The file name of the template in the edit area."""
        return Path(self.current_file).name if self.current_file else ""

    def _may_discard_edits(self, question_key: str, filename: str) -> bool:
        """True when nothing unsaved is in the edit area, or the user lets it go."""
        if not self.middle_editor.document().isModified():
            return True
        word = language_wrapper.language_word_dict
        reply = QMessageBox.question(
            self, word.get(self._labels.info_title),
            word.get(question_key).format(filename=filename),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        return reply == QMessageBox.StandardButton.Yes

    def load_file_content(self, index: int) -> None:
        """載入選擇的檔案內容 / Show the selected file, or say it is not there yet."""
        name = self.prompt_files[index]
        self._shown_index = index
        self.current_file = str(prompt_path(name))
        path = Path(self.current_file)
        if path.is_file():
            self.middle_editor.setPlaceholderText("")
            self._show_file(path)
            return
        # Said as a placeholder, not as text: text would be what a save writes,
        # and a saved "does not exist" note overrode the built-in prompt.
        self.middle_editor.setPlaceholderText(
            language_wrapper.language_word_dict.get(
                self._labels.file_not_exist).format(filename=name))
        self._show_text("")

    def _show_file(self, path: Path) -> None:
        """Put the prompt file in the edit area, however it was encoded."""
        text = read_prompt_file(path)
        if text is None:
            try:
                # Not UTF-8: shown with what cannot be read replaced, so that a
                # save writes it back as UTF-8 and the review can use it again.
                text = path.read_bytes().decode("utf-8", errors="replace")
            except OSError as error:
                pybreeze_logger.error("Prompt file %s could not be opened: %r", path.name, error)
                # Nothing was shown, so there is nothing a save may write back.
                # The edit area is emptied: it kept the previous template's text,
                # shown under this template's name
                self.current_file = None
                self.middle_editor.setPlaceholderText(
                    language_wrapper.language_word_dict.get("prompt_editor_unreadable").format(
                        filename=path.name, error=error.strerror or type(error).__name__))
                self._show_text("")
                return
            QMessageBox.information(
                self, language_wrapper.language_word_dict.get(self._labels.info_title),
                language_wrapper.language_word_dict.get("prompt_editor_not_utf8").format(
                    filename=path.name))
        self._show_text(text)

    def _show_text(self, text: str) -> None:
        """Replace the edit area's text; what is shown now counts as unedited."""
        self.middle_editor.setPlainText(text)
        self.middle_editor.document().setModified(False)

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

        # Text typed into the empty editor would be replaced by the template
        if not self._may_discard_edits("prompt_editor_create_over_edits", Path(self.current_file).name):
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

    def closeEvent(self, event) -> None:
        """Stop watching the prompt files once the editor closes.

        A change on disk after that -- the next save from another window, or
        the directory being cleaned up -- would otherwise reach a widget that is
        on its way out, and with unsaved edits open a question box over it.
        """
        self.watcher.blockSignals(True)
        watched = self.watcher.files()
        if watched:
            self.watcher.removePaths(watched)
        super().closeEvent(event)

    def on_file_changed(self, path: str) -> None:
        """外部改動時重新載入 / Reload when the file changes underneath us.

        Unsaved edits are not thrown away without asking: another window, an
        external editor or a sync client touching the file used to replace
        whatever had been typed here.
        """
        if path != self.current_file:
            return
        if self._may_discard_edits("prompt_editor_reload_over_edits", Path(path).name):
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
        self.middle_editor.document().setModified(False)
        QMessageBox.information(
            self, word.get(self._labels.success_title),
            word.get(self._labels.file_saved).format(filename=self.current_file))
