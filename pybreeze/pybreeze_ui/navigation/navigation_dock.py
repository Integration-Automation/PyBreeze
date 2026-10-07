"""The navigation panel: PyBreeze's areas as a tree that stays in view and can be searched.

It is a dock at the left of the main window. Typing in its box keeps the lines
that hold the text, and Enter or a double click on a line does what the menu
entry it stands for does. What it lists is decided by ``navigation_model``.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QLineEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.design.panels import StatusLine
from pybreeze.pybreeze_ui.design.tokens import Space, State, TextRole, apply_spacing, em, text_font
from pybreeze.pybreeze_ui.navigation.navigation_model import CATEGORIES, NavigationEntry
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.ui_state import remember

# The name the panel's visibility is remembered under (utils/ui_state.py)
VISIBLE_STATE = "navigation_visible"
# The least width the panel asks for, in ems: room for a tool's name
_MIN_WIDTH_EMS = 14
# Where an item keeps the entry it stands for
_ENTRY_ROLE = Qt.ItemDataRole.UserRole


class NavigationDock(QDockWidget):
    """The navigation tree with its search box.

    :param navigation: what each category holds, by the category's key
        (``navigation_model.build_navigation``)
    :param parent: the main window
    """

    def __init__(self, navigation: dict[str, list[NavigationEntry]], parent: QWidget | None = None) -> None:
        word = language_wrapper.language_word_dict
        super().__init__(word.get("navigation_dock_title"), parent)
        self.setObjectName("pybreeze_navigation")

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText(word.get("navigation_filter_placeholder"))
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.textChanged.connect(self.apply_filter)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemActivated.connect(self._activate)

        self.status = StatusLine()
        self.status.hide()

        body = QWidget()
        layout = QVBoxLayout(body)
        apply_spacing(layout, around=Space.TIGHT)
        layout.addWidget(self.filter_edit)
        layout.addWidget(self.tree)
        layout.addWidget(self.status)
        body.setMinimumWidth(_MIN_WIDTH_EMS * em(body))
        self.setWidget(body)

        self._fill(navigation)

    def _fill(self, navigation: dict[str, list[NavigationEntry]]) -> None:
        """List each category that holds something, open, with its entries under it."""
        word = language_wrapper.language_word_dict
        for key, title_key in CATEGORIES:
            entries = navigation.get(key, [])
            if not entries:
                continue
            category = QTreeWidgetItem(self.tree, [word.get(title_key)])
            category.setFont(0, text_font(TextRole.TITLE, self.tree))
            for entry in entries:
                self._add(category, entry)
            category.setExpanded(True)

    def _add(self, parent: QTreeWidgetItem, entry: NavigationEntry) -> None:
        item = QTreeWidgetItem(parent, [entry.text])
        item.setData(0, _ENTRY_ROLE, entry)
        for child in entry.children:
            self._add(item, child)

    def _activate(self, item: QTreeWidgetItem, _column: int) -> None:
        """Do what the line stands for; a line that only holds others does nothing."""
        entry = item.data(0, _ENTRY_ROLE)
        if not isinstance(entry, NavigationEntry) or entry.activate is None:
            return
        try:
            entry.activate()
        except RuntimeError as error:
            # The menu action it stood for is gone (a menu rebuilt since the panel was filled)
            pybreeze_logger.error("navigation_dock.py entry %r could not be activated: %r", entry.text, error)

    def apply_filter(self, text: str) -> None:
        """Keep the lines that hold *text*, whatever its case, with the lines they are under.

        A line that matches keeps everything under it. With no text, every
        line is back and the tree is as it was opened.
        """
        wanted = text.strip().casefold()
        found = False
        for index in range(self.tree.topLevelItemCount()):
            category = self.tree.topLevelItem(index)
            # A category's own title does not match: "Tools" would list every tool
            kept = [self._keep(category.child(row), wanted) for row in range(category.childCount())]
            category.setHidden(not any(kept))
            category.setExpanded(True)
            found = found or any(kept)
        self.status.setVisible(not found)
        if not found:
            self.status.show_state(
                State.WARNING, language_wrapper.language_word_dict.get("navigation_no_match"))

    def _keep(self, item: QTreeWidgetItem, wanted: str) -> bool:
        """Show *item* when it or a line under it holds *wanted*; return whether it is shown."""
        own = wanted in item.text(0).casefold()
        kept = [self._keep(item.child(row), "" if own else wanted) for row in range(item.childCount())]
        shown = own or any(kept)
        item.setHidden(not shown)
        # Open what a search found; leave the tree as the user had it otherwise
        if wanted and any(kept):
            item.setExpanded(True)
        return shown

    def closeEvent(self, event) -> None:
        # Closed with its own button: stay closed next time. The Dock menu's
        # entry remembers the same when it is used (main_ui.py).
        remember(VISIBLE_STATE, False)
        super().closeEvent(event)
