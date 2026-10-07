# 0003. A JSON file is one document: its text is the truth, its tree is read from it

- **Status**: Accepted
- **Date**: 2026-10-08
- **Code**: `pybreeze/utils/json_format/json_document.py`, `test/test_utils/test_json_document.py`

## Context

The roadmap's Phase 5 puts a visual editor (a tree and forms) beside the text editor for JSON
files, which is how the automation packages' action files are written. Two views of one file can
disagree: each holds its own copy, and whichever writes last wins without a word. The roadmap names
the answer in one line, "one document model + explicit serialization boundary", and leaves where
that boundary runs to this record.

The JSON tools had already settled what PyBreeze takes JSON to be: a number keeps its own text, a
key given twice in one object is refused, `NaN` and `Infinity` are refused, and text shown in a view
is written so that the view gives it back (`json_process.py`, `view_safe.py`).

## Decision

1. **One document, two faces.** A `JsonDocument` holds the text and the tree. Both editors edit
   that one object.
2. **The text is the truth.** It is kept exactly as given, also while it is not JSON. Invalid text
   raises nothing: the document has a `problem` (with the line and column of a syntax error) and no
   tree until the text parses again.
3. **The tree is what the text says, without its layout.** Objects keep the text's member order;
   a number is a `JsonNumber` holding its text. No indentation, spacing or line breaks are in it.
4. **A tree becomes text in one place.** `serialize_json(tree, SerializationOptions)` is the only
   way, and the options (indent, `ensure_ascii`, a trailing line break) belong to the document.
   The default layout is the JSON tools' own.
5. **An edit names the revision it was made against.** `set_text()` and `set_tree()` take the
   revision the editor last saw. An edit against an older one raises `StaleRevisionError` and
   changes nothing. Nothing is merged.
6. **As strict as the JSON tools, and quiet.** `parse_json()` refuses what they refuse and logs
   nothing, since an editor asks on every keystroke.
7. **No widget in it.** It lives in `utils/` and both editors reach it through the same calls.

## Alternatives considered

- **Two models kept in step by signals.** This is the drift the roadmap warns of: an edit arriving
  while the other side is mid-change has no defined outcome.
- **The tree as the truth, the text generated from it.** Half-typed text has no tree, so typing in
  the text view would either be blocked or lost.
- **A syntax tree that keeps every space and line break.** A visual edit would then leave hand
  layout untouched. It also needs a node type for each kind of whitespace and makes every edit
  operation larger. Not ruled out for later; not needed to make the two views safe.
- **Python `int` and `float` for numbers.** `1.0` comes back as whatever the writer makes of it
  and `1e400` as `Infinity`, which is not JSON. The formatter was changed away from this for the
  same reason.
- **Last writer wins.** No conflict to handle, and an edit silently gone.

## Consequences

- While the text does not parse, the visual editor has nothing to edit. It shows the problem and
  waits.
- A visual edit writes the whole text again in the document's layout, so hand alignment and blank
  lines in the file are lost at the first such edit. Reading a file's own indent into the options
  when it is opened is the editor's part, in Phase 5.
- Each tree edit serialises and parses the whole document. That is what keeps the two faces from
  ever disagreeing, and it is proportional to the file: fine for action files, to be measured
  before it is used on files of megabytes.
- Inserting, deleting, reordering and renaming nodes, undo and the unsaved mark are not here. They
  come with the editor, on top of `set_tree()`.
- `json_process._Numbers` became the public `HeldNumbers`: the document writes numbers back through
  the same holder as the formatter.
