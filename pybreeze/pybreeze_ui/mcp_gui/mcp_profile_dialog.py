"""The window an MCP server is set up in: its name, the command that starts it, and what it needs.

The command is written one argument a line, the program first, so that no
quoting rule stands between what is typed and what is run: each line is one
argument, exactly. Keys and tokens go in the environment table, whose values
are shown as dots; the command is shown again whenever the server is started,
and those values never are.
"""
from __future__ import annotations

from PySide6.QtCore import QLocale, Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QPushButton, QSpinBox, QStyledItemDelegate, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.design.panels import wrapping_row
from pybreeze.pybreeze_ui.exact_text import exact_text
from pybreeze.pybreeze_ui.fixed_pitch import use_fixed_pitch_font
from pybreeze.utils.mcp.mcp_profile import McpServerProfile

_NAME, _VALUE = range(2)
# What a value is shown as while values are hidden, whatever its length
_DOTS = "•" * 8
# How long one request may take, in seconds: the least and the most a profile is given
_TIMEOUT_RANGE = (1, 3600)


def _word(key: str) -> str:
    return language_wrapper.language_word_dict.get(key)


class _HiddenValue(QStyledItemDelegate):
    """Shows a table's values as dots, and types them as a password, while they are hidden."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.hidden = True

    def displayText(self, value, locale: QLocale) -> str:
        shown = super().displayText(value, locale)
        return _DOTS if self.hidden and shown else shown

    def createEditor(self, parent: QWidget, option, index) -> QWidget:
        editor = super().createEditor(parent, option, index)
        if self.hidden and isinstance(editor, QLineEdit):
            editor.setEchoMode(QLineEdit.EchoMode.Password)
        return editor


class McpProfileDialog(QDialog):
    """Set up one MCP server.

    :param parent: the window it belongs to
    :param profile: the server being changed; ``None`` for a new one
    :param taken_names: the names other servers have, which this one may not take
    """

    def __init__(self, parent: QWidget | None, profile: McpServerProfile | None, taken_names: set[str]) -> None:
        super().__init__(parent)
        self._editing = profile
        self._taken_names = taken_names
        self.setWindowTitle(_word("mcp_profile_dialog_title"))

        self.name_edit = QLineEdit(profile.name if profile is not None else "")
        self.command_edit = QPlainTextEdit("\n".join(profile.command) if profile is not None else "")
        self.command_edit.setPlaceholderText(_word("mcp_profile_command_placeholder"))
        use_fixed_pitch_font(self.command_edit)
        self.folder_edit = QLineEdit(profile.working_directory if profile is not None else "")
        self.browse_button = QPushButton(_word("mcp_profile_browse_button"))
        self.browse_button.clicked.connect(self._choose_folder)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(*_TIMEOUT_RANGE)
        self.timeout_spin.setValue(round(profile.timeout_seconds) if profile is not None else 30)

        self.environment_table = QTableWidget(0, 2)
        self.environment_table.setHorizontalHeaderLabels(
            [_word("mcp_profile_variable_name"), _word("mcp_profile_variable_value")])
        self.environment_table.horizontalHeader().setStretchLastSection(True)
        self._values = _HiddenValue(self.environment_table)
        self.environment_table.setItemDelegateForColumn(_VALUE, self._values)
        for name, value in (profile.environment.items() if profile is not None else ()):
            self._add_variable(name, value)
        self.add_variable_button = QPushButton(_word("mcp_profile_add_variable_button"))
        self.add_variable_button.clicked.connect(self._add_variable)
        self.remove_variable_button = QPushButton(_word("mcp_profile_remove_variable_button"))
        self.remove_variable_button.clicked.connect(self._remove_variable)
        self.show_values_box = QCheckBox(_word("mcp_profile_show_values"))
        self.show_values_box.toggled.connect(self._show_values)

        form = QFormLayout()
        form.addRow(_word("mcp_profile_name_label"), self.name_edit)
        form.addRow(_word("mcp_profile_command_label"), self.command_edit)
        form.addRow(_word("mcp_profile_folder_label"), wrapping_row(self.folder_edit, self.browse_button))
        form.addRow(_word("mcp_profile_timeout_label"), self.timeout_spin)
        # The note is PyBreeze's own words
        secrets_note = QLabel(_word("mcp_profile_environment_note"))
        secrets_note.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel(_word("mcp_profile_environment_label")))
        layout.addWidget(secrets_note)
        layout.addWidget(self.environment_table)
        layout.addLayout(wrapping_row(self.add_variable_button, self.remove_variable_button, self.show_values_box))
        layout.addWidget(buttons)

    def _add_variable(self, name: str | bool = "", value: str = "") -> None:
        """Add a row to the environment table; a button's click gives its checked state, which is no name."""
        row = self.environment_table.rowCount()
        self.environment_table.insertRow(row)
        self.environment_table.setItem(row, _NAME, QTableWidgetItem(name if isinstance(name, str) else ""))
        self.environment_table.setItem(row, _VALUE, QTableWidgetItem(value))

    def _remove_variable(self) -> None:
        row = self.environment_table.currentRow()
        if row >= 0:
            self.environment_table.removeRow(row)

    def _show_values(self, shown: bool) -> None:
        self._values.hidden = not shown
        self.environment_table.viewport().update()

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, _word("mcp_profile_folder_label"), self.folder_edit.text())
        if folder:
            self.folder_edit.setText(folder)

    def command(self) -> tuple[str, ...]:
        """The command as typed: one argument a line, lines with nothing on them left out."""
        return tuple(line for line in exact_text(self.command_edit).split("\n") if line.strip())

    def environment(self) -> dict[str, str]:
        """The variables of the table; a row without a name is left out."""
        variables = {}
        for row in range(self.environment_table.rowCount()):
            name, value = self.environment_table.item(row, _NAME), self.environment_table.item(row, _VALUE)
            if name is not None and name.text().strip():
                variables[name.text().strip()] = value.text() if value is not None else ""
        return variables

    def _problem(self) -> str | None:
        """The language key of what keeps the server from being saved, or ``None``."""
        name = self.name_edit.text().strip()
        if not name:
            return "mcp_profile_needs_name"
        if name in self._taken_names:
            return "mcp_profile_name_taken"
        if not self.command():
            return "mcp_profile_needs_command"
        return None

    def accept(self) -> None:
        """Close with the server saved, or say what it still needs."""
        problem = self._problem()
        if problem is not None:
            word = language_wrapper.language_word_dict
            box = QMessageBox(QMessageBox.Icon.Warning, word.get("mcp_profile_dialog_title"), "", parent=self)
            box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            box.setTextFormat(Qt.TextFormat.PlainText)
            box.setText(word.get(problem))
            box.exec()
            return
        super().accept()

    def profile(self) -> McpServerProfile:
        """The server as it is set up now; what the user had decided about its tools is kept."""
        return McpServerProfile(
            name=self.name_edit.text().strip(), command=self.command(), environment=self.environment(),
            working_directory=self.folder_edit.text().strip(), timeout_seconds=float(self.timeout_spin.value()),
            trusted_tools=self._editing.trusted_tools if self._editing is not None else frozenset())
