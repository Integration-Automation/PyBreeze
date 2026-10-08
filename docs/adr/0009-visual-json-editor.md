# 0009. The JSON editor is two views of one document, with one history

- **Status**: Accepted
- **Date**: 2026-10-08
- **Code**: `pybreeze/pybreeze_ui/tools_gui/json_editor_gui.py`, `json_tree_panel.py`;
  `pybreeze/utils/json_format/json_tree_edit.py`, `json_document.py`; `test_json_editor_gui.py`,
  `test_json_tree_edit.py`

## Context

The automation packages' scripts are JSON, and the IDE had nothing between typing JSON and
reformatting it. [0003](0003-json-document-boundary.md) settled what a text editor and a visual
editor may each do to a JSON document and left the visual editor to be built. Phase 5 of the
roadmap asks for it: a tree that is edited, insert / delete / reorder / rename, formatting kept,
validation that does not block typing, undo and redo, unsaved work asked about, and a switch
between the visual and the text view that cannot lose an edit.

## Decision

1. **A tool tab, opened on purpose.** `JsonEditorGUI` is one more line in `TOOLS`. A `.json` file is
   opened into it from its own Open button; the code editor still opens every file. It is not a
   second code editor: no highlighting, no search, no run.
2. **Two views, one `JsonDocument`.** The Text view's text is the document's text. The Tree view
   (`JsonTreePanel`) holds nothing of the document: it shows the tree it is given and *asks* for an
   edit (`edit_asked`: the function that gives the new tree, and the path to select). The tab makes
   the edit through `set_tree()` with the revision it read, and shows both views again from the
   document. Neither view can get ahead of the other, and an edit that is refused has changed
   nothing.
3. **An edit of a tree is a pure function of a path** (`json_tree_edit.py`): `insert`, `delete`,
   `rename`, `move`, `set_value`, each giving a new tree and sharing what it did not touch. The
   document's tree is never changed in place. What a cell takes when typed into
   (`value_from_text`) and what a value becomes when given another kind (`converted`) are there
   too, so the panel decides nothing about JSON.
4. **One history, of texts.** A step of the `QUndoStack` is the document's text before and after,
   whichever view made it. An edit in the tree is one step; a run of typing is one step, ended by a
   tree edit, a save or a change of view. The text box's own history is off and its Undo keys are
   handed to the stack. At most 200 steps are kept.
5. **Text that is not JSON is kept.** It is the document's text, it can be saved, and a line under
   the views says where it goes wrong. The tree shows nothing and offers no edit until the text is
   JSON again.
6. **The layout follows the text.** Whenever the text is given (opened, typed, brought back by
   Undo) its indent, its final line break and whether it escapes non-ASCII are read
   (`detect_options`) into the document's options, which is how the next tree edit writes it. A
   text with nothing in it keeps the layout it had; a new document has the JSON tools' own.
7. **A value's items are made when it is opened**, not for the whole document.
8. **What a text view would change is escaped as the file is opened** (`escape_for_view`: U+2029
   and its kind), so that typing one character does not rewrite another.

## Alternatives considered

- **A panel beside the code editor's tab, on the editor's own text.** The editor is JEditor's:
  its text, its history and its save are not PyBreeze's to share with a second view, and the
  roadmap's own risk table keeps JEditor as the editor core.
- **One undo command per kind of edit, each with its inverse.** Typing has no inverse to write, so
  there would be two histories to keep in order across two views. A text before and after is the
  same step for both, and adjacent steps share the same string.
- **Changing the items of the tree in place after an edit** instead of filling it again. Every edit
  would need its own way of patching the view, kept true to the pure function beside it. Filling
  only what is open is fast enough (see below) and cannot disagree with the document.
- **Keeping comments, alignment and blank lines** through a tree edit: rejected in 0003 (a concrete
  syntax tree for a file format that has no comments).
- **A form generated from a JSON Schema.** The scripts the IDE edits come with no schema. The
  tree's Type column and the Type box are the form.
- **Refusing to save text that is not JSON.** Half-finished work would have nowhere to go but the
  clipboard.

## Consequences

- A further kind of edit is a pure function in `json_tree_edit.py`, its tests, and a control in
  the panel that emits `edit_asked`.
- `JsonDocument.options` can be set. It is not an edit: the text and the revision stay.
- Measured on this machine (offscreen, a list of records of four members each): 100 KB / 7,000
  values opens in about 50 ms and takes about 55 ms for a tree edit; 520 KB / 35,000 values opens
  in about 280 ms and takes about 480 ms for a tree edit, most of it writing and reading the text.
  A keystroke in the text view costs one parse: 4 ms and 24 ms.
- A tree edit writes the whole text again in the document's layout, so alignment by hand and blank
  lines are lost at the first one (0003). Line endings are the platform's, as everywhere
  `replace_text` writes.
- After 200 steps the oldest is dropped; if the saved state was among them, Undo no longer reaches
  it and the document stays marked as changed until it is saved.
- A file is read through `read_text_capped`, so the IDE's size cap for opening a file applies.
