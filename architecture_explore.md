# PyBreeze 架構探勘 / Architecture Exploration

> 掃描範圍：`pybreeze/`（235 個 `.py`、約 30,600 行，不含空行與註解約 23,900 行）＋ `test/`、`exe/`、`docs/`、CI 設定
> 對應版本：`pyproject.toml` 1.0.21（stable）／`dev.toml` 1.0.14（dev；只是下限，發佈的版號由 CI 取 PyPI 最新版加一），分支 `dev`

---

## 1. 專案定位

PyBreeze 是一個「自動化優先」的 Python IDE，建構在 **PySide6 + JEditor** 之上。它本身不重寫編輯器，而是繼承 `je_editor.EditorMain`，再把四個維度的自動化（API / GUI / Web / Load）、AI 程式碼審查、SSH、JupyterLab、圖表編輯器與一整組 HTTP 開發工具掛進同一個視窗。

核心設計理念只有一句：**編輯器主行程永遠不執行使用者腳本**。所有自動化都丟到子行程，輸出用 Queue + QTimer 打回 UI 執行緒。

---

## 2. 分層總覽

```
                         ┌──────────────────────────────────┐
   進入點 Entry           │ pybreeze/__main__.py             │
                         │ exe/start_pybreeze.py            │
                         │   → pybreeze.start_editor()      │
                         └───────────────┬──────────────────┘
                                         ▼
   Facade                 pybreeze/__init__.py
                          （start_editor / PyBreezeMainWindow / EDITOR_EXTEND_TAB
                            + 轉出 je_editor 插件 API）
                                         ▼
   ┌─────────────────────────────────────────────────────────────────────────┐
   │ 表現層 Presentation  pybreeze/pybreeze_ui/                              │
   │  editor_main   主視窗（繼承 EditorMain）＋ 檔案樹右鍵選單                │
   │  menu          選單建構器：automation / install / tools / plugin / dock │
   │  tools_gui     13 個工具 widget（curl、HAR、JWT、diff、regex…）          │
   │  diagram_editor 架構圖 WYSIWYG 編輯器（QGraphicsScene）                  │
   │  extend_ai_gui  CoT 程式碼審查、Prompt 編輯器、Skills 發送               │
   │  connect_gui    SSH 終端 + SFTP 檔案樹、AI Code Review HTTP client      │
   │  jupyter_lab_gui JupyterLab 內嵌分頁（QWebEngineView）                   │
   │  show_code_window CodeWindow：所有子行程輸出的顯示視窗                   │
   │  syntax        自動化關鍵字語法高亮定義                                  │
   │  dialog        prthinker 設定對話框                                     │
   │  design        設計系統：以 em 計的間距與字級、會換行的列、Panel          │
   │  navigation    導覽面板：選單與工具表攤成可搜尋的樹（左側 dock）        │
   └────────────────────────────────┬────────────────────────────────────────┘
                                    ▼
   ┌─────────────────────────────────────────────────────────────────────────┐
   │ 執行層 Execution  pybreeze/extend/                                      │
   │  process_executor/  子行程隔離層（Template Method）                      │
   │  mail_thunder_extend/  測試後寄報告 hook（mail_thunder_setting.py）      │
   │  prthinker_extend/     prthinker 設定與指令組裝（純邏輯）                │
   └────────────────────────────────┬────────────────────────────────────────┘
                                    ▼
   ┌─────────────────────────────────────────────────────────────────────────┐
   │ 基礎層 Foundation                                                        │
   │  pybreeze/utils/              21 個工具子套件（純邏輯，可單測）           │
   │  pybreeze/extend_multi_language/  內建 i18n（英 / 繁中，各 872 鍵）      │
   └─────────────────────────────────────────────────────────────────────────┘
                                    ▼
   外部子行程：python -m je_api_testka / je_auto_control / je_web_runner /
               je_load_density / automation_file / je_mail_thunder /
               test_pioneer / prthinker
```

---

## 3. 啟動流程

`pybreeze/pybreeze_ui/editor_main/main_ui.py:216` 的 `start_editor()`（第 2 到 4 步在 `open_main_window()`，它回傳視窗給 `start_editor()` 握到程式結束）：

1. 取得（或建立）`QApplication`，裝上 `collect_garbage_on_gui_thread()`（`pybreeze_ui/gui_thread_gc.py`：關掉自動垃圾回收，改在 UI 執行緒上定時回收，見 §16）
2. 建立 `PyBreezeMainWindow`，其 `__init__` 依序：
   - `update_language_dict()` 併入 PyBreeze 的 872 條翻譯——**必須在 `super().__init__` 之前**：JEditor 在那裡依設定挑啟動語言，英文以外的語言讀的是當下合併出來的一份副本，之後才加進去的字串它看不到，選單拿到 `None` 標題就讓 Qt 當掉（access violation）
   - `super().__init__(..., extend=True)` — JEditor 在此已呼叫 `load_external_plugins()`，自動掃描 CWD 下的 `jeditor_plugins/`，也以 `startup_setting()` 套上存下的設定與 UI Style 主題
   - `show_only_warnings_in_code_result()`（`pybreeze_ui/code_result_logs.py`）— JEditor 剛把一個 `RedirectStdErr` 掛到當下每個 logger 上、收到的顯示在 Code Result；自動化套件 import 時把 root 設成 DEBUG，所以開檔就有 gitpython 的除錯訊息以紅字出現。把這個 handler 的門檻調到 WARNING，logger 本身的層級不動
   - 刪掉 JEditor 原本的 Help 選單
   - 設定標題、Windows AppUserModelID、圖示（`pybreeze_icon.ico`，在 `main_ui.py` 旁邊、以 package data 隨套件發佈：`pyproject.toml` / `dev.toml` 的 `[tool.setuptools.package-data]`，執行檔建置用 `datas` 帶進去，所以不論從哪個資料夾啟動都有圖示）
   - `add_menu_to_menubar()` — 建構全部選單（見 §5）
   - `syntax_extend_package()` — 註冊 `.json` / `.yml` / `.yaml` 自動化關鍵字高亮
   - `_add_navigation_dock()` — 選單建好之後，把導覽面板加到左側（見 §5.6），它的每一行都是剛建好的某個選單 action；`~/.pybreeze/ui_state.json` 記著上次關掉就不顯示
   - 依 `EDITOR_EXTEND_TAB` 註冊表加入外部擴充分頁（`_add_extend_tabs()`：每一個分頁各自建，建不起來的只記 log，不會讓整個 IDE 起不來）
   - `setup_file_tree_context_menu()` — 掛上檔案樹右鍵選單，以及焦點在樹上時的 F2（重新命名）與 Delete（刪除，先問、預設否）快捷鍵（`_attach_keys()`，`WidgetShortcut`，走選單的同一組動作）。改名時開著的分頁跟著檔案走（改資料夾也一樣，底下每個開著的檔案都跟著走）：先停掉分頁的自動存檔、改名、再用新路徑重開一條（`_stop_auto_save()` / `_start_auto_save()`）——JEditor 的存檔執行緒只認開檔當下的路徑，沒辦法改指向。外部修改監視也跟著搬（改名前就先移除，檔案搬走後 Windows 放不掉舊名），並照 `open_an_file` 重載語法高亮、git 基準與語言伺服器（`rename_self_tab()` 會清掉「未儲存」標記，有未存的編輯就用 `_on_text_changed()` 放回去，否則改名後五秒內關分頁會直接丟掉編輯）；Dock Editor（`FullEditorWidget`，關閉時才寫回、檔案不存在就不寫）的 `current_file` 也改指新路徑（`_dock_editors_under()`）。新增與改名的名稱不能帶磁碟代號、根目錄、`..` 或 `:`，也不能解析到資料夾外（`_inside()`；改名只能是單一名稱）。刪除先移到系統的回收筒（`_move_to_trash()`：`QFile.moveToTrash`，Windows 的資源回收筒、macOS 與 freedesktop 的垃圾桶）；沒有回收筒可用時再問一次（預設否）才永久刪除，資料夾用 `remove_folder()`（唯讀檔清掉唯讀屬性再刪，git 的物件檔就是唯讀）；符號連結與 junction 只刪連結本身，不進回收筒。刪除時同樣用 `_editors_under()`：檔案或資料夾底下每個開著的分頁先停掉自動存檔，再刪；刪完只關掉檔案真的不見了的分頁，刪不掉（被鎖住、唯讀）的檔案分頁留著、自動存檔重開。「在檔案總管中顯示」由 `reveal_command()` 組指令：Windows 用 Explorer 的 `/select,`、macOS 用 `open -R` 把檔案選起來，其他平台 `xdg-open` 只能開資料夾；啟動失敗（例如沒有 `xdg-open`）經 `_perform_file_op()` 跳警告
   - `close_tab()` 覆寫 JEditor 的：分頁有 `may_close()` 就先問（提示詞編輯器、架構圖編輯器有未存的變更時會問）；關掉的工具分頁 `deleteLater()`（JEditor 的 `removeTab` 不刪 widget，關過的工具分頁會留到 IDE 結束），JEditor 自己的編輯器分頁不動，關閉 IDE 時也先問過每個分頁與 dock，有一個說不就取消關閉
   - `debug_mode=True` 時啟動 10 秒自動關閉 `QTimer`（CI 用）
3. `start_editor(theme=...)` 給了主題時（`_apply_given_theme()`）：寫進 `user_setting_dict["ui_style"]` 成為選定的主題，再跑一次 `startup_setting()` 套上；它失敗時記 log，仍用 qt_material 的 `apply_stylesheet()` 套上這個主題。沒給主題就不再套：建構子已經套過 JEditor 存下的 `ui_style`（UI Style 選的，沒選過是 `dark_amber.xml`），而套一次主題要將近一秒；只把視窗自己的字型 style sheet 再設一次（`startup_setting()` 先設它、後套主題，不再設一次的話工具列比給了主題時高 4 px）
4. `showMaximized()` → `app.exec()`
5. 離開時以 `os._exit(ret)` 硬退出（避開 Qt 拆解殘留執行緒）

模組層級有一個副作用：`main_ui.py` 在匯入 PySide6 之前就設定 `LOCUST_SKIP_MONKEY_PATCH`（值是 `subprocess_util.IDE_ONLY`；使用者自己設過就沿用），避免 locust 一 import 就對整個行程做的 gevent monkey patch 破壞 Qt（Load Density GUI、JEditor 行程內的 IPython console 都可能 import 它）。IDE 啟動的行程拿到的是 `child_environment()`，不帶這個值：負載測試要靠 patch 才能讓使用者同時跑，帶著它時 HttpUser 一個接一個跑，3 秒的測試跑了三分多鐘。

---

## 4. 執行層：process_executor（整個專案的心臟）

### 4.1 `python_task_process_manager.py` — `TaskProcessManager`

Template Method 定義的子行程生命週期：

| 階段 | 做的事 |
|---|---|
| 解譯器解析 | `renew_path()` → 執行視窗帶著 IDE 選定的直譯器（`python_compiler`，由 `build_task_process()` 從主視窗抄過來）就用它；沒選才用 `default_interpreter()`：工作目錄有 `venv/`、`.venv/` 就交給 `check_and_choose_venv()`，沒有就用 IDE 自己的直譯器（`sys.executable`，和 JupyterLab 分頁一樣；PATH 上的 `python3` 在 Windows 常是 Store 的空殼，exit 9009 什麼也不說），只有打包版才去 PATH 找；找不到時**不拋例外**，直接把錯誤寫進執行視窗並回傳 `False` |
| 啟動 | `subprocess.Popen(args, shell=False, stdin=DEVNULL, creationflags=CREATE_NO_WINDOW, env=PYTHONIOENCODING=...)`；`stdin` 不接 IDE 的主控台（腳本 `input()` 立刻拿到 EOF）；`Popen` 丟 `OSError`（直譯器不見、命令列超過 Windows 上限）時寫進執行視窗並顯示，不從選單拋出 |
| 讀取 | 兩條 daemon Thread 各自經 `queue_pump.read_stream_into_queue()` 對 stdout / stderr `read1()`（有多少讀多少，不等換行：沒換行的狀態列與用 `\r` 重畫的進度條才會即時出現；沒有 `read1` 的文字串流才逐行讀），原樣塞進 `Queue`（保留縮排、行尾與空行）；**空讀 = EOF 立刻 break**（否則會 100% CPU 空轉） |
| 送 UI | `QTimer` 每 100 ms 呼叫 `pull_text()`，經 `pump_message_queue()` 每 tick 最多抽 256 則，交給 `CodeWindow.append_output()` |
| 收尾 | 子行程結束後，pump 照樣每 tick 抽 queue，直到兩條 reader 都讀到 EOF 或寬限（`ReaderGrace`，2 秒，那個 tick 還有輸出就重新起算，最長到結束後 30 秒）用完，UI 執行緒不 join 任何執行緒。`exit_program()`：drain queue（`max_messages=None` 一次抽乾）→ reader 還活著（子行程開的行程還握著管線）就在視窗註明之後的輸出不會顯示 → `terminate()` → 呼叫 `task_done_trigger_function`（例如寄信） |
| 停止 | `stop()`：子行程還在跑就 `stop_tree()`（連它開的行程一起：Windows 用 `taskkill /T /F`，POSIX 對子行程自己的 process group 送 SIGTERM；`go run`、`cargo run` 的程式與網頁執行開的瀏覽器是孫行程，只停子行程會留下它們），失敗就退回只 `terminate()` 子行程，之後照一般結束的路徑回報。經 `CodeWindow.stop_runner()` 呼叫；關閉 IDE 時 `PyBreezeMainWindow.closeEvent()` 對每個執行視窗都呼叫一次（經 `_close_guarded()`：一個視窗、分頁或 dock 關閉時丟例外只記錄，其餘照關，JEditor 自己的 `closeEvent` 一定會跑到） |

三種啟動介面：

- `start_test_process(package, exec_str, subject="")` — 腳本內容直接走 `--execute_str`（Windows 上先 `json.dumps` 逃逸）；Windows 上命令列超過 30,000 字元（上限 32,767）時改寫進暫存的 `pybreeze_run_*.json`、走 `--execute_file`（JSON 以全跳脫的 ASCII 寫回，套件用哪種編碼讀都一樣），執行結束或啟動失敗就刪掉
- `start_test_process_file(package, file_path)` — 走 `--execute_file`，避開 Windows ~32K 命令列上限
- `start_module_process(package, arguments, environment, subject="")` — 通用形式；**祕密（API key、token）走 environment 不走命令列**，工作管理員看不到

執行視窗的標題是 `套件 - 檔名`（`subject`：編輯器分頁的檔名、`--execute_file` 的檔案、TestPioneer 的 YAML），沒有檔案時只有套件名；一次執行整個資料夾時，每個檔案一個視窗，這樣才分得出來

### 4.2 `process_executor_utils.py` — 工廠函式

| 函式 | 用途 |
|---|---|
| `build_process()` | 取當前分頁的程式碼（或傳入的 `exec_str`）→ `start_process()`。沒給 `exec_str` 又不是編輯器分頁時，開一個執行視窗寫明「腳本要在前面的編輯器分頁裡」（`report_no_script_tab()`），不會把 `None` 交給套件 |
| `start_process()` | 建 `CodeWindow` + `TaskProcessManager` → `start_test_process()` |
| `build_process_from_file()` | 以檔案路徑執行單一檔案，回傳它的 manager；`then` 在執行結束時呼叫 |
| `run_dir_files_with_package()` | 問使用者選資料夾（`_ask_for_action_files()`，對話框掛在主視窗上；資料夾裡沒有 `.json` 就明說），每個 `.json` 一個執行視窗，一個跑完才跑下一個（`run_one_after_another()`：報告都寫到同一個 `default_name.html`，同時跑會互相蓋掉、寄錯報告）；被停止的執行（停止鈕、關閉 IDE）結束整批，啟動不了的檔案跳過 |
| `open_run_window()` | 開一個執行視窗、掛進 `main_window.current_run_code_window`，並接上 `finished_and_closed`：使用者關掉一個已經跑完的執行視窗時主視窗就放掉它（以前這份清單只增不減，每次執行都留下一個視窗、一個執行器、兩個 queue 和一個 timer）；使用者在執行中關掉視窗（`closeEvent` 的 spontaneous 事件；IDE 關閉時以程式呼叫 `close()` 不算）會先問：是＝`stop_runner()`、否＝讓它在沒有視窗的情況下跑完、取消＝不關；執行中被關掉的視窗記下 `_closed_while_running`，等執行器在結束路徑尾端呼叫 `CodeWindow.run_ended()` 時才放掉（排到 timer 的 slot 回來之後才發，視窗是 timer 的 parent）。插件執行也走這裡 |
| `build_task_process()` | 共用建構：`open_run_window()` 並帶上主視窗選定的直譯器、決定要不要接寄報告的 hook（`report_mail_hook(code_window)`：建立時記下子行程工作目錄裡 `default_name.html` 的絕對路徑與開始時間，比這次執行還舊的報告不寄；寄送結果經無 parent 的 `_MailNotice` 以 queued signal 回到執行視窗，寫出寄到了或沒寄的原因）。建好的 `TaskProcessManager` 掛在執行視窗的 `runner` 上，所以呼叫端可以不留參考。prthinker 審查也走這裡 |

### 4.3 各自動化套件的執行項目

五個套件的 Run 子選單都是同樣四項，由 `automation_menu_factory.package_run_actions(ui, label_prefix, package)` 產生（標籤鍵是前綴加 `RUN_ENTRY_LABEL_SUFFIXES`）：

```
<prefix>_run_script_label                   → build_process(ui, package, send_mail=False)
<prefix>_run_script_with_send_label         → build_process(ui, package, send_mail=True)
<prefix>_run_multi_script_label             → run_dir_files_with_package(ui, package, send_mail=False)
<prefix>_run_multi_script_with_send_label   → run_dir_files_with_package(ui, package, send_mail=True)
```

| 選單 | 標籤前綴 | 套件 |
|---|---|---|
| APITestka | `apitestka` | `je_api_testka` |
| AutoControl | `autocontrol` | `je_auto_control` |
| WebRunner | `web_runner` | `je_web_runner` |
| LoadDensity | `load_density` | `je_load_density` |
| FileAutomation | `file_automation` | `automation_file` |
| MailThunder | — | `je_mail_thunder`（只有一項，選單直接呼叫 `build_process(..., send_mail=False)`） |

以前每個套件在 `extend/process_executor/` 下各有一個結構完全相同的模組（只差 `_PACKAGE`），各轉呼叫這兩個函式。

`test_pioneer/test_pioneer_process_manager.py` 只剩 `init_and_start_test_pioneer_process()`：經 `build_task_process()` 開執行視窗，再用 `start_module_process("test_pioneer", ["-e", <yaml>])` 跑，跟其他套件走同一個 `TaskProcessManager`（找不到直譯器時一樣寫進執行視窗，不會從選單 callback 拋出）。

### 4.4 特化執行器

- **`file_runner_process.py`** — `FileRunnerProcess`。**唯一不跑 Python 的執行器**，服務插件註冊的 run config：
  - 直譯式：`compiler [args...] file`（如 `go run main.go`）
  - 編譯式：`compiler file -o out` → 執行 `out` → 執行完整個建置資料夾刪掉。`out` 建在 `tempfile.mkdtemp()` 開的資料夾裡，不在原始檔旁邊（旁邊同名的檔案會被蓋掉再刪掉，同一個檔案跑兩次也會互搶）。編譯器跟執行一樣走 `_start_process()`（輸出即時串流、不佔 UI 執行緒），結束碼交給 `after_exit`：0 才接著跑產物，否則印 `[Compile failed]`
  - 編譯最多 `COMPILE_TIME_LIMIT_SECONDS`（60 秒），由 pump 檢查、超過就 `stop_tree()`；編譯中也能 `stop()`。QTimer 間隔 50 ms（比 Python 執行器更快），編譯與執行共用同一個
  - 讀取、pump、drain 與寫進視窗都用 §4.5 的共用函式
  - `run_current_file_with()` 建好後同樣掛在執行視窗的 `runner` 上；輸出用執行設定的 `"encoding"` 解碼（`output_encoding()`，`"locale"` 表示本機字碼頁，Java 與中文化的編譯器就是輸出本機字碼頁；取自 `locale.getencoding()`，UTF-8 模式下（Python 3.15 起預設開啟）也不會變成 UTF-8），沒寫就用 IDE 的編碼
  - 有和 `TaskProcessManager` 相同語意的 `stop()`
  - 子行程的 `stdin` 是 `DEVNULL`：執行視窗沒有輸入欄，讀取要立刻拿到 EOF，不能卡在沒人寫的管線上
  - 視窗自己的訊息（`run_notice()` 的每一則、`> 指令` 回顯）一律 `own_line=True`，不會接在程式沒換行的輸出後面；結束那一行是 `run_notice("process_exited")`，跟著 IDE 的語言
  - 啟動失敗（找不到指令、是資料夾、沒有執行權限、產物被鎖）都寫進執行視窗，建置資料夾經 `_remove_build_dir()` 一併刪掉。`stop()` 會設 `_cancelled`：編譯中或剛編譯完按停止都顯示「[Stopped]」、不執行產物；每個子行程有自己的讀取旗標（`_reading`），編譯的讀取執行緒不會延續到執行階段

### 4.5 `queue_pump.py` 與 `CodeWindow.append_output()`

子行程輸出到執行視窗的整條管線，兩個執行器（`TaskProcessManager`、`FileRunnerProcess`）共用：

- `read_stream_into_queue(stream, queue, buffer_size, encoding, keep_reading)` — reader 執行緒用。行**原樣**進 queue（縮排、行尾、空行都留著）；空讀 = EOF 即停，管線被關掉的 `OSError` / `ValueError` 記 debug 後停。超過 `buffer_size` 的長行分段讀進來：用 incremental decoder 解碼（被切斷的多位元組字元接到下一段），段尾的 `\r` 留到下一段（`\r\n` 被切開時不會變成兩個換行）；不認得的 encoding 退回 UTF-8 並記 warning
- `pump_message_queue(q, append_fn, is_error, max_messages)` — UI 執行緒用。`MAX_MESSAGES_PER_PUMP = 256`：每 tick 只抽一則的話輸出上限只有 ~10 行/秒，聒噪的腳本會爬行；有上界則避免洪水輸出卡住 UI 執行緒。`max_messages=None` 是收尾時一次抽乾。只跳過空字串
- `output_queue()` — 每條管線的 queue 最多 `MAX_QUEUED_MESSAGES`（10,000）則；滿了 reader 就等（每 0.2 秒看一次 `keep_reading`），子行程寫管線也跟著等，跑得跟視窗顯示一樣快，像終端機；以前不設上限，印個不停的腳本會一直吃記憶體，按 Stop 後再一口氣全倒進視窗
- `ReaderGrace` / `any_alive()` — 子行程結束後 reader 還能讀多久（`READER_GRACE_SECONDS = 2.0`，從結束後第一個 tick 起算）。管線要等最後一個握著它的行程結束才會 EOF，子行程開的行程沒轉向輸出時會一直握著；以前兩個執行器在 UI 執行緒上各 join 2 秒，IDE 卡 4 秒還是丟掉之後的輸出。現在由 pump 逐 tick 詢問，時間到就結束執行並在視窗註明
- 執行器寫進執行視窗、說明這次執行本身的訊息（`[Error] Command not found: …`、`[Compile]`、`[Run]`、`[Stopped]`、`[Mail] …`、`Task exit with code …`、行程仍握著輸出的註明，共 15 種）一律經 `run_notice.run_notice(名稱, **欄位)`：取語言字典的 `run_window_<名稱>` 填入欄位，字典沒有時（腳本、測試在 `update_language_dict()` 之前啟動執行器）退回 PyBreeze 的英文；`test_run_notice.py` 擋掉在執行器裡直接寫 `"[Error] …"` 字串
- 執行視窗上方有「停止」按鈕：執行器在子行程跑起來後呼叫 `CodeWindow.run_started()` 打開它，`run_ended()` 關掉它，按下去走 `stop_runner()`（`stop_tree` 停掉子行程和它開的所有行程）；關掉執行視窗不會停止執行。Run > Stop All Program（JEditor 的 `run_menu.stop_all_program_action`，本來只停 JEditor 自己選單開的程式）另接到 `PyBreezeMainWindow.stop_all_runs()`，對每個執行視窗呼叫 `stop_runner()`，視窗與輸出留著。
- `CodeWindow.append_output(text, is_error, own_line=False)`（`show_code_window/code_window.py`，輸出是上限 10,000 行的 `QPlainTextEdit`：`QTextEdit` 到上限後每寫一行要花約 15 ms 丟掉最舊的一行）— 一律寫在文件**尾端**（不用 widget 自己的游標：那個游標跟著使用者的點擊與選取走，寫在那裡會把輸出插進中間、或蓋掉使用者選取的文字）。終端機控制碼（CSI 顏色與游標移動、OSC 等控制字串、`ESC ( B` 這類 nF 與其他兩位元組 escape）先拿掉、backspace 套用到前一個字元、tab、換行、`\r` 以外的控制字元丟掉（與 SSH terminal 共用 `utils/terminal_text.strip_terminal_controls()`；讀取切斷在 escape 中間時，reader 把尾巴留給下一段，`queue_pump` 的 `split_incomplete_escape()`），`\r\n` 是換行，單獨的 `\r` 像終端機一樣回到行首、由後面的文字取代這一行（`pybreeze_ui/terminal_view.insert_rewinding()`；結尾的 `\r` 記在 `_rewind_pending`，等下一段來才套用：接著是 `\n` 就是換行，否則回捲，跑完的進度條不會被清掉）；輸出用等寬字型（`fixed_pitch.use_fixed_pitch_font()`：有 Consolas 用 Consolas，否則系統的等寬字型，Windows 上是 Courier New，與 SSH terminal 共用）；換行只出現在文字本身有換行的地方，所以超過 buffer 被切段的長行會接回同一行。`own_line=True` 給視窗自己的狀態訊息（`Task exit with code …`），程式留下沒換行的半行時先補一個換行。捲軸在最底時畫面跟著輸出走（像終端機）；使用者往上捲去讀時就停在原處

### 4.6 語言伺服器 `extend/language_server/`

另一種由 IDE 啟動的行程，但不是執行器：它不跑使用者的腳本，而是回答編輯器對動作腳本（`.json`）的詢問（`docs/adr/0010`）。

- **`launch.py`**(42) — `server_command(interpreter, language)` 組出啟動指令 `[sys.executable, <…/language_server/__main__.py>, --language …, --interpreter …]`；`offer_to_jeditor()` 把它寫進 JEditor 的 `DEFAULT_SERVERS[".json"]`（JEditor 的 `LspClient.start_for()` 依副檔名查這張表，用 `QProcess` 啟動）。`can_serve()`：打包版的 `sys.executable` 是 app 本身，沒有直譯器可以跑伺服器，就不提供。主視窗 `_offer_language_server()` 在選單建好後呼叫它（這時才知道啟動語言），並讓 JEditor 還原出來、已經開著 `.json` 的分頁重新 `start_language_server()`。
- **`__main__.py`**(17) — 進入點。IDE 用**檔案路徑**啟動它而不是 `-m`：`-m` 會把行程的工作目錄放在 import path 最前面，而 IDE 的工作目錄是使用者開的專案，裡面若有一個叫 `pybreeze` 的套件就會被匯入。用路徑啟動時 `sys.path[0]` 是這個資料夾，進入點把它換成 PyBreeze 所在的資料夾。`python -m pybreeze.extend.language_server` 也能用（給其他編輯器）。
- **`server_main.py`**(59) — `main(argv)`：`--interpreter`（執行腳本的 Python，預設是跑伺服器的這一個）、`--language`（JEditor 的語言名稱；`words_of()` 從 `supported_languages.MAINTAINED` 取該語言的字典，不是維護中的語言就用英文）。建立 `ActionLanguageServer`，對 `PROFILES` 的每個框架各給 `serve()` 一個工作 `ask_framework()`：在自己的執行緒上 `read_metadata()`，回傳「把結果交給伺服器」的那一步（`server.offer(metadata)` 或 `server.decline(framework, reason)`）。

實測：啟動後 0.3 秒回覆 `initialize`，2.7 秒內三個框架的關鍵字都到齊（WebRunner 0.9 秒、AutoControl 0.6 秒、LoadDensity 2.5 秒，平行）。

---

## 5. 選單層 `pybreeze_ui/menu/`

`build_menubar.py:add_menu_to_menubar()` 是唯一入口，依序建構 15 個選單建構器。`menu_utils.py` 的 `open_web_browser()` 讓各選單的 Help 連結開成內嵌瀏覽器分頁；`pybreeze_ui/busy_cursor.busy_cursor()` 在選單項目於 UI 執行緒建 widget 時顯示等待游標（第一個瀏覽器分頁要啟動 Chromium，約 2.5 秒；SSH 第一次開要 import paramiko，約 0.7 秒），Tools 的分頁與 dock、自動化套件的 GUI、Help 頁與 JupyterLab 分頁都經過它；`extend_jeditor_tab_menu/jupyter_lab_tab.py` 的 `extend_tab_tools_menu()` 把 JupyterLab 分頁加進 JEditor 的分頁選單。

### 5.1 `automation_menu_factory.py` — 選單工廠

`build_automation_menu(ui, spec)` 依一份 `AutomationMenu` 描述組出標準自動化子選單：`Run` 子選單（`RunAction` 列表）/ `Help`（`HelpLink` 列表，文件＋GitHub，開內嵌瀏覽器分頁）/ `Project`（建立範本目錄）/ GUI 分頁（`gui_widget_factory`，選到才呼叫，套件可以到那時才 import 它的 GUI），每一段各由一個小函式建（`_add_run_menu` 等），沒有項目的段落不建。三個描述都是 frozen dataclass。六個自動化模組全部靠它，`build_*_menu.py` 只剩一份 `AutomationMenu(...)`；Run 子選單的四項由 `package_run_actions()` 產生（§4.3）。每個 QAction 都以它所在的選單為 parent，由 Qt 持有；AutoControl 額外的 `Record` 子選單也一樣；它的停止錄製不論前面是哪個分頁都會停，把動作以 AutoControl 執行器讀的 JSON 插在編輯分頁的游標處（沒有編輯分頁就放剪貼簿），沒錄到東西就告知。`je_auto_control` 一 import 就把行程設成 system DPI aware，所以這個模組只在用到時才 import 它（`_auto_control()`、`_autocontrol_gui()`）：跟著選單在應用程式建立前 import，Qt 就設不成 per-monitor v2（每次啟動都警告 `SetProcessDpiAwarenessContext() failed`），在縮放比例跟主螢幕不同的螢幕上，Windows 把整個 IDE 當點陣圖拉伸。`test_startup_imports.py` 守著這點，也守著三個 GUI 與 SSH 用到時才 import：跟著選單一起 import 時，光是 import 主視窗模組就要 6.45 秒（中位數），現在 4.65 秒。

`safe_create_project(ui, import_name)` 回傳延遲 import 的 closure：專案建在 IDE 開著的資料夾（`working_dir`，沒開就用行程的工作目錄）；套件的資料夾（`create_project_dir` 的 `parent_name` 預設值）已存在時先問（預設否），因為各套件一律覆寫範本檔；模組沒裝、寫入失敗都跳警告並記 log，成功時說出建在哪裡。

| 選單 | 文件 | GUI 分頁 |
|---|---|---|
| APITestka | apitestka.readthedocs.io | `APITestkaWidget`（開分頁時才 import） |
| AutoControl | autocontrol.readthedocs.io | `AutoControlGUIWidget`（開分頁時才 import） |
| WebRunner | webrunner.readthedocs.io | — |
| LoadDensity | loaddensity.readthedocs.io | `LoadDensityWidget`（開分頁時才 import：套件會帶進 locust 與 gevent） |
| FileAutomation | fileautomation.readthedocs.io | — |
| MailThunder | mailthunder.readthedocs.io | — |

### 5.2 非工廠的兩個選單

- **`test_pioneer_menu/`** — 建範本目錄（寫在 IDE 的工作目錄，已有範本先問是否取代，寫入失敗跳警告）+ `QFileDialog` 選 `.yml` / `.yaml`（副檔名清單與語法高亮共用 `syntax_keyword.TEST_PIONEER_SUFFIXES`；會驗副檔名，選錯跳 `QMessageBox`）+ Help 子選單（`add_help_menu`，只有 GitHub：它的 readthedocs 網站沒有建出來）
- **`prthinker_menu/`** — 審查目前檔案（先照 Run with... 的方式存檔：`save_current_file_for_run()`）/ 審查 PR（`QInputDialog` 問編號，範圍 1–1,000,000）/ 設定對話框 / Help

### 5.3 `tools/tools_menu.py` — 一張表的工具註冊

每個工具在 `TOOLS: dict[str, ToolDescriptor]` 裡只有一行（`_tool(key, words, factory, ...)`），Tools 選單、Dock 選單與導覽面板都從這一張表建出來。原本是四張以同一個字串為鍵的表（`_WIDGET_FACTORIES`、`_TAB_ACTIONS`、`_DOCK_ACTIONS`、`_DOCK_TITLES`），新增一個工具要改四處：

- `ToolDescriptor`（frozen dataclass）：`key`、`words`（四個語言鍵的詞幹：`extend_tools_menu_<words>` 接 `TOOL_WORD_SUFFIXES` 的 `_tab_action`／`_tab_label`／`_dock_action`／`_dock_title`，由 property 組出來）、`factory`（SSH 的經 `_ssh_widget()`，第一次開才 import：paramiko 與 cryptography 約佔啟動的六分之一秒）、`tab_attribute`／`dock_attribute`（把 QAction 掛在主視窗上的屬性名，預設 `tools_<words>_action`／`tools_<words>_dock_action`，五個歷史上不規則的照原樣指定）、`group`（列在哪個子選單：無、`ssh`、`ai`，對應 `_GROUP_MENUS`）、`category`（導覽面板把它列在哪一類：`tools`、`mcp`、`reports`）
- `test_language_keys_used.py` 認得 `_tool("<key>", "<words>"` 這個寫法，四個語言鍵不必在原始碼裡各寫一次
- 同一個工具也能開成右側 dock（`add_dock()`、`closing.AskingDock`：關 dock 前先問 widget 的 `may_close()`，有未存變更的提示詞與架構圖編輯器不會被 dock 的關閉鈕直接丟掉）；AI 類的 dock 放進 JEditor Dock 選單原有的 AI 子選單（`dock_ai_menu`），沒有才自己建一個
- `build_tool_widget(window, key)` 是分頁與 dock 共用的建構點：包在 `busy_cursor()` 裡呼叫 factory，再用 `design.tokens.apply_spacing()` 給 widget 的最外層 layout 標準的邊距與間距；自己把邊距設成 0 的（架構圖編輯器的畫布貼齊分頁邊緣）不動

`_register_action()` 有一段關鍵註解：QAction 必須 `setattr` 掛回主視窗，否則 Qt 不持有它、被 GC 後選單項就失效。另一種做法是建構時把選單當 parent（自動化選單工廠、插件選單用這種）。`test_started_menus.py` 在子行程啟動真的 IDE、GC 後走訪整條選單列，任何子選單變空就失敗（JEditor 的兩個字型選單除外：offscreen 平台沒有字型）。

### 5.4 插件選單

- **`build_plugin_menu.py`** — 讀 `je_editor.plugins.get_all_plugin_metadata()`，每個插件一個子選單（About + 一個 Run 動作，多個副檔名時一併列在標籤裡，動作直接呼叫 `run_current_file_with()`）；另有「Plugin Browser」分頁入口，沒有任何插件時選單也照建、只有這一項（第一個插件就是從它裝的）。插件是第三方程式：不是 dict 的 metadata 或 run config 略過並記 log，名稱經 `plugin_text()` 轉成文字（`addMenu(None)` 會讓 Qt access violation），每個插件的選單各自建、失敗只少它自己那一項
- **`build_run_with_menu.py`** — 讀 `get_all_plugin_run_configs()`，在 Run 選單下加「Run with…」。`run_config_suffixes()` 把插件登記的副檔名正規化成 `Path.suffix` 的樣子（小寫、一個前導點；JEditor 原樣保存，`.R`、`r` 以前永遠比對不上）。`run_current_file_with()` 先經 `save_current_file_for_run()` 存檔（已有檔名的分頁照 JEditor 自己存檔的方式寫：`write_file_with_encoding()` 用分頁的編碼與行尾，寫成功後才 `mark_ignore_next_file_change()` 與 `mark_saved()`；存檔失敗跳警告、不執行；沒檔名的走 JEditor 的另存新檔），再驗副檔名、交給 `FileRunnerProcess`。Plugins 選單的 Run 動作也走這一條

### 5.5 安裝選單

`install_utils.install_packages()` 用 `build_task_process()` 開一個執行視窗，`start_module_process("pip", ["install", "-U", *packages])`：參數清單、不經 shell（以前借 JEditor 的 `ShellManager`，它用 `shell=True` 交給 `cmd.exe`，使用者選的資料夾名稱裡有 `&` 就會把指令切開）。多個套件一次 pip（建置工具以前是三個 pip 同時對同一個環境跑）。pip 用 IDE 選定的直譯器，沒選時照一般執行的退路。`install_package()` 是單一套件的寫法

- `automation_menu/` — 八個自動化套件的一鍵安裝（PyPI 上的七個列在 `PYPI_PACKAGES`）。**prthinker 例外**：不在 PyPI 上，第一次會問來源資料夾、記進設定，之後裝 `<path>[runner]`
- `tools_menu/` — 安裝 setuptools / build / wheel

### 5.6 導覽面板 `pybreeze_ui/navigation/` 與設計系統 `pybreeze_ui/design/`

**導覽面板**是主視窗左側的一個 dock（`NavigationDock`，普通的 `QDockWidget`，關掉只是隱藏），把原本藏在最多四層選單裡的功能列成一棵一直看得到、可以搜尋的樹。它自己不定義任何功能：

- `navigation_model.py`(151)：`CATEGORIES` 依序是 Automation、Tools、MCP、Reports、Settings；`build_navigation(window)` 回傳每一類的 `NavigationEntry`（文字、`activate`、子項）。Automation 是整個 `automation_menu` 的鏡像（`entries_from_menu()`：分隔線、隱藏的項目、空的子選單略過，`&` 助記符去掉）；Tools／MCP／Reports 取自 `TOOLS` 中該 `category` 的工具，文字用分頁標籤、`activate` 就是分頁 action 的 `trigger`，有 `group` 的收在以子選單標題命名的一行底下；Settings 是 JEditor 的 UI Style 選單（JEditor 沒留屬性，靠 `style_menu_label` 這個字在選單列上找）、`language_menu`、`venv_menu` 與 PyBreeze 的 `install_menu`，找不到的就不列。沒有內容的類別整個不列，所以 MCP 與 Reports 要等有那一類的工具註冊才出現
- 子選單一律用 `submenus_under()` 找（`findChildren(QMenu)` 加每個選單的 `menuAction()`），不呼叫 `QAction.menu()`：PySide6 6.11.0 之下它回傳的物件被丟掉時會把選單一起刪掉（這個版本上 11 個選單測試失敗就是這個原因），讀選單不該動到選單
- `navigation_dock.py`(128)：搜尋框加 `QTreeWidget`。輸入文字只留下含有它的行與它們的上層（不分大小寫；某一行符合就保留它底下全部；類別自己的標題不參與搜尋，不然打「Tools」會列出所有工具），都沒有就以 `StatusLine` 說沒有符合的項目；Enter 或按兩下執行該行的 `activate`，action 已經不在了（`RuntimeError`）只記 log
- 顯示與否記在 `~/.pybreeze/ui_state.json`（`utils/ui_state.py`），而且只在使用者表示的時候記：Dock 選單裡那個項目的 `triggered`，或面板自己的關閉鈕（`closeEvent`）。不接 `toggled`／`visibilityChanged`，因為 IDE 關閉時那個項目的勾選狀態也會變，每次離開都會被記成隱藏

**設計系統**是 PyBreeze 自己的面板共用的尺寸與零件，讓面板不必各自寫像素：

- `tokens.py`(117)：一切以 em（目前字型的高度）計。`Space`（HAIRLINE 0.25、TIGHT 0.5、NORMAL 1、SECTION 1.5）、`TextRole`（CAPTION 0.9、BODY 1、TITLE 1.15、HEADING 1.4，後兩者粗體）、`IconSize`（1、1.5、2）、`State`（NEUTRAL／SUCCESS／WARNING／ERROR，值是 JEditor 主題色的鍵，`state_colour()` 從 `actually_color_dict` 取，沒有就用文字色）；`em()`、`space()`、`text_font()`、`icon_size()`、`apply_spacing(layout)`。字型變大、螢幕變密、主題換字級時面板維持比例，深色與淺色主題下顏色都讀得到
- `flow_layout.py`(101)：`FlowLayout`，一列控制項由左到右排，下一個放不下就換行（`hasHeightForWidth`），所以面板的最小寬度是最寬的那一個控制項，不是全部加起來
- `panels.py`(78)：`Panel`（有標題的群組，標準邊距）、`StatusLine`（一行結果，依 `State` 上色）、`wrapping_row(*controls)`。標題與訊息一律 `PlainText`，可能來自檔案或伺服器
- 目前的使用者：導覽面板；`build_tool_widget()` 給每個工具標準邊距；Response Inspector 的四顆轉交按鈕、架構圖編輯器的兩列工具列、提示詞編輯器的底列改用會換行的列，HAR Import 的摘要與提示詞編輯器的資料夾標籤可以換行／縮窄。三個原本比 1280 px 螢幕還寬的工具（12 px 字型下 1382、1176、994 px）現在都在 60 em 以內，`test_tools_fit_small_screens.py` 對每個工具守著寬 60 em、高 30 em
- 主視窗本身的最小寬度仍有約 1770 px（12 px 字型），全部來自 JEditor 編輯器分頁裡的 Git 面板，那是編輯器核心的事（`progress.md` #126）

---

## 6. 工具分頁 `pybreeze_ui/tools_gui/`（15 個工具 widget + 2 個共用機制）

每個工具都是 `QWidget`，UI 極薄，真正邏輯全在 `pybreeze/utils/` 對應的純函式套件裡（所以測得動、也測了）。

| 工具 widget | 對應 utils | 功能 |
|---|---|---|
| `CurlImportGUI` | `utils/curl_import/`、`utils/import_targets/` | 貼上 curl 指令 → 產生 requests / pytest / APITestka(py & json) / LoadDensity 腳本；有哪些目標、各自怎麼產生、存檔的檔名與副檔名都問 `IMPORT_TARGETS`，分頁自己不認得任何一個目標；輸出下方的 `gaps_line`（`StatusLine`）說選定的目標沒送出請求的哪些部分 |
| `HarImportGUI` | `utils/har_import/`、`utils/import_targets/` | 開 `.har` → 列出錄到的請求（可只看 API-like）→ 批次產生腳本，目標與 cURL 分頁同一份 `IMPORT_TARGETS`，同樣有 `gaps_line`（選到的每個請求少了什麼，合起來每個部分只說一次） |
| `JwtDecoderGUI` | `utils/jwt_tools/` | 解 JWT header/payload（不驗簽），時間戳轉可讀 UTC；貼上的文字先去掉空白，不是單純的 token 就取出裡面第一個（`Bearer `、引號、換行都可以），base64url 嚴格解碼；五段、標頭有 `enc` 的是 JWE（RFC 7516），回報 `encrypted_jwt_error`，不說成段數不對 |
| `TimestampGUI` | `utils/timestamp_tools/` | epoch（依大小自動判秒／毫秒／微秒／奈秒；整數用 `int()`、小數用 `Decimal` 精確換算，一律往過去截到微秒）↔ ISO-8601（`_ISO_RE` 自己解析，3.10 到 3.14 讀法一致：`Z`/`z`、`±HH`、`±HHMM`、任意位數小數、basic 格式；八位數而且是合法日期就當 `YYYYMMDD`；RFC 9557 後綴 `[...]` 由 `_without_suffixes()` 從尾端線性剝掉，前面必須有偏移量；都不是就試 HTTP 日期 `_from_http_date()`（`email.utils.parsedate_to_datetime`，IMF-fixdate、RFC 850、asctime，沒有時區當 GMT））。epoch 換算用 `utc_from_epoch_seconds()`（epoch + `timedelta`；`datetime.fromtimestamp` 在 Windows 上拒絕 1970 年前幾小時以外的值），JWT 的時間戳 claim 也用它 |
| `HashGUI` | `utils/hash_tools/` | 多演算法摘要 |
| `QueryJsonGUI` | `utils/query_tools/` | query string ↔ JSON 雙向 |
| `UrlBuilderGUI` | `utils/url_tools/` | URL 拆成 JSON 元件 / 由元件組回 URL |
| `RegexGUI` | `utils/regex_tools/` | regex 測試，flag 勾選、列出每個 match 與群組。pattern 在另一個行程裡跑（`find_matches_bounded()`：從原始碼執行時是 `python -I -S -c` 跑一段只用標準函式庫的固定腳本，工作用 JSON 從 stdin 進、結果從 stdout 出，5 秒後 kill；打包版沒有直譯器可用，仍是 multiprocessing spawn），分頁用 `RegexMatchThread` 等它：`re` 開始比對後就停不下來，災難性回溯只有整個行程能停。spawn 會重新匯入啟動 IDE 的腳本，README 那種沒有 `__main__` 防護的腳本會每跑一次就再開一個 IDE。還在跑的 worker 記在 `_RUNNING`，分頁關閉時 `stop_running_workers()` 結束它（IDE 以 `os._exit` 結束，子行程不會跟著走）；執行中不能存檔，列到 `MAX_MATCHES` 上限時會註明可能還有更多 |
| `HttpStatusGUI` | `utils/http_reference/` | 狀態碼參考，可依碼前綴、描述或 RFC 9110 取代前的舊名稱搜尋；用詞在每個 Python 上都照 3.14（`_CURRENT_WORDS`） |
| `DiffGUI` | `utils/diff_tools/` | unified diff + 增刪統計，`compare_texts()` 的統計與 diff 共用同一次比對（`_TrimmedMatcher`：先把相同的開頭結尾放一邊再比對中間，長而重複的文字改一行就是一行；放一邊有時反而比對得更差（`b b a b a` 對 `b a c b`），所以有放一邊、且兩段合計不超過 2,000 行時，`_closest_match` 也照原樣比一次，取改動行數少的（更大的文字再比一次會讓等待加倍）；autojunk 照 difflib 的預設，關掉的話重複的文字比對時間隨行數平方成長；diff 照 `difflib.unified_diff` 的格式從它的 grouped opcodes 寫出），在 `DiffThread` 上算、不佔 UI 執行緒（4 萬行要四秒多），比對中按鈕停用、關閉時交給 `let_run_out()`。逐行比不出差別、文字卻不同時（最後少一個換行、`\r\n` 對 `\n`），改成連行尾一起比：少換行的那行下面標 `\ No newline at end of file`，其他行尾寫出來。輸出由 `UnifiedDiffHighlighter` 依行首上色（`diff_line_colour()`：`@@`、`+`、`-`、`\ No newline` 各用 JEditor 的主題色，深色淺色各一組；只有前兩行算 `---`/`+++` 標頭） |
| `JsonFormatGUI` | `utils/json_format/` | 美化 / 壓縮 / 驗證 |
| `JsonEditorGUI`(398) + `JsonTreePanel`(338，`json_tree_panel.py`) | `utils/json_format/json_document.py`、`json_tree_edit.py` | 視覺化 JSON 編輯器（`docs/adr/0009`）：同一份 `JsonDocument` 的兩個檢視。**文字**檢視的內容就是文件的文字，每按一鍵 `set_text()`，不是 JSON 時照樣留著、可以存檔，檢視下方的 `StatusLine` 說錯在第幾行第幾欄；**樹狀**檢視（`JsonTreePanel`：Key / Value / Type 三欄、新增／刪除／上移／下移、類型下拉）不持有文件，只把編輯「提出來」（`edit_asked(edit, select)`：`edit()` 回新的樹或丟 `JsonEditError`），由分頁用 `set_tree()` 帶著 revision 做，再從文件重畫兩個檢視，所以樹不會跑在文字前面，被拒絕的編輯什麼都沒改。只有成員的名稱與字串／數字／布林的值可以在格子裡直接輸入（`_CellDelegate` 問 `may_type_into()`）。一個值的子項目在它被展開時才建立（`_fill()`，一次 `addChildren`），不是整份文件：520 KB／35,000 個值的檔案開啟約 280 ms、一次樹狀編輯約 480 ms。復原只有一份歷史（`QUndoStack`，200 步）：一步是文件編輯前後的文字（`_DocumentChange`），樹狀的一次編輯是一步，一段連續輸入合成一步（樹狀編輯、存檔、切換檢視都會結束這一段）；文字框自己的復原關掉，Ctrl+Z／Ctrl+Y 由 `_DocumentText.keyPressEvent` 交給堆疊。排版跟著文字走：文字每次被給定（開啟、輸入、復原）就用 `detect_options()` 讀出縮排、結尾換行與是否跳脫非 ASCII，寫進文件的 `options`，下一次樹狀編輯照它寫回。開檔經 `read_text_capped()`（`utf-8-sig`）與 `escape_for_view()`，存檔經 `replace_text()`；有未儲存變更時 `may_close()` 與開啟另一個檔案都先問（預設「否」） |
| `HeaderAnalyzerGUI` | `utils/header_tools/` | HTTP header 安全稽核（HSTS、CSP、CORS、Set-Cookie、banner…）；「將發現匯出為 SARIF」把目前這次分析存成 `.sarif`（`header_sarif.write_sarif()`，和命令列同一條路；還沒分析時按鈕停用，寫不進去跳警告） |
| `ResponseInspectorGUI` | `utils/response_inspector/` | 貼整包 response → 拆狀態列/headers/body，順便挖出 JWT；`curl -i` 印出的多段回應（`100 Continue`、proxy 的 `Connection established`、`-L` 的轉址）取最後一段；只有一行又沒有狀態列就當 body |
| `KeywordReferenceGUI`(281) + `KeywordReadThread` | `utils/language_service/`（`metadata_probe.py`、`action_adapter.py`） | 自動化關鍵字：三個框架各自安裝的版本實際提供的關鍵字（和編輯器補全、檢查用的是同一份中繼資料、同一個直譯器：`main_window.python_compiler`，沒選就是 `default_interpreter()`）。框架下拉、篩選（名稱或說明）、關鍵字清單、右側顯示簽名＋說明＋定義位置、「複製成動作」（`["WR_to_url", {"url": null}]`，必填參數先列出來）、狀態列說版本、關鍵字數與編輯器能提供的能力，讀不到時說原因（`error_text()` 翻譯 `exception_tags` 的理由）。第一次顯示（`showEvent`）才讀，讀過的框架留著，「重新讀取」丟掉重讀。讀取在 `KeywordReadThread` 上（`read_metadata()` 會在子行程匯入框架，要幾秒）；一次只讀一個，讀取中選了別的框架，等這一個回答後接著讀（用分頁自己記的 `_reading` 判斷而不是執行緒的 `isRunning()`：執行緒回答之後還會「執行中」一小段時間，那時要求的讀取曾經永遠沒被啟動）。執行中的讀取執行緒由模組層的 `_READING` 留到結束，分頁沒經過 `closeEvent` 就被刪掉也不會毀掉執行中的 QThread |

### 兩個橫向共用機制

- **`tool_tabs.open_tool_tab()`** — 工具之間互相「轉交」：Response Inspector 把狀態碼丟給 HTTP Status、headers 丟給 Header Analyzer、JWT 丟給 JWT Decoder、JSON body 丟給 JSON Format；curl 匯入把 URL 丟給 URL Builder。開新分頁並自動聚焦。
- **`pybreeze_ui/busy_cursor.busy_cursor()`**（不在 `tools_gui/` 裡）— JSON Format 的格式化與壓縮、HAR Import 的載入、Response Inspector 的分析在 UI 執行緒上處理整段輸入，幾 MB 就要幾秒（3.3 MB 的 JSON：排版約 1.2 秒、顯示約 2 秒），期間顯示等待游標
- **`pybreeze_ui/run_shortcut.press_on_ctrl_enter()`**（不在 `tools_gui/` 裡）— 只有一個主要動作的工具（cURL、Diff、Hash、Header、JSON Format、JWT、Regex、Response）在工具裡任何地方按 Ctrl+Enter 就等於按那顆鈕（文字框裡的 Enter 是換行）；shortcut 是工具的子物件、`WidgetWithChildrenShortcut`，焦點不在工具裡時不會搶走編輯器的按鍵，按鈕停用時（還在跑）不會觸發；AI Code Review、CoT Code Review 與 Skill Send 的送出鈕也用它；雙向的 Query ↔ JSON 與 URL Builder 用 `act_on_ctrl_enter()` 接到 `convert_as_pasted()`，輸入是 JSON 物件就往另一個方向轉
- **`import_gaps.gaps_text(target, requests)`** — cURL 與 HAR 兩個分頁共用：把 `TargetDescriptor.unrepresented()` 回報的部分換成語言字典裡的名稱（`request_part_*`），依 `RequestPart` 的順序接成一行（「這個目標不會送出：標頭 · 本文」，部分之間用中間點隔開，各語言相同）；什麼都沒少就是空字串、那一行不顯示。只說是哪一類，不說值
- **`output_actions.OutputActions`** — 統一的「複製 / 在編輯器開啟 / 存檔」三顆按鈕，綁在工具的唯讀輸出 `QTextEdit` 上，輸出也經 `exact_text()` 讀（不讓 U+00A0、U+2028 被改掉）；副檔名與檔名可傳 callable 動態決定。存檔經 `replace_text()` 整檔替換，失敗（唯讀資料夾、被鎖住的檔案、磁碟滿）時原檔不動、會跳警告，說出檔名與原因。Qt 的文字元件留不住貼上的 CR，換行一律讀成 LF

---

## 7. `pybreeze_ui/diagram_editor/` — 架構圖編輯器（4,055 行，最大子系統）

| 檔案 | 職責 |
|---|---|
| `diagram_editor_widget.py` (695) | 外層 widget：兩排工具列（工具模式列 + 檔案/undo/對齊/格線/匯出/縮放列）、canvas 與屬性面板的 splitter、快捷鍵（只在編輯器有焦點時作用，當 dock 開著也不搶程式碼編輯器的按鍵）；PNG/SVG 匯出；Mermaid 匯入對話框。「從 URL 加入圖片」也交給 `ImageDownloadThread`，圖片回來才放上畫布，失敗或不是圖片就跳警告；關閉時還在跑的下載交給 `let_run_out()`。存檔經 `replace_text()` 先寫 `<name>.saving` 再換上去，存檔失敗不會毀掉上一份 |
| `diagram_scene.py` (915) | `DiagramScene(QGraphicsScene)`：**State pattern** 的 `ToolMode` 決定滑鼠行為；undo/redo、複製貼上（節點、連線與圖片）、多選對齊與分佈、z-order、序列化 `to_dict()` / `load_from_dict()`。`get_all_nodes/connections/images()` 由下往上列出（`_bottom_first()`），存檔與 undo 還原時同 z 值的重疊項目維持原本的上下；右鍵選單先選取點到的項目；置頂／置底放到所有其他節點與圖片之上／之下；`to_dict()` 給每個節點與圖片記下它在兩者之間由下往上的位置（`stack`），載入後 `_restore_stacking()` 照這個順序重新加回場景（同 z 值時後加的在上面），圖片也存 `z`。`load_from_dict()` 先用 `_check_is_a_diagram()` 確認資料形狀才清空畫布（不合就丟 `ValueError`，畫布原封不動），每一筆節點／連線／圖片再各自容錯；清空前先 `to_dict()` 留一份，載入途中還是出錯就放回原樣再往上丟——載入要嘛成功、要嘛什麼都沒變（編輯器存檔寫回上次開的檔案，半途清空的畫布會蓋掉使用者的檔）。圖片的 `source` 不是字串就丟掉。`undo_scope` 用 `try/finally`，本體丟例外也一定收掉快照；圖片來源先看副檔名、拒絕 UNC（`_is_on_this_machine()`）才碰檔案系統；URL 圖片交給 `ImageDownloadThread(QThread)` 下載並快取在 `_pixmap_cache`，undo/redo 重建項目時直接用快取，不會再連一次網路；編輯器關閉時 `let_image_downloads_run_out()` 把還在跑的下載交給 `let_run_out()`，不在 UI 執行緒等 |
| `diagram_items.py` (962) | 圖元：`DiagramNode`（矩形/圓角/橢圓/菱形 4 種 body + 置中標籤 + 4 個 `ResizeHandle`；填色、框線色、字級收在 frozen dataclass `NodeStyle`）、`DiagramConnection`（三次貝茲 + 箭頭，連到節點邊界交點）、`DiagramImage`。`_EditableLabel` 刻意預設唯讀、雙擊才進編輯（對應 CLAUDE.md 的 Qt 規範）；雙擊時記下場景快照，失去焦點時經 `DiagramScene.record_change()` 記成一步「Edit Text」undo（有改才記）。`DiagramScene.add_image()`（`diagram_scene.py`）把圖放進 scene 的 `_pixmap_cache`，undo 重建時不必重讀檔案或重新下載。檔案裡的字級經 `_clamped_font_size()`：不是有限數字（`1e999` 讀進來是無限大、NaN、字串）就用預設字級；位置經 `_coordinate()`：不是有限數字就跳過這一筆，超過 `MAX_COORDINATE`（一百萬）就夾回來；連線建好所有東西之後才掛到兩端節點上 |
| `diagram_mermaid_parser.py` (850) | Mermaid flowchart → diagram dict。跨行的 markdown 字串（`"`...`"`）由 `_logical_lines()` 併成一行（沒關上的不併）；`_label_text()` 把 markdown 字串換成純文字（`_markdown_text`：去掉粗體、斜體記號，每行去頭尾空白）。Mermaid 11 的 `A@{ shape: ..., label: ... }` 由 `_split_shape_data()` 切出、`_with_shape_data()` 套用：形狀名稱（含別名）經 `_NAMED_SHAPES` 對到四種節點形狀，其餘為矩形；`label` 經 `_label_text()`。`&` 群組與 `@{}` 的逗號都由 `_split_outside()` 在括號與引號外切。先去掉開頭的 YAML front matter（`_without_front_matter`）與可跨行的 `%%{...}%%` 指令（`_without_directives`），`accTitle:`/`accDescr:` 整行與 `accDescr { ... }` 區塊略過。一行先依 `;` 切成敘述，關鍵字（`subgraph`、`end`、`style`、`classDef`、`class`、`click`、`linkStyle`、`direction`）逐敘述略過。切箭頭與 `;` 之前先用 `_protect()` 把引號與括號裡的標籤、以及實體碼（`#35;`）換成佔位符，解析節點時再 `_restore()`（標籤裡的 `-->`、`;` 和實體碼的 `;` 不會被當成語法）。節點文字與連線標籤經 `_label_text()` 照 Mermaid 的顯示方式轉換：`<br>` 換行，再把實體碼換成字元（HTML 字元名稱或十進位；不認得的名稱保留原文）。線型只看 `_link_body()`（箭頭去掉 `|label|` 的部分），標籤裡的 `==`、`-.`、`~~~` 是文字。節點寬度照最長一行，超過兩行起每行加高 `_LINE_H`。箭頭的 `|label|` 由 `_arrow_label()` 用兩個相鄰部分不共用字元的樣式讀（引號標籤一個、一般標籤一個，取最左邊的），線性時間：原本合成一個、標籤兩側可有空白的樣式在未閉合的標籤上是立方時間回溯。含 **Sugiyama 風格自動排版**：分層 → 交叉最小化掃描 → 交叉軸偏移解析 → `_layout_steps()` 依最大的節點決定層距與格距（寬度至少留 200、高度至少 `_NODE_H`），節點置中在格位上（`_position_node`） |
| `diagram_property_panel.py` (453) | 右側屬性側欄，依選取型別切換 node / connection / image 三組表單；每記一步 undo（場景的 `recorded`）就重新整理（在畫布上拖把手改大小時選取沒變）；寬、高各自只改自己那一邊；數字欄位不追鍵盤、輸入完才套用 |
| `diagram_view.py` (228) | `QGraphicsView`：滾輪與按鈕縮放都經 `_step_zoom()`（有上下界，界外時仍可往界內走；橫向滾輪不縮放），`fit()` 把「符合視窗」夾在上下界內、中鍵或右鍵拖曳平移（右鍵拖過畫布就不開右鍵選單，`contextMenuEvent`；放開沒送到它時下一次移動就停止平移）、`drawBackground` 畫格線 |
| `diagram_commands.py` (48) | `DiagramSnapshotCommand(QUndoCommand)` — 快照式 undo，存變更前後完整場景狀態；有 `merge_key` 的連續步驟（同一個項目的同一個屬性：大小、字級、線寬）合併成一步（`id()` / `mergeWith`） |
| `diagram_net_utils.py` (117) | **SSRF 防護參考實作**：scheme 白名單、DNS 解析後比對私有/迴環/link-local/reserved 網段、`_ValidatingRedirectHandler` 對每一跳重驗（驗過就關掉轉址回應，urllib 不會把轉址的內容整個讀完）、`_OPENER` 用 `PublicHTTPHandler` / `PublicHTTPSHandler`（連線當下再檢查一次並只連到那個位址）、20 MB 大小上限、每次等資料 15 秒 timeout，整個下載另有 `overall_deadline(DOWNLOAD_DEADLINE_SECONDS)` 120 秒上限（慢慢送位元組的伺服器原本可以一直卡住下載執行緒） |

`diagram_net_utils` 是 CLAUDE.md 指定的網路安全參考實作，其他 HTTP 呼叫端則統一走 `utils/network/url_validation.py` 驗證、經 `utils/network/public_http.py` 的 `public_session()` 送出。

---

## 8. `pybreeze_ui/extend_ai_gui/` — AI 輔助

```
extend_ai_gui/
├── ai_gui_global_variable.py     模板檔名清單 + 檔名→內建模板內容對照表
├── prompt_store.py               編輯過的 prompt 檔案解析（~/.pybreeze/prompts/；`read_prompt_file()` 讀 utf-8-sig，非 UTF-8 視同讀不到、退回內建；讀取時什麼都不建立（`pybreeze_data_path()`），查檔丟 `OSError` 也退回內建）
├── code_review/
│   ├── cot_chain.py              接線表（純邏輯，無 Qt）：哪步引用哪步
│   ├── code_review_thread.py     SenderThread(QThread)：跑八步審查鏈
│   └── cot_code_review_gui.py    UI（工具 → AI 的分頁與 dock）；URL 只由 worker 驗證，UI 執行緒不查 DNS；沒貼程式碼就不送（整條鏈八個請求都會白跑）；每次送出先清掉上一輪的回覆；關閉時請審查停在目前這一步，交給 let_run_out()，不等
├── prompt_edit_gui/
│   ├── prompt_editor_widget.py         共用編輯器（QFileSystemWatcher 熱更新，watcher 以編輯器為 parent、關閉時停止監看；有未存編輯時，外部改動、「重新載入」和切換模板都先問；還沒有檔案的模板只用 placeholder 說明，存檔不會把說明寫進去）
│   ├── cot_prompt_editor_widget.py     8 個 CoT 模板的檔案清單＋語言鍵
│   ├── skills_prompt_editor_widget.py  2 個 Skill 模板的檔案清單＋語言鍵
│   ├── prompt_file_io.py               共用存檔（經 `replace_text()`：先寫 `.saving` 再換上去；失敗跳警告對話框，不顯示路徑）
│   ├── cot_code_review_prompt_templates/   8 個模板常數＋global_rule
│   └── skills_prompt_templates/            2 個模板常數
└── skills/skills_send_gui.py     單次 prompt 發送（RequestThread：回答走 `answered`，不再蓋掉 QThread 自己的 `finished`；關閉時交給 `thread_keeper.let_run_out()`；換模板前編輯區有修改就先問；prompt 還留著 `{code_diff}` 就不送出）
```

**CoT 審查鏈**（`cot_chain.py` 定義接線，`code_review_thread.py` 執行）八個步驟：

```
first_summary → first_code_review → judge_single_review ┐（評分前一步的審查）
              → linter → code_smell_detector → step_by_step_analysis ┐（走過每條發現）
              → total_summary → judge（帶 linter/code smell 脈絡評分總結）
```

**編輯過的 prompt 會生效**（`prompt_store.py`）：每個模板都以程式碼常數出貨，`~/.pybreeze/prompts/<名稱>.md` 存在且非空時覆寫它。編輯器讀寫的就是這個位置，所以在編輯器裡改 prompt 會改變審查實際送出的內容 —— 這正是編輯器存在的理由。檔案缺失、空白、讀不到都退回內建版本；編輯過的 prompt 若含有鏈填不了的 placeholder，記 log 後退回內建，不讓整次審查倒在使用者無法從 UI 診斷的 `KeyError` 上。讀取不會建目錄，只有存檔才會。

`cot_chain.py` 用兩張表描述接線：`STEP_RESULT_KEY`（每步答案存在哪個 key）與 `STEP_ARGUMENTS`（每步的 placeholder 由哪個 key 填）。**順序即相依順序** —— 每步只能引用它上面的步驟，`test_cot_chain.py` 有結構性測試守住這件事。步驟失敗時錯誤訊息只顯示給使用者、不會被存進 results，避免後續步驟把「傳送失敗」當成審查內容引用。每步都套 `build_global_rule_template()` 包一層全域規則。

安全處理：送出前 `validate_url()`、`allow_redirects=False`、`stream=True` 搭配 `read_capped_text()` 限制回應大小、非 2xx（`succeeded()`）算這一步失敗、不會被後面的步驟引用、單一 `requests.Session` 重用 TCP/TLS 連線、`isInterruptionRequested()` 讓 widget 關閉時能中止。

---

## 9. `pybreeze_ui/connect_gui/`

### `ssh/`（2,517 行）

| 檔案 | 職責 |
|---|---|
| `ssh_main_widget.py` | 組合視圖：上方共用登入表單，下方 splitter 左 30% 檔案樹、右 70% 終端。兩半各自連線、各自發 `state_changed`，共用的狀態列每次有一半連上或斷開就重報兩者的狀態（不是按下按鈕時）。`closeEvent` 把關閉往下傳給兩半（Qt 只會送給被關的那個 widget） |
| `ssh_login_widget.py` | 登入表單（密碼欄用 `EchoMode.Password`；任一欄按 Enter 就按下連線；金鑰欄旁的「瀏覽...」從 `~/.ssh` 開檔案對話框，選了檔就勾起金鑰驗證） |
| `ssh_command_widget.py` | 互動式 shell。連線和開 shell 的 channel（`open_shell_channel()`：開 session 最多等 paramiko 的 `channel_timeout` 一小時，pty 與 shell 沒有逾時；pty 開成 terminal 看得到的大小，`terminal_view.terminal_size()`：以等寬字型算出完整看得到的欄與列，至少 20 × 5）都在 `SshConnectThread` 上做，UI 執行緒只接手啟動 reader；連線中再按 Connect 不理，連線中關掉 widget 時執行緒交給 `let_run_out()`，晚到的連線一結束就關掉。`SSHReaderThread(QThread)` 輪詢 channel（shell 結束時先把緩衝裡剩下的讀完；伺服器那端結束 shell 時 `_on_closed()` 一樣 `_cleanup()` 關掉連線並發 `state_changed`，共用狀態列照兩半的實際狀態重報），`TerminalDecoder` 把每次讀到的 bytes 轉成 `TerminalOutput`：是否先清畫面（`clear`、`reset`：`split_at_screen_clear()`，只留最後一次清除之後的文字，清除前設的顏色延續、`ESC c` 則重設；widget 先 `clear()` 畫面並忘掉待套用的 `\r`），以及一段段帶樣式的文字（SGR 顏色與粗體等由 `utils/terminal_style.split_styled()` 讀出，跨次讀取延續、`reset()` 清掉；畫面用 `terminal_view.style_format()` 轉成 `QTextCharFormat`，一段結尾的單獨 `\r` 記在 `_rewind_pending` 給下一段套用）：UTF-8 字元、escape 與結尾的 `\r` 被讀取切斷時留到下一次接上（`split_unfinished_end()`，`\r\n` 被切開不會多一行空行），escape（CSI、OSC/DCS/SOS/PM/APC 控制字串、`ESC ( B` 這類 nF、其他兩位元組 escape）用 regex 剝除，backspace 套用到前一個字元、其餘 C0 控制字元丟掉（`utils/terminal_text.py` 的 `strip_terminal_controls()`；切斷的 escape 由 `split_incomplete_escape()` 留到下一次）；送出指令走 `send_all()`：整串 UTF-8 bytes 用 `sendall` 送完（`Channel.send` 一次只送一個封包），只在這次送出時給 channel 5 秒逾時；空白的一行也送出（只送換行，用來接受提示的預設值）；沒連線時，空白的一行不跳「尚未連線」提示；「中斷」按鈕與指令列的 Ctrl+C（沒有選取文字時；有選取就照常複製，`eventFilter`）送出 `\x03`（`send_interrupt()`），停止 shell 中正在跑的程式，指令列打到一半的字留著；上下鍵走過送出過的指令（`CommandHistory`：最多 500 行，連續重複只記一次，往下走過最新一行就還回原本打到一半的字）；輸出接在最後一行後面（不用 `appendPlainText`，那會讓每次讀取都另起一行），單獨的 `\r` 回到行首、由後面的文字取代這一行（進度條；與執行視窗共用 `terminal_view.insert_rewinding()`），輸出用等寬字型（`fixed_pitch.use_fixed_pitch_font()`，同執行視窗，欄位對齊的輸出才對得齊），terminal 的 viewport 改變大小、換算成字元數有變時送 `resize_pty`（`_follow_view_size()`，經 `eventFilter`；shell 開好時再對一次，連線中改了大小也跟上；伺服器拒絕時記 log，下次再試），自己的提示訊息才另起一行，terminal 有 block 上限，keepalive。`closeEvent` 一律 `_cleanup()`：執行緒不能活得比 widget 久（QThread 還在跑就被銷毀會讓 Qt abort） |
| `ssh_file_viewer_widget.py` (756) + `sftp_session.py` (473) | `SSHFileTreeManager`（樹與右鍵選單，只看執行緒的 signal 做事；焦點在樹上時 F2 重新命名、Delete 刪除目前項目，走選單同一組動作，`_act_on()` 把斷線的錯誤變成對話框）＋ `sftp_session.py` 的 `SFTPClientWrapper`、`SftpListThread` / `SftpTransferThread` / `SftpCallThread` 與純路徑工具（`remote_join`、`plain_remote_name`、`sort_entries`）：延遲載入的遠端檔案樹、右鍵選單（重新整理/建資料夾/改名/刪除/下載/上傳；新名稱只能是單一項目，`plain_remote_name()` 擋掉 `/`、`.`、`..`；改名已載入的資料夾會用新路徑重列子項；從檔案項目建資料夾或上傳時重新整理它所在的資料夾，`folder_item()`）、目錄優先 + 自然排序（項目是資料夾還是檔案記在 `KIND_ROLE`，`is_folder()` / `is_file()` 讀它，不看類型欄的字）；列目錄時符號連結用 `stat` 換成它指向的東西的類型與大小（`_follow_link`，伺服器列目錄用的是 `lstat`，連到資料夾的連結原本當成檔案），指不到東西的連結照舊當檔案。每個 SFTP 操作都經 `_session()`：拿 `_in_use` 鎖（paramiko 的 SFTP client 會把別的執行緒的回覆讀走丟掉，送出那個請求的執行緒就永遠等下去）、再 `_require_connection()`；列目錄與傳輸在工作執行緒上一直等，右鍵選單的建資料夾／改名／刪除交給 `SftpCallThread`（SFTP 回覆沒有逾時，放在 UI 執行緒會凍到 TCP 放棄），等 session 最多 `UI_WAIT_SECONDS`（1 秒），等不到就丟 `SftpBusy`（「連線忙碌」），完成後才更新樹（樹被清掉就不動）；下載先寫到同資料夾的暫存檔（`.<檔名>.*.part`），完整了才 `os.replace` 換上，失敗就刪掉暫存檔、原檔不動；上傳同理：先 `stat` 目標，已存在又沒說要取代就什麼都不傳、發 `exists` 讓樹先問（預設「否」），再 `put` 到 `.<檔名>.<亂數>.part`，完整了才 `posix_rename`（伺服器沒有這個擴充就先刪再 `rename`）換上；連線交給 `SshConnectThread`，成功後才列出根目錄；`SFTPClientWrapper.connect()` 用區域變數建連線，登入完如果 wrapper 已經被 `close()`（Disconnect 或關分頁）就自己關掉這條連線、丟 `ConnectAbandoned`，失敗時也只關自己的；連線中按 Disconnect 會把連線執行緒交給 `let_run_out()`（不跳「連線失敗」），可以再按 Connect；每次列目錄（根目錄、展開、重新整理）交給 `SftpListThread`，先顯示「載入中」，結果回來時只在樹沒被清掉（`_tree_generation`）、而且該項目等的還是這一次（`LISTING_ROLE` 序號，重新整理會取代前一次）時才填進去；下載／上傳交給 `SftpTransferThread(QThread)`（傳輸沒有自己的逾時，跑在 UI 執行緒會把整個 IDE 凍到傳完），一次只允許一個，傳輸中右鍵選單多一項「取消傳輸」（`SftpTransferThread.cancel()`：paramiko `get` / `put` 的進度回呼每塊都檢查，丟 `TransferCancelled`，暫存檔照失敗處理刪掉、要被取代的檔案不動，發 `cancelled`）；傳輸中按 Connect 不重連檔案樹（連線一開始就 `close()`，會把傳輸砍斷），只提示正在傳輸，`_refused_while_transferring()`；`closeEvent` 不等它也不打斷它（打斷會留下半個檔案），交給 `let_run_out()`，傳完才關掉 SFTP 連線 |
| `ssh_host_key_policy.py` | **`InteractiveHostKeyPolicy`** — 取代 `AutoAddPolicy`。首次連線顯示 SHA256 指紋要使用者確認，確認後寫入 `~/.pybreeze/ssh_known_hosts`（TOFU）。查詢、詢問、寫入都在模組層的 `_DECISION_LOCK` 裡一次一個（只有連線執行緒會拿，UI 執行緒不等它）；問之前先重讀檔案（同一次 Connect 的另一半剛接受過就不再問），使用者拒絕的 (host, 指紋) 記 10 秒（從使用者按「否」起算；因此被拒絕的不重新計時，否則一直按 Connect 就永遠不再問），另一半直接拒絕；寫入時在檔案現況後面加一行（`_store()`），不用 `client.save_host_keys()`（那會用 Connect 時讀到的舊副本蓋掉別的分頁剛接受的主機），也不用 `HostKeys.save()`（paramiko 讀不懂的行，壞行或 `ssh-dss`，會被寫掉）。兩個 known_hosts 都經 `load_known_hosts()` 逐行讀，讀不懂的行跳過（`HostKeys.load` 遇到非 base64 的 key 丟 `InvalidHostKey`，整個 Connect 就失敗）。問題由 `HostKeyAsker`（住在 UI 執行緒的 QObject，`host_key_asker()` 取得，兩個 SSH widget 建立時先建好）顯示：從連線執行緒問時走 `BlockingQueuedConnection`，連線執行緒等答案、UI 不等。每個問題都從「否」開始；發問的面板已經關掉（dock 關閉即刪除）就答「否」，不會沿用上一題的答案。信任過的主機換了金鑰時 paramiko 自己丟 `BadHostKeyException`、不經過這個 policy；`changed_host_key_message()` 把它說成兩個 SHA256 指紋加上該刪哪個檔案的那一行（PyBreeze 的檔案裡這台主機——任何連接埠 `[host]:port`——的那一行就是受信任的金鑰時指它，否則指 `~/.ssh/known_hosts`；同一把金鑰記在別的名稱下不算） |
| `ssh_connect_thread.py` | `SshConnectThread(QThread)`：在自己的執行緒上跑一次會阻塞的 `connect()`，發 `connected` 或 `failed(message)`。`CONNECT_ERRORS` 是連線會丟的例外，其中 `BadHostKeyException` 先接、以 `changed_host_key_message()` 的文字報出（paramiko 原文是兩把 base64 金鑰）；`SHA1_ALGORITHMS` 是每個 `connect()` 都帶上的 `disabled_algorithms`，拒絕 SHA-1 的 RSA 簽章與金鑰交換（paramiko 5 已移除，paramiko 4 仍會提供；CVE-2026-44405）。TCP 10 秒、banner 15 秒、auth 30 秒逾時加起來，連不到的主機以前會把 IDE 凍住將近一分鐘 |
| `ssh_key_loader.py` | 依序嘗試各種私鑰型別，回傳第一個能解析的；paramiko 不讀的 PKCS#8（`BEGIN PRIVATE KEY`／`BEGIN ENCRYPTED PRIVATE KEY`）由 `cryptography` 讀進來、在記憶體裡轉成 OpenSSH 格式再交給 paramiko；都不行時 `unloadable_key_reason()` 分辨是密語沒給／給錯（檔案有加密，而且給的密語解不開它；用 `cryptography` 試解）還是不支援的私鑰（例如加密的 DSA），或是要先匯出成 OpenSSH 格式的 PuTTY `.ppk` 金鑰 |

### `url/ai_code_review_gui.py`

獨立的 HTTP client widget：送出程式碼給審查端點、接受/拒絕回覆並記錄統計到 `~/.pybreeze/response_stats.txt`（開啟時用 `read_stats()` 讀回上次的總數接著算；檔案不是這個格式或讀不了就從 0 開始）。

- 請求走 `ReviewRequestThread(QThread)`，只有 `answered` / `failed` 兩個 signal 碰 UI（和 `SkillsSendGUI` 同一套）；送出中再按不會重送；`closeEvent` 不等它，交給 `thread_keeper.let_run_out()`：斷開它和面板的連線、留著參考直到它結束（等它會讓 IDE 凍住最長一個讀取逾時）
- `urls.txt` 只存 URL 的 SHA-256 指紋（`url_fingerprint()`）：API URL 可能帶權杖，依 CLAUDE.md 要當憑證看待；舊版留下的明文檔會在下次送出時改寫成指紋
- 方法預設 POST（`DEFAULT_METHOD`）；POST／PUT（`METHODS_WITH_A_BODY`）把程式碼照貼上的樣子放進本文的表單欄位 `code`，程式碼是空的就不送、在面板說明；GET／DELETE 只送 URL
- 非 2xx（含不跟隨的轉址）走 `failed`，狀態碼寫進面板，不會只留空白
- 接受/拒絕只在收到回答（`answered`）後可按，每個回答只能評一次；Send 按鈕由執行緒的 `finished` 恢復，請求不論怎麼結束都回得來

---

## 10. `pybreeze_ui/jupyter_lab_gui/`

- `jupyter_lab_thread.py` — `JupyterLauncherThread(QThread)`：`find_free_port()`（綁 127.0.0.1 讓核心挑空 port）→ `choose_python()`（IDE 選定的直譯器優先，否則和執行一樣走 `default_interpreter()`：工作目錄的 `venv`／`.venv`，再來 IDE 自己的；打包版找 PATH，找不到的 `JEditorExecException` 在分頁上顯示原因）→ `installed_jupyter()`（問直譯器 `find_spec('jupyterlab')` 與 jupyterlab、jupyter_server 的版本，不問 pip；缺就以 `pip install -U jupyterlab jupyter_server` 自動裝，pip 以 `utf8_subprocess_env()` 寫 UTF-8、IDE 以 UTF-8 讀，UTF-8 模式的直譯器說的原因才不會變成解碼錯誤；`vulnerable_parts()` 認出 `_VULNERABLE_RELEASES` 裡有頁面能利用的已知漏洞的版本（jupyterlab 4.5.10 之前與 4.6.0–4.6.1、jupyter_server 2.20.0 之前；server 沒有 token）時，`_upgrade()` 先用同一個指令升級並在狀態列說明，升級失敗只記 warning、照樣啟動）→ 啟動 server（`_start_server()`，在 `_process_lock` 裡先看 `_stopped`：`stop()` 之後就不再啟動，即使還在安裝）→ `_wait_until_ready()` 輪詢 port（60 秒 timeout）→ emit `server_ready(url)`。server 的輸出寫進暫存檔而不是管線（server 起來後沒人讀管線，緩衝區滿了它會卡在 `write()`）；提早結束時錯誤訊息取這個檔案的尾巴。失敗時 `error_occurred` 送的是原因（例外訊息，最多 2,000 字），traceback 只進 log；已經 `stop()`（分頁關了）的失敗不算失敗，只記 debug
- `lab_page.py` — `LabPage(QWebEnginePage)`：分頁的 view 只留在 lab 上（`lab_url`：同 scheme、host、port），其他網址的主框架導覽改交給系統瀏覽器（`open_outside()`，只收 http／https）；notebook 連結要開新分頁（`target="_blank"`）時 `createWindow()` 給一個不顯示的 `_NewTab`，它第一次導覽就交給系統瀏覽器再刪掉自己（以前沒有 `createWindow`，點了沒反應）；lab 裡的 iframe 照常載入
- `jupyter_lab_widget.py` — 設 `WA_DeleteOnClose`：分頁關閉就刪掉（`close_tab` 只移除分頁、不刪 widget，網頁檢視與它的 Chromium renderer 會一直留到 IDE 結束）。收到 URL 後用 `QWebEngineView.setUrl()` 載入；失敗時在狀態列顯示「初始化失敗：原因」（純文字、可選取、自動換行）；`closeEvent` 一律關掉 server（launcher 執行緒在 lab 載入完就結束了，只停「還在跑的執行緒」等於從不停 server）；還在安裝或啟動的 launcher 交給 `let_run_out()`，不在 UI 執行緒等（安裝可能要好幾分鐘），也不用 `blockSignals`（那會連 `finished` 一起擋掉，keeper 永遠放不掉它）。IDE 關閉時 `PyBreezeMainWindow._close_tool_tabs_and_docks()` 會關掉所有非編輯器分頁與 `DestroyDock`，這個 `closeEvent` 才會被呼叫到

安全前提（CLAUDE.md 已明列）：server 只綁 localhost，因此 token/password 刻意留空（jupyter_server 2 的 `IdentityProvider.token` / `PasswordIdentityProvider.hashed_password` 與 1.x 的 `ServerApp.token` / `password` 都傳：2.x 讀舊名稱時只記過時警告，只傳舊名稱的話，不再讀它們的版本會自己產生 token，分頁就只剩登入頁）、`disable_check_xsrf=True` 才能內嵌。`--ServerApp.port_retries=0`：port 被占就直接結束（走「提早結束」的回報），不讓它默默換 port。**不設 `allow_origin`**：loopback 擋不住瀏覽器，開放來源的話使用者逛到的任何網頁都能操作這個沒有 token 的 server。

---

## 11. `pybreeze_ui/syntax/`

- `syntax_keyword.py`（629 行）— 七份關鍵字清單，彙整成 `package_keyword_list`：
  `je_auto_control` / `je_load_density` / `je_api_testka` / `je_web_runner` / `automation_file` / `mail_thunder` / `test_pioneer`
- `syntax_extend.py` — 把前六個註冊到 `.json`（黃色，JEditor 主題色鍵 `warning_output_color`），`test_pioneer` 註冊到 `TEST_PIONEER_SUFFIXES` 的每個副檔名（`.yml`、`.yaml`，橘色，`diff_modified_marker_color`）；顏色給的是主題色的鍵而不是固定顏色，JEditor 的 highlighter 每次建立時查 `actually_color_dict`，所以深色與淺色主題各用各的一組，然後重置當前編輯器的 highlighter

`PackageManager.syntax_check_list` 決定要註冊哪些；用 `package_keyword_list.get(pkg, [])` 取值，套件沒有關鍵字清單時註冊空集合而不是炸掉。

---

## 12. `pybreeze/utils/` — 基礎工具（21 個子套件）

| 套件 | 內容 |
|---|---|
| `app_dirs.py` | `pybreeze_data_dir()` → `~/.pybreeze`，所有持久化資料的單一位置，建立時為 `0700`（`DATA_DIR_MODE`）；`pybreeze_data_path()` 只給路徑、不建立 |
| `terminal_text.py` | 終端輸出的 escape 與控制字元：`strip_terminal_controls()`（CSI、OSC/DCS 等控制字串、nF、兩位元組 escape 剝除，backspace 套用，其餘 C0 丟掉）、`split_incomplete_escape()`（讀取切斷在 escape 中間時把尾巴留給下一次）、`split_unfinished_end()`（再加上它前面或最後的 `\r`）、`take_leading_backspaces()`（一段開頭的 backspace 留給畫面，擦掉前一段已經顯示的字，不越過行首）、`split_at_screen_clear()`（最後一個清除整個畫面的序列：`ESC [ 2J`、`ESC [ 3J`、`ESC c`，前後切開；`ESC [ J` 只清游標以下，shell 重畫提示字元時會送，不算）。SSH terminal 與執行視窗共用 |
| `terminal_style.py` | SGR（`ESC [ … m`）讀成 `TextStyle`（frozen dataclass：前景、背景、粗體、斜體、底線、反白）：`apply_sgr()`（16 色與亮色、`38;5;n` 256 色、`38;2;r;g;b` 24 位元色、各開關與 39/49 預設、0 重設；看不懂或格式錯的參數不改任何東西，超過 5 位數的參數略過，`int()` 不收超過 4300 位數）、`split_styled()`（文字在 SGR 處切段，每段帶它的樣式，其餘 escape 留給 `strip_terminal_controls()`）、`colour_rgb(colour, on_dark=)`（前 16 色用 VS Code 終端機的預設值，深色與淺色主題各一組，`terminal_view.style_format()` 依 view 背景的亮度挑；256 色的色塊、灰階與 24 位元色照 xterm）。只有 SSH terminal 用：執行視窗的程式寫到 pipe，不會上色 |
| `subprocess_util.py` | `child_environment()`（`os.environ` 去掉值為 `IDE_ONLY` 的變數：IDE 只給自己設的）、`utf8_subprocess_env()`（以它為底再釘 `PYTHONIOENCODING`，解 Windows cp950 亂碼）、`no_window_creationflags()`（`CREATE_NO_WINDOW`，避免 GUI 程式彈出黑窗） |
| `logging/logger.py` | `pybreeze_logger`（具名 logger，**不動 root logger**）+ `PyBreezeLogger(RotatingFileHandler)`：寫到 `~/.pybreeze/logs/PyBreeze.log`（`PYBREEZE_LOG_FILE` 可改），UTF-8、附加模式、每行帶行程編號，第一筆紀錄才開檔；只在開檔時輪替，門檻 `PYBREEZE_LOG_MAX_BYTES`（預設 100 MB）；開不了檔就改寫 `os.devnull` 並警告一次。與 JEditor、FrontEngine 同一套做法（工作區 X-6） |
| `exception/` | `ITEException` 為根的 18 個例外類別 + `exception_tags.py` 訊息常數；`error_templates.py` 把名稱以 `_error` 結尾的常數變成語言字典的 `error_text_<名稱>`（英文字典直接取常數本身） |
| `network/url_validation.py` | `validate_url()`：先拒絕 `urlparse` 與 `urllib3` 讀出不同主機的 URL（反斜線、空白、控制字元，或兩者主機不同；`_check_one_reading`），再做 scheme 白名單、私有/迴環/link-local/reserved 阻擋、額外處理 CGNAT 與 NAT64 網段、IPv6 內嵌 IPv4 的偵測 |
| `network/public_http.py` | 只連到剛檢查過的位址（防 DNS rebinding）：`public_session()`（`_NoRedirectSession`：不跟也不準備轉址，3xx 原封不讀地回來；`PublicAddressAdapter`，連線開 socket 時把 urllib3 的 `_dns_host` 依序暫換成 `public_addresses()` 回傳的每個位址，連得上就用，全部失敗才丟最後一個錯誤）、`PublicHTTPHandler` / `PublicHTTPSHandler`（`http.client` 的 `_create_connection`）。主機名仍是連線的 host，所以 SNI、憑證檢查與 `Host` 標頭照舊；經 proxy 的連線不釘住。`overall_deadline(seconds)`：這個執行緒在區塊內的請求總共最多這麼久，釘住的連線等回應時把 socket 登記上去，時間到就 shutdown，丟 `ReadTimeout`（讀取逾時每來一個位元組就重算，慢慢送標頭的伺服器原本可以一直拖）；AI 審查、Skill、CoT 每一步都包在 `overall_deadline(DEFAULT_MAX_READ_SECONDS)` 裡。`test_http_goes_through_public_connections.py` 擋下直接呼叫 `requests.*` / `urlopen` |
| `network/http_client.py` | `read_capped_text()`（串流讀取有上限，超出丟 `ResponseTooLargeError`；照 `Content-Type` 明寫的 charset 解碼，沒寫就 UTF-8，不用 requests 給 `text/*` 的 ISO-8859-1，`named_charset()`；整個回應最多讀 `DEFAULT_MAX_READ_SECONDS`（300 秒），時間到由 `_Watchdog` 關掉連線（urllib3 的 `HTTPResponse.shutdown()` 能中斷別的執行緒上正在等的讀取），丟 `ReadTimeout`：讀取逾時只管每一塊之間，一次送一個位元組的伺服器可以一直拖下去；狀態列與標頭由呼叫端的 `public_http.overall_deadline()` 涵蓋）、`describe_request_error()`（給使用者看的失敗原因：逾時、連不上、URL 不合法等，不含 URL；requests 的錯誤訊息會引用含 token 的完整 URL）、`succeeded()`（只有 2xx 算回答；`response.ok` 連 3xx 都算，這些請求又不跟隨轉址）、`truncate_for_display()`、`CONNECT_TIMEOUT` |
| `curl_import/` | `curl_parser.py`(668) 完整 curl 解析（`-I` 是 HEAD、有本文是 POST，但 `-X` 指定的方法兩者都不改（`method_given`：`-X GET -d` 照 curl 送出帶本文的 GET）、`--oauth2-bearer` 變成 `Authorization`（`-H` 給的優先）、URL 的 `#fragment` 丟掉、URL 拆不開（沒關的 `[`、不是數字的 port）就是 `CurlParseException`，`url_is_well_formed()` 也給 HAR 用：這種 entry 跳過；同名的 `-F` 全留（`request_body.py` 的 `form_parts()` 回傳 list，產生的程式寫成 `files=[(…), …]`）；表單一律以 multipart 送出：文字欄位也放進 `files=`，寫成 `(None, 文字)`（`form_entries()`），複製來的 `Content-Type: multipart/...` 不寫進 headers（`sent_headers()`，requests 要自己帶 boundary），接受 `br`／`zstd`／`*` 的 `Accept-Encoding` 也不寫（requests 沒裝 brotli／zstandard 就解不開，交給它自己宣告能解的）；APITestka JSON action 遇到上傳檔案、`@file` body 或 `-b` cookie 檔就丟 `CurlParseException`；`@file` body 一律以位元組讀（`--data-binary` 原樣、`-d` 去掉 CR/LF，和 curl 一樣），和其他 `-d` 片段照命令列的順序接起來（`data_file_positions`）；`-b <檔案>` 存進 `cookie_files`，產生的程式以註解說明沒有讀它；`-G` 搭 `@file` 拒絕；bash 的 `$'...'` 先展開成一般引號字串再交給 `shlex`、短旗標叢集展開、`--data-urlencode`、`-F`、`--form-string`、`-b`、`-G`）；`-F` 的值照 curl 語法（`@` 開頭是上傳檔案），`--form-string` 與 HAR 的文字欄位進 `form_strings`、照字面；URL 的 query 只有「解碼再編碼會一模一樣」時才拆進 `params`（`query_tools.query_round_trips()`，URL Builder 也用它決定 query 顯示成 dict 還是原字串；否則照原樣留在 URL，`requests` 原封送出，簽章 URL 才不會壞），query 參數 `params` 同一個 key 出現多次時存成值的清單（`add_repeated_value()`），URL 的在前、`-G` 的在後，和 curl 實際送出的一樣；`--url-query` 的片段（`url_query_parts`，照 `--data-urlencode` 編碼、`+` 開頭照原樣）只在 `-G` 沒有資料時才放進 query，和 curl 的 `single_transfer` 一樣；curl 選項表（`tool_getparam.c`）裡其他要參數的選項都在 `_IGNORED_VALUE_FLAGS`，參數不會被當成 URL；`--expand-X` 照 `--X` 讀（`_unexpanded()`），值裡的 `{{變數}}` 照原樣；`http_method()` 只收 RFC 9110 的 token（HAR 也用它），方法會寫進產生的程式碼，不是 token 就拒絕；`request_body.py` 判斷 body 型別（`body_kind()`：JSON 物件要能原樣送回才走 `json=`，重複的 key、float 裝不下的數字、`NaN`、巢狀超過 100 層都照原字串送）；`request_codegen.py` 產 requests 程式（字串一律經 `python_string()`：`json.dumps` 預設把 BMP 以外的字元寫成兩個 surrogate，Python 讀成兩個字；JSON body 經 `python_literal()` 寫成 Python，`true`/`null` 在 Python 裡是未定義的名稱）；`script_templates.py`(261) 產 APITestka/LoadDensity/pytest 模板（單一請求的形式） |
| `har_import/` | `har_parser.py`(368) HAR → `CurlRequest`（重用 curl 那套 codegen；建不出請求的 entry 跳過，含半個字元（JSON 的 `\ud800`）的也跳過，同名 cookie 改走 `Cookie` header）；`is_api_like()` 濾掉靜態資源；`har_codegen.py` 批次產生單一腳本（每個目標一個函式：`requests_script()`、`pytest_script()`、`apitestka_python_script()`、`apitestka_action_script()`、`loaddensity_script()`）、函式名去重，每段開頭註解裡的控制字元寫成 `\xNN`（URL 裡的換行不會結束註解） |
| `import_targets/` | 擷取到的請求可以產生成什麼（「目標」），每個目標只說一次。`normalized_request.py`(119)：`normalize(CurlRequest) -> NormalizedRequest`，把「解析的紀錄」算成「實際送出的請求」（frozen dataclass：方法、含 query 的完整 URL、會送出的 headers 與 cookies、一個 `Payload`（`PayloadKind`：NONE／RAW／JSON／FORM／FILES，照產生器的順序：表單優先，其次讀自檔案的 body，最後才是 inline body）、帳密、秒數的時間限制、沒被讀的 cookie 檔），裡面沒有任何 curl 或 HAR 特有的東西，之後的目標照它寫就不必認得兩個解析器。`target_registry.py`(156)：`TargetDescriptor`（frozen dataclass：`key`、語言字典的 `label_key`、輸出檔的 `extension`、寫一個請求的 `generate_one`、把多個請求寫進同一份輸出的 `generate_many`、輸出會送出的請求部分 `carries`、存檔時建議的 `single_basename`／`batch_basename`）與 `ImportTargetRegistry`（`register()` 同一個 key 只收一次，`targets()` 照註冊順序，`target(key)` 遇到不認得的 key 給第一個、也就是預設的目標，`generate(key, requests)`：沒有請求給空字串、一個請求用單一形式、多個用批次形式，所以 cURL 與 HAR 兩個分頁對同一個請求產生一樣的東西）。`RequestPart` 列出不是每個目標都寫得出來的部分（GET 以外的方法、headers、cookies、body、表單欄位、上傳檔案、讀自檔案的 body、cookie 檔、auth、timeout；URL 與 query 每個目標都帶），`parts_of(request)` 從正規化後的請求找出有哪些，`TargetDescriptor.unrepresented(request)` 回報這個目標的輸出不會送出的部分。`webrunner_target.py`(79)：把請求寫成 WebRunner 的 JSON action 清單，也就是瀏覽器做得到的那一部分：`WR_get_webdriver_manager`（Chrome）→ 每個請求 `WR_to_url`（完整 URL）→ `WR_quit`；有 cookie 就在第一次造訪後逐一 `WR_add_cookie`、再造訪一次讓它們送出（瀏覽器只收目前頁面的 cookie）；時間限制變成 `WR_set_page_load_timeout`（整數秒、無條件進位，0 表示不設）。方法、headers、body、表單、上傳、帳密都沒有對應的 action，不寫。`builtin_targets.py`(69) 把內建的六個目標註冊成 `IMPORT_TARGETS`（requests、pytest、APITestka Python、APITestka JSON action、LoadDensity、WebRunner JSON action；兩個 action 是 `.json`，檔名 `action`／`actions` 與 `web_action`／`web_actions`，其餘 `.py`、`request`／`session`）：LoadDensity 只帶方法與 URL，APITestka 不帶 timeout，APITestka JSON action 另外不帶上傳檔案與讀自檔案的 body，WebRunner 只帶 cookies 與 timeout（連方法都不帶，造訪一律是 GET），沒有任何目標讀 `-b` 指的 cookie 檔。`test_import_targets.py` 對每個目標、每個部分檢查 `carries` 和產生器實際寫出來的一致（註解裡提到不算送出）；`test_import_round_trip.py` 把 `test/test_utils/fixtures/import/` 的四個 curl 指令與一份 HAR 交給每個目標產生，再把輸出讀回來：Python 腳本對著只記錄呼叫、不真的送出的 `requests`／`je_api_testka`／`je_load_density` 替身執行，JSON 直接解析，和 fixture 裡的請求逐欄比對；同一個測試也擋住這三個套件 import 任何送得出請求的東西 |
| `execution_report/` | 一次執行產生了什麼，不論是哪個框架跑的都同一個形狀。`report_schema.py`(373)：`ExecutionReport`（`framework` 用套件的 import 名稱、`results`、`name`、`started`／`duration`、框架自己的報告 `raw`）底下是 `ExecutionResult` 的樹（`kind`：suite／test／case／step，`status`：skipped／passed／failed／error，`started` 是 epoch 秒、`duration` 是秒，`stdout`／`stderr`，`error` 是 `ErrorDetail`（訊息、型別、traceback），`attachments` 是 `Attachment`（名稱、路徑、media type），`children`，以及框架自己那一筆紀錄 `raw`，共同欄位沒說到的留在裡面），全部是 frozen dataclass。`stable_id(parent_id, name, occurrence)` 給結果一個每次執行都相同的 ID（SHA-256 取前 16 個十六進位字元；每一段先寫長度再寫內容，名稱裡有分隔字元也不會撞；不含時間、不含在同層的位置），兩次執行才能逐筆比較。`rolled_up()` 取最嚴重的狀態（error > failed > passed > skipped，沒有結果算 skipped），`ExecutionReport.status` 是最上層結果的彙總（框架自己給 suite 的判定照用，不從子結果重算），`counts()` 只數沒有子結果的結果（suite 不和它的 test 重複計算），`walk()` 先父後子。`to_dict()`／`from_dict()` 是 JSON 的進出口，寫出 `schema_version`（目前 1）；`from_dict()` 逐欄檢查型別（檔案可能是任何東西）：缺欄位或型別不對丟 `ExecutionReportException`，訊息用 JSONPath 式的路徑指出是哪一欄（`$.results[0].children[2].status`），`true` 與 `NaN` 不算秒數，較新的 schema 版本、巢狀超過 `MAX_DEPTH`（64）層、兩個結果同一個 ID 都拒絕；不認得的欄位略過，較新的寫入者多寫的欄位不會讓報告打不開。建構 `ExecutionReport` 時也檢查 ID 不重複與深度。這裡不執行測試、也不讀任何框架的檔案：把各框架的輸出轉成這個形狀是之後的 adapter 的事 |
| `header_tools/` | `header_analyzer.py`(420) 安全稽核（照 OWASP HTTP Headers Cheat Sheet：CSP 的 `frame-ancestors` 視同 `X-Frame-Options`，`X-XSS-Protection: 0` 不報，`_DEPRECATED_HEADERS` 是現行瀏覽器已忽略的標頭；RFC 6265bis 讓瀏覽器整個丟掉的 cookie 另外回報：違反 `__Secure-`／`__Host-` 前綴規則的、`SameSite=None` 沒有 `Secure` 的）；`header_merge.py` 依 HTTP 規則合併重複 header（Cookie 用 `; ` 其餘用 `, `）；`HeaderField` 與 `HeaderFinding` 帶著自己在文字裡的行號（`line`，不參與相等比較；講整段的發現，例如缺少某個標頭，沒有行號；重複的標頭報在第一次重複的那一行）。`header_rules.py`(179)：每個發現代碼一條 `HeaderRule`（frozen dataclass：`id` 就是代碼、PascalCase 的 `name`、預設 `level`、一句話的 `summary`、帶 `{header}`／`{detail}` 的英文句子 `message`、處理方式 `remediation`、`help_uri`），共 20 條；英文字典的 `header_finding_<代碼>` 直接取自 `message`（和 `error_templates` 同一種做法），IDE 顯示的與匯出的報告是同一個字串。`header_sarif.py`(191)：`to_sarif(analysis, source)`／`sarif_text()`／`write_sarif()` 把一次分析寫成 SARIF 2.1.0 的一個 run：`tool.driver.rules` 永遠列出全部規則、依 id 排序（`ruleIndex` 才不會變），`results` 依行號再依規則排序，每筆有 `ruleId`、`ruleIndex`、`level`（warning，或 info 對應的 note）、英文訊息、`artifactLocation.uri` 與 `region.startLine`（沒有行號的放第 1 行）、`partialFingerprints`（規則、標頭名、detail 的雜湊，不含行號，發現沒變就不變）；輸出是縮排的 ASCII JSON，同樣的標頭每次產生一樣的文字，不引用輸入的任何一行，憑證類標頭的值到不了報告。同一個模組可以不靠 IDE、不 import Qt 執行：`python -m pybreeze.utils.header_tools.header_sarif <檔案或 -> [-o 報告] [--fail-on-warning]`，結束碼 0、有警告且要求時 1、讀不到輸入或寫不出報告時 2，訊息寫到 stderr |
| `jwt_tools/`、`hash_tools/`、`timestamp_tools/`、`regex_tools/`、`query_tools/`、`url_tools/`、`diff_tools/`、`http_reference/`、`json_format/`、`response_inspector/` | 對應 §6 工具分頁的純邏輯。`json_format` 的 Format / Minify 不改內容：數字保留原文（先換成帶隨機標記的佔位字串、輸出後一次換回）、非 ASCII 原樣輸出、同一物件重複的 key 與 `NaN`/`Infinity` 報錯；`pretty_json_or_none()` 是同一套解析、不記 log 的版本，Response Inspector 的 body 與 JWT 各段（`jwt_decoder.shown_json()`）用它排版。`json_format/view_safe.py` 的 `dumps_for_view()` / `escape_for_view()`：工具顯示的 JSON 把文字框還不回原樣的字元（U+2029、U+FDD0、U+FDD1 會變換行，落單的 surrogate 會消失；U+2028 經 `toPlainText()`、U+0085 經 `splitlines()` 也會斷行）寫成 `\uXXXX`，JSON Format、Query/URL 轉 JSON、JWT、Response Inspector、cURL/HAR 產生的 JSON 與 Python 字串都經過它。`json_format/json_document.py`(262) 是文字編輯器與視覺化編輯器共用的那一份 JSON：`JsonDocument` 以文字為準（原樣保留，還不是 JSON 時也留著、不丟例外，`problem` 說哪裡不對，這時 `tree` 是 `None`），`tree` 是文字說的內容、不帶排版，數字是保留原文的 `JsonNumber`（建構時檢查 RFC 8259 的數字語法），物件的鍵照文字裡的順序；樹寫回文字一律經 `serialize_json(tree, SerializationOptions)`（縮排、`ensure_ascii`、結尾換行；預設排版和 `pretty_json_or_none()` 相同，輸出一樣經 `escape_for_view()`），排版只存在這一個地方；`parse_json()` 拒絕的和 JSON 工具一樣（同一物件重複的鍵、`NaN`、`Infinity`），錯誤是 `JsonProblem`（`ITEJsonException` 的子類別，語法錯誤帶行與欄），不記 log，因為編輯器每按一鍵就問一次；`set_text()`／`set_tree()` 都要帶這次編輯所根據的 `revision`，根據舊版本的編輯丟 `StaleRevisionError`、文件不動，另一邊在這期間改的東西不會被蓋掉。`json_process.py` 的 `HeldNumbers`（原本的 `_Numbers`）公開給它用。新增、刪除、排序節點，undo 與未存檔狀態是之後視覺化編輯器的事。`query_tools` 與 `url_tools` 讀 JSON 也保留數字原文、拒收 `NaN` 與同一物件重複的 key（`load_json_verbatim()`，用 `json_process.unique_pairs`），Query 轉 JSON 遇到不是 UTF-8 的 percent-escape 報錯而不換成 U+FFFD，`urlencode` 經 `encode_pairs()`：寫不進 URL 的字元（落單的 surrogate）報自己的錯，不從分頁的 slot 漏出去 |
| `language_service/` | 編輯器向框架要語言功能的同一種問法，AutoControl、WebRunner、LoadDensity 之後各寫一個 adapter。`service_adapter.py`(271)：`LanguageServiceAdapter`（ABC：`framework` 是套件的 import 名稱；`capabilities()` 每次請求前都會被問，答案跟著當下安裝的框架版本走；`complete()` 與 `diagnose()` 每個 adapter 都要實作，`hover()`、`definition()` 是框架有對應資料才做的，預設什麼都不給）。型別照 Language Server Protocol（`Position`、`Range`、`TextDocument`、`Diagnostic`、`Severity`、`CompletionItem`、`Hover`、`Location`，都是 frozen dataclass），之後 adapter 後面換成真的 language server，編輯器這一側不用改；`Position.character` 以 UTF-16 code unit 計（LSP 的預設，也是 Qt 文字游標的算法，BMP 以外的字元算兩個），`utf16_offset()`／`index_at()` 和 Python 的索引互轉。編輯器不直接呼叫 adapter，而是經 `LanguageService`：只問 adapter 說它做得到的，adapter 丟出的任何例外記進 log、回空結果（連 `capabilities()` 自己失敗也一樣），框架出錯賠掉的是一次補全，不是 IDE。`LanguageServiceRegistry` 每個框架一個服務。這裡不 import 任何框架，也還沒有任何 adapter：guard 擋得住例外，擋不住當機與卡死，所以要載入框架程式碼的 adapter 得像執行器一樣放到子行程 |
| `ui_state.py` | `read_ui_state()`／`remember(name, value)`：`~/.pybreeze/ui_state.json`，IDE 對自己面板記得的事（導覽面板關掉過）。讀取不建立資料夾；不是 JSON、不是物件、不是 UTF-8 都當作空的；寫不進去只記 log，不跳訊息 |
| `file_process/get_dir_file_list.py` | 遞迴收集指定副檔名的檔案（大小寫不敏感） |
| `file_process/read_capped.py` | `read_text_capped(path, encoding, max_bytes=None)`：先看大小，超過 `MAX_OPEN_BYTES`（100 MB）丟 `FileTooLargeError`（`OSError`，`strerror` 說明大小與上限），HAR 分頁與架構圖編輯器開檔都經它，不在 UI 執行緒讀好幾 GB 的檔案 |
| `file_process/replace_file.py` | `replace_text(path, text, private=False)`：寫到旁邊的 `<名稱>.saving` 再 `os.replace` 過去，失敗時原檔不動、半成品刪掉；`private` 以 `0600` 建立（存金鑰的檔案用）；`replace_written(path, write)` 給別人寫的檔案（圖片、SVG）：`write` 拿到旁邊的 `<主檔名>.saving<副檔名>`（副檔名不變，看副檔名決定格式的寫入器照樣用），寫完才換上 |
| `manager/package_manager/` | `PackageManager`（單例 `package_manager`）持有 `syntax_check_list` |

**分層原則**：`utils/` 不 import Qt 或 JEditor，由 `test_utils_has_no_qt.py` 守著，所以全部是不需要視窗的純邏輯測試。

**共用契約**：`import_targets/`、`execution_report/`、`json_format/json_document.py`、`language_service/` 是自動化平台路線圖（PR #141）Phase 0 的四份契約，之後的 WebRunner 匯入目標、統一的報告檢視器、視覺化 JSON 編輯器與三個框架的語言服務都建在它們上面。各自為什麼這樣設計（背景、決定、沒選的做法、後果）記在 `docs/adr/` 的 0001 到 0004；由決定衍生的規則寫在 `CLAUDE.md`，不寫在那裡。目前匯入目標（cURL 與 HAR 兩個分頁）、JSON 文件（JSON 編輯器分頁）與語言服務（動作語言伺服器、自動化關鍵字分頁）有使用者，執行報告還沒有任何程式呼叫，只有測試。

**JSON 樹的編輯** `json_format/json_tree_edit.py`(300)：視覺化編輯器不是在打 JSON，是在改一棵樹。每一種編輯都是「樹 + 路徑 → 新的樹」的純函式：`set_value`、`insert`（物件的新成員排最後、陣列照索引插入）、`delete`、`rename`（成員留在原位）、`move`（回傳新的樹與值的新路徑；超出範圍的位置取最近的一端）、`position_of`。路徑 `JsonPath` 是從根走到值的鍵與索引（`()` 是文件本身）。交進來的樹不會被改動：路徑上的容器各複製一份（`_rebuilt()`，不用遞迴），其餘和原樹共用，所以文件的樹在新樹交給 `set_tree()` 之前都是完整的。做不到的編輯丟 `JsonEditError`（`ITEJsonException` 的子類別，六個理由都在 `exception_tags.py`：位置不存在、鍵已存在、不是容器、文件本身不能刪／改名／移動、不是數字、不是布林），樹不變。`kind_of()`／`empty_value()`（`JsonKind`：物件、陣列、字串、數字、布林、null）、`scalar_text()`／`value_from_text()`（格子顯示與收回的文字；數字照打的樣子留成 `JsonNumber`）、`converted()`（換類型時能說成同一件事就保留，例如數字 ↔ 寫著它的字串，否則是空值）也在這裡，面板對 JSON 不做任何判斷。`json_document.py` 另有 `detect_options(text)`（從文字讀出縮排是幾個空白或 tab、是否一行、結尾有沒有換行、是否跳脫非 ASCII），`JsonDocument.options` 可以設定（不是編輯，文字與 revision 不變）。

**動作腳本的語言服務** `language_service/`（`docs/adr/0010`）：WebRunner、AutoControl、LoadDensity 的腳本形狀相同（JSON 的動作清單，`["關鍵字"]` 或 `["關鍵字", 引數]`；整份是清單，或放在框架自己的 key 底下），所以一個 adapter 服務三個框架。

| 模組 | 內容 |
|---|---|
| `service_adapter.py`(271) | Phase 0 的契約（`docs/adr/0004`）：LSP 形狀的型別、`LanguageServiceAdapter`、只問 adapter 說自己會的事並把它的例外留在裡面的 `LanguageService`、`LanguageServiceRegistry` |
| `framework_profiles.py`(55) | `FrameworkProfile`：匯入套件前就得知道的那一點（套件名、顯示名、物件形腳本的 key `webdriver_wrapper`／`auto_control`／`load_density`、executor 模組、發行名稱、關鍵字前綴 `WR_`／`AC_`／`LD_`）。`PROFILES` 照路線圖的導入順序；多支援一個框架就是多一筆 |
| `keyword_metadata.py`(223) | 跨行程傳遞的資料：`KeywordParameter`（名稱、`ParameterKind`、是否必填、預設值的 repr、型別註記）、`Keyword`（參數、說明、定義的檔案與行、是否為 Python 內建、`signature_known`：有些內建函式 Python 說不出參數，就不檢查它的引數；`signature()`、`named()`、`missing()`、`positional_range()`、`needs_a_name()`）、`FrameworkMetadata`（框架、版本、關鍵字；`own_keywords()` 不含內建）。`to_dict()`／`metadata_from_dict()`：資料來自另一個行程裡不是 PyBreeze 寫的套件，每個欄位都檢查，schema 不認得就拒絕（`LanguageServiceException`） |
| `metadata_probe.py`(163) | `read_metadata(profile, interpreter, timeout)`：用執行腳本的那個直譯器跑一段只用標準函式庫、語法不超過 3.8 的固定腳本（`PROBE_SCRIPT`）：匯入 executor 模組，把 `executor.event_dict` 的每個名稱寫成 JSON（`inspect.signature`、`inspect.getdoc`、`__code__` 的檔案與行、`importlib.metadata.version`）。匯入時套件印的東西導到 stderr，答案是 stdout 上帶標記的那一行。上限 60 秒，工作目錄是直譯器自己的資料夾（IDE 所在的專案資料夾不在 import path 上）。沒安裝、匯入失敗、逾時、答非所問都是 `LanguageServiceException`，給使用者的只有例外的名稱（訊息可能帶路徑，寫進 log） |
| `json_scan.py`(274) | JSON 文字裡每個東西的位置。`tokens()` 切詞（沒關的字串到行尾為止）；`locate(text)` 把是 JSON 的文字讀成帶起訖 offset 的 `Located`（還沒關的容器在文字結尾關上，打到一半的腳本也讀得出來），給診斷、懸停、跳到定義用；`context_at(text, offset)` 只讀游標之前的文字（不必是 JSON），回傳那裡還開著的物件與陣列（`Frame`：在第幾個元素、陣列的第一個字串、物件目前的 key 與已經寫過的 key），給補全用；`LineIndex` 在 offset 與 LSP 的行／UTF-16 欄之間轉換。都不用遞迴 |
| `action_adapter.py`(343) | `ActionLanguageAdapter(profile, metadata, words)`：**補全**（動作名稱的位置給關鍵字，框架自己的在前、Python 內建在後；引數名稱的位置給該關鍵字還沒給過的參數，游標之後已經寫的也算；物件最上層給框架的 key；不在字串裡時連引號一起給）、**診斷**（`unknown-keyword`、`unknown-parameter`，兩者用 `difflib` 建議最接近的名稱；`missing-parameter`、`too-many-values`、`too-few-values`、`action-shape`、`actions-not-list`、`json-syntax`；訊息從傳進來的字典 `words` 取，所以是 IDE 的語言，並帶上回答的框架版本）、**懸停**（關鍵字的簽名＋說明；參數的型別與必填／選填）、**跳到定義**（關鍵字說得出檔案與行時才有這個能力）。`framework_of(text, metadata)`：物件有某框架的 key 就是它的；清單看用了誰的關鍵字最多（有中繼資料看中繼資料，沒有就看前綴）；其他 JSON 誰的都不是。`syntax_diagnostics()` 用標準的 `json.loads`（框架自己的 `json.load` 收的這裡就收） |
| `lsp_server.py`(431) | `ActionLanguageServer`：一則協定訊息進、要送出的訊息出（不讀串流、不開執行緒，所以能逐則測試）。`initialize`、`textDocument/didOpen`／`didChange`／`didSave`／`didClose`（回 `publishDiagnostics`）、`completion`、`hover`、`definition`、`shutdown`、`exit`，以及自訂的 `pybreeze/frameworks`（每個框架是 loading／ready／unavailable、版本、關鍵字數、能力、原因）。`offer(metadata)` 註冊 adapter 並重新診斷開著的文件；`decline(framework, reason)`。腳本屬於某個框架就只問那個框架（它的關鍵字還沒到時只報 JSON 語法）；還不屬於誰的新檔案問所有框架。`encode()`／`read_message()` 是 `Content-Length` 封包（上限 64 MB）；`serve(server, stdin, stdout, tasks)` 在**主執行緒**讀訊息（另開執行緒讀 stdin 的話，直譯器結束時還卡在讀取的執行緒會讓行程以致命錯誤收場），慢的工作各自一條執行緒，做完的結果在兩則訊息之間、同一把鎖底下交給伺服器。失敗的請求回 JSON-RPC 錯誤（`-32601`、`-32602`、`-32603`，只帶例外名稱） |


---

## 13. `pybreeze/extend_multi_language/`

`extend_english.py` 與 `extend_traditional_chinese.py` 各 872 個鍵，`update_language_dict()` 把它們併進 `je_editor` 的字典，並把 `application_name`（「PyBreeze」）寫進 `language_wrapper.choose_language_dict` 裡每一個語言：這是 PyBreeze 唯一覆寫而非新增的 JEditor 鍵，日文、簡中等 PyBreeze 沒翻譯的語言自帶「JEditor」，不寫的話會蓋過英文退回值。`test_language_parity.py` 守住兩邊鍵值必須對齊，也檢查每個已註冊語言都解得出程式用到的每個鍵；`test_startup_language.py` 在子行程裡用存好的繁中／日文真的啟動主視窗。

`supported_languages.py`(88) 把「支援哪些語言」寫明白：`MAINTAINED`（`MaintainedLanguage`：JEditor 語言包裝器裡的 key、語言選單顯示的名稱、字典）是 PyBreeze 自己維護、每個鍵都有翻譯的語言，目前是 English 與繁體中文；`EDITOR_ONLY` 是 JEditor 自帶、PyBreeze 沒有加任何字串的日本語與简体中文（選了之後編輯器自己的選單會變，PyBreeze 的仍是英文，那不是 PyBreeze 的缺陷）；兩邊都不在的是翻譯外掛註冊的（`who_translates()` 回 `Owner.PLUGIN`）。字串屬於定義那個鍵的一方，兩邊只在 `REWORDED_JEDITOR_KEYS` 重疊（`application_name`、`plugin_browser_*`、`plugin_menu_*`：JEditor 的鍵，PyBreeze 在自己維護的語言裡用自己的說法）。`update_language_dict()` 照 `MAINTAINED` 逐一把字典併進 `choose_language_dict[key]`（JEditor 沒有那個語言時記 log、其餘照併）；`extend_english.py` 與 `extend_traditional_chinese.py` 因此只剩資料，不再 import JEditor。`test_supported_languages.py` 讀 JEditor 自己的語言清單：有一個語言兩邊都沒列、維護中的字典和第一份鍵不一樣、多出一個和 JEditor 重疊的鍵、三份 README 少寫任何一個語言在選單上的名稱，都會失敗。

---

## 14. `pybreeze/extend/prthinker_extend/prthinker_setting.py`

純邏輯、無 Qt，值得單獨一節，因為它示範了本專案處理祕密的方式：

- 設定存 `~/.pybreeze/prthinker_setting.json`（經 `replace_text(..., private=True)` 整檔替換，只有擁有者讀得到；讀取時什麼都不建立，存檔失敗時對話框會說；「額外參數」斷不了詞（引號沒關）就不存，`read_extra_arguments()` 與執行時用同一套斷詞）
- `environment_for()` 把設定轉成 `PRTHINKER_*` 環境變數交給子行程，**命令列只留「這次要審什麼」** — API key 不會出現在工作管理員或執行紀錄
- `SECRET_SETTINGS` 四個欄位在 `loggable()` 中一律縮成 `(set)` / 空字串
- 模型名稱依後端交給不同變數（`MODEL_ENVIRONMENT`）：`remote` / `local` 是 `PRTHINKER_MODEL_NAME`，其他後端是各自的 `PRTHINKER_<BACKEND>_MODEL`。prthinker 只有 local 讀 `PRTHINKER_MODEL_NAME`（remote 由伺服器決定模型，只拿來標示）
- Gemini、Cohere、Mistral 在設定表上沒有金鑰欄位：prthinker 從啟動 IDE 的環境裡的 `KEY_FROM_ENVIRONMENT` 變數讀金鑰（`PRTHINKER_<BACKEND>_API_KEY`）；對話框選到它們時在表格下方說出是哪個變數（`key_note`），契約測試也用這張表給 prthinker 金鑰。存著的後端、平台、RAG 值不在選單上（較新的 prthinker 的）時，列在選單最後並選著，沒碰它就存檔不會被換掉
- `extra_arguments()` 經 `split_arguments()` 以命令列規則斷詞（引號內空白不拆，`#` 不當註解）；反斜線是路徑分隔字元的平台（Windows）上反斜線不當跳脫字元，`C:\reviews` 才不會變成 `C:reviews`。解析失敗當作沒有而不是讓整次審查失敗
- `install_target()` 回傳 `<path>[runner]`，因為 prthinker 不在 PyPI 上；資料夾要有 `pyproject.toml` 且專案名稱是 prthinker，否則不給目標、也不記住
- 規則檢索（`rag`，`RAG_MODES = ("off", "remote")`）**永遠明講**，而且兩個變數都送：`off` 給 `PRTHINKER_RAG_ENABLED=false` + `PRTHINKER_REMOTE_RAG=false`，`remote` 兩個都 `true`（走伺服器的 `/rag`），認不得的值當 `off`。子行程繼承 IDE 的環境，少送一個就會被使用者 shell 裡的設定決定。prthinker 的預設是本機 FAISS 檢索，但那份索引（`codes/`）只在它的原始碼庫、被排除在套件外，從這裡裝的 prthinker 一跑就 `ModuleNotFoundError: codes`

支援的後端：`remote / local / openai / anthropic / gemini / cohere / mistral / claude-cli / codex-cli`；平台：`github / gitlab / gitea`。

---

## 15. 設計模式落點

| 模式 | 落點 |
|---|---|
| **Facade** | `pybreeze/__init__.py` — 對外只暴露 `start_editor`、`PyBreezeMainWindow`、`EDITOR_EXTEND_TAB` 與轉出的插件 API；第一次用到才 import（PEP 562 `__getattr__`），所以 `import pybreeze.utils.*` 不會連帶載入 PySide6 與 JEditor |
| **Template Method** | `TaskProcessManager` 固定 spawn → read threads → QTimer poll → drain → exit 的骨架 |
| **Observer** | Queue + QTimer 把子行程輸出橋接到 UI 執行緒；Qt Signal/Slot（`SenderThread.update_response`、`JupyterLauncherThread.server_ready`） |
| **Factory** | `build_automation_menu()`；`ToolDescriptor.factory`（`tools_menu.TOOLS`） |
| **Registry / Table-driven** | `tools_menu.TOOLS`（`ToolDescriptor`）、`navigation_model.CATEGORIES`、`package_keyword_list`、`EDITOR_EXTEND_TAB`、`IMPORT_TARGETS`（`ImportTargetRegistry`） |
| **State** | `DiagramScene.ToolMode` 決定滑鼠事件行為 |
| **Command** | `DiagramSnapshotCommand(QUndoCommand)` |
| **Plugin** | `jeditor_plugins/` 自動探索，插件用 `register()` 註冊語法/翻譯/run config |

---

## 16. 執行緒模型

```
  UI Thread (QApplication)
    │
    ├── QTimer (100ms / 50ms) ──► pull_text() ──► pump_message_queue() ──► QPlainTextEdit
    │                                  ▲
    │                          thread-safe Queue
    │                                  ▲
    ├── daemon Thread: stdout read1 ───┤
    ├── daemon Thread: stderr read1 ───┘
    ├── daemon Thread: pybreeze-report-mail（send_after_test → send_report；連線、TLS 握手與每次回覆各有 30 秒上限，`_with_timeout()` 覆寫 `SMTP_SSL._get_socket`，因為 MailThunder 的 `SMTPWrapper` 不傳逾時；結果經 _MailNotice queued signal 寫回執行視窗；_MailNotice 掛在 QApplication 底下、送達後 deleteLater，在 GUI 執行緒上刪除）
    │
    ├── QThread: SSHReaderThread      ──Signal──► terminal widget
    ├── QThread: SshConnectThread     ──Signal──► shell / file tree（連線＋開 shell channel；host key 問題 BlockingQueued 回 UI）
    ├── QThread: SftpListThread / SftpTransferThread / SftpCallThread ──Signal──► file tree
    ├── QThread: SenderThread (CoT)   ──Signal──► review UI
    ├── QThread: RequestThread(Skills)──Signal──► result UI
    ├── QThread: ReviewRequestThread  ──Signal──► AI review client panel
    ├── QThread: ImageDownloadThread  ──Signal──► diagram canvas
    ├── QThread: RegexMatchThread     ──Signal──► Regex tab（pattern 在另一個行程跑）
    ├── QThread: DiffThread           ──Signal──► Diff tab
    ├── QThread: KeywordReadThread    ──Signal──► Automation Keywords tab（框架在另一個行程被匯入）
    └── QThread: JupyterLauncherThread──Signal──► QWebEngineView
```

垃圾回收只在 UI 執行緒跑：`start_editor()` 裝上 `gui_thread_gc.GuiThreadGarbageCollector`，關掉自動回收，改由 UI 執行緒上每秒一次的 QTimer 照直譯器自己的門檻回收（單元測試由 `test/test_utils/conftest.py` 做同樣的事）。自動回收會在任何配置超過門檻的執行緒跑，worker 上的一次回收曾把 UI 執行緒建立的 Qt 物件在 worker 上銷毀，計時器停不掉，之後 UI 執行緒把計時器事件送給已釋放的物件而崩潰。不要在 IDE 裡呼叫 `gc.enable()`。

給使用者看的文字：伺服器或檔案來的字（遠端路徑、錯誤訊息、主機名、檔名）放進 `QMessageBox` / `QLabel` 前經 `pybreeze_ui/plain_text.as_text()`（`Qt.convertFromPlainText`），Qt 才不會把它當 markup、去載入裡面的 `<img>`；`test_message_boxes_show_text.py` 檢查每個 `QMessageBox`。

讀使用者輸入的文字一律走 `pybreeze_ui/exact_text.exact_text()`（`document().toRawText()`，區塊分隔換回 `\n`）：`toPlainText()` 是顯示用的，會把不斷行空白（U+00A0）變成空白、U+2028 變成換行，Hash 算的是別的字串、Diff 看不出差別。

工具拒絕輸入的原因：`utils` 的純邏輯用 `exception_tags` 的英文常數拋例外、原樣寫進 log；工具分頁顯示前經 `pybreeze_ui/error_text.error_text()`，它認出訊息出自哪個常數（連同填進去的值與後面附加的細節），換成語言字典裡的 `error_text_<常數名>`。新增的 `_error` 常數要在繁中字典補翻譯，`test_error_text.py` 會檢查每一個。

鐵律：worker thread 一律不碰 UI。普通執行緒走 Queue + QTimer，`QThread` 走 Signal/Slot。分頁或視窗關閉時還在跑的 `QThread` 交給 `thread_keeper.let_run_out()`，不等它、也不讓它在執行中被銷毀。widget 留著的 thread（或其他物件）上接的 slot 不能抓住 widget 本身：接 bound method，或用 `thread_keeper.if_alive(weakref.ref(self), ...)`；lambda 抓 `self` 是經過 Qt 的循環參照，Python 的 GC 看不到，關掉的 widget 永遠不會釋放（`test_closed_panels_are_freed.py`）。

執行器的壽命：QTimer 接到執行器的 `pull_text()` / `_pull_text()` 這條連線**不會**讓執行器活著；reader 執行緒一結束，沒人持有的執行器就會被 GC，剩下的輸出和結束那一行都不會出現。所以執行器一律掛在它寫入的 `CodeWindow.runner` 上，跟視窗同壽；視窗又掛在主視窗的 `current_run_code_window`。

---

## 17. 持久化資料

全部集中在 `~/.pybreeze/`（`app_dirs.pybreeze_data_dir()`），刻意不依賴啟動時的工作目錄：

| 檔案 | 內容 |
|---|---|
| `ssh_known_hosts` | TOFU 確認過的 SSH host key |
| `prthinker_setting.json` | prthinker 後端/平台/金鑰設定 |
| `prompts/*.md` | 編輯過的 CoT / Skill prompt，覆寫內建模板 |
| `response_stats.txt` | AI 審查接受/拒絕統計 |
| `urls.txt` | AI 審查端點歷史 |
| `ui_state.json` | IDE 對自己的面板記得的事：目前只有導覽面板是否顯示（`navigation_visible`）。`utils/ui_state.py` 讀寫，讀取不建立任何東西，檔案壞了就當作什麼都沒記 |

另有 `~/.pybreeze/logs/PyBreeze.log`（`PYBREEZE_LOG_FILE` 可改；開檔時超過 100 MB 就輪替成 `.1`）與各自動化套件自己的 log。

---

## 18. 測試與 CI

- **單元測試** `test/test_utils/` — 192 個 `test_*.py`、4622 個測試（14 個 prthinker 契約測試在沒有 prthinker 的直譯器上跳過）。純邏輯 + headless Qt widget 測試（`QT_QPA_PLATFORM=offscreen`）。涵蓋 curl/HAR 解析、SSRF 驗證、SSH 安全、對本機回環 SSH 伺服器實際登入並列目錄（`test_ssh_loopback.py`：密碼與各種私鑰檔，只用 SHA-1 簽章的伺服器被拒，信任過的主機換了金鑰就拒絕、不再詢問，終端機分頁說出兩個指紋而不是「金鑰驗證失敗」；終端機分頁開 shell、送指令與 Ctrl+C、伺服器結束 shell 時一併斷線；`test_sftp_tree_loopback.py`：SFTP 檔案樹對真實資料夾的列目錄、建資料夾、改名、刪除、下載與上傳；伺服器在 `ssh_loopback_server.py`）、子行程 IDE 的測試（`started_window.py`：開著的對話框會被記下並關掉、測試失敗時點名，逾時會附上子行程的 stderr）、process reader EOF、queue pump、語言對齊、mermaid parser、diagram 序列化、prthinker 設定、JEditor 內部介面契約（`test_jeditor_contract.py`）、`except Exception` 只能重拋或註明理由（`test_no_blind_except.py`）等。有 hypothesis fuzz 測試（`test_fuzz_pure_logic.py`）。
- **整合測試** `test/unit_test/start_automation/` — 以 `debug_mode=True` 啟動 IDE，10 秒後自動關閉，驗證啟動流程與 extend tab
- **CI** `.github/workflows/{dev,stable}.yml` — `unit-tests` job 跑 Windows runner、Python 3.10–3.14 矩陣，`setup-python` 快取 pip 的下載（依需求檔當鍵；版本每次仍向 PyPI 解析），3.12 那一腳額外上傳 `coverage-xml` artifact；`platform-smoke` job 在 `ubuntu-latest` 與 `macos-latest`（Python 3.12）只跑 `test_platform_smoke.py`（12 個測試：套件不靠 Qt 就能 import、真的主視窗在子行程裡建起來再關掉、子行程的輸出原樣回來、只給 IDE 自己的環境變數不進子行程、放在有空白與多種文字的資料夾裡的腳本跑得起來、一次執行的輸出一路進到執行視窗、資料夾建在家目錄而且只有擁有者能讀、檔案整檔替換、offscreen 平台上 widget 畫得出來、計時器在 GUI 執行緒觸發、QtWebEngine import 得進來；每一項都不依賴是哪個系統，檔名用的字都沒有分解形式，macOS 的檔案系統不會還回別的寫法），Linux 先用 apt 裝 PySide6 wheel 沒帶的系統函式庫（`libegl1` 等）；整個 job 30 分鐘逾時，沒有任何 job `needs` 它，所以不擋 SonarCloud 與發佈（`test_workflow_actions.py` 守著這兩個 workflow 都有這個 job、沒有人等它）。完整的測試只在 Windows 跑：某個系統上整套都過了，才把它加進 `unit-tests` 的矩陣（`progress.md` #125，這個 job 還沒有實際跑過）；`sonarcloud` job 跑 ubuntu、`needs: unit-tests`。每日 02:00 排程 + push/PR 觸發。`stable.yml` 另有 `publish` job 負責版號遞增與 PyPI 發布。`dev.yml` 另有 `publish-dev` job（`needs: unit-tests`，只在 push 到 `dev` 時跑）：`scripts/dev_release.py` 把 `dev.toml` 寫成 `pyproject.toml`、版號取 PyPI 上最新的 `pybreeze_dev` 加一，建好的 wheel 和 PyPI 上最新的不同、而且這個 commit 仍是 `dev` 最新一筆時才上傳；不寫回 repo，checkout 不留憑證。兩個拿得到 PyPI token 的 job（`publish-dev`、`publish`）只安裝 `.github/requirements/publish.txt` 鎖住的工具（`build`、`twine`、建置後端 `setuptools` 與其相依共 30 個套件，每個都有版本與雜湊；`pip install --require-hashes --only-binary :all:`，不再升級 pip），再以 `python -m build --no-isolation` 建置：建置後端就是鎖檔裡的 `setuptools`，不會在 job 執行時另外向 PyPI 下載最新版；`pyproject.toml`、`dev.toml` 的 `[build-system]` `requires` 調高下限時要一併重產鎖檔。清單與重新產生鎖檔的 `uv pip compile` 指令在 `publish.in`。每個 action 都鎖在 commit SHA、後面註明版本（Node 24 的版本：checkout v7、setup-python v7、upload-artifact v7、download-artifact v8），Dependabot 的 `github-actions` 每週、`pip` 每天在 `dev` 更新（`pip` 除了 `/` 也讀 `/.github/requirements`；新版本等 7 天才提，`cooldown`）；checkout 一律寫明 `persist-credentials`，只有要 push 版號的 `publish` 保留憑證（`test_workflow_actions.py` 守著）
- **覆蓋率** `.coveragerc` — `relative_files = True` 是必要的：報告在 Windows 產生、由 Linux 上的 scanner 讀取，路徑不能帶機器資訊。`patch = subprocess` 也是必要的：pytest-cov 7 不再量測子行程，沒有它，測試在子直譯器裡建出的真主視窗（`started_window.py`）一行都不算。目前整體語句 98.9%、連分支 97.8%（`dialog`、`jupyter_lab_gui` 100%；`menu` 99.7%；`tools_gui`、`utils/`、`extend/`、`extend_ai_gui` 99.5%；`editor_main` 99.1%；最低的是 `connect_gui` 97.7% 與 `diagram_editor` 97.9%）。子行程的資料由 pytest-cov 併進它的報告，只看 `.coverage` 的 `coverage report` 會少算子行程裡跑的部分。coverage 只追蹤 Python 自己開的執行緒，`test/test_utils/conftest.py` 讓每個 `QThread` 子類別的 `run` 在 Qt 的執行緒上裝上 coverage 的 tracer，否則沒有一個 `QThread.run` 算得到
- **靜態分析** SonarCloud（`sonar-project.properties`，CI-based analysis；Automatic Analysis 已關閉且必須維持關閉，兩種模式互斥）+ Codacy（`.codacy.yml`）+ Bandit（`pyproject.toml` 中排除 test、skip B101/B404）
- **SonarCloud 方案限制** 該組織的方案只開放 `main` 與 PR 的分析結果。非 main 分支的分析送得出去、CE 任務也會成功，但結果讀回來是 403（組織內每個專案都只有 `main` 一條分支）。因此 `dev.yml` 只在 PR 時掃描，`stable.yml` 另外掃 push to `main`

---

## 19. 掃描過程中發現的事實記錄

以下是客觀觀察，不是缺陷判定，但值得留意：

1. **`file_tree_context_menu.setup_file_tree_context_menu()` 用 monkey patch** — 直接覆寫 `main_window.tab_widget.addTab` 來攔截新分頁。可行但脆弱，若他處也包裝 `addTab` 會疊加。

2. **`PyBreezeMainWindow.__init__` 的 `extend` 參數語意分歧** — 對 `super()` 恆傳 `extend=True`，而參數本身只用來決定要不要設定 Windows AppUserModelID 與視窗圖示。

3. **`start_editor()` 以 `os._exit(ret)` 收場** — 繞過 atexit 與 Qt 拆解。對 GUI 主程式常見（避免殘留執行緒卡住），但 `closeEvent` 之後的清理路徑等於不存在。

4. **`PackageManager` 名實不符** — 類別名暗示 pip 管理，實際只承載 `syntax_check_list` 六個項目；pip 安裝落在 `install_utils.install_package()`。

5. **儲存的直譯器在啟動時被清掉** — JEditor 的 `EditorMain.startup_setting()` 把設定檔的 `python_compiler` 放回 `self.python_compiler`，`PyBreezeMainWindow.__init__` 在 `super().__init__()` 之後又設成 `None`（`main_ui.py`）。實測：設定檔存了直譯器路徑，啟動後 `window.python_compiler` 是 `None`，要到使用者再從 Python 環境選單選一次才有值。執行與語言伺服器因此在啟動時都用 `default_interpreter()`（`progress.md` #130）。

---

## 20. 一句話總結

PyBreeze 的架構骨幹是 **「薄 UI + 表格化註冊 + 純邏輯 utils + 子行程隔離執行」**：選單與工具用宣告式表格組裝，業務邏輯下沉到無 Qt 依賴的 `utils/` 以便測試，任何會跑使用者程式碼的東西一律推到子行程，再用 Queue + QTimer 這條單向管線把輸出安全地送回 UI 執行緒。
