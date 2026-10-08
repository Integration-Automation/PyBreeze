"""A tool tab that edits a JSON file as a tree and as text.

The automation packages' scripts are JSON, and JSON written by hand is where a
missing comma or a quote too many hides. This tab shows one file two ways: a
**Tree** in which a value is added, deleted, moved, renamed, retyped or changed
in place (``json_tree_panel.py``), and the **Text** itself. Both are views of
one ``JsonDocument`` (``utils/json_format/json_document.py``), so they cannot
disagree:

- typing in the text changes the document as it is typed; while the text is not
  JSON the tree waits and a line under the views says where the text goes wrong;
- an edit in the tree writes the text again, laid out as the text was;
- Undo and Redo step through the document, whichever view changed it. A run of
  typing is one step, and so is each edit in the tree.

It is a JSON editor, not a replacement for the code editor: a file is opened
into it on purpose, from its Open button.
"""
from __future__ import annotations

import weakref
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut, QUndoCommand, QUndoStack
from PySide6.QtWidgets import (
    QFileDialog, QLabel, QMessageBox, QPlainTextEdit, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.design.panels import StatusLine, wrapping_row
from pybreeze.pybreeze_ui.design.tokens import State
from pybreeze.pybreeze_ui.error_text import error_text
from pybreeze.pybreeze_ui.exact_text import exact_text
from pybreeze.pybreeze_ui.fixed_pitch import use_fixed_pitch_font
from pybreeze.pybreeze_ui.plain_text import as_text
from pybreeze.pybreeze_ui.tools_gui.json_tree_panel import JsonTreePanel
from pybreeze.utils.file_process.read_capped import read_text_capped
from pybreeze.utils.file_process.replace_file import replace_text
from pybreeze.utils.json_format.json_document import JsonDocument, JsonProblem, StaleRevisionError, detect_options
from pybreeze.utils.json_format.json_tree_edit import JsonEditError, JsonPath, children
from pybreeze.utils.json_format.view_safe import escape_for_view
from pybreeze.utils.logging.logger import pybreeze_logger

# The document a new tab starts with
_NEW_DOCUMENT = "{}"
# A change that is not part of a run of typing never merges with another
_NO_RUN = -1
# How many steps Undo keeps. A step holds the text it leaves, so a long session on a
# large file would otherwise hold a copy of it for every edit ever made
_UNDO_STEPS = 200


def _word(key: str) -> str:
    return language_wrapper.language_word_dict.get(key)


class _DocumentChange(QUndoCommand):
    """One step of the document: its text before and after.

    The steps of one run of typing share an id and merge into one, so Undo
    takes back what was typed since the last edit in the tree, the last save
    or the last change of view, not a letter.
    """

    def __init__(self, editor: JsonEditorGUI, before: str, after: str, run: int) -> None:
        super().__init__()
        # Not the editor itself: the stack is the editor's, and would keep it
        self._editor = weakref.ref(editor)
        self._before = before
        self.after = after
        self._run = run
        self._made = False

    def id(self) -> int:
        return self._run

    def mergeWith(self, other: QUndoCommand) -> bool:
        if self._run == _NO_RUN or not isinstance(other, _DocumentChange) or other.id() != self._run:
            return False
        self.after = other.after
        return True

    def undo(self) -> None:
        self._show(self._before)

    def redo(self) -> None:
        # Pushing a step calls redo, and the change it stands for is made already
        if self._made:
            self._show(self.after)
        self._made = True

    def _show(self, text: str) -> None:
        editor = self._editor()
        if editor is not None:
            editor.show_text(text)


class _DocumentText(QPlainTextEdit):
    """The text view. Undo and Redo are the document's steps, not the box's own.

    A text box keeps its own history and takes the Undo key for itself, so a
    shortcut on the tab never sees it: the keys are handed on from here.
    """

    def __init__(self, undo_stack: QUndoStack) -> None:
        super().__init__()
        self._undo_stack = undo_stack
        self.setUndoRedoEnabled(False)

    def keyPressEvent(self, event) -> None:
        if event.matches(QKeySequence.StandardKey.Undo):
            self._undo_stack.undo()
        elif event.matches(QKeySequence.StandardKey.Redo):
            self._undo_stack.redo()
        else:
            super().keyPressEvent(event)


class JsonEditorGUI(QWidget):
    """Edit a JSON file as a tree and as text, over one document."""

    def __init__(self) -> None:
        super().__init__()
        self._document = JsonDocument(_NEW_DOCUMENT)
        self._file: Path | None = None
        # Set while the text view is being filled from the document, so that
        # filling it is not taken for typing
        self._showing = False
        self._typing_run = 0
        self.undo_stack = QUndoStack(self)
        self.undo_stack.setUndoLimit(_UNDO_STEPS)

        self.open_button = QPushButton(_word("json_editor_open_button"))
        self.open_button.clicked.connect(self.open_file)
        self.save_button = QPushButton(_word("json_editor_save_button"))
        self.save_button.clicked.connect(self.save)
        self.save_as_button = QPushButton(_word("json_editor_save_as_button"))
        self.save_as_button.clicked.connect(self.save_as)
        self.undo_button = QPushButton(_word("json_editor_undo_button"))
        self.redo_button = QPushButton(_word("json_editor_redo_button"))
        self._follow_undo_stack()
        # The file's name is the user's: shown as text
        self.file_label = QLabel()
        self.file_label.setTextFormat(Qt.TextFormat.PlainText)

        self.tree_panel = JsonTreePanel()
        self.tree_panel.edit_asked.connect(self._change_tree)
        self.text_edit = _DocumentText(self.undo_stack)
        use_fixed_pitch_font(self.text_edit)
        self.text_edit.textChanged.connect(self._text_typed)
        self.views = QTabWidget()
        self.views.addTab(self.tree_panel, _word("json_editor_tree_view"))
        self.views.addTab(self.text_edit, _word("json_editor_text_view"))
        self.views.currentChanged.connect(self._view_changed)
        self.status = StatusLine()

        layout = QVBoxLayout()
        layout.addLayout(wrapping_row(
            self.open_button, self.save_button, self.save_as_button, self.undo_button, self.redo_button))
        layout.addWidget(self.file_label)
        layout.addWidget(self.views, 1)
        layout.addWidget(self.status)
        self.setLayout(layout)

        self._show_document()
        self._show_file_name()

    def _follow_undo_stack(self) -> None:
        """Have the Undo and Redo buttons and keys step through the document, and the file name show unsaved work."""
        for button, step, can_step in (
                (self.undo_button, self.undo_stack.undo, self.undo_stack.canUndoChanged),
                (self.redo_button, self.undo_stack.redo, self.undo_stack.canRedoChanged)):
            button.clicked.connect(step)
            button.setEnabled(False)
            can_step.connect(button.setEnabled)
        # The tree leaves the Undo keys to the tab; the text view hands them on itself
        for keys, step in ((QKeySequence.StandardKey.Undo, self.undo_stack.undo),
                           (QKeySequence.StandardKey.Redo, self.undo_stack.redo)):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(step)
        self.undo_stack.cleanChanged.connect(self._show_file_name)

    # ------------------------------------------------------------------
    # The document
    # ------------------------------------------------------------------

    @property
    def document(self) -> JsonDocument:
        """The document both views show."""
        return self._document

    def load_text(self, text: str, file: Path | None = None) -> None:
        """Start over with *text* as the document, laid out as *text* is.

        :param text: the document's text; it need not be JSON
        :param file: the file it came from, which Save then writes; none for a new document
        """
        # A character the text view would give back as another one (U+2029 as a
        # newline) is shown as its escape, which says the same to JSON
        self._document = JsonDocument(escape_for_view(text))
        self._follow_layout(text)
        self._file = file
        self._typing_run += 1
        self.undo_stack.clear()
        self.undo_stack.setClean()
        self._show_document()
        self._show_file_name()

    def show_text(self, text: str) -> None:
        """Make *text* the document's text, as Undo and Redo do; no step is recorded for it."""
        self._document.set_text(text, self._document.revision)
        self._follow_layout()
        self._typing_run += 1
        self._show_document()

    def is_modified(self) -> bool:
        """Whether the document differs from what was last opened or saved."""
        return not self.undo_stack.isClean()

    def _follow_layout(self, written: str | None = None) -> None:
        """Have the next edit in the tree write the text laid out as it is now.

        The layout is read from the text whenever the text is given: opened,
        typed, or brought back by Undo. A pasted document then keeps its own
        indent through an edit in the tree. A text with nothing in it (``{}``,
        a lone number) has no indent to read, so only how it ends is taken.

        :param written: the text to read the layout from, when it is not the
            document's own (a file's, before a character was shown as its escape)
        """
        document = self._document
        if document.problem is not None:
            return
        layout = detect_options(document.text if written is None else written)
        if not children(document.tree):
            layout = replace(document.options, trailing_newline=layout.trailing_newline)
        document.options = layout

    def _show_document(self, select: JsonPath | None = None) -> None:
        """Fill the views from the document, and say whether its text is JSON."""
        if exact_text(self.text_edit) != self._document.text:
            self._showing = True
            try:
                self._set_text_view(self._document.text)
            finally:
                self._showing = False
        # The tree is filled when it is the view in front, and when it is turned to
        if self.views.currentWidget() is self.tree_panel:
            self._show_tree(select)
        self._show_state()

    def _set_text_view(self, text: str) -> None:
        """Show *text* in the text view with the cursor where it was, as near as the new text allows."""
        position = self.text_edit.textCursor().position()
        self.text_edit.setPlainText(text)
        cursor = self.text_edit.textCursor()
        cursor.setPosition(min(position, self.text_edit.document().characterCount() - 1))
        self.text_edit.setTextCursor(cursor)

    def _show_tree(self, select: JsonPath | None = None) -> None:
        """Show the document's tree in the tree view; nothing while the text is not JSON."""
        if self._document.problem is None:
            self.tree_panel.show_tree(self._document.tree, select)
        else:
            self.tree_panel.show_nothing()

    def _show_state(self) -> None:
        """Say under the views whether the text is JSON, and where it stops being."""
        problem = self._document.problem
        if problem is None:
            self.status.show_state(State.SUCCESS, _word("json_editor_valid"))
            return
        reason = error_text(str(problem))
        if problem.line is not None:
            reason = _word("json_editor_problem_at").format(line=problem.line, column=problem.column, reason=reason)
        self.status.show_state(State.ERROR, reason)

    def _show_file_name(self, *_clean) -> None:
        name = self._file.name if self._file is not None else _word("json_editor_untitled")
        self.file_label.setText(f"{name} *" if self.is_modified() else name)

    def _record(self, before: str, run: int) -> None:
        """Record the step from *before* to the document's text now."""
        if before != self._document.text:
            self.undo_stack.push(_DocumentChange(self, before, self._document.text, run))

    # ------------------------------------------------------------------
    # Edits from either view
    # ------------------------------------------------------------------

    def _text_typed(self) -> None:
        """The text was edited: it is the document's text from now, JSON or not."""
        if self._showing:
            return
        before = self._document.text
        self._document.set_text(exact_text(self.text_edit), self._document.revision)
        self._follow_layout()
        self._record(before, self._typing_run)
        self._show_state()

    def _view_changed(self, _index: int) -> None:
        """A change of view ends a run of typing, and the tree turned to shows the document as it is now."""
        self._typing_run += 1
        if self.views.currentWidget() is self.tree_panel:
            self._show_tree()

    def _change_tree(self, edit, select: JsonPath | None = None) -> None:
        """Make the edit the tree view asked for the document's, as one step; say why when it cannot be made.

        :param edit: gives the new tree, or raises ``JsonEditError``
        :param select: the path to select afterwards; the one selected now when not given
        """
        before = self._document.text
        try:
            self._document.set_tree(edit(), self._document.revision)
        except (JsonEditError, JsonProblem, StaleRevisionError) as error:
            pybreeze_logger.info("json_editor_gui.py edit refused: %r", error)
            # The cell typed into shows what the document holds again
            self._show_tree()
            self.status.show_state(State.ERROR, error_text(str(error)))
            return
        self._typing_run += 1
        self._record(before, _NO_RUN)
        self._show_document(select)

    # ------------------------------------------------------------------
    # Files
    # ------------------------------------------------------------------

    def may_close(self) -> bool:
        """Whether the tab may close: the document is as last saved or opened, or the user lets it go."""
        return self._may_lose_edits("json_editor_close_over_edits")

    def _may_lose_edits(self, question_key: str) -> bool:
        if not self.is_modified():
            return True
        word = language_wrapper.language_word_dict
        reply = QMessageBox.question(
            self, word.get("unsaved_close_title"), word.get(question_key),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        return reply == QMessageBox.StandardButton.Yes

    def open_file(self) -> str | None:
        """Ask for a JSON file and open it; return its path, or ``None`` when none was opened."""
        if not self._may_lose_edits("json_editor_open_over_edits"):
            return None
        path, _selected = QFileDialog.getOpenFileName(
            self, _word("json_editor_open_dialog_title"), "", _word("json_editor_file_filter"))
        if not path:
            return None
        try:
            # utf-8-sig: a file saved with a byte-order mark is still JSON
            text = read_text_capped(Path(path), encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as error:
            pybreeze_logger.info("json_editor_gui.py read failed: %r", error)
            self.status.show_state(
                State.ERROR, _word("json_editor_read_error").format(error=self._reason(error)))
            return None
        self.load_text(text, Path(path))
        return path

    def save(self) -> str | None:
        """Write the document to its file, asking for one when it has none; return the path, or ``None``."""
        if self._file is None:
            return self.save_as()
        return self._write(self._file)

    def save_as(self) -> str | None:
        """Ask where to write the document and write it there; return the path, or ``None``."""
        suggested = str(self._file) if self._file is not None else "document.json"
        path, _selected = QFileDialog.getSaveFileName(
            self, _word("json_editor_save_dialog_title"), suggested, _word("json_editor_file_filter"))
        return self._write(Path(path)) if path else None

    def _write(self, file: Path) -> str | None:
        try:
            # Replaced in one step: a failure part-way leaves the file as it was
            replace_text(file, self._document.text)
        except (OSError, UnicodeEncodeError) as error:
            pybreeze_logger.error("json_editor_gui.py save failed: %r", error)
            QMessageBox.warning(
                self, _word("output_actions_save_failed_title"),
                as_text(_word("output_actions_save_failed_message").format(
                    file=file.name, error=self._reason(error))))
            return None
        self._file = file
        self._typing_run += 1
        self.undo_stack.setClean()
        self._show_file_name()
        return str(file)

    @staticmethod
    def _reason(error: Exception) -> str:
        """Why a file could not be read or written, without its path: ``str(OSError)`` carries the full path."""
        return error.strerror if isinstance(error, OSError) and error.strerror else type(error).__name__
