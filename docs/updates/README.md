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
| U-20260925-12 | 2026-09-25 | AI Code Review sends the code by default | #fix #ai #readme | [2026-09-c](2026-09-c.md) |
| U-20260925-11 | 2026-09-25 | AI panels no longer suggest an endpoint they refuse | #fix #ai #readme | [2026-09-c](2026-09-c.md) |
| U-20260925-10 | 2026-09-25 | JWT, Query and URL tools in the fixed-pitch font | #fix #tools #ui | [2026-09-c](2026-09-c.md) |
| U-20260925-09 | 2026-09-25 | No private address in the SSH host placeholder | #fix #ssh #i18n | [2026-09-c](2026-09-c.md) |
| U-20260925-08 | 2026-09-25 | Say what to do with a PuTTY key instead of offering it | #fix #ssh #i18n #readme | [2026-09-c](2026-09-c.md) |
| U-20260925-07 | 2026-09-25 | SSH and SFTP log in with a PKCS#8 private key | #feature #ssh | [2026-09-c](2026-09-c.md) |
| U-20260925-06 | 2026-09-25 | The Mermaid paste box in the fixed-pitch font | #fix #diagram #ui | [2026-09-c](2026-09-c.md) |
| U-20260925-05 | 2026-09-25 | Free the diagram editor's Mermaid import dialog | #fix #diagram | [2026-09-c](2026-09-c.md) |
| U-20260925-04 | 2026-09-25 | The project tree's menu opens where it was asked for | #fix #ui | [2026-09-c](2026-09-c.md) |
| U-20260925-03 | 2026-09-25 | Free the project and SFTP trees' right-click menus | #fix #ui #ssh | [2026-09-c](2026-09-c.md) |
| U-20260925-02 | 2026-09-25 | Full-width punctuation in the Traditional Chinese strings | #fix #i18n | [2026-09-c](2026-09-c.md) |
| U-20260925-01 | 2026-09-25 | Start the 2026-09-c batch | #docs | [2026-09-c](2026-09-c.md) |
| U-20260924-320 | 2026-09-24 | Help, not HELP, in the automation menus | #fix #i18n | [2026-09-b](2026-09-b.md) |
| U-20260924-319 | 2026-09-24 | Drop the ReEdgeGPT words no menu asks for | #cleanup #i18n | [2026-09-b](2026-09-b.md) |
| U-20260924-318 | 2026-09-24 | Say that the SSH terminal is line by line | #docs #ssh #readme | [2026-09-b](2026-09-b.md) |
| U-20260924-317 | 2026-09-24 | Say what the CoT review's step selector is | #fix #ai | [2026-09-b](2026-09-b.md) |
| U-20260924-316 | 2026-09-24 | Reword the Traditional Chinese Open in editor tab button | #fix #i18n | [2026-09-b](2026-09-b.md) |
| U-20260924-315 | 2026-09-24 | Tell apart labels that read the same | #fix #i18n | [2026-09-b](2026-09-b.md) |
| U-20260924-314 | 2026-09-24 | Code in the tool tabs in the fixed-pitch font | #feature #tools #readme | [2026-09-b](2026-09-b.md) |
| U-20260924-313 | 2026-09-24 | Consolas before Courier New for terminal output | #fix #ui | [2026-09-b](2026-09-b.md) |
| U-20260924-312 | 2026-09-24 | Move the fixed-pitch font helper out of terminal_view | #refactor #ui | [2026-09-b](2026-09-b.md) |
| U-20260924-311 | 2026-09-24 | Remove the images nothing shows | #docs #cleanup | [2026-09-b](2026-09-b.md) |
| U-20260924-310 | 2026-09-24 | Redo the README's main window and correct its caption | #docs #readme | [2026-09-b](2026-09-b.md) |
| U-20260924-309 | 2026-09-24 | Keep library debug records out of Code Result | #fix #editor #logging | [2026-09-b](2026-09-b.md) |
| U-20260924-308 | 2026-09-24 | The cURL import button names the chosen target | #fix #tools #readme | [2026-09-b](2026-09-b.md) |
| U-20260924-307 | 2026-09-24 | Redo the README screenshots of the AI tabs | #docs #readme | [2026-09-b](2026-09-b.md) |
| U-20260924-306 | 2026-09-24 | Record the gitpython floor question as progress #109 | #docs #deps #security | [2026-09-b](2026-09-b.md) |
| U-20260924-305 | 2026-09-24 | Taiwan terms for Help and template in the Traditional Chinese IDE | #fix #i18n | [2026-09-b](2026-09-b.md) |
| U-20260924-304 | 2026-09-24 | A HELP submenu for TestPioneer | #feature #menu | [2026-09-b](2026-09-b.md) |
| U-20260924-303 | 2026-09-24 | Make the automation menus' HELP builder public | #refactor #menu | [2026-09-b](2026-09-b.md) |
| U-20260924-302 | 2026-09-24 | Install TestPioneer from the Install menu | #feature #menu | [2026-09-b](2026-09-b.md) |
| U-20260924-301 | 2026-09-24 | Build the automation Install menu from a table | #refactor #menu | [2026-09-b](2026-09-b.md) |
| U-20260924-300 | 2026-09-24 | Correction to U-20260924-295: the keyword colours are not shown yet | #docs #jeditor | [2026-09-b](2026-09-b.md) |
| U-20260924-299 | 2026-09-24 | clear and reset wipe the SSH terminal | #fix #ssh | [2026-09-b](2026-09-b.md) |
| U-20260924-298 | 2026-09-24 | Arrow labels in the README's tool screenshots | #docs | [2026-09-b](2026-09-b.md) |
| U-20260924-297 | 2026-09-24 | README screenshots of the SSH tab, the run window and the diagram editor redone | #docs | [2026-09-b](2026-09-b.md) |
| U-20260924-296 | 2026-09-24 | The diff tool shows its diff in colour | #feature #ui | [2026-09-b](2026-09-b.md) |
| U-20260924-295 | 2026-09-24 | Automation keywords readable on a light theme | #fix #ui #jeditor | [2026-09-b](2026-09-b.md) |
| U-20260924-294 | 2026-09-24 | The terminal font holds under the IDE's theme | #fix #ssh #ui | [2026-09-b](2026-09-b.md) |
| U-20260924-293 | 2026-09-24 | Terminal colours readable on a dark and on a light theme | #fix #ssh #ui | [2026-09-b](2026-09-b.md) |
| U-20260924-292 | 2026-09-24 | Colours in the SSH terminal | #feature #ssh #ui | [2026-09-b](2026-09-b.md) |
| U-20260924-291 | 2026-09-24 | The SSH shell's pty follows the terminal's size | #feature #ssh | [2026-09-b](2026-09-b.md) |
| U-20260924-290 | 2026-09-24 | Terminal output in a fixed-pitch font | #fix #ssh #ui | [2026-09-b](2026-09-b.md) |
| U-20260924-289 | 2026-09-24 | A progress bar in the SSH terminal redraws its line | #fix #ssh | [2026-09-b](2026-09-b.md) |
| U-20260924-288 | 2026-09-24 | Refactor: the run window's line rewinding in a shared module | #refactor | [2026-09-b](2026-09-b.md) |
| U-20260924-287 | 2026-09-24 | Command history on the SSH command line | #feature #ssh | [2026-09-b](2026-09-b.md) |
| U-20260924-286 | 2026-09-24 | Interrupt what runs in the SSH shell | #feature #ssh #i18n | [2026-09-b](2026-09-b.md) |
| U-20260924-285 | 2026-09-24 | Enter on an empty SSH command line sends Enter | #fix #ssh | [2026-09-b](2026-09-b.md) |
| U-20260924-284 | 2026-09-24 | Taiwan terms in the Traditional Chinese interface | #fix #i18n | [2026-09-b](2026-09-b.md) |
| U-20260924-283 | 2026-09-24 | architecture_explore.md coverage figures re-measured | #docs #test | [2026-09-b](2026-09-b.md) |
| U-20260924-282 | 2026-09-24 | A right-drag on the diagram canvas pans without opening the menu | #fix #diagram | [2026-09-b](2026-09-b.md) |
| U-20260924-281 | 2026-09-24 | architecture_explore.md line counts re-measured | #docs | [2026-09-b](2026-09-b.md) |
| U-20260924-280 | 2026-09-24 | curl -b '' reads no cookie file | #fix #curl | [2026-09-b](2026-09-b.md) |
| U-20260924-279 | 2026-09-24 | A new diagram node's text in the IDE language | #fix #i18n #diagram | [2026-09-b](2026-09-b.md) |
| U-20260924-278 | 2026-09-24 | Tests for the property panel on a connection and an image | #test #diagram | [2026-09-b](2026-09-b.md) |
| U-20260924-277 | 2026-09-24 | Tests for the diagram editor's align and distribute | #test #diagram | [2026-09-b](2026-09-b.md) |
| U-20260924-276 | 2026-09-24 | Check the trimmed diff against the plain one only on small texts | #fix #diff #perf | [2026-09-b](2026-09-b.md) |
| U-20260924-275 | 2026-09-24 | The Traditional and Simplified Chinese READMEs follow README.md again | #docs #readme | [2026-09-b](2026-09-b.md) |
| U-20260924-274 | 2026-09-24 | The exit-code line and the held-output note in the IDE language too | #fix #i18n #run-window | [2026-09-b](2026-09-b.md) |
| U-20260924-273 | 2026-09-24 | Why a report mail was not sent, in the IDE language | #fix #i18n #mail | [2026-09-b](2026-09-b.md) |
| U-20260924-272 | 2026-09-24 | Refactor: the reasons a report mail was not sent come from exception_tags | #refactor #i18n #mail | [2026-09-b](2026-09-b.md) |
| U-20260924-271 | 2026-09-24 | A run window's own notices in the IDE language | #fix #i18n #run-window | [2026-09-b](2026-09-b.md) |
| U-20260924-270 | 2026-09-24 | Report a deeply nested regex instead of crashing on CPython 3.10 | #fix #regex | [2026-09-b](2026-09-b.md) |
| U-20260924-269 | 2026-09-24 | Adopt je_editor 1.0.27 docked-editor contract | #done #cross-project | [2026-09-b](2026-09-b.md) |
| U-20260924-268 | 2026-09-24 | A file that is not a diagram, and a refused CoT URL, say why in the IDE language | #fix #i18n #diagram #ai | [2026-09-b](2026-09-b.md) |
| U-20260924-267 | 2026-09-24 | Refactor: the diagram file checks raise from exception_tags | #refactor #i18n #diagram | [2026-09-b](2026-09-b.md) |
| U-20260924-266 | 2026-09-24 | A test that no tool tab shows a reason as it was raised | #test #i18n | [2026-09-b](2026-09-b.md) |
| U-20260924-265 | 2026-09-24 | The SFTP tree says a host key was declined in the IDE language | #done #fix #ssh #i18n | [2026-09-b](2026-09-b.md) |
| U-20260924-264 | 2026-09-24 | A diff never changes more lines than difflib's own | #fix #diff | [2026-09-b](2026-09-b.md) |
| U-20260924-263 | 2026-09-24 | An SFTP transfer can be cancelled | #feature #ssh #ui | [2026-09-b](2026-09-b.md) |
| U-20260924-262 | 2026-09-24 | The SFTP context menu dispatches from a table | #refactor #ssh | [2026-09-b](2026-09-b.md) |
| U-20260924-261 | 2026-09-24 | A Stop button in the run window | #feature #run #ui | [2026-09-b](2026-09-b.md) |
| U-20260924-260 | 2026-09-24 | The SFTP menu opens with exec, not the deprecated exec_ | #cleanup #ssh #qt | [2026-09-b](2026-09-b.md) |
| U-20260924-259 | 2026-09-24 | Network, image, host-key and Skills reasons in the IDE language | #fix #i18n #network | [2026-09-b](2026-09-b.md) |
| U-20260924-258 | 2026-09-24 | Refactor: the network, image, host-key and Skills messages become exception_tags constants | #refactor #i18n | [2026-09-b](2026-09-b.md) |
| U-20260924-257 | 2026-09-24 | Drop TaskProcessManager's unused error hook | #cleanup #executor | [2026-09-b](2026-09-b.md) |
| U-20260924-256 | 2026-09-24 | A HAR file that is not one says why in the IDE language too | #fix #tools #i18n | [2026-09-b](2026-09-b.md) |
| U-20260924-255 | 2026-09-24 | A plugin run config's args given as a string is one argument | #fix #plugins #run | [2026-09-b](2026-09-b.md) |
| U-20260924-254 | 2026-09-24 | Why a tool refused its input, in the IDE language | #fix #tools #i18n | [2026-09-b](2026-09-b.md) |
| U-20260924-253 | 2026-09-24 | The AI review panel lists its methods from one place | #refactor #ai | [2026-09-b](2026-09-b.md) |
| U-20260924-252 | 2026-09-24 | Reveal in file explorer shows a file selected, and says when it cannot | #fix #editor #ui | [2026-09-b](2026-09-b.md) |
| U-20260924-251 | 2026-09-24 | Enter in the regex pattern runs it | #feature #tools #ui | [2026-09-b](2026-09-b.md) |
| U-20260924-250 | 2026-09-24 | SSH login: Enter connects, and the key file can be browsed for | #feature #ssh #ui | [2026-09-b](2026-09-b.md) |
| U-20260924-249 | 2026-09-24 | Say why an SFTP folder was not deleted | #fix #ssh #ui | [2026-09-b](2026-09-b.md) |
| U-20260924-248 | 2026-09-24 | SFTP Rename starts from the current name | #fix #ssh #ui | [2026-09-b](2026-09-b.md) |
| U-20260924-247 | 2026-09-24 | The SFTP tree's Type column in the IDE language | #fix #ssh #i18n | [2026-09-b](2026-09-b.md) |
| U-20260924-246 | 2026-09-24 | The SFTP tree tells folders from files by item data, not by its Type column | #refactor #ssh | [2026-09-b](2026-09-b.md) |
| U-20260924-245 | 2026-09-24 | Remove the SFTP tree's event filter nothing installs | #cleanup #ssh | [2026-09-b](2026-09-b.md) |
| U-20260924-244 | 2026-09-24 | A link to a folder opens as a folder in the SFTP tree | #fix #ssh | [2026-09-b](2026-09-b.md) |
| U-20260924-243 | 2026-09-24 | Multi-script menu entries read as Chinese, without a word twice | #fix #i18n | [2026-09-b](2026-09-b.md) |
| U-20260924-242 | 2026-09-24 | The CoT review's last English words in Traditional Chinese | #fix #ai #i18n | [2026-09-b](2026-09-b.md) |
| U-20260924-241 | 2026-09-24 | Drop five translations nothing shows | #cleanup #i18n | [2026-09-b](2026-09-b.md) |
| U-20260924-240 | 2026-09-24 | A Save As button in the diagram editor | #fix #diagram #ui | [2026-09-b](2026-09-b.md) |
| U-20260924-239 | 2026-09-24 | Why JupyterLab did not start, in the IDE language | #fix #jupyter #i18n | [2026-09-b](2026-09-b.md) |
| U-20260924-238 | 2026-09-24 | The SSH shell's connect line in the IDE language, and its status Connected | #fix #ssh #i18n | [2026-09-b](2026-09-b.md) |
| U-20260924-237 | 2026-09-24 | SFTP tree speaks the IDE language, and an entry named ... is not its placeholder | #fix #ssh #i18n | [2026-09-b](2026-09-b.md) |
| U-20260923-236 | 2026-09-24 | Apply backspaces in one pass, so a long rub-out does not hold the UI | #fix #output #perf | [2026-09-b](2026-09-b.md) |
| U-20260923-235 | 2026-09-24 | Skip a HAR entry holding half a character instead of failing the whole file | #fix #har | [2026-09-b](2026-09-b.md) |
| U-20260923-234 | 2026-09-24 | Never write a known_hosts file over when it cannot be read, and keep its bytes | #fix #ssh | [2026-09-b](2026-09-b.md) |
| U-20260923-233 | 2026-09-24 | Round a long decimal epoch down inside the decimal arithmetic too | #fix #timestamp | [2026-09-b](2026-09-b.md) |
| U-20260923-232 | 2026-09-24 | Call an encrypted SSH key of a type paramiko cannot load unsupported, not its passphrase wrong | #fix #ssh | [2026-09-b](2026-09-b.md) |
| U-20260923-231 | 2026-09-24 | Generate the HAR script again when going back from a target that could not carry it | #fix #har | [2026-09-b](2026-09-b.md) |
| U-20260923-230 | 2026-09-24 | Keep difflib's junk heuristic on for what is left after trimming, so a repetitive diff stays quick | #fix #diff #perf | [2026-09-b](2026-09-b.md) |
| U-20260923-229 | 2026-09-24 | Run with the IDE's own interpreter when no venv is found, not whatever python3 is on PATH | #fix #executor | [2026-09-b](2026-09-b.md) |
| U-20260923-228 | 2026-09-24 | Give pip the prthinker source folder as a path, not a name | #fix #prthinker | [2026-09-b](2026-09-b.md) |
| U-20260923-227 | 2026-09-24 | Leave a redirect's body and Location unread in the AI panels and the image download | #fix #network #security | [2026-09-b](2026-09-b.md) |
| U-20260923-226 | 2026-09-24 | Scale a diagram image from the image as loaded, so resizing does not blur it | #fix #diagram | [2026-09-b](2026-09-b.md) |
| U-20260923-225 | 2026-09-24 | Draw the canvas where it is when the diagram is exported | #fix #diagram | [2026-09-b](2026-09-b.md) |
| U-20260923-224 | 2026-09-24 | Hand -b cookies to the header analyzer as the Cookie header curl sends | #fix #curl | [2026-09-b](2026-09-b.md) |
| U-20260923-223 | 2026-09-24 | Percent-encode what a text box would change when the URL Builder builds a URL | #fix #url | [2026-09-b](2026-09-b.md) |
| U-20260923-222 | 2026-09-24 | Show a plugin's suffixes in the Run with box as text, and check every box by what it is assigned to | #fix #qt #plugin | [2026-09-b](2026-09-b.md) |
| U-20260923-221 | 2026-09-24 | Keep the HAR tab's output the script of the file and target shown | #fix #har | [2026-09-b](2026-09-b.md) |
| U-20260923-220 | 2026-09-24 | Let a backspace take back what an earlier read showed | #fix #output #done | [2026-09-b](2026-09-b.md) |
| U-20260923-219 | 2026-09-24 | Keep a carriage return split from what follows it in the run window and the SSH terminal | #fix #output | [2026-09-b](2026-09-b.md) |
| U-20260923-218 | 2026-09-24 | Skip a bad known_hosts line instead of failing the SSH connect | #fix #ssh | [2026-09-b](2026-09-b.md) |
| U-20260923-217 | 2026-09-24 | Say when an SSH key's passphrase is missing or wrong | #fix #ssh | [2026-09-b](2026-09-b.md) |
| U-20260923-216 | 2026-09-24 | Send curl's data pieces in command-line order when one is a file | #fix #curl | [2026-09-b](2026-09-b.md) |
| U-20260923-215 | 2026-09-24 | Send a JSON body raw when the object would not send it back as it was | #fix #curl | [2026-09-b](2026-09-b.md) |
| U-20260923-214 | 2026-09-24 | Share one refuse_constant between the JSON tools | #refactor | [2026-09-b](2026-09-b.md) |
| U-20260923-213 | 2026-09-24 | Show one changed line in a long repetitive text as one line | #fix #diff | [2026-09-b](2026-09-b.md) |
| U-20260923-212 | 2026-09-24 | Read an HTTP/2 status pseudo-header only when it is ASCII digits | #fix #inspector | [2026-09-b](2026-09-b.md) |
| U-20260923-211 | 2026-09-24 | Keep an empty host empty when the URL Builder rebuilds a URL | #fix #url | [2026-09-b](2026-09-b.md) |
| U-20260923-210 | 2026-09-24 | Keep a quoted Mermaid edge label that holds a bar | #fix #diagram | [2026-09-b](2026-09-b.md) |
| U-20260923-209 | 2026-09-24 | Skip a diagram image entry that is not an object instead of failing Open | #fix #diagram | [2026-09-b](2026-09-b.md) |
| U-20260923-208 | 2026-09-24 | Keep the prthinker extra arguments after a # | #fix #prthinker | [2026-09-b](2026-09-b.md) |
| U-20260923-207 | 2026-09-24 | Round a decimal epoch toward the past and refuse an offset past 59 minutes | #fix #timestamp | [2026-09-b](2026-09-b.md) |
| U-20260923-206 | 2026-09-24 | Save a prompt file with the characters it was opened with | #fix #ai | [2026-09-b](2026-09-b.md) |
| U-20260923-205 | 2026-09-24 | Move exact_text beside plain_text in pybreeze_ui | #refactor | [2026-09-b](2026-09-b.md) |
| U-20260923-204 | 2026-09-24 | Keep every recorded call, cookie and entry when importing a HAR file | #fix #har | [2026-09-b](2026-09-b.md) |
| U-20260923-203 | 2026-09-24 | Run a script too long for a Windows command line from a file | #fix #executor | [2026-09-b](2026-09-b.md) |
| U-20260923-202 | 2026-09-24 | Bring the architecture map, README and CLAUDE.md back in line with the code | #docs | [2026-09-b](2026-09-b.md) |
| U-20260923-201 | 2026-09-24 | Continue the September update log in 2026-09-b.md | #docs | [2026-09-b](2026-09-b.md) |
| U-20260923-200 | 2026-09-24 | Check that every tool tab opened and closed is freed | #test | [2026-09](2026-09.md) |
| U-20260923-199 | 2026-09-24 | Free the Regex tab and the SFTP tree after a match or a transfer | #fix #tools #ssh | [2026-09](2026-09.md) |
| U-20260923-198 | 2026-09-24 | Free the SFTP tree after its listings and menu requests | #fix #ssh | [2026-09](2026-09.md) |
| U-20260923-197 | 2026-09-24 | Free the diagram editor after it has fetched an image from a URL | #fix #diagram | [2026-09](2026-09.md) |
| U-20260923-196 | 2026-09-24 | Drop a half-made connection when the diagram is rebuilt | #fix #diagram | [2026-09](2026-09.md) |
| U-20260923-195 | 2026-09-24 | Show file names, paths, hosts and errors in message boxes as text, and check every box | #fix #security #ui | [2026-09](2026-09.md) |
| U-20260923-194 | 2026-09-24 | Wrap the three code lines past 120 characters | #refactor | [2026-09](2026-09.md) |
| U-20260923-193 | 2026-09-24 | Bound a whole diagram image download, and a body cut short by the deadline | #fix #diagram #security | [2026-09](2026-09.md) |
| U-20260923-192 | 2026-09-24 | Bound a whole AI request, its status line and headers included | #fix #ai #security #done | [2026-09](2026-09.md) |
| U-20260923-191 | 2026-09-24 | Cut a trickling AI answer off at its deadline, not only between chunks | #fix #ai #security | [2026-09](2026-09.md) |
| U-20260923-190 | 2026-09-24 | Free the CoT review, Skill send, Diff and SSH panels once they are closed | #fix #ai #ssh #tools | [2026-09](2026-09.md) |
| U-20260923-189 | 2026-09-24 | Let the TestPioneer menu's stand-in message box take the delete-on-close attribute | #test | [2026-09](2026-09.md) |
| U-20260923-188 | 2026-09-24 | Delete message boxes and the prthinker settings dialog once they are answered | #fix #ui | [2026-09](2026-09.md) |
| U-20260923-187 | 2026-09-24 | Show a plugin's About text as text, in a box that belongs to the main window | #fix #plugin | [2026-09](2026-09.md) |
| U-20260923-186 | 2026-09-24 | Strip escape sequences a read cuts in two, and every two-byte escape, from the run window | #fix #executor | [2026-09](2026-09.md) |
| U-20260923-185 | 2026-09-24 | Move the terminal escape handling out of the SSH widget into utils | #refactor #ssh | [2026-09](2026-09.md) |
| U-20260923-184 | 2026-09-24 | Delete a tool tab once it is closed | #fix #ui | [2026-09](2026-09.md) |
| U-20260923-183 | 2026-09-24 | Free a run window once the main window lets go of it | #fix #executor | [2026-09](2026-09.md) |
| U-20260923-182 | 2026-09-24 | Refuse a query byte that is not UTF-8 and a JSON key given twice instead of losing them | #fix #tools | [2026-09](2026-09.md) |
| U-20260923-181 | 2026-09-24 | Show a response's status when its code is not a registered one | #fix #tools | [2026-09](2026-09.md) |
| U-20260923-180 | 2026-09-24 | End a pasted JWT where it ends, and find one whose header is not written eyJ | #fix #tools | [2026-09](2026-09.md) |
| U-20260923-179 | 2026-09-24 | Lay out the Response Inspector's body and a JWT's segments as JSON Format does | #fix #tools | [2026-09](2026-09.md) |
| U-20260923-178 | 2026-09-24 | Write JSON a tool shows so that its text box gives it back as it was | #fix #tools | [2026-09](2026-09.md) |
| U-20260923-177 | 2026-09-24 | Check that every header finding and level has a message | #test #tools #i18n | [2026-09](2026-09.md) |
| U-20260923-176 | 2026-09-24 | Translate the diagram export failure, and check every language key the code uses | #fix #diagram #i18n | [2026-09](2026-09.md) |
| U-20260923-175 | 2026-09-24 | Report a mail settings file that cannot be read, and always tell the run window how the report mail went | #fix #executor | [2026-09](2026-09.md) |
| U-20260923-174 | 2026-09-24 | Remove a partial save on any failure, and report a prthinker setting UTF-8 cannot write | #fix #ai | [2026-09](2026-09.md) |
| U-20260923-173 | 2026-09-24 | Name every line ending the diff tool compares, and a changed line that starts with dashes | #fix #tools | [2026-09](2026-09.md) |
| U-20260923-172 | 2026-09-24 | Keep a query's order in the URL Builder and refuse a port written in other digits | #fix #tools | [2026-09](2026-09.md) |
| U-20260923-171 | 2026-09-24 | Remove fourteen error messages nothing raises | #refactor | [2026-09](2026-09.md) |
| U-20260923-170 | 2026-09-24 | Remove an unused upload helper and type the output actions' name arguments | #refactor #tools | [2026-09](2026-09.md) |
| U-20260923-169 | 2026-09-24 | Refuse a curl command that has no URL | #fix #tools | [2026-09](2026-09.md) |
| U-20260923-168 | 2026-09-24 | Remove a leftover fragment of a finished item from progress | #docs | [2026-09](2026-09.md) |
| U-20260923-167 | 2026-09-24 | Restore blank lines lost in recent edits | #refactor | [2026-09](2026-09.md) |
| U-20260923-166 | 2026-09-24 | Restore the main window's tool-tab close check name | #refactor | [2026-09](2026-09.md) |
| U-20260923-165 | 2026-09-24 | Ask before a docked prompt or diagram editor closes from its dock's own button | #fix #ai #diagram #done | [2026-09](2026-09.md) |
| U-20260923-164 | 2026-09-24 | Ask before closing a prompt or diagram with unsaved changes, from its tab or from closing the IDE | #fix #ai #diagram #done | [2026-09](2026-09.md) |
| U-20260923-163 | 2026-09-24 | Ask before the prompt editor's Create replaces typed text, and empty the editor when a template cannot be read | #fix #ai #done | [2026-09](2026-09.md) |
| U-20260923-162 | 2026-09-24 | Hand the Response Inspector's analysed headers to the header analyzer, not whatever the input box holds now | #fix #tools #done | [2026-09](2026-09.md) |
| U-20260923-161 | 2026-09-24 | Keep the diagram's Fit within the zoom range, and let zoom always step back toward it | #fix #diagram #done | [2026-09](2026-09.md) |
| U-20260923-160 | 2026-09-24 | Keep the diagram property panel in step with the canvas, set only the side that changed, and make a run of steps on one property one undo step | #fix #diagram #done | [2026-09](2026-09.md) |
| U-20260923-159 | 2026-09-24 | Refuse to open a HAR export or diagram over 100 MB, and report the diagram editor's read errors without the path | #fix #tools #diagram #done | [2026-09](2026-09.md) |
| U-20260923-158 | 2026-09-24 | Suggest only the last, Windows-safe part of a server's file name when saving an SFTP download | #fix #security #ssh #done | [2026-09](2026-09.md) |
| U-20260923-157 | 2026-09-24 | Escape U+2028, U+2029 and U+0085 in generated scripts, so a pasted curl command cannot add code through a comment | #fix #security #tools #done | [2026-09](2026-09.md) |
| U-20260923-156 | 2026-09-24 | Show server and file text in message boxes and labels as text, never as markup Qt would load | #fix #security #ssh | [2026-09](2026-09.md) |
| U-20260923-155 | 2026-09-24 | Bring two tests in line with the compile folder and the JupyterLab tab's delete-on-close | #test | [2026-09](2026-09.md) |
| U-20260923-154 | 2026-09-24 | Stop a run's whole process tree, not only its direct child | #fix #executor #done | [2026-09](2026-09.md) |
| U-20260923-153 | 2026-09-24 | Run a folder's files one after another, so each run has its own report and mail | #fix #executor #done | [2026-09](2026-09.md) |
| U-20260923-152 | 2026-09-24 | Let a plugin run config name the encoding its program writes | #fix #plugins #executor #done | [2026-09](2026-09.md) |
| U-20260923-151 | 2026-09-24 | Build compile-then-run binaries in a folder of their own, and make Stop during or just after a compile run nothing | #fix #executor #done | [2026-09](2026-09.md) |
| U-20260923-150 | 2026-09-24 | Keep one malformed plugin from stopping the IDE's start: check run configs and names, and build each plugin's entry on its own | #fix #plugins #crash #done | [2026-09](2026-09.md) |
| U-20260923-149 | 2026-09-24 | Delete a closed JupyterLab tab and its web view | #fix #jupyter #done | [2026-09](2026-09.md) |
| U-20260923-148 | 2026-09-24 | Keep an edited tab's unsaved mark when the file tree renames its file | #fix #editor #done | [2026-09](2026-09.md) |
| U-20260923-147 | 2026-09-24 | Delete a folder with read-only files whole, delete a link as a link, and keep new names inside their folder in the file tree | #fix #editor #done | [2026-09](2026-09.md) |
| U-20260923-146 | 2026-09-24 | Show run output as it arrives, and let a carriage return redraw the line as a terminal does | #fix #executor #done | [2026-09](2026-09.md) |
| U-20260923-145 | 2026-09-24 | Free the report mail's notice on the GUI thread, not on the mail thread | #fix #crash #threading #done | [2026-09](2026-09.md) |
| U-20260923-144 | 2026-09-24 | Store an accepted SSH host key by replacing known_hosts in one step | #fix #ssh | [2026-09](2026-09.md) |
| U-20260923-143 | 2026-09-24 | Save tool output by replacing the chosen file in one step, and say that pasted line endings come back as LF | #fix #tools #done | [2026-09](2026-09.md) |
| U-20260923-142 | 2026-09-24 | Read an indented header block line by line in the header analyzer | #fix #tools #done | [2026-09](2026-09.md) |
| U-20260923-141 | 2026-09-24 | Keep numbers as written in the query and URL tools, refuse lone surrogates there, and keep them escaped in the JSON formatter | #fix #tools #done | [2026-09](2026-09.md) |
| U-20260923-140 | 2026-09-24 | Run regex patterns in a plain worker script, stop it when the tab closes, and keep a running tab's output from being saved | #fix #tools #done | [2026-09](2026-09.md) |
| U-20260923-139 | 2026-09-24 | Try every checked address of a host in turn, and check international names as they are looked up | #fix #network #security #done | [2026-09](2026-09.md) |
| U-20260923-138 | 2026-09-24 | Give an AI answer five minutes in all, and the CoT chain the 30 s read timeout the rule sets | #fix #ai #network #done | [2026-09](2026-09.md) |
| U-20260923-137 | 2026-09-24 | Decode an AI answer by the charset its Content-Type names, UTF-8 otherwise, not Latin-1 | #fix #ai #network #done | [2026-09](2026-09.md) |
| U-20260923-136 | 2026-09-24 | Show AI review answers as text, cut long error pages, save review totals in one step, and name only a redirect's host | #fix #ai #security | [2026-09](2026-09.md) |
| U-20260923-135 | 2026-09-24 | Read the final response of curl -i output in the response inspector, and a one-line body as a body | #fix #tools #done | [2026-09](2026-09.md) |
| U-20260923-134 | 2026-09-24 | Decode a JWT pasted with Bearer, quotes or line breaks around it, and refuse characters outside base64url | #fix #tools #done | [2026-09](2026-09.md) |
| U-20260923-133 | 2026-09-24 | Read ISO-8601 the same on every Python, epoch microseconds and nanoseconds, and eight-digit dates in the timestamp converter | #fix #tools #done | [2026-09](2026-09.md) |
| U-20260923-132 | 2026-09-24 | Export a diagram to PNG or SVG through a file beside the target, so a failed export leaves the previous one | #fix #diagram #done | [2026-09](2026-09.md) |
| U-20260923-131 | 2026-09-24 | Read capitalised keywords as nodes, class suffixes, open-link chains, percent signs and quoted edge labels right in the Mermaid import | #fix #diagram #mermaid #done | [2026-09](2026-09.md) |
| U-20260923-130 | 2026-09-24 | Keep diagram images and nodes stacked as they were across save, load and undo | #fix #diagram #done | [2026-09](2026-09.md) |
| U-20260923-129 | 2026-09-24 | Skip diagram items a file places nowhere, keep far ones within reach, and leave nodes alone when a connection cannot be built | #fix #diagram #done | [2026-09](2026-09.md) |
| U-20260923-128 | 2026-09-24 | Let an image on the diagram canvas be resized by its corner handles | #fix #diagram | [2026-09](2026-09.md) |
| U-20260923-127 | 2026-09-24 | Refactor: drop the executor's exception handlers that nothing could reach | #refactor #executor | [2026-09](2026-09.md) |
| U-20260923-126 | 2026-09-24 | Keep a Connect click from cutting an SFTP transfer short | #fix #ssh | [2026-09](2026-09.md) |
| U-20260923-125 | 2026-09-24 | Refactor: move the SFTP session and its threads out of the file tree's module | #refactor #ssh | [2026-09](2026-09.md) |
| U-20260923-124 | 2026-09-24 | Run the SFTP menu's requests off the UI thread, and upload through a temporary name after asking before a replace | #fix #ssh #threading #done | [2026-09](2026-09.md) |
| U-20260923-123 | 2026-09-24 | Open the SSH shell's channel on the connect thread, not the UI thread | #fix #ssh #threading #done | [2026-09](2026-09.md) |
| U-20260923-122 | 2026-09-24 | Send a whole SSH command however long, and strip the escapes and controls the terminal still showed | #fix #ssh #done | [2026-09](2026-09.md) |
| U-20260923-121 | 2026-09-24 | Keep the SFTP tree's paths right after a folder rename, refresh the folder written to, and refuse names that are paths | #fix #ssh #done | [2026-09](2026-09.md) |
| U-20260923-120 | 2026-09-24 | Answer No for an SSH host key nobody could be asked about, instead of the previous question's Yes | #fix #security #ssh | [2026-09](2026-09.md) |
| U-20260923-119 | 2026-09-24 | Highlight TestPioneer scripts saved as .yaml, the other suffix its menu runs | #fix #syntax | [2026-09](2026-09.md) |
| U-20260923-118 | 2026-09-24 | Collect cyclic garbage on the GUI thread only, so a worker never destroys a Qt object | #fix #threading #crash | [2026-09](2026-09.md) |
| U-20260923-117 | 2026-09-23 | A data folder the log creates is its owner's only, like the one pybreeze_data_dir creates | #fix #security | [2026-09](2026-09.md) |
| U-20260923-116 | 2026-09-23 | JupyterLab runs in the interpreter chosen in the IDE, finds itself without pip, and fails fast on a taken port | #fix #jupyter | [2026-09](2026-09.md) |
| U-20260923-115 | 2026-09-23 | The run window shows coloured and redrawn output as text, not escape codes | #fix #executor | [2026-09](2026-09.md) |
| U-20260923-114 | 2026-09-23 | A run's output waits in a bounded queue, so a print loop no longer fills memory or floods Stop | #fix #executor | [2026-09](2026-09.md) |
| U-20260923-113 | 2026-09-23 | The run window shows output past its 10,000-line cap without freezing the IDE | #fix #executor #performance | [2026-09](2026-09.md) |
| U-20260923-112 | 2026-09-23 | URL Builder rebuilds a query it cannot decode losslessly exactly as it was | #fix #tools | [2026-09](2026-09.md) |
| U-20260923-111 | 2026-09-23 | cURL and HAR import send a query that would not survive re-encoding as it was written | #fix #tools | [2026-09](2026-09.md) |
| U-20260923-110 | 2026-09-23 | The Diff tab matches the lines once and off the UI thread | #fix #tools #performance | [2026-09](2026-09.md) |
| U-20260923-109 | 2026-09-23 | cURL import reads @file bodies as curl sends them and stops sending a -b cookie file's name as a cookie | #fix #tools | [2026-09](2026-09.md) |
| U-20260923-108 | 2026-09-23 | cURL and HAR import send a form as multipart without the copied Content-Type, and the JSON action refuses what it cannot carry | #fix #tools | [2026-09](2026-09.md) |
| U-20260923-107 | 2026-09-23 | Tool output is copied and saved as generated, and Regex and HAR report patterns and files they cannot take | #fix #tools | [2026-09](2026-09.md) |
| U-20260923-106 | 2026-09-23 | prthinker settings refuse extra arguments with an open quote at Save instead of dropping them at run time | #fix #prthinker | [2026-09](2026-09.md) |
| U-20260923-105 | 2026-09-23 | A file-tree rename moves a docked editor and the tab's watch, highlighter, git baseline and language server with the file | #fix #editor | [2026-09](2026-09.md) |
| U-20260923-104 | 2026-09-23 | Header Analyzer and Response Inspector read quoted max-age, folded lines, header names in any case and HTTP/2 :status | #fix #tools | [2026-09](2026-09.md) |
| U-20260923-103 | 2026-09-23 | JSON Format and Minify keep numbers and characters as written, and report a repeated key | #fix #tools | [2026-09](2026-09.md) |
| U-20260923-102 | 2026-09-23 | Prompt and diagram saves use the shared replace_text (refactor) | #refactor #tools | [2026-09](2026-09.md) |
| U-20260923-101 | 2026-09-23 | prthinker settings: a failed save keeps the stored keys, the file is its owner's only, reading creates nothing, and a failure is shown | #fix #security #prthinker | [2026-09](2026-09.md) |
| U-20260923-100 | 2026-09-23 | URL Builder and Query JSON: deeply nested JSON reported, null parts empty, ports checked, an empty port accepted | #fix #tools | [2026-09](2026-09.md) |
| U-20260923-99 | 2026-09-23 | Plugin runs match suffixes registered in any case or without the dot, and the Plugins menu has one run entry per plugin | #fix #plugin | [2026-09](2026-09.md) |
| U-20260923-98 | 2026-09-23 | Reading a prompt creates nothing and cannot stop a review on a folder it may not look into | #fix #ai | [2026-09](2026-09.md) |
| U-20260923-97 | 2026-09-23 | Skills panel: switching the template keeps an edited prompt unless the user agrees, and a prompt without its code is not sent | #fix #ai | [2026-09](2026-09.md) |
| U-20260923-96 | 2026-09-23 | A failed AI request is described in its panel without the URL and any token in it | #fix #security #ai | [2026-09](2026-09.md) |
| U-20260923-95 | 2026-09-23 | Create Project writes into the folder open in the IDE and asks before it replaces a template | #fix #menu | [2026-09](2026-09.md) |
| U-20260923-94 | 2026-09-23 | Requests to user URLs connect only to the address checked as they connect (DNS rebinding) | #done #security #network | [2026-09](2026-09.md) |
| U-20260923-93 | 2026-09-23 | Run and send: an earlier run's report is not mailed, and the run window says whether the mail went | #fix #executor #mail | [2026-09](2026-09.md) |
| U-20260923-92 | 2026-09-23 | A run whose started process keeps its output open no longer freezes the IDE when it ends | #fix #executor | [2026-09](2026-09.md) |
| U-20260923-91 | 2026-09-23 | A run that cannot start says so in its window, and a Python run no longer reads the IDE's stdin | #fix #executor | [2026-09](2026-09.md) |
| U-20260923-90 | 2026-09-23 | SSRF check refuses a URL whose host urlparse and urllib3 read differently | #fix #security #network | [2026-09](2026-09.md) |
| U-20260923-89 | 2026-09-23 | Diagram undo keeps text typed on the canvas and images it cannot reload | #done #diagram | [2026-09](2026-09.md) |
| U-20260923-88 | 2026-09-23 | Tools work on the text as entered, not Qt's display copy | #fix #tools | [2026-09](2026-09.md) |
| U-20260923-87 | 2026-09-23 | curl and HAR import: malformed URLs reported, -I, --oauth2-bearer, fragments, repeated -F | #fix #tools | [2026-09](2026-09.md) |
| U-20260923-86 | 2026-09-23 | A diagram file with an infinite or non-numeric font size opens | #fix #diagram | [2026-09](2026-09.md) |
| U-20260923-85 | 2026-09-23 | A tool's Save to file says when the file was not saved | #fix #tools | [2026-09](2026-09.md) |
| U-20260923-84 | 2026-09-23 | Diff shows a change when only a final newline or a line ending differs | #fix #tools | [2026-09](2026-09.md) |
| U-20260923-83 | 2026-09-23 | Epoch values and JWT claims before 1970 convert on Windows | #fix #tools | [2026-09](2026-09.md) |
| U-20260923-82 | 2026-09-23 | SFTP: one request at a time on the session, and a download replaces its file only when complete | #fix #ssh | [2026-09](2026-09.md) |
| U-20260923-81 | 2026-09-23 | Unknown SSH host key: asked once per Connect, and no accepted host written away | #fix #ssh #security | [2026-09](2026-09.md) |
| U-20260923-80 | 2026-09-23 | SSH shell ended by the server closes its session and reports both halves | #fix #ssh | [2026-09](2026-09.md) |
| U-20260923-79 | 2026-09-23 | JupyterLab tab says why it did not start; a closed tab is no failure | #fix #jupyter | [2026-09](2026-09.md) |
| U-20260923-78 | 2026-09-23 | A run window closed mid-run is let go of when its run ends | #fix #executor | [2026-09](2026-09.md) |
| U-20260923-77 | 2026-09-23 | SFTP: a session that comes up after Disconnect or tab close is closed | #fix #ssh | [2026-09](2026-09.md) |
| U-20260923-76 | 2026-09-23 | Run a folder: a parented dialog, a message when nothing matches, and a Qt-free utils | #fix #executor #refactor | [2026-09](2026-09.md) |
| U-20260923-75 | 2026-09-23 | AI review panel: Send always comes back, and only an answer can be voted on | #fix #ai | [2026-09](2026-09.md) |
| U-20260923-74 | 2026-09-23 | Install prthinker: a parented dialog, and only prthinker's source is kept | #done #prthinker | [2026-09](2026-09.md) |
| U-20260923-73 | 2026-09-23 | Closing the IDE survives a tab, dock or run window that raises | #done #lifecycle | [2026-09](2026-09.md) |
| U-20260923-72 | 2026-09-23 | File tree Delete closes only the tabs whose files are gone | #done #filetree | [2026-09](2026-09.md) |
| U-20260923-71 | 2026-09-23 | prthinker Review current file saves the file first | #done #prthinker | [2026-09](2026-09.md) |
| U-20260923-70 | 2026-09-23 | TestPioneer Create template: in the working directory, asks before replacing | #done #testpioneer | [2026-09](2026-09.md) |
| U-20260923-69 | 2026-09-23 | AutoControl Record Stop: stops from any tab, inserts runnable JSON | #done #autocontrol | [2026-09](2026-09.md) |
| U-20260923-68 | 2026-09-23 | Run with: a save that fails is reported and runs nothing | #fix #plugins | [2026-09](2026-09.md) |
| U-20260923-67 | 2026-09-23 | CoT code review panel: in the menus, no DNS on the UI thread, fresh runs | #done #ai | [2026-09](2026-09.md) |
| U-20260923-66 | 2026-09-23 | AI panels: no URLs in logs, damaged urls.txt, shared vote totals, prompt fields | #fix #ai #security | [2026-09](2026-09.md) |
| U-20260923-65 | 2026-09-23 | Prompt editor: no saved 'does not exist' note, no lost edits on switch | #fix #ai | [2026-09](2026-09.md) |
| U-20260923-64 | 2026-09-23 | Diagram editor shortcuts act only while it has focus | #fix #diagram | [2026-09](2026-09.md) |
| U-20260923-63 | 2026-09-23 | Mermaid import: syntax inside labels, bare headers, directions and more links | #done #diagram | [2026-09](2026-09.md) |
| U-20260923-62 | 2026-09-23 | Diagram editing: right-click, stacking, undo, sizes, wheel and teardown | #done #diagram | [2026-09](2026-09.md) |
| U-20260923-61 | 2026-09-23 | A file can be renamed to a different case of its name on Windows | #done #editor | [2026-09](2026-09.md) |
| U-20260923-60 | 2026-09-23 | Three menu actions that did nothing or raised now work | #done #menu | [2026-09](2026-09.md) |
| U-20260923-59 | 2026-09-23 | A hand-edited null no longer becomes the prthinker API key "None" | #done #prthinker #security | [2026-09](2026-09.md) |
| U-20260923-58 | 2026-09-23 | A diagram load either happens or leaves the canvas as it was | #done #diagram | [2026-09](2026-09.md) |
| U-20260923-57 | 2026-09-23 | The AI review panel's accept/reject totals carry across sessions | #done #ai | [2026-09](2026-09.md) |
| U-20260923-56 | 2026-09-23 | The SSRF check also refuses IPv6 site-local addresses | #done #security | [2026-09](2026-09.md) |
| U-20260923-55 | 2026-09-23 | Query null, repeated response headers and an out-of-range port are handled | #done #tools | [2026-09](2026-09.md) |
| U-20260923-54 | 2026-09-23 | Copy as cURL (bash) commands with $'...' bodies import correctly | #done #tools | [2026-09](2026-09.md) |
| U-20260923-53 | 2026-09-23 | A query parameter given twice keeps both values | #done #tools | [2026-09](2026-09.md) |
| U-20260923-52 | 2026-09-23 | A text form field starting with @ is no longer uploaded as a file | #done #tools | [2026-09](2026-09.md) |
| U-20260923-51 | 2026-09-23 | The timestamp tool keeps milliseconds and rounds times before 1970 down | #done #tools | [2026-09](2026-09.md) |
| U-20260923-50 | 2026-09-23 | Five inputs that made a tool tab raise are reported instead | #done #tools | [2026-09](2026-09.md) |
| U-20260923-49 | 2026-09-23 | The diff tab's summary no longer takes a minute on a large text | #done #tools #performance | [2026-09](2026-09.md) |
| U-20260923-48 | 2026-09-23 | Generated scripts write JSON bodies and non-BMP characters as Python | #done #tools | [2026-09](2026-09.md) |
| U-20260923-47 | 2026-09-23 | A request's method or URL can no longer write code into a generated script | #done #security #tools | [2026-09](2026-09.md) |
| U-20260923-46 | 2026-09-23 | Package installs no longer go through cmd.exe | #done #security #install | [2026-09](2026-09.md) |
| U-20260923-45 | 2026-09-23 | Deleting a folder closes the tabs open inside it | #done #editor | [2026-09](2026-09.md) |
| U-20260923-44 | 2026-09-23 | A long output line no longer garbles its characters or doubles its line ending | #done #executor | [2026-09](2026-09.md) |
| U-20260923-43 | 2026-09-23 | The SSH terminal no longer breaks lines, characters or escapes where a read ends | #done #ssh | [2026-09](2026-09.md) |
| U-20260923-42 | 2026-09-23 | Skills status wording and the review panel's layout split out | #done #refactor #ai | [2026-09](2026-09.md) |
| U-20260923-41 | 2026-09-23 | A redirect or an HTTP error no longer passes for an AI answer | #done #ai | [2026-09](2026-09.md) |
| U-20260923-40 | 2026-09-23 | SSH connects refuse SHA-1 on any paramiko (CVE-2026-44405) | #done #security #ssh | [2026-09](2026-09.md) |
| U-20260923-39 | 2026-09-23 | A plugin's compile step streams instead of freezing the IDE | #done #executor #plugin | [2026-09](2026-09.md) |
| U-20260923-38 | 2026-09-23 | Closing a tab no longer waits for its worker, and a closed JupyterLab tab starts no server | #done #jupyter #ssh #ai | [2026-09](2026-09.md) |
| U-20260923-37 | 2026-09-23 | Blind catches narrowed to what each call raises | #done #quality | [2026-09](2026-09.md) |
| U-20260923-36 | 2026-09-23 | Mailing a run's report no longer freezes the IDE | #done #executor | [2026-09](2026-09.md) |
| U-20260923-35 | 2026-09-23 | Adding an image from a URL no longer freezes the IDE | #done #diagram | [2026-09](2026-09.md) |
| U-20260923-34 | 2026-09-23 | Remote directories are listed without freezing the IDE | #done #ssh | [2026-09](2026-09.md) |
| U-20260923-33 | 2026-09-23 | Connecting an SSH tab no longer freezes the IDE | #done #ssh | [2026-09](2026-09.md) |
| U-20260923-32 | 2026-09-23 | A runaway regex no longer freezes the IDE | #done #tools | [2026-09](2026-09.md) |
| U-20260923-31 | 2026-09-23 | Importing a utility no longer imports the whole IDE | #done #refactor #performance | [2026-09](2026-09.md) |
| U-20260923-30 | 2026-09-23 | Prompt files: other encodings, unsaved edits, half-written saves | #done #ai | [2026-09](2026-09.md) |
| U-20260923-29 | 2026-09-23 | Closing a request panel no longer waits for its request | #done #ai | [2026-09](2026-09.md) |
| U-20260923-28 | 2026-09-23 | One broken extend tab no longer stops the IDE from starting | #done #editor | [2026-09](2026-09.md) |
| U-20260923-27 | 2026-09-23 | PyBreeze.log leaves the working directory and becomes UTF-8 | #done #logging | [2026-09](2026-09.md) |
| U-20260923-26 | 2026-09-23 | Dependabot opens its PRs against dev | #done #ci | [2026-09](2026-09.md) |
| U-20260923-25 | 2026-09-23 | PySide6 6.11.2, after je_editor and frontengine | #done #dependencies | [2026-09](2026-09.md) |
| U-20260923-24 | 2026-09-23 | Imported requests sent a different query than was recorded | #done #tools | [2026-09](2026-09.md) |
| U-20260923-23 | 2026-09-23 | Three tool tabs let an exception out of their slots | #done #tools | [2026-09](2026-09.md) |
| U-20260923-22 | 2026-09-23 | Renaming an open file brought the old name back | #done #editor | [2026-09](2026-09.md) |
| U-20260923-21 | 2026-09-23 | The embedded JupyterLab took any origin and outlived its tab | #incident #security #jupyter | [2026-09](2026-09.md) |
| U-20260923-20 | 2026-09-23 | One Connect button, two sessions, one honest label | #done #ssh | [2026-09](2026-09.md) |
| U-20260923-19 | 2026-09-23 | An SFTP transfer held the IDE until it finished | #done #ssh | [2026-09](2026-09.md) |
| U-20260923-18 | 2026-09-23 | Copy and duplicate ignored images | #done #diagram | [2026-09](2026-09.md) |
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
| [2026-09.md](2026-09.md) | 2026-09 | 218 |
| [2026-09-b.md](2026-09-b.md) | 2026-09 | 120 |
| [2026-09-c.md](2026-09-c.md) | 2026-09 | 12 |
