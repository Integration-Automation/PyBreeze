# docs/updates: update log index

`progress.md` holds only work that is **not done yet**. Everything that *was* done (what changed, measured numbers, decisions, snapshots) is recorded here: **one batch file per month**, one entry per piece of work, each entry with a fixed-format ID and tags, and one row per entry in the index below.

> No TODOs here. If an entry mentions something still open, it only points to it (e.g. "open item: `progress.md` #3"); the item itself lives in `progress.md`.

## How to query

Run from the repository root:

| To find | Command |
|---|---|
| every entry, one line each | `rg -n "^## U-2" docs/updates` |
| entries of one type | `rg -n "^## U-2.*#done" docs/updates` |
| entries with a topic tag | `rg -n "^## U-2.*#<tag>" docs/updates` |
| one day or one month | `rg -n "^## U-202609" docs/updates` |
| the full text of one entry | `rg -n -A 60 "^## U-20260922-01" docs/updates` |
| any keyword | `rg -n "keyword" docs/updates` |

Without `rg`: `git grep -n "^## U-2" -- docs/updates`, or in PowerShell `Select-String -Path docs/updates/*.md -Pattern '^## U-2'`.

## Entry format

```markdown
## U-YYYYMMDD-NN · YYYY-MM-DD · one-line title · #type #topic

- **What**: ...
- **Result / numbers**: ...
- **Files**: `path` ...
- **Evidence**: commit, file:line, link ...
- **Open items**: none / see `progress.md` ...
```

- **ID**: `U-` + date + two-digit sequence for that day. IDs are never renumbered or reused, so code comments and other documents can cite them.
- **Type tag** (exactly one): `#done` finished `progress.md` item, `#snapshot` measurement or inventory, `#decision`, `#incident`, `#migration`, `#docs`, `#release`.
- Topic tags are free-form (`#mcp`, `#wayland`, ...).
- Keep conclusions, numbers, files and evidence; drop the reasoning trail and dead ends.

## Batch rules

1. One file per month: `docs/updates/YYYY-MM.md`. Append new entries at the end.
2. Over about 800 lines, continue in `YYYY-MM-b.md` (then `-c`) and list it in the batch table below.
3. **Claim the ID under a lock.** Several sessions may write this log at the same time (for example parallel autonomous runs), and without a lock two of them pick the same number:
   1. `mkdir docs/updates/.id-lock`. Creating a directory is atomic, so only one writer succeeds. If it already exists, someone else is claiming: wait a few seconds and retry. A lock older than 10 minutes is stale and may be removed.
   2. Find the day's last number with `rg -n "^## U-YYYYMMDD" docs/updates` and write the heading line and the index row.
   3. `rmdir docs/updates/.id-lock`, then fill in the body. Git never tracks the empty lock directory.
   4. Before committing, `rg -c "^## U-<your ID>" docs/updates` must report one match in total. If not, renumber your entry under the lock and fix its index row. Whoever merges a branch renumbers entries that reuse an ID.
4. **One line per index row**: title only (about 60 characters), no summary.
5. Never rewrite a recorded entry. Correct it with a new `#decision` or `#incident` entry and add "→ corrected in U-..." to the old one.

## When a `progress.md` item is done

In the same commit: delete the item from `progress.md`, add a `#done` entry here that names it, and add its index row.

---

## Index (newest first)

| ID | Date | Title | Tags | Batch |
|---|---|---|---|---|
| U-20260923-17 | 2026-09-23 | Run windows were kept for the whole session | #done #process-executor | [2026-09](2026-09.md) |
| U-20260923-16 | 2026-09-23 | A diagram fetched its images again on every undo | #done #diagram | [2026-09](2026-09.md) |
| U-20260923-15 | 2026-09-23 | The AI review request froze the IDE while it waited | #done #ai | [2026-09](2026-09.md) |
| U-20260923-14 | 2026-09-23 | Closing an SSH tab left its thread and session running | #incident #ssh | [2026-09](2026-09.md) |
| U-20260923-13 | 2026-09-23 | Four findings from reviewing the day's work | #incident #review | [2026-09](2026-09.md) |
| U-20260923-12 | 2026-09-23 | The AI review panel kept API URLs, tokens and all | #incident #security | [2026-09](2026-09.md) |
| U-20260923-11 | 2026-09-23 | Image sources, undo scopes and stacking order | #done #diagram | [2026-09](2026-09.md) |
| U-20260923-10 | 2026-09-23 | A diagram that failed to load took the open one with it | #incident #diagram | [2026-09](2026-09.md) |
| U-20260923-09 | 2026-09-23 | A run with no script tab handed the package nothing | #incident #process-executor | [2026-09](2026-09.md) |
| U-20260923-08 | 2026-09-23 | Install did nothing without an editor tab in front | #incident #install | [2026-09](2026-09.md) |
| U-20260923-07 | 2026-09-23 | A plugin run that read input hung for good | #incident #process-executor | [2026-09](2026-09.md) |
| U-20260923-06 | 2026-09-23 | Runs outlived the IDE | #incident #process-executor | [2026-09](2026-09.md) |
| U-20260923-05 | 2026-09-23 | parse_mermaid back under the cognitive complexity cap | #done #refactor #diagram | [2026-09](2026-09.md) |
| U-20260923-04 | 2026-09-23 | DiagramNode takes its style as one NodeStyle | #done #refactor #diagram | [2026-09](2026-09.md) |
| U-20260923-03 | 2026-09-23 | Automation menus described by one AutomationMenu | #done #refactor #menus | [2026-09](2026-09.md) |
| U-20260923-02 | 2026-09-23 | prthinker ignored the model name for seven backends | #incident #prthinker | [2026-09](2026-09.md) |
| U-20260923-01 | 2026-09-23 | First real prthinker review run from PyBreeze | #done #prthinker | [2026-09](2026-09.md) |
| U-20260922-18 | 2026-09-22 | Run windows lost their output and exit line | #incident #process-executor | [2026-09](2026-09.md) |
| U-20260922-17 | 2026-09-22 | Automation submenus came up empty | #incident #menus | [2026-09](2026-09.md) |
| U-20260922-16 | 2026-09-22 | Contract test for the prthinker command line | #done #prthinker #ci | [2026-09](2026-09.md) |
| U-20260922-15 | 2026-09-22 | Dependency audit of what CI installs | #snapshot #dependencies | [2026-09](2026-09.md) |
| U-20260922-14 | 2026-09-22 | Extra prthinker arguments lost their Windows backslashes | #incident #prthinker | [2026-09](2026-09.md) |
| U-20260922-13 | 2026-09-22 | Write down and test what PyBreeze takes from JEditor | #done #jeditor | [2026-09](2026-09.md) |
| U-20260922-12 | 2026-09-22 | Run with rewrote the file in UTF-8 and CRLF | #incident #plugins | [2026-09](2026-09.md) |
| U-20260922-11 | 2026-09-22 | IDE crashed on start with a non-English language saved | #done #i18n | [2026-09](2026-09.md) |
| U-20260922-10 | 2026-09-22 | Pin PySide6 6.11.1 like the published je_editor | #done #dependencies | [2026-09](2026-09.md) |
| U-20260922-09 | 2026-09-22 | Describe the release flow CI actually runs | #done #ci | [2026-09](2026-09.md) |
| U-20260922-08 | 2026-09-22 | PLUGIN_GUIDE.md points to JEditor's guide | #done #docs | [2026-09](2026-09.md) |
| U-20260922-07 | 2026-09-22 | Install the checkout, not the published build | #done #dependencies | [2026-09](2026-09.md) |
| U-20260922-06 | 2026-09-22 | Run window follows its output | #incident #process-executor | [2026-09](2026-09.md) |
| U-20260922-05 | 2026-09-22 | One output pipeline for every run window | #done #process-executor | [2026-09](2026-09.md) |
| U-20260922-04 | 2026-09-22 | Run window keeps the output's indentation | #done #process-executor | [2026-09](2026-09.md) |
| U-20260922-03 | 2026-09-22 | Point project URLs at the current repository | #done #metadata | [2026-09](2026-09.md) |
| U-20260922-02 | 2026-09-22 | Run windows ignored the interpreter chosen in the IDE | #incident #process-executor | [2026-09](2026-09.md) |
| U-20260922-01 | 2026-09-22 | Adopt progress/architecture/docs-updates rules | #docs #migration | [2026-09](2026-09.md) |

## Batches

| File | Period | Entries |
|---|---|---:|
| [2026-09.md](2026-09.md) | 2026-09 | 35 |
