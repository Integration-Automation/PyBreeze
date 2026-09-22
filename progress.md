# progress.md: PyBreeze

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: X-1, X-13, X-17).

## Open

- **#2** [DECIDE] Closing one run window leaves its child running, with no window and no way to stop it short of a task manager; only closing the whole IDE stops it (`PyBreezeMainWindow.closeEvent`, `pybreeze/pybreeze_ui/editor_main/main_ui.py`). Should closing a run window stop its run (`CodeWindow.stop_runner()` already exists), ask first, or keep going on purpose (for example a long load test that mails its report)? `CodeWindow` has no `closeEvent` today.
- **#3** [UNVERIFIED] One unit test failed once, in a full run of `test/test_utils/` that took 282 s instead of the usual 35–60 s while the machine was busy; its name was not captured. Nine later full runs passed, three of them in parallel. Candidates are the tests that wait on a clock: `test_run_output.py` (30 s per child), `started_window.py` (120 s per IDE start). Record the name if it happens again.
- **#4** An image source from a saved diagram reaches `Path.is_file()` before its extension is checked (`pybreeze/pybreeze_ui/diagram_editor/diagram_scene.py:_try_load_image_source`). On Windows a UNC source (`\\host\share\x.png`) makes the SMB client authenticate to that host; an unreachable one also blocks the UI thread for the SMB timeout. Check the suffix first, refuse UNC and resolve the rest.
- **#5** A diagram's image downloads run on the UI thread (`_try_load_image_source` -> `safe_download_image`, 15 s each) and the pixmap is not part of the undo snapshot, so every undo and redo re-fetches every URL image: three unreachable ones freeze the IDE for ~45 s per Ctrl+Z, and an image whose host is offline silently blanks on an unrelated undo. Cache the pixmap on the item and fetch off the UI thread.
- **#6** `DiagramScene.undo_scope` has no `try/finally` (`diagram_scene.py`), so an exception inside a scope (the Mermaid import catches one a frame up) leaves `_pending_undo_snapshot` set; the next `mouseReleaseEvent` calls `end_undo()` with no matching `begin_undo` and pushes a command that undoes far more than the gesture.
- **#7** Node z-order is neither serialised (`DiagramNode.to_dict`) nor undoable (`DiagramScene._change_z` runs outside `undo_scope`), so "Bring to Front" is lost on save and reset by any unrelated undo.
