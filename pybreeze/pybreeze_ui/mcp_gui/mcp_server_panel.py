"""The servers of the MCP tab: the user's own, kept under ``~/.pybreeze``, and those a project brings.

A project's ``.mcp.json`` names servers too. They are listed, marked as the
project's, and never started on being found: starting one runs a command a
file in an opened folder asked for, and the tab asks before it does.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout, QWidget
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.design.panels import wrapping_row
from pybreeze.pybreeze_ui.mcp_gui.mcp_profile_dialog import McpProfileDialog
from pybreeze.pybreeze_ui.plain_text import as_text
from pybreeze.utils.exception.exceptions import McpException
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.mcp.mcp_profile import McpServerProfile, discovered_profiles, load_profiles, save_profiles

# Where a list item keeps its server and whether it is the user's own
_PROFILE_ROLE = Qt.ItemDataRole.UserRole


def _word(key: str) -> str:
    return language_wrapper.language_word_dict.get(key)


class McpServerPanel(QWidget):
    """The list of servers, and the buttons that set one up, connect to it and let it go.

    :param folder: the project folder, whose ``.mcp.json`` is looked for
    """

    connect_asked = Signal()
    disconnect_asked = Signal()

    def __init__(self, folder: Path) -> None:
        super().__init__()
        self._folder = folder
        self._own: list[McpServerProfile] = []
        #: Why the user's own servers could not be read, in the words of ``exception_tags``; empty when they were
        self.load_problem = ""
        try:
            self._own = load_profiles()
        except (McpException, OSError, UnicodeDecodeError) as error:
            pybreeze_logger.error("mcp_server_panel.py servers not read: %r", error)
            self.load_problem = str(error) if isinstance(error, McpException) else type(error).__name__

        self.server_list = QListWidget()
        self.server_list.currentItemChanged.connect(self._selection_changed)
        self.add_button = QPushButton(_word("mcp_servers_add_button"))
        self.add_button.clicked.connect(self.add_server)
        self.edit_button = QPushButton(_word("mcp_servers_edit_button"))
        self.edit_button.clicked.connect(self.edit_server)
        self.remove_button = QPushButton(_word("mcp_servers_remove_button"))
        self.remove_button.clicked.connect(self.remove_server)
        self.connect_button = QPushButton(_word("mcp_servers_connect_button"))
        self.connect_button.clicked.connect(self.connect_asked)
        self.disconnect_button = QPushButton(_word("mcp_servers_disconnect_button"))
        self.disconnect_button.clicked.connect(self.disconnect_asked)
        self.disconnect_button.setEnabled(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(_word("mcp_servers_label")))
        layout.addWidget(self.server_list, 1)
        layout.addLayout(wrapping_row(self.add_button, self.edit_button, self.remove_button))
        layout.addLayout(wrapping_row(self.connect_button, self.disconnect_button))
        self._show_servers()

    # ------------------------------------------------------------------
    # The list
    # ------------------------------------------------------------------

    def _show_servers(self, select: str | None = None) -> None:
        """List the user's own servers, then the project's that are not also the user's, and select *select*."""
        self.server_list.clear()
        own_names = {profile.name for profile in self._own}
        found = [profile for profile in discovered_profiles(self._folder) if profile.name not in own_names]
        for profile, own in (*((profile, True) for profile in self._own), *((profile, False) for profile in found)):
            label = profile.name if own else _word("mcp_servers_found_label").format(name=profile.name)
            item = QListWidgetItem(label)
            item.setData(_PROFILE_ROLE, (profile, own))
            self.server_list.addItem(item)
            if profile.name == select:
                self.server_list.setCurrentItem(item)
        if self.server_list.currentItem() is None and self.server_list.count():
            self.server_list.setCurrentRow(0)
        self._selection_changed()

    def selected(self) -> tuple[McpServerProfile, bool] | None:
        """The server selected and whether it is the user's own, or ``None``."""
        item = self.server_list.currentItem()
        return None if item is None else item.data(_PROFILE_ROLE)

    def _selection_changed(self, *_items) -> None:
        chosen = self.selected()
        self.connect_button.setEnabled(chosen is not None)
        # A server of the project's is taken into the user's own with Edit; only one of the user's is removed
        self.edit_button.setEnabled(chosen is not None)
        self.remove_button.setEnabled(chosen is not None and chosen[1])

    def show_connected(self, connected: bool) -> None:
        """Offer Disconnect while a server is connected."""
        self.disconnect_button.setEnabled(connected)

    # ------------------------------------------------------------------
    # Setting servers up
    # ------------------------------------------------------------------

    def _keep(self, profiles: list[McpServerProfile], select: str | None = None) -> bool:
        """Make *profiles* the user's own servers; say so when they cannot be saved, and keep the list as it was."""
        try:
            save_profiles(profiles)
        except OSError as error:
            pybreeze_logger.error("mcp_server_panel.py servers not saved: %r", error)
            reason = error.strerror or type(error).__name__
            QMessageBox.warning(self, _word("output_actions_save_failed_title"), as_text(
                _word("output_actions_save_failed_message").format(file="mcp_servers.json", error=reason)))
            return False
        self._own = profiles
        self._show_servers(select)
        return True

    def _set_up(self, profile: McpServerProfile | None, taken: set[str]) -> McpServerProfile | None:
        """Show the set-up window for *profile*; the server as saved there, or ``None`` when it was cancelled."""
        dialog = McpProfileDialog(self, profile, taken)
        try:
            return dialog.profile() if dialog.exec() == McpProfileDialog.DialogCode.Accepted else None
        finally:
            dialog.deleteLater()

    def add_server(self) -> bool:
        """Set up a new server of the user's own; return whether one was added."""
        added = self._set_up(None, {profile.name for profile in self._own})
        return added is not None and self._keep([*self._own, added], added.name)

    def edit_server(self) -> bool:
        """Change the selected server; one of the project's becomes the user's own by being saved here."""
        chosen = self.selected()
        if chosen is None:
            return False
        profile, own = chosen
        others = [each for each in self._own if not (own and each.name == profile.name)]
        changed = self._set_up(profile, {each.name for each in others})
        if changed is None:
            return False
        kept = [changed if own and each.name == profile.name else each for each in self._own]
        return self._keep(kept if own else [*self._own, changed], changed.name)

    def remove_server(self) -> bool:
        """Remove the selected server from the user's own, after asking; return whether it was removed."""
        chosen = self.selected()
        if chosen is None or not chosen[1]:
            return False
        word = language_wrapper.language_word_dict
        reply = QMessageBox.question(
            self, word.get("mcp_servers_remove_title"),
            as_text(word.get("mcp_servers_remove_question").format(name=chosen[0].name)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return False
        return self._keep([each for each in self._own if each.name != chosen[0].name])

    def trust(self, profile: McpServerProfile, tool: str) -> McpServerProfile:
        """Keep that *tool* of *profile* is called without asking; the profile as it is from now.

        Only a server of the user's own keeps it between sessions.
        """
        trusting = profile.trusting(tool)
        if any(each.name == profile.name for each in self._own):
            self._keep([trusting if each.name == profile.name else each for each in self._own], profile.name)
        return trusting
