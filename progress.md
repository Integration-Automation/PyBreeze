# progress.md: PyBreeze

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: X-1, X-13, X-17).

## Open

- **#2** [DECIDE] Closing one run window leaves its child running, with no window and no way to stop it short of a task manager; only closing the whole IDE stops it (`PyBreezeMainWindow.closeEvent`, `pybreeze/pybreeze_ui/editor_main/main_ui.py`). Should closing a run window stop its run (`CodeWindow.stop_runner()` exists; `CodeWindow.closeEvent` today only lets the main window forget a finished one), ask first, or keep going on purpose (for example a long load test that mails its report)?
- **#10** SSH directory listing still runs on the UI thread (`ssh_file_viewer_widget.py` `populate_children`, from `load_root`, `on_item_expanded` and `action_refresh`): `listdir_attr()` has no timeout, so a directory with tens of thousands of entries or a stalled server freezes the IDE. Connecting moved off it in U-20260923-33, transfers in U-20260923-19. A listing that runs on a thread has to find its tree item again when it returns, because `load_root`, a refresh or a disconnect may have cleared the tree in the meantime.

