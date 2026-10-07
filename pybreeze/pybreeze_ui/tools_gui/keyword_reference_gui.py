"""A tool tab that lists the keywords an action script may use, as the installed frameworks give them.

The editor completes and checks WebRunner, AutoControl and LoadDensity scripts
from the keywords their packages have installed (``utils/language_service/``).
This tab shows the same keywords, for the same interpreter: which version of
each framework answers, what the editor can do with it, every keyword with its
parameters and documentation, and, when a framework gives none, why.

The keywords are read in another process (the framework is imported there, not
in the IDE), on a worker thread, the first time the tab is shown.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QComboBox, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton,
    QSplitter, QVBoxLayout, QWidget,
)
from je_editor import JEditorExecException, language_wrapper

from pybreeze.extend.process_executor.python_task_process_manager import default_interpreter
from pybreeze.pybreeze_ui.design.panels import StatusLine, wrapping_row
from pybreeze.pybreeze_ui.design.tokens import State
from pybreeze.pybreeze_ui.error_text import error_text
from pybreeze.pybreeze_ui.fixed_pitch import use_fixed_pitch_font
from pybreeze.utils.exception.exceptions import LanguageServiceException
from pybreeze.utils.language_service.action_adapter import ActionLanguageAdapter
from pybreeze.utils.language_service.framework_profiles import PROFILES, FrameworkProfile
from pybreeze.utils.language_service.keyword_metadata import FrameworkMetadata, Keyword
from pybreeze.utils.language_service.metadata_probe import read_metadata
from pybreeze.utils.language_service.service_adapter import Capability
from pybreeze.utils.logging.logger import pybreeze_logger

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow

# What the editor can do with a framework's keywords, in the order it is said, and the language key of each
_CAPABILITY_WORDS: dict[Capability, str] = {
    Capability.COMPLETION: "keyword_reference_capability_completion",
    Capability.DIAGNOSTICS: "keyword_reference_capability_diagnostics",
    Capability.HOVER: "keyword_reference_capability_hover",
    Capability.DEFINITION: "keyword_reference_capability_definition",
}
# Between the capabilities in the status line
_BETWEEN = " · "
# Where an item keeps its keyword's name
_NAME_ROLE = Qt.ItemDataRole.UserRole

# Readers that are running. A QThread destroyed while it runs ends the IDE, and
# a tab can go without being closed: each reader is kept here until it ends.
_READING: set[KeywordReadThread] = set()


def _word(key: str) -> str:
    return language_wrapper.language_word_dict.get(key)


class KeywordReadThread(QThread):
    """Asks one framework for its keywords, off the UI thread.

    :param profile: the framework
    :param interpreter: the Python that runs the scripts
    """

    loaded = Signal(object)  # FrameworkMetadata
    failed = Signal(str, str)  # the framework, and why (an exception_tags message)

    def __init__(self, profile: FrameworkProfile, interpreter: str) -> None:
        super().__init__()
        self._profile = profile
        self._interpreter = interpreter

    def start_kept(self) -> None:
        """Start, kept alive until it ends whatever becomes of the tab that started it."""
        _READING.add(self)
        self.finished.connect(self._forget)
        self.start()

    def _forget(self) -> None:
        _READING.discard(self)

    def run(self) -> None:
        try:
            metadata = read_metadata(self._profile, self._interpreter)
        except LanguageServiceException as error:
            self.failed.emit(self._profile.framework, str(error))
            return
        self.loaded.emit(metadata)


class KeywordReferenceGUI(QWidget):
    """The keywords of each framework's action scripts, searchable, with what the editor does with them."""

    def __init__(self, main_window: PyBreezeMainWindow | None = None) -> None:
        """
        :param main_window: the window whose chosen interpreter the keywords are read for
        """
        super().__init__()
        self._main_window = main_window
        self._metadata: dict[str, FrameworkMetadata] = {}
        # The framework being read, until its reader says what it read or why not. Not the
        # reader's own state: a thread is still running for a moment after it has answered,
        # and the read asked for in that moment was never started
        self._reading: str | None = None
        self._shown_once = False

        self.framework_label = QLabel(_word("keyword_reference_framework_label"))
        self.framework_select = QComboBox()
        for profile in PROFILES:
            self.framework_select.addItem(profile.label, profile)
        self.framework_select.currentIndexChanged.connect(self._framework_chosen)
        self.refresh_button = QPushButton(_word("keyword_reference_refresh_button"))
        self.refresh_button.clicked.connect(self.read_again)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(_word("keyword_reference_search_placeholder"))
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._show_keywords)

        self.keyword_list = QListWidget()
        self.keyword_list.currentItemChanged.connect(self._show_keyword)
        # A keyword's documentation is the package's own: shown as text
        self.detail_view = QPlainTextEdit()
        self.detail_view.setReadOnly(True)
        use_fixed_pitch_font(self.detail_view)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.keyword_list)
        self.splitter.addWidget(self.detail_view)
        self.splitter.setStretchFactor(1, 1)

        self.copy_button = QPushButton(_word("keyword_reference_copy_button"))
        self.copy_button.clicked.connect(self.copy_action)
        self.copy_button.setEnabled(False)
        self.status = StatusLine()

        layout = QVBoxLayout()
        layout.addLayout(wrapping_row(self.framework_label, self.framework_select, self.refresh_button))
        layout.addWidget(self.search_edit)
        layout.addWidget(self.splitter, 1)
        layout.addLayout(wrapping_row(self.copy_button))
        layout.addWidget(self.status)
        self.setLayout(layout)

    def showEvent(self, event) -> None:
        """Read the chosen framework's keywords the first time the tab is seen."""
        super().showEvent(event)
        if not self._shown_once:
            self._shown_once = True
            self._framework_chosen()

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def profile(self) -> FrameworkProfile:
        """The framework chosen."""
        return self.framework_select.currentData()

    def _framework_chosen(self, *_index) -> None:
        """Show the chosen framework's keywords, reading them when they have not been."""
        if self.profile().framework in self._metadata:
            self._show_framework()
        else:
            self.read()

    def read_again(self) -> None:
        """Forget what the chosen framework said and ask it again (after installing or upgrading it)."""
        self._metadata.pop(self.profile().framework, None)
        self.read()

    def read(self) -> bool:
        """Ask the chosen framework for its keywords; return whether a reader was started."""
        self._clear()
        profile = self.profile()
        if self._reading is not None:
            # One at a time: the one chosen now is read when the one being read has answered
            self.status.show_state(
                State.NEUTRAL, _word("keyword_reference_loading").format(framework=profile.label))
            return False
        try:
            interpreter = getattr(self._main_window, "python_compiler", None) or default_interpreter()
        except JEditorExecException as error:
            pybreeze_logger.info("keyword_reference_gui.py no interpreter: %r", error)
            self.status.show_state(State.ERROR, _word("keyword_reference_no_interpreter"))
            return False
        self.status.show_state(State.NEUTRAL, _word("keyword_reference_loading").format(framework=profile.label))
        reader = KeywordReadThread(profile, interpreter)
        reader.loaded.connect(self._loaded)
        reader.failed.connect(self._failed)
        self._reading = profile.framework
        reader.start_kept()
        return True

    def is_reading(self) -> bool:
        """Whether a framework has been asked and has not answered yet."""
        return self._reading is not None

    def _loaded(self, metadata: FrameworkMetadata) -> None:
        self._reading = None
        self._metadata[metadata.framework] = metadata
        self._after_reading(metadata.framework)

    def _failed(self, framework: str, reason: str) -> None:
        self._reading = None
        if framework == self.profile().framework:
            self.status.show_state(State.ERROR, error_text(reason))
        self._after_reading(framework)

    def _after_reading(self, framework: str) -> None:
        """Show what was read when it is still the chosen framework; read the chosen one when it is another."""
        chosen = self.profile().framework
        if chosen in self._metadata:
            self._show_framework()
        elif chosen != framework:
            self.read()

    # ------------------------------------------------------------------
    # Showing
    # ------------------------------------------------------------------

    def _clear(self) -> None:
        self.keyword_list.clear()
        self.detail_view.clear()
        self.copy_button.setEnabled(False)

    def _show_framework(self) -> None:
        """Show the chosen framework's keywords, and say its version and what the editor does with it."""
        profile = self.profile()
        metadata = self._metadata[profile.framework]
        offered = ActionLanguageAdapter(profile, metadata, language_wrapper.language_word_dict).capabilities()
        self.status.show_state(State.SUCCESS, _word("keyword_reference_ready").format(
            framework=f"{profile.label} {metadata.version}".strip(), count=len(metadata.own_keywords()),
            capabilities=_BETWEEN.join(_word(key) for capability, key in _CAPABILITY_WORDS.items()
                                       if capability in offered)))
        self._show_keywords()

    def _show_keywords(self, *_text) -> None:
        """List the chosen framework's own keywords that match what is typed in the filter."""
        self._clear()
        metadata = self._metadata.get(self.profile().framework)
        if metadata is None:
            return
        wanted = self.search_edit.text().strip().lower()
        for keyword in metadata.own_keywords():
            if wanted in keyword.name.lower() or wanted in keyword.doc.lower():
                item = QListWidgetItem(keyword.name)
                item.setData(_NAME_ROLE, keyword.name)
                self.keyword_list.addItem(item)
        if self.keyword_list.count():
            self.keyword_list.setCurrentRow(0)

    def selected_keyword(self) -> Keyword | None:
        """The keyword selected in the list, or ``None``."""
        item = self.keyword_list.currentItem()
        metadata = self._metadata.get(self.profile().framework)
        return None if item is None or metadata is None else metadata.keyword(item.data(_NAME_ROLE))

    def _show_keyword(self, *_items) -> None:
        keyword = self.selected_keyword()
        self.copy_button.setEnabled(keyword is not None)
        if keyword is None:
            self.detail_view.clear()
            return
        parts = [keyword.signature(), keyword.doc]
        if keyword.source_file and keyword.source_line:
            parts.append(_word("keyword_reference_defined_in").format(
                file=keyword.source_file, line=keyword.source_line))
        self.detail_view.setPlainText("\n\n".join(part for part in parts if part))

    def copy_action(self) -> str | None:
        """Copy the selected keyword as an action, its required parameters named; return what was copied."""
        keyword = self.selected_keyword()
        if keyword is None:
            return None
        required = {name: None for name in keyword.missing(set())}
        action = json.dumps([keyword.name, required] if required else [keyword.name], ensure_ascii=False)
        QApplication.clipboard().setText(action)
        return action
