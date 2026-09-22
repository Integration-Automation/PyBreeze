# progress.md: PyBreeze

Outstanding work only. When an item is done, delete it in the same commit and add a `#done` entry to `docs/updates/` (format and query commands: `docs/updates/README.md`). No finished items, no history, no rules (rules live in `CLAUDE.md`).
Item numbers (`#n`) are never reused. Tags: [DECIDE] needs the owner's decision, [BLOCKED] waits on something else, [UNVERIFIED] observed but not confirmed.
Cross-repo and workspace items live in `D:\Codes\progress.md` (relevant here: X-1, X-8, X-11, X-13, X-17).

## Open

- **#1** [BLOCKED] The prthinker integration (menu, settings, install; commit `99ef96f`) has never run a real review: this machine's PyBreeze venv is Python 3.11 and prthinker needs 3.12 or newer. Install prthinker with a 3.12+ interpreter and run one review (moved from JEditor's `PROGRESS.md`; workspace X-8).
- **#2** The run window strips indentation from program output: `.strip()` in `pybreeze/extend/process_executor/queue_pump.py:36` and `file_runner_process.py:150` (`architecture_explore.md` ≈:428).
- **#3** `_append_text` is duplicated verbatim in three places, and the TestPioneer runner raises out when no interpreter is found (`architecture_explore.md` ≈:426, ≈:438).
- **#4** `requirements.txt` lists `pybreeze` itself and `dev_requirements.txt` lists `pybreeze_dev`, so CI installs the PyPI build instead of the checkout. FrontEngine fixed the same problem (see the header comment of its `requirements.txt`).
- **#5** `CLAUDE.md` "Branching & CI" says `dev` publishes `pybreeze_dev`, but `dev.yml` has no publish job and `dev.toml` is not kept in step (workspace X-13).
- **#6** [UNVERIFIED] With Traditional Chinese selected at startup, PyBreeze's labels may be missing until the language is switched once: JEditor builds the merged dictionary before PyBreeze adds its strings to JEditor's word dicts (found by reading the code, not by running it).
- **#7** PySide6 is pinned `==6.11.0` while je_editor and frontengine pin `==6.11.1`, so the latest releases cannot be installed together (workspace X-1).
- **#8** PyBreeze imports JEditor modules that je_editor does not export (`PluginBrowserWidget`, `DestroyDock`, `check_and_choose_venv`, `choose_file_get_save_file_path`, `write_file`, `actually_color_dict`) and edits JEditor's `english_word_dict` / `traditional_chinese_word_dict` in place — an undocumented contract (workspace X-17).
- **#9** Package metadata and README clone instructions still point to `Intergration-Automation-Testing/AutomationEditor` (workspace X-11).
