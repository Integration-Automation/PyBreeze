# progress.md: PyBreeze

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: X-1, X-13, X-17).

## Open

- **#2** [DECIDE] Closing one run window leaves its child running, with no window and no way to stop it short of a task manager; only closing the whole IDE stops it (`PyBreezeMainWindow.closeEvent`, `pybreeze/pybreeze_ui/editor_main/main_ui.py`). Should closing a run window stop its run (`CodeWindow.stop_runner()` already exists), ask first, or keep going on purpose (for example a long load test that mails its report)? `CodeWindow` has no `closeEvent` today.
- **#10** SSH connecting and directory listing still run on the UI thread (`ssh_command_widget.py`, `ssh_file_viewer_widget.py`): `connect()` is bounded only by paramiko's own timeouts (banner 15 s, auth 30 s) and `listdir_attr()` by nothing at all, so an unresponsive host or a directory with tens of thousands of entries freezes the IDE. Transfers moved off it in U-20260923-19; moving `connect()` has to route the host-key prompt (`ssh_host_key_policy.apply_host_key_policy`, a modal box inside `SSHClient.connect`) back through a signal.

