"""The tree view of the JSON editor: a document's values, and the controls that edit them.

The panel shows a tree it is given and holds nothing of the document. An edit
made in it -- a name or a value typed over, Add, Delete, Move Up, Move Down, a
kind chosen -- is *asked for* (``edit_asked``): the function that gives the new
tree (``utils/json_format/json_tree_edit.py``), and the path to select once it
is made. Whoever holds the document makes the edit, records it for Undo and
shows the new tree here, so the tree cannot get ahead of the text.
"""
from __future__ import annotations

import weakref

from PySide6.QtCore import QModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QLabel, QPushButton, QStyledItemDelegate, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.design.panels import wrapping_row
from pybreeze.pybreeze_ui.design.tokens import em
from pybreeze.utils.json_format.json_document import JsonValue
from pybreeze.utils.json_format.json_tree_edit import (
    JsonEditError, JsonKind, JsonPath, children, converted, delete, empty_value, insert, kind_of, move,
    position_of, rename, scalar_text, set_value, value_at, value_from_text,
)

# The columns of the tree
KEY_COLUMN, VALUE_COLUMN, TYPE_COLUMN = range(3)
# Where an item keeps the path of the value it shows
_PATH_ROLE = Qt.ItemDataRole.UserRole
# The name a member added in the tree starts with; a number is added when it is taken
_NEW_KEY = "new_key"
# The kinds a cell of the Value column can be typed into
_TYPED_KINDS = (JsonKind.STRING, JsonKind.NUMBER, JsonKind.BOOLEAN)
# How wide the Key and Value columns start, in ems; the Type column takes the rest
_KEY_WIDTH, _VALUE_WIDTH = 14, 18
# Each kind and the language key of its name
_KIND_WORDS: dict[JsonKind, str] = {
    JsonKind.OBJECT: "json_editor_kind_object",
    JsonKind.ARRAY: "json_editor_kind_array",
    JsonKind.STRING: "json_editor_kind_string",
    JsonKind.NUMBER: "json_editor_kind_number",
    JsonKind.BOOLEAN: "json_editor_kind_boolean",
    JsonKind.NULL: "json_editor_kind_null",
}


def _word(key: str) -> str:
    return language_wrapper.language_word_dict.get(key)


def _path_of(item: QTreeWidgetItem) -> JsonPath:
    """The path of the value *item* shows. Qt hands a stored sequence back as a list."""
    return tuple(item.data(KEY_COLUMN, _PATH_ROLE) or ())


class _CellDelegate(QStyledItemDelegate):
    """Opens an editor only for the cells that can be typed into: a member's name, a typed value."""

    def __init__(self, panel: JsonTreePanel) -> None:
        super().__init__(panel)
        self._panel = weakref.ref(panel)

    def createEditor(self, parent: QWidget, option, index: QModelIndex) -> QWidget | None:
        panel = self._panel()
        if panel is None or not panel.may_type_into(index):
            return None
        return super().createEditor(parent, option, index)


class JsonTreePanel(QWidget):
    """A JSON tree, and the controls that ask for it to be edited."""

    # (edit, select): ``edit()`` gives the new tree or raises ``JsonEditError``;
    # *select* is the path to select once it is made, ``None`` for the one selected now
    edit_asked = Signal(object, object)

    def __init__(self) -> None:
        super().__init__()
        self._value: JsonValue = None
        self._has_tree = False
        # Set while the tree is being filled, so that filling it is not taken for typing
        self._showing = False

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels([
            _word("json_editor_column_key"), _word("json_editor_column_value"), _word("json_editor_column_type")])
        self.tree.setColumnWidth(KEY_COLUMN, _KEY_WIDTH * em(self.tree))
        self.tree.setColumnWidth(VALUE_COLUMN, _VALUE_WIDTH * em(self.tree))
        self.tree.setItemDelegate(_CellDelegate(self))
        self.tree.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.tree.itemChanged.connect(self._cell_typed)
        self.tree.itemExpanded.connect(self._fill)
        self.tree.currentItemChanged.connect(self._selection_changed)

        self.add_button = QPushButton(_word("json_editor_add_button"))
        self.add_button.clicked.connect(self.add_value)
        self.delete_button = QPushButton(_word("json_editor_delete_button"))
        self.delete_button.clicked.connect(self.delete_selected)
        self.up_button = QPushButton(_word("json_editor_up_button"))
        self.up_button.clicked.connect(self.move_up)
        self.down_button = QPushButton(_word("json_editor_down_button"))
        self.down_button.clicked.connect(self.move_down)
        self.type_label = QLabel(_word("json_editor_type_label"))
        self.type_select = QComboBox()
        for kind, key in _KIND_WORDS.items():
            self.type_select.addItem(_word(key), kind)
        self.type_select.activated.connect(self._type_chosen)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tree)
        layout.addLayout(wrapping_row(
            self.add_button, self.delete_button, self.up_button, self.down_button, self.type_label, self.type_select))
        self._selection_changed()

    # ------------------------------------------------------------------
    # Showing a tree
    # ------------------------------------------------------------------

    def show_tree(self, tree: JsonValue, select: JsonPath | None = None) -> None:
        """Show *tree*, open where the last one was open.

        :param tree: the document's tree
        :param select: the path to select; the one selected now when not given.
            When nothing is there any more (an undone Add), what held it is selected.
        """
        open_paths = self._open_paths()
        path = select if select is not None else self.selected_path() or ()
        self._value = tree
        self._has_tree = True
        self._refill(open_paths)
        while not self.select_path(path) and path:
            path = path[:-1]
        self._selection_changed()

    def show_nothing(self) -> None:
        """Show no tree, and offer no edit: the text is not JSON at the moment."""
        self._value = None
        self._has_tree = False
        self._refill(set())
        self._selection_changed()

    def _refill(self, open_paths: set[JsonPath]) -> None:
        self._showing = True
        try:
            self.tree.clear()
            self.tree.setEnabled(self._has_tree)
            if self._has_tree:
                root = self._item((), _word("json_editor_root"), self._value)
                self.tree.addTopLevelItem(root)
                self._open(root, open_paths | {()})
        finally:
            self._showing = False

    def _open(self, root: QTreeWidgetItem, open_paths: set[JsonPath]) -> None:
        """Open *root* and every item under it whose path is in *open_paths*. Without recursion: a tree can be deep."""
        pending = [root]
        while pending:
            item = pending.pop()
            if _path_of(item) not in open_paths:
                continue
            self._fill(item)
            item.setExpanded(True)
            pending.extend(item.child(row) for row in range(item.childCount()))

    def _fill(self, item: QTreeWidgetItem) -> None:
        """Give *item* an item for each value its own holds, when it has none yet.

        A value's items are made when it is opened, not for the whole document:
        a file of some thousands of values took a second to show again after
        every edit. They are made on their own and put in together, which has
        the view lay itself out once.
        """
        if item.childCount():
            return
        path = _path_of(item)
        item.addChildren([
            self._item((*path, key), key if isinstance(key, str) else f"[{key}]", child)
            for key, child in children(value_at(self._value, path))])

    @staticmethod
    def _item(path: JsonPath, name: str, value: JsonValue) -> QTreeWidgetItem:
        holds = isinstance(value, (dict, list))
        item = QTreeWidgetItem([name, f"({len(value)})" if holds else scalar_text(value),
                                _word(_KIND_WORDS[kind_of(value)])])
        item.setData(KEY_COLUMN, _PATH_ROLE, list(path))
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        if holds and value:
            # Its items are not made yet: it can be opened all the same
            item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
        return item

    def _open_paths(self) -> set[JsonPath]:
        """The paths of the items that are open now."""
        found: set[JsonPath] = set()
        pending = [self.tree.topLevelItem(index) for index in range(self.tree.topLevelItemCount())]
        while pending:
            item = pending.pop()
            if item.isExpanded():
                found.add(_path_of(item))
                pending.extend(item.child(row) for row in range(item.childCount()))
        return found

    # ------------------------------------------------------------------
    # The selected value
    # ------------------------------------------------------------------

    def selected_path(self) -> JsonPath | None:
        """The path of the selected value, or ``None`` when nothing is selected."""
        item = self.tree.currentItem()
        return None if item is None else _path_of(item)

    def select_path(self, path: JsonPath) -> bool:
        """Select the value at *path*, opening what holds it; return whether there is one."""
        item = self.tree.topLevelItem(0)
        if item is None:
            return False
        try:
            rows = [position_of(self._value, path[:depth]) for depth in range(1, len(path) + 1)]
        except JsonEditError:
            return False
        for row in rows:
            self._fill(item)
            # A view that is not on screen selects an item without opening the way to it
            item.setExpanded(True)
            item = item.child(row)
        self.tree.setCurrentItem(item)
        return True

    def may_type_into(self, index: QModelIndex) -> bool:
        """Whether the cell at *index* is typed into: the name of an object's member, or a typed value."""
        item = self.tree.itemFromIndex(index)
        path = None if item is None else _path_of(item)
        if not path or not self._has_tree:
            return False
        if index.column() == KEY_COLUMN:
            return isinstance(path[-1], str)
        return index.column() == VALUE_COLUMN and kind_of(value_at(self._value, path)) in _TYPED_KINDS

    def _selection_changed(self, *_items) -> None:
        """Offer what can be done with the selected value."""
        path = self.selected_path()
        editable = self._has_tree and path is not None
        self.add_button.setEnabled(editable)
        self.type_select.setEnabled(editable)
        for button in (self.delete_button, self.up_button, self.down_button):
            button.setEnabled(editable and bool(path))
        if editable:
            self.type_select.setCurrentIndex(self.type_select.findData(kind_of(value_at(self._value, path))))

    # ------------------------------------------------------------------
    # Edits
    # ------------------------------------------------------------------

    def _cell_typed(self, item: QTreeWidgetItem, column: int) -> None:
        """A cell was typed into: rename the member, or give the value what was typed."""
        if self._showing:
            return
        path = _path_of(item)
        typed = item.text(column)
        tree = self._value
        if column == KEY_COLUMN:
            self.edit_asked.emit(lambda: rename(tree, path, typed), (*path[:-1], typed))
        elif column == VALUE_COLUMN:
            self.edit_asked.emit(
                lambda: set_value(tree, path, value_from_text(kind_of(value_at(tree, path)), typed)), None)

    def _type_chosen(self, index: int) -> None:
        """Give the selected value the kind chosen, keeping what it says where the new kind can say it."""
        path = self.selected_path()
        if path is None or not self._has_tree:
            return
        tree = self._value
        kind = self.type_select.itemData(index)
        self.edit_asked.emit(lambda: set_value(tree, path, converted(value_at(tree, path), kind)), None)

    def add_value(self) -> bool:
        """Ask for a null: in the selected object or array, or after the selected value in what holds it.

        :return: whether there was a place to add one
        """
        path = self.selected_path()
        if path is None or not self._has_tree:
            return False
        tree = self._value
        selected = value_at(tree, path)
        inside = isinstance(selected, (dict, list))
        parent = path if inside else path[:-1]
        holder = selected if inside else value_at(tree, parent)
        if isinstance(holder, dict):
            key: str | int = self._free_key(holder)
        else:
            key = len(holder) if inside else path[-1] + 1
        self.edit_asked.emit(lambda: insert(tree, parent, key, empty_value(JsonKind.NULL)), (*parent, key))
        return True

    @staticmethod
    def _free_key(members: dict) -> str:
        """A member name *members* does not have yet: ``new_key``, then ``new_key_2`` and so on."""
        name, number = _NEW_KEY, 1
        while name in members:
            number += 1
            name = f"{_NEW_KEY}_{number}"
        return name

    def delete_selected(self) -> bool:
        """Ask for the selected value to be deleted; return whether one that can be was selected."""
        path = self.selected_path()
        if not path or not self._has_tree:
            return False
        tree = self._value
        self.edit_asked.emit(lambda: delete(tree, path), path[:-1])
        return True

    def move_up(self) -> bool:
        """Ask for the selected value to move one place towards the start; return whether it has one to move to."""
        return self._move(-1)

    def move_down(self) -> bool:
        """Ask for the selected value to move one place towards the end; return whether it has one to move to."""
        return self._move(1)

    def _move(self, by: int) -> bool:
        path = self.selected_path()
        if not path or not self._has_tree:
            return False
        tree = self._value
        target = position_of(tree, path) + by
        if not 0 <= target < len(children(value_at(tree, path[:-1]))):
            return False
        moved, new_path = move(tree, path, target)
        self.edit_asked.emit(lambda: moved, new_path)
        return True
