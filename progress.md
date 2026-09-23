# progress.md: PyBreeze

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: X-1, X-13, X-17).

## Open

- **#2** [DECIDE] Closing one run window leaves its child running, with no window and no way to stop it short of a task manager; only closing the whole IDE stops it (`PyBreezeMainWindow.closeEvent`, `pybreeze/pybreeze_ui/editor_main/main_ui.py`). Should closing a run window stop its run (`CodeWindow.stop_runner()` exists; `CodeWindow.closeEvent` today only lets the main window forget a finished one), ask first, or keep going on purpose (for example a long load test that mails its report)?
- **#27** [DECIDE] paramiko is not pinned (`requirements.txt`, `pyproject.toml`, `dev.toml`), so an install may get 4.x, which still has CVE-2026-44405 (SHA-1 RSA signatures). The code refuses SHA-1 on every connect whatever the version (`SHA1_ALGORITHMS`, U-20260923-40), and the SSH tests pass on 5.0.0. Should the dependency say `paramiko>=5.0.0`, or be pinned exactly like PySide6?
- **#44** File tree Delete (`editor_main/file_tree_context_menu.py:451-463`) closes the file's tabs, bypassing JEditor's unsaved-changes prompt, before the delete runs; when `unlink`/`rmtree` then fails (a locked or read-only file), the file stays but its tab and unsaved edits are gone.
- **#46** `PyBreezeMainWindow.closeEvent` (`editor_main/main_ui.py:103-122`) closes run windows, tool tabs and docks unguarded before `super().closeEvent`; one widget whose close raises stops JEditor's own close (open files, settings, auto-save threads).
- **#47** [DECIDE] `PyBreezeMainWindow.closeEvent` closes every `DestroyDock` (`editor_main/main_ui.py:121`), which includes JEditor's docked file editors; their `closeEvent` writes the buffer back, so exiting saves unsaved dock edits without asking and rewrites an LF file with CRLF. Should docked editors be skipped (JEditor alone never saved them on exit), or asked about?
- **#48** Install prthinker (`menu/install_menu/automation_menu/build_automation_install_menu.py:105-120`) calls the static `getExistingDirectory` through an instance, so the dialog has no parent, and saves any existing folder as prthinker's source before pip runs, with no check that it is one.
