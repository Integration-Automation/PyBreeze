"""The JSON editor: a tree and a text over one document, with undo, unsaved work asked about, and files."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QLineEdit, QMessageBox, QTreeWidgetItem
from je_editor import language_wrapper

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.design.tokens import State
from pybreeze.pybreeze_ui.tools_gui.json_editor_gui import JsonEditorGUI
from pybreeze.utils.json_format.json_document import JsonNumber
from pybreeze.utils.json_format.json_tree_edit import JsonEditError, JsonKind

SERVERS = """{
  "name": "demo",
  "servers": [
    {
      "port": 80
    },
    {
      "port": 443
    }
  ],
  "on": true,
  "note": null
}
"""
KEY, VALUE, TYPE = range(3)


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture
def editor(app):
    gui = JsonEditorGUI()
    gui.load_text(SERVERS)
    yield gui
    gui.deleteLater()


def _word(key: str) -> str:
    return language_wrapper.language_word_dict.get(key)


def _item(editor: JsonEditorGUI, *path):
    assert editor.tree_panel.select_path(path), path
    return editor.tree_panel.tree.currentItem()


def _names(item) -> list[str]:
    return [item.child(row).text(KEY) for row in range(item.childCount())]


def _choose_kind(editor: JsonEditorGUI, kind: JsonKind) -> None:
    editor.tree_panel.type_select.activated.emit(editor.tree_panel.type_select.findData(kind))


def _show_text_view(editor: JsonEditorGUI) -> None:
    editor.views.setCurrentWidget(editor.text_edit)


def _show_tree_view(editor: JsonEditorGUI) -> None:
    editor.views.setCurrentWidget(editor.tree_panel)


# ----------------------------------------------------------------------
# One document, two views
# ----------------------------------------------------------------------

def test_a_new_editor_holds_an_empty_object(app):
    gui = JsonEditorGUI()
    try:
        assert gui.document.text == "{}"
        assert gui.document.tree == {}
        assert not gui.is_modified()
        assert gui.file_label.text() == _word("json_editor_untitled")
        assert gui.status.state is State.SUCCESS
        assert gui.tree_panel.tree.topLevelItemCount() == 1
        assert gui.tree_panel.tree.topLevelItem(0).childCount() == 0
    finally:
        gui.deleteLater()


def test_the_tree_shows_every_value_with_its_name_and_kind(editor):
    root = editor.tree_panel.tree.topLevelItem(0)

    assert _names(root) == ["name", "servers", "on", "note"]
    assert [_item(editor, "name").text(column) for column in range(3)] == [
        "name", "demo", _word("json_editor_kind_string")]
    assert _item(editor, "servers").text(VALUE) == "(2)"
    assert _item(editor, "servers", 1, "port").text(VALUE) == "443"
    assert _item(editor, "on").text(VALUE) == "true"
    assert _item(editor, "note").text(TYPE) == _word("json_editor_kind_null")


def test_a_values_items_are_made_when_it_is_opened(editor):
    servers = _item(editor, "servers")
    assert servers.childCount() == 0
    assert servers.childIndicatorPolicy() is QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator

    servers.setExpanded(True)

    assert _names(servers) == ["[0]", "[1]"]
    assert servers.child(0).childCount() == 0


def test_an_empty_object_or_array_has_nothing_to_open(editor):
    editor.load_text('{"none": {}, "nothing": []}')

    for name in ("none", "nothing"):
        item = _item(editor, name)
        assert item.text(VALUE) == "(0)"
        assert item.childIndicatorPolicy() is not QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator


def test_a_large_document_makes_items_only_for_what_is_open(editor):
    editor.load_text(json.dumps([{"id": number, "tags": ["a", "b"]} for number in range(2000)]))
    root = editor.tree_panel.tree.topLevelItem(0)

    assert root.childCount() == 2000
    assert all(root.child(row).childCount() == 0 for row in range(0, 2000, 97))

    _item(editor, 1999, "tags", 1)
    assert root.child(1999).childCount() == 2
    assert root.child(0).childCount() == 0


def test_the_text_view_holds_the_documents_text(editor):
    assert editor.text_edit.toPlainText() == SERVERS
    assert not editor.is_modified()


def test_typing_in_the_text_changes_the_document_and_the_tree(editor):
    _show_text_view(editor)
    editor.text_edit.setPlainText('{"only": [1, 2, 3]}')
    _show_tree_view(editor)

    assert editor.document.tree == {"only": [JsonNumber("1"), JsonNumber("2"), JsonNumber("3")]}
    assert _names(editor.tree_panel.tree.topLevelItem(0)) == ["only"]
    assert editor.is_modified()


def test_text_that_is_not_json_is_kept_and_its_place_is_said(editor):
    _show_text_view(editor)
    editor.text_edit.setPlainText('{\n  "a": 1,\n  "b" 2\n}')

    assert editor.document.text == '{\n  "a": 1,\n  "b" 2\n}'
    assert editor.status.state is State.ERROR
    assert editor.status.text() == _word("json_editor_problem_at").format(
        line=3, column=7, reason=editor.status.text().split(": ", 1)[1])


def test_an_edit_the_document_refuses_changes_nothing_and_is_said(editor):
    def refused():
        raise JsonEditError("only an object or an array holds other values")

    editor.tree_panel.edit_asked.emit(refused, None)

    assert editor.document.text == SERVERS
    assert editor.status.state is State.ERROR
    assert not editor.is_modified()


def test_the_tree_waits_while_the_text_is_not_json_and_comes_back_when_it_is(editor):
    _show_text_view(editor)
    editor.text_edit.setPlainText('{"a": ')
    _show_tree_view(editor)

    assert not editor.tree_panel.tree.isEnabled()
    assert editor.tree_panel.tree.topLevelItemCount() == 0
    assert not editor.tree_panel.add_button.isEnabled()
    assert editor.tree_panel.add_value() is False

    _show_text_view(editor)
    editor.text_edit.setPlainText('{"a": 1}')
    _show_tree_view(editor)

    assert editor.tree_panel.tree.isEnabled()
    assert _names(editor.tree_panel.tree.topLevelItem(0)) == ["a"]
    assert editor.status.state is State.SUCCESS


# ----------------------------------------------------------------------
# Edits in the tree
# ----------------------------------------------------------------------

def test_a_member_is_added_to_the_selected_object_and_selected(editor):
    _item(editor)

    assert editor.tree_panel.add_value() is True

    assert list(editor.document.tree) == ["name", "servers", "on", "note", "new_key"]
    assert editor.tree_panel.selected_path() == ("new_key",)
    assert editor.document.tree["new_key"] is None


def test_a_second_new_member_gets_a_name_that_is_free(editor):
    _item(editor)
    editor.tree_panel.add_value()
    _item(editor)
    editor.tree_panel.add_value()

    assert list(editor.document.tree)[-2:] == ["new_key", "new_key_2"]


def test_an_item_is_added_at_the_end_of_the_selected_array(editor):
    _item(editor, "servers")

    editor.tree_panel.add_value()

    assert len(editor.document.tree["servers"]) == 3
    assert editor.tree_panel.selected_path() == ("servers", 2)


def test_with_a_plain_value_selected_the_new_one_goes_after_it(editor):
    editor.load_text("[1, 2, 3]")
    _item(editor, 0)

    editor.tree_panel.add_value()

    assert editor.document.text == "[1, null, 2, 3]"
    assert editor.tree_panel.selected_path() == (1,)


def test_a_new_document_is_laid_out_as_the_json_tools_lay_theirs_out(app):
    gui = JsonEditorGUI()
    try:
        gui.tree_panel.select_path(())
        gui.tree_panel.add_value()

        assert gui.document.text == '{\n    "new_key": null\n}'
    finally:
        gui.deleteLater()


def test_a_document_pasted_into_the_text_keeps_its_own_indent_through_a_tree_edit(app):
    gui = JsonEditorGUI()
    try:
        _show_text_view(gui)
        gui.text_edit.setPlainText('{\n "a": 1\n}\n')
        _show_tree_view(gui)
        gui.tree_panel.select_path(())
        gui.tree_panel.add_value()

        assert gui.document.text == '{\n "a": 1,\n "new_key": null\n}\n'
    finally:
        gui.deleteLater()


def test_an_empty_document_keeps_the_indent_it_had_and_the_way_it_ends(editor):
    _show_text_view(editor)
    editor.text_edit.setPlainText('{}\n')
    _show_tree_view(editor)
    _item(editor)
    editor.tree_panel.add_value()

    assert editor.document.text == '{\n  "new_key": null\n}\n'


def test_the_text_is_written_again_laid_out_as_the_file_was(editor):
    _item(editor, "servers", 0)
    editor.tree_panel.add_value()

    assert '    {\n      "port": 80,\n      "new_key": null\n    },' in editor.document.text
    assert editor.document.text.endswith("}\n")
    assert editor.text_edit.toPlainText() == editor.document.text


@pytest.mark.parametrize(("text", "expected"), [
    ('{\n\t"a": 1\n}', '{\n\t"a": 1,\n\t"new_key": null\n}'),
    ('{"a": 1}', '{"a": 1, "new_key": null}'),
    ('{\n    "a": "\\u00e9"\n}', '{\n    "a": "\\u00e9",\n    "new_key": null\n}'),
])
def test_tabs_one_line_and_escapes_are_kept_as_the_file_had_them(editor, text, expected):
    editor.load_text(text)
    _item(editor)

    editor.tree_panel.add_value()

    assert editor.document.text == expected


def test_the_selected_value_is_deleted(editor):
    _item(editor, "servers", 0)

    assert editor.tree_panel.delete_selected() is True

    assert editor.document.tree["servers"] == [{"port": JsonNumber("443")}]
    assert editor.tree_panel.selected_path() == ("servers",)


def test_the_document_itself_is_not_deleted(editor):
    _item(editor)

    assert editor.tree_panel.delete_selected() is False
    assert not editor.tree_panel.delete_button.isEnabled()
    assert not editor.is_modified()


def test_a_value_moves_down_and_up_and_stays_selected(editor):
    _item(editor, "servers", 0)

    assert editor.tree_panel.move_down() is True
    assert [item["port"].text for item in editor.document.tree["servers"]] == ["443", "80"]
    assert editor.tree_panel.selected_path() == ("servers", 1)

    assert editor.tree_panel.move_up() is True
    assert [item["port"].text for item in editor.document.tree["servers"]] == ["80", "443"]
    assert editor.tree_panel.selected_path() == ("servers", 0)


def test_a_member_moves_among_the_members_and_keeps_its_name(editor):
    _item(editor, "name")

    editor.tree_panel.move_down()

    assert list(editor.document.tree) == ["servers", "name", "on", "note"]
    assert editor.tree_panel.selected_path() == ("name",)


def test_a_value_at_the_end_does_not_move_further(editor):
    _item(editor, "name")
    assert editor.tree_panel.move_up() is False
    _item(editor, "note")
    assert editor.tree_panel.move_down() is False

    assert not editor.is_modified()


def test_each_button_asks_for_what_it_says(editor):
    panel = editor.tree_panel
    _item(editor, "servers", 0)

    panel.down_button.click()
    assert panel.selected_path() == ("servers", 1)
    panel.up_button.click()
    assert panel.selected_path() == ("servers", 0)
    panel.add_button.click()
    assert panel.selected_path() == ("servers", 0, "new_key")
    panel.delete_button.click()
    assert editor.document.tree["servers"][0] == {"port": JsonNumber("80")}

    for _step in range(4):
        editor.undo_stack.undo()
    assert editor.document.text == SERVERS


def test_a_member_is_renamed_by_typing_over_its_name(editor):
    _item(editor, "servers").setText(KEY, "hosts")

    assert list(editor.document.tree) == ["name", "hosts", "on", "note"]
    assert editor.tree_panel.selected_path() == ("hosts",)


def test_a_name_that_is_taken_is_refused_and_the_tree_shows_what_is_there(editor):
    _item(editor, "name").setText(KEY, "on")

    assert list(editor.document.tree) == ["name", "servers", "on", "note"]
    assert _names(editor.tree_panel.tree.topLevelItem(0)) == ["name", "servers", "on", "note"]
    assert editor.status.state is State.ERROR
    assert "'on'" in editor.status.text() or "on" in editor.status.text()
    assert not editor.is_modified()


def test_a_value_is_changed_by_typing_over_it_and_keeps_its_kind(editor):
    _item(editor, "servers", 0, "port").setText(VALUE, "8080")
    _item(editor, "name").setText(VALUE, "12")
    _item(editor, "on").setText(VALUE, "False")

    tree = editor.document.tree
    assert tree["servers"][0]["port"] == JsonNumber("8080")
    assert tree["name"] == "12"
    assert tree["on"] is False


def test_a_number_is_kept_as_it_was_typed(editor):
    _item(editor, "servers", 0, "port").setText(VALUE, "80.00")

    assert '"port": 80.00' in editor.document.text


def test_what_is_not_a_number_is_refused_and_the_cell_shows_the_number_again(editor):
    _item(editor, "servers", 0, "port").setText(VALUE, "eighty")

    assert editor.document.tree["servers"][0]["port"] == JsonNumber("80")
    assert _item(editor, "servers", 0, "port").text(VALUE) == "80"
    assert editor.status.state is State.ERROR
    assert not editor.is_modified()


def test_a_cell_is_edited_in_place_with_the_keyboard(editor):
    item = _item(editor, "name")
    editor.tree_panel.tree.editItem(item, VALUE)
    box = editor.tree_panel.tree.findChild(QLineEdit)
    assert box is not None

    box.setText("renamed")
    QTest.keyClick(box, Qt.Key.Key_Return)
    QApplication.processEvents()

    assert editor.document.tree["name"] == "renamed"
    assert _item(editor, "name").text(VALUE) == "renamed"


@pytest.mark.parametrize(("path", "column", "typed"), [
    ((), KEY, False), ((), VALUE, False),
    (("name",), KEY, True), (("name",), VALUE, True), (("name",), TYPE, False),
    (("servers",), KEY, True), (("servers",), VALUE, False),
    (("servers", 0), KEY, False), (("note",), VALUE, False), (("on",), VALUE, True),
])
def test_only_a_members_name_and_a_typed_value_are_typed_into(editor, path, column, typed):
    index = editor.tree_panel.tree.indexFromItem(_item(editor, *path), column)

    assert editor.tree_panel.may_type_into(index) is typed


def test_the_kind_of_the_selected_value_is_shown_and_can_be_changed(editor):
    _item(editor, "servers", 0, "port")
    assert editor.tree_panel.type_select.currentData() is JsonKind.NUMBER

    _choose_kind(editor, JsonKind.STRING)

    assert editor.document.tree["servers"][0]["port"] == "80"
    assert editor.tree_panel.selected_path() == ("servers", 0, "port")
    assert editor.tree_panel.type_select.currentData() is JsonKind.STRING


def test_a_value_made_an_object_can_then_take_members(editor):
    _item(editor, "note")
    _choose_kind(editor, JsonKind.OBJECT)
    editor.tree_panel.add_value()

    assert editor.document.tree["note"] == {"new_key": None}
    assert editor.tree_panel.selected_path() == ("note", "new_key")


def test_what_was_open_in_the_tree_stays_open_after_an_edit(editor):
    _item(editor, "servers", 1, "port")
    assert _item(editor, "servers").isExpanded()

    _item(editor, "name").setText(VALUE, "other")

    assert _item(editor, "servers").isExpanded()
    assert _item(editor, "servers", 1).isExpanded()


def test_a_deep_document_is_shown_without_recursion(app):
    depth = 150
    gui = JsonEditorGUI()
    try:
        gui.load_text("[" * depth + "]" * depth)
        assert gui.status.state is State.SUCCESS
        assert gui.tree_panel.select_path((0,) * (depth - 1))
    finally:
        gui.deleteLater()


# ----------------------------------------------------------------------
# Undo and redo
# ----------------------------------------------------------------------

def test_an_edit_in_the_tree_is_one_step_to_undo_and_redo(editor):
    _item(editor, "servers", 0)
    editor.tree_panel.delete_selected()
    edited = editor.document.text

    editor.undo_stack.undo()
    assert editor.document.text == SERVERS
    assert editor.text_edit.toPlainText() == SERVERS
    assert len(editor.document.tree["servers"]) == 2
    assert not editor.is_modified()

    editor.undo_stack.redo()
    assert editor.document.text == edited
    assert editor.is_modified()


def test_the_buttons_follow_what_can_be_undone(editor):
    assert not editor.undo_button.isEnabled() and not editor.redo_button.isEnabled()

    _item(editor)
    editor.tree_panel.add_value()
    assert editor.undo_button.isEnabled() and not editor.redo_button.isEnabled()

    editor.undo_button.click()
    assert not editor.undo_button.isEnabled() and editor.redo_button.isEnabled()


def test_a_run_of_typing_is_one_step(editor):
    _show_text_view(editor)
    editor.text_edit.setPlainText("[")
    for typed in ("1", ",", "2", "]"):
        editor.text_edit.moveCursor(editor.text_edit.textCursor().MoveOperation.End)
        editor.text_edit.insertPlainText(typed)
    assert editor.document.text == "[1,2]"

    editor.undo_stack.undo()

    assert editor.document.text == SERVERS
    assert not editor.undo_stack.canUndo()


def test_an_edit_in_the_tree_ends_a_run_of_typing(editor):
    _show_text_view(editor)
    editor.text_edit.setPlainText("[1]")
    _show_tree_view(editor)
    _item(editor)
    editor.tree_panel.add_value()
    _show_text_view(editor)
    editor.text_edit.setPlainText("[1, null, 2]")

    editor.undo_stack.undo()
    assert editor.document.text == "[1, null]"
    editor.undo_stack.undo()
    assert editor.document.text == "[1]"
    editor.undo_stack.undo()
    assert editor.document.text == SERVERS


def test_the_undo_key_in_the_text_view_undoes_the_documents_step(editor):
    _item(editor, "on")
    editor.tree_panel.delete_selected()
    _show_text_view(editor)

    QTest.keyClick(editor.text_edit, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert editor.document.text == SERVERS

    QTest.keyClick(editor.text_edit, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
    assert "on" not in editor.document.tree


def test_the_text_box_keeps_no_history_of_its_own(editor):
    assert not editor.text_edit.isUndoRedoEnabled()


def test_only_so_many_steps_are_kept_and_the_saved_text_is_then_out_of_reach(editor):
    limit = editor.undo_stack.undoLimit()
    assert limit > 0

    for _step in range(limit + 3):
        editor.tree_panel.select_path(())
        editor.tree_panel.add_value()
    assert editor.undo_stack.count() == limit

    while editor.undo_stack.canUndo():
        editor.undo_stack.undo()
    assert list(editor.document.tree)[-3:] == ["new_key", "new_key_2", "new_key_3"]
    assert editor.is_modified()


def test_an_undone_edit_selects_what_is_still_there(editor):
    _item(editor, "servers")
    editor.tree_panel.add_value()
    assert editor.tree_panel.selected_path() == ("servers", 2)

    editor.undo_stack.undo()

    assert editor.tree_panel.selected_path() == ("servers",)
    assert editor.tree_panel.add_button.isEnabled()


# ----------------------------------------------------------------------
# Unsaved work
# ----------------------------------------------------------------------

def _answer(monkeypatch, button) -> list:
    asked = []

    def question(_parent, title, text, _buttons, default):
        asked.append((title, text, default))
        return button

    monkeypatch.setattr(QMessageBox, "question", question)
    return asked


def test_an_unchanged_document_closes_without_a_question(editor, monkeypatch):
    asked = _answer(monkeypatch, QMessageBox.StandardButton.No)

    assert editor.may_close() is True
    assert asked == []


def test_a_changed_document_asks_and_no_is_the_default(editor, monkeypatch):
    asked = _answer(monkeypatch, QMessageBox.StandardButton.No)
    _item(editor, "on")
    editor.tree_panel.delete_selected()

    assert editor.may_close() is False
    assert asked == [(_word("unsaved_close_title"), _word("json_editor_close_over_edits"),
                      QMessageBox.StandardButton.No)]


def test_yes_lets_the_changes_go(editor, monkeypatch):
    _answer(monkeypatch, QMessageBox.StandardButton.Yes)
    _item(editor, "on")
    editor.tree_panel.delete_selected()

    assert editor.may_close() is True


def test_the_file_name_is_marked_while_there_are_changes(editor):
    assert editor.file_label.text() == _word("json_editor_untitled")

    _item(editor, "on")
    editor.tree_panel.delete_selected()
    assert editor.file_label.text() == _word("json_editor_untitled") + " *"

    editor.undo_stack.undo()
    assert editor.file_label.text() == _word("json_editor_untitled")


# ----------------------------------------------------------------------
# Files
# ----------------------------------------------------------------------

def _choose(monkeypatch, method: str, path) -> None:
    monkeypatch.setattr(QFileDialog, method, staticmethod(lambda *_args, **_kwargs: (str(path), "")))


def test_a_file_is_opened_into_both_views(editor, monkeypatch, tmp_path):
    file = tmp_path / "config.json"
    file.write_text('{"a": [true]}', encoding="utf-8")
    _choose(monkeypatch, "getOpenFileName", file)

    assert editor.open_file() == str(file)

    assert editor.document.tree == {"a": [True]}
    assert editor.text_edit.toPlainText() == '{"a": [true]}'
    assert editor.file_label.text() == "config.json"
    assert not editor.is_modified() and not editor.undo_stack.canUndo()


def test_a_file_with_a_byte_order_mark_is_json_all_the_same(editor, monkeypatch, tmp_path):
    file = tmp_path / "bom.json"
    file.write_bytes(b"\xef\xbb\xbf[1]")
    _choose(monkeypatch, "getOpenFileName", file)

    editor.open_file()

    assert editor.document.problem is None
    assert editor.document.text == "[1]"


def test_a_file_that_is_not_json_is_opened_as_text_to_be_put_right(editor, monkeypatch, tmp_path):
    file = tmp_path / "broken.json"
    file.write_text('{"a": 1,}', encoding="utf-8")
    _choose(monkeypatch, "getOpenFileName", file)

    editor.open_file()

    assert editor.document.text == '{"a": 1,}'
    assert editor.status.state is State.ERROR
    assert not editor.is_modified()


def test_a_file_that_cannot_be_read_is_said_without_its_path(editor, monkeypatch, tmp_path):
    _choose(monkeypatch, "getOpenFileName", tmp_path / "gone.json")

    assert editor.open_file() is None

    assert editor.status.state is State.ERROR
    assert str(tmp_path) not in editor.status.text()
    assert editor.document.text == SERVERS


def test_a_file_that_is_not_text_is_said_and_nothing_is_opened(editor, monkeypatch, tmp_path):
    file = tmp_path / "binary.json"
    file.write_bytes(b"\xff\xfe\x00\x80")
    _choose(monkeypatch, "getOpenFileName", file)

    assert editor.open_file() is None
    assert editor.status.state is State.ERROR
    assert editor.document.text == SERVERS


def test_opening_over_changes_asks_first(editor, monkeypatch, tmp_path):
    asked = _answer(monkeypatch, QMessageBox.StandardButton.No)
    _choose(monkeypatch, "getOpenFileName", tmp_path / "never.json")
    _item(editor, "on")
    editor.tree_panel.delete_selected()
    edited = editor.document.text

    assert editor.open_file() is None

    assert [text for _title, text, _default in asked] == [_word("json_editor_open_over_edits")]
    assert editor.document.text == edited


def test_a_cancelled_dialog_opens_and_saves_nothing(editor, monkeypatch):
    _choose(monkeypatch, "getOpenFileName", "")
    _choose(monkeypatch, "getSaveFileName", "")

    assert editor.open_file() is None
    assert editor.save() is None
    assert editor.save_as() is None
    assert editor.document.text == SERVERS


def test_a_new_document_asks_where_to_be_saved_and_is_then_clean(editor, monkeypatch, tmp_path):
    file = tmp_path / "saved.json"
    _choose(monkeypatch, "getSaveFileName", file)
    _item(editor, "on")
    editor.tree_panel.delete_selected()

    assert editor.save() == str(file)

    assert file.read_text(encoding="utf-8") == editor.document.text
    assert not editor.is_modified()
    assert editor.file_label.text() == "saved.json"


def test_save_writes_the_file_it_was_opened_from_without_asking(editor, monkeypatch, tmp_path):
    file = tmp_path / "config.json"
    file.write_text('{\n  "a": 1\n}\n', encoding="utf-8")
    _choose(monkeypatch, "getOpenFileName", file)
    editor.open_file()
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(
        lambda *_args, **_kwargs: pytest.fail("Save asked for a file it already has")))
    _item(editor)
    editor.tree_panel.add_value()

    assert editor.save() == str(file)

    assert file.read_text(encoding="utf-8") == '{\n  "a": 1,\n  "new_key": null\n}\n'


def test_text_that_is_not_json_can_be_saved_as_it_is(editor, monkeypatch, tmp_path):
    file = tmp_path / "draft.json"
    _choose(monkeypatch, "getSaveFileName", file)
    _show_text_view(editor)
    editor.text_edit.setPlainText('{"half": ')

    assert editor.save() == str(file)
    assert file.read_text(encoding="utf-8") == '{"half": '


def test_an_edit_after_a_save_is_undone_to_the_saved_state(editor, monkeypatch, tmp_path):
    _choose(monkeypatch, "getSaveFileName", tmp_path / "saved.json")
    _show_text_view(editor)
    editor.text_edit.setPlainText("[1]")
    editor.save()
    editor.text_edit.setPlainText("[1, 2]")
    assert editor.is_modified()

    editor.undo_stack.undo()

    assert editor.document.text == "[1]"
    assert not editor.is_modified()


def test_a_save_that_fails_says_so_and_the_document_stays_changed(editor, monkeypatch, tmp_path):
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, title, text: warned.append((title, text)))
    _choose(monkeypatch, "getSaveFileName", tmp_path / "no_such_folder" / "saved.json")
    _item(editor, "on")
    editor.tree_panel.delete_selected()

    assert editor.save() is None

    assert len(warned) == 1
    assert str(tmp_path) not in warned[0][1]
    assert editor.is_modified()
    assert editor.file_label.text() == _word("json_editor_untitled") + " *"


def test_a_character_the_text_view_would_change_is_shown_as_its_escape(editor, monkeypatch, tmp_path):
    file = tmp_path / "separators.json"
    file.write_text('{"a": "one\u2029two"}', encoding="utf-8")
    _choose(monkeypatch, "getOpenFileName", file)

    editor.open_file()

    assert editor.document.text == '{"a": "one\\u2029two"}'
    assert editor.document.tree == {"a": "one\u2029two"}
    assert not editor.is_modified()


# ----------------------------------------------------------------------
# The tool
# ----------------------------------------------------------------------

def test_the_editor_is_one_of_the_tools(app):
    from pybreeze.pybreeze_ui.menu.tools import tools_menu

    assert "JsonEditor" in tools_menu.TOOLS
    widget = tools_menu.build_tool_widget(None, "JsonEditor")
    try:
        assert isinstance(widget, JsonEditorGUI)
    finally:
        widget.deleteLater()


def test_text_loaded_into_the_editor_is_not_a_change_to_save(app):
    gui = JsonEditorGUI()
    try:
        gui.load_text("[1, 2]")

        assert gui.document.tree == [JsonNumber("1"), JsonNumber("2")]
        assert not gui.is_modified() and not gui.undo_stack.canUndo()
    finally:
        gui.deleteLater()


def test_the_editor_reads_and_writes_through_the_shared_helpers():
    source = Path(__file__).resolve().parents[2].joinpath(
        "pybreeze", "pybreeze_ui", "tools_gui", "json_editor_gui.py").read_text(encoding="utf-8")

    assert "read_text_capped(" in source and "replace_text(" in source and "escape_for_view(" in source
    assert ".write_text(" not in source and ".read_text(" not in source
