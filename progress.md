# progress.md: PyBreeze

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: X-1, X-13, X-17).

## Open

- **#2** [DECIDE] Closing one run window leaves its child running, with no window and no way to stop it short of a task manager; only closing the whole IDE stops it (`PyBreezeMainWindow.closeEvent`, `pybreeze/pybreeze_ui/editor_main/main_ui.py`). Should closing a run window stop its run (`CodeWindow.stop_runner()` exists; `CodeWindow.closeEvent` today only lets the main window forget a finished one), ask first, or keep going on purpose (for example a long load test that mails its report)?
- **#27** [DECIDE] paramiko is not pinned (`requirements.txt`, `pyproject.toml`, `dev.toml`), so an install may get 4.x, which still has CVE-2026-44405 (SHA-1 RSA signatures). The code refuses SHA-1 on every connect whatever the version (`SHA1_ALGORITHMS`, U-20260923-40), and the SSH tests pass on 5.0.0. Should the dependency say `paramiko>=5.0.0`, or be pinned exactly like PySide6?
- **#32** curl/HAR import fidelity: repeated query keys keep only one value (`curl_parser._split_url_query`, `_finalise_method`, `har_parser._apply_query` store a dict); bash `$'...'` quoting from browsers' Copy as cURL is not understood (`curl_parser._tokenize`); a HAR multipart text value starting with `@` becomes a file upload (`har_parser._multipart_fields`); a HAR file with a UTF-8 BOM is rejected (`har_import_gui.open_file`); `--max-time nan` generates `timeout=nan` (`curl_parser._apply_timeout`).
- **#34** Minor tool output errors: `query_convert.json_to_query` turns `null` into `None` and a nested object into its Python repr; the response inspector keeps only the last `Set-Cookie` header (`response_analyzer.py:80`); `url_to_json` drops an out-of-range port silently.
