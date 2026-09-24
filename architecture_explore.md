# PyBreeze 架構探勘 / Architecture Exploration

> 掃描範圍：`pybreeze/`（201 個 `.py`、約 22,200 行，不含空行與註解約 17,300 行）＋ `test/`、`exe/`、`docs/`、CI 設定
> 對應版本：`pyproject.toml` 1.0.21（stable）／`dev.toml` 1.0.14（dev），分支 `dev`

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
   └────────────────────────────────┬────────────────────────────────────────┘
                                    ▼
   ┌─────────────────────────────────────────────────────────────────────────┐
   │ 執行層 Execution  pybreeze/extend/                                      │
   │  process_executor/  子行程隔離層（Strategy + Template Method）           │
   │  mail_thunder_extend/  測試後寄報告 hook（mail_thunder_setting.py）      │
   │  prthinker_extend/     prthinker 設定與指令組裝（純邏輯）                │
   └────────────────────────────────┬────────────────────────────────────────┘
                                    ▼
   ┌─────────────────────────────────────────────────────────────────────────┐
   │ 基礎層 Foundation                                                        │
   │  pybreeze/utils/              18 個工具子套件（純邏輯，可單測）           │
   │  pybreeze/extend_multi_language/  內建 i18n（英 / 繁中，各 733 鍵）      │
   └─────────────────────────────────────────────────────────────────────────┘
                                    ▼
   外部子行程：python -m je_api_testka / je_auto_control / je_web_runner /
               je_load_density / automation_file / je_mail_thunder /
               test_pioneer / prthinker
```

---

## 3. 啟動流程

`pybreeze/pybreeze_ui/editor_main/main_ui.py:189` 的 `start_editor()`：

1. 取得（或建立）`QApplication`，裝上 `collect_garbage_on_gui_thread()`（`pybreeze_ui/gui_thread_gc.py`：關掉自動垃圾回收，改在 UI 執行緒上定時回收，見 §16）
2. 建立 `PyBreezeMainWindow`，其 `__init__` 依序：
   - `update_language_dict()` 併入 PyBreeze 的 733 條翻譯——**必須在 `super().__init__` 之前**：JEditor 在那裡依設定挑啟動語言，英文以外的語言讀的是當下合併出來的一份副本，之後才加進去的字串它看不到，選單拿到 `None` 標題就讓 Qt 當掉（access violation）
   - `super().__init__(..., extend=True)` — JEditor 在此已呼叫 `load_external_plugins()`，自動掃描 CWD 下的 `jeditor_plugins/`
   - 刪掉 JEditor 原本的 Help 選單
   - 設定標題、Windows AppUserModelID、圖示
   - `add_menu_to_menubar()` — 建構全部選單（見 §5）
   - `syntax_extend_package()` — 註冊 `.json` / `.yml` / `.yaml` 自動化關鍵字高亮
   - 依 `EDITOR_EXTEND_TAB` 註冊表加入外部擴充分頁（`_add_extend_tabs()`：每一個分頁各自建，建不起來的只記 log，不會讓整個 IDE 起不來）
   - `setup_file_tree_context_menu()` — 掛上檔案樹右鍵選單。改名時開著的分頁跟著檔案走（改資料夾也一樣，底下每個開著的檔案都跟著走）：先停掉分頁的自動存檔、改名、再用新路徑重開一條（`_stop_auto_save()` / `_start_auto_save()`）——JEditor 的存檔執行緒只認開檔當下的路徑，沒辦法改指向。外部修改監視也跟著搬（改名前就先移除，檔案搬走後 Windows 放不掉舊名），並照 `open_an_file` 重載語法高亮、git 基準與語言伺服器（`rename_self_tab()` 會清掉「未儲存」標記，有未存的編輯就用 `_on_text_changed()` 放回去，否則改名後五秒內關分頁會直接丟掉編輯）；Dock Editor（`FullEditorWidget`，關閉時才寫回、檔案不存在就不寫）的 `current_file` 也改指新路徑（`_dock_editors_under()`）。新增與改名的名稱不能帶磁碟代號、根目錄、`..` 或 `:`，也不能解析到資料夾外（`_inside()`；改名只能是單一名稱）。刪除資料夾用 `remove_folder()`（唯讀檔清掉唯讀屬性再刪，git 的物件檔就是唯讀），符號連結與 junction 只刪連結本身。刪除時同樣用 `_editors_under()`：檔案或資料夾底下每個開著的分頁先停掉自動存檔，再刪；刪完只關掉檔案真的不見了的分頁，刪不掉（被鎖住、唯讀）的檔案分頁留著、自動存檔重開。「在檔案總管中顯示」由 `reveal_command()` 組指令：Windows 用 Explorer 的 `/select,`、macOS 用 `open -R` 把檔案選起來，其他平台 `xdg-open` 只能開資料夾；啟動失敗（例如沒有 `xdg-open`）經 `_perform_file_op()` 跳警告
   - `close_tab()` 覆寫 JEditor 的：分頁有 `may_close()` 就先問（提示詞編輯器、架構圖編輯器有未存的變更時會問）；關掉的工具分頁 `deleteLater()`（JEditor 的 `removeTab` 不刪 widget，關過的工具分頁會留到 IDE 結束），JEditor 自己的編輯器分頁不動，關閉 IDE 時也先問過每個分頁與 dock，有一個說不就取消關閉
   - `debug_mode=True` 時啟動 10 秒自動關閉 `QTimer`（CI 用）
3. `apply_stylesheet()` 套 qt_material 主題（預設 `dark_amber.xml`）
4. `showMaximized()` → `startup_setting()` → `app.exec()`
5. 離開時以 `os._exit(ret)` 硬退出（避開 Qt 拆解殘留執行緒）

模組層級有一個副作用：`main_ui.py:8` 在匯入 PySide6 之前就設定 `LOCUST_SKIP_MONKEY_PATCH=1`，避免 LoadDensity 的 gevent monkey patch 破壞 Qt。

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

- `start_test_process(package, exec_str)` — 腳本內容直接走 `--execute_str`（Windows 上先 `json.dumps` 逃逸）；Windows 上命令列超過 30,000 字元（上限 32,767）時改寫進暫存的 `pybreeze_run_*.json`、走 `--execute_file`（JSON 以全跳脫的 ASCII 寫回，套件用哪種編碼讀都一樣），執行結束或啟動失敗就刪掉
- `start_test_process_file(package, file_path)` — 走 `--execute_file`，避開 Windows ~32K 命令列上限
- `start_module_process(package, arguments, environment)` — 通用形式；**祕密（API key、token）走 environment 不走命令列**，工作管理員看不到

### 4.2 `process_executor_utils.py` — 工廠函式

| 函式 | 用途 |
|---|---|
| `build_process()` | 取當前分頁的程式碼（或傳入的 `exec_str`）→ `start_process()`。沒給 `exec_str` 又不是編輯器分頁時，開一個執行視窗寫明「腳本要在前面的編輯器分頁裡」（`report_no_script_tab()`），不會把 `None` 交給套件 |
| `start_process()` | 建 `CodeWindow` + `TaskProcessManager` → `start_test_process()` |
| `build_process_from_file()` | 以檔案路徑執行單一檔案，回傳它的 manager；`then` 在執行結束時呼叫 |
| `run_dir_files_with_package()` | 問使用者選資料夾（`_ask_for_action_files()`，對話框掛在主視窗上；資料夾裡沒有 `.json` 就明說），每個 `.json` 一個執行視窗，一個跑完才跑下一個（`run_one_after_another()`：報告都寫到同一個 `default_name.html`，同時跑會互相蓋掉、寄錯報告）；被停止的執行（停止鈕、關閉 IDE）結束整批，啟動不了的檔案跳過 |
| `open_run_window()` | 開一個執行視窗、掛進 `main_window.current_run_code_window`，並接上 `finished_and_closed`：使用者關掉一個已經跑完的執行視窗時主視窗就放掉它（以前這份清單只增不減，每次執行都留下一個視窗、一個執行器、兩個 queue 和一個 timer）；執行中被關掉的視窗記下 `_closed_while_running`，等執行器在結束路徑尾端呼叫 `CodeWindow.run_ended()` 時才放掉（排到 timer 的 slot 回來之後才發，視窗是 timer 的 parent）。插件執行也走這裡 |
| `build_task_process()` | 共用建構：`open_run_window()` 並帶上主視窗選定的直譯器、決定要不要接寄報告的 hook（`report_mail_hook(code_window)`：建立時記下子行程工作目錄裡 `default_name.html` 的絕對路徑與開始時間，比這次執行還舊的報告不寄；寄送結果經無 parent 的 `_MailNotice` 以 queued signal 回到執行視窗，寫出寄到了或沒寄的原因）。建好的 `TaskProcessManager` 掛在執行視窗的 `runner` 上，所以呼叫端可以不留參考。prthinker 審查也走這裡 |

### 4.3 各自動化模組（Strategy）

`api_testka/`、`auto_control/`、`web_runner/`、`load_density/`、`file_automation/` 五個模組**結構完全一致** — 只有 `_PACKAGE` 常數不同，各提供 4 個函式：

```
call_X()                       → build_process(..., send_mail=False)
call_X_with_send()             → build_process(..., send_mail=True)
call_X_multi_file()            → run_dir_files_with_package(..., False)
call_X_multi_file_and_send()   → run_dir_files_with_package(..., True)
```

| 模組 | `_PACKAGE` |
|---|---|
| `api_testka` | `je_api_testka` |
| `auto_control` | `je_auto_control` |
| `web_runner` | `je_web_runner` |
| `load_density` | `je_load_density` |
| `file_automation` | `automation_file` |
| `mail_thunder` | `je_mail_thunder`（只有單一 `call_mail_thunder()`） |

`test_pioneer/test_pioneer_process_manager.py` 只剩 `init_and_start_test_pioneer_process()`：經 `build_task_process()` 開執行視窗，再用 `start_module_process("test_pioneer", ["-e", <yaml>])` 跑，跟其他套件走同一個 `TaskProcessManager`（找不到直譯器時一樣寫進執行視窗，不會從選單 callback 拋出）。

### 4.4 特化執行器

- **`file_runner_process.py`** — `FileRunnerProcess`。**唯一不跑 Python 的執行器**，服務插件註冊的 run config：
  - 直譯式：`compiler [args...] file`（如 `go run main.go`）
  - 編譯式：`compiler file -o out` → 執行 `out` → 執行完整個建置資料夾刪掉。`out` 建在 `tempfile.mkdtemp()` 開的資料夾裡，不在原始檔旁邊（旁邊同名的檔案會被蓋掉再刪掉，同一個檔案跑兩次也會互搶）。編譯器跟執行一樣走 `_start_process()`（輸出即時串流、不佔 UI 執行緒），結束碼交給 `after_exit`：0 才接著跑產物，否則印 `[Compile failed]`
  - 編譯最多 `COMPILE_TIME_LIMIT_SECONDS`（60 秒），由 pump 檢查、超過就 `stop_tree()`；編譯中也能 `stop()`。QTimer 間隔 50 ms（比 Python 執行器更快），編譯與執行共用同一個
  - 讀取、pump、drain 與寫進視窗都用 §4.5 的共用函式
  - `run_current_file_with()` 建好後同樣掛在執行視窗的 `runner` 上；輸出用執行設定的 `"encoding"` 解碼（`output_encoding()`，`"locale"` 表示本機字碼頁，Java 與中文化的編譯器就是輸出本機字碼頁），沒寫就用 IDE 的編碼
  - 有和 `TaskProcessManager` 相同語意的 `stop()`
  - 子行程的 `stdin` 是 `DEVNULL`：執行視窗沒有輸入欄，讀取要立刻拿到 EOF，不能卡在沒人寫的管線上
  - 啟動失敗（找不到指令、是資料夾、沒有執行權限、產物被鎖）都寫進執行視窗，建置資料夾經 `_remove_build_dir()` 一併刪掉。`stop()` 會設 `_cancelled`：編譯中或剛編譯完按停止都顯示「[Stopped]」、不執行產物；每個子行程有自己的讀取旗標（`_reading`），編譯的讀取執行緒不會延續到執行階段

### 4.5 `queue_pump.py` 與 `CodeWindow.append_output()`

子行程輸出到執行視窗的整條管線，兩個執行器（`TaskProcessManager`、`FileRunnerProcess`）共用：

- `read_stream_into_queue(stream, queue, buffer_size, encoding, keep_reading)` — reader 執行緒用。行**原樣**進 queue（縮排、行尾、空行都留著）；空讀 = EOF 即停，管線被關掉的 `OSError` / `ValueError` 記 debug 後停。超過 `buffer_size` 的長行分段讀進來：用 incremental decoder 解碼（被切斷的多位元組字元接到下一段），段尾的 `\r` 留到下一段（`\r\n` 被切開時不會變成兩個換行）；不認得的 encoding 退回 UTF-8 並記 warning
- `pump_message_queue(q, append_fn, is_error, max_messages)` — UI 執行緒用。`MAX_MESSAGES_PER_PUMP = 256`：每 tick 只抽一則的話輸出上限只有 ~10 行/秒，聒噪的腳本會爬行；有上界則避免洪水輸出卡住 UI 執行緒。`max_messages=None` 是收尾時一次抽乾。只跳過空字串
- `output_queue()` — 每條管線的 queue 最多 `MAX_QUEUED_MESSAGES`（10,000）則；滿了 reader 就等（每 0.2 秒看一次 `keep_reading`），子行程寫管線也跟著等，跑得跟視窗顯示一樣快，像終端機；以前不設上限，印個不停的腳本會一直吃記憶體，按 Stop 後再一口氣全倒進視窗
- `ReaderGrace` / `any_alive()` — 子行程結束後 reader 還能讀多久（`READER_GRACE_SECONDS = 2.0`，從結束後第一個 tick 起算）。管線要等最後一個握著它的行程結束才會 EOF，子行程開的行程沒轉向輸出時會一直握著；以前兩個執行器在 UI 執行緒上各 join 2 秒，IDE 卡 4 秒還是丟掉之後的輸出。現在由 pump 逐 tick 詢問，時間到就結束執行並在視窗註明
- 執行器寫進執行視窗、說明這次執行本身的訊息（`[Error] Command not found: …`、`[Compile]`、`[Run]`、`[Stopped]`、`[Mail] …`、`Task exit with code …`、行程仍握著輸出的註明，共 15 種）一律經 `run_notice.run_notice(名稱, **欄位)`：取語言字典的 `run_window_<名稱>` 填入欄位，字典沒有時（腳本、測試在 `update_language_dict()` 之前啟動執行器）退回 PyBreeze 的英文；`test_run_notice.py` 擋掉在執行器裡直接寫 `"[Error] …"` 字串
- 執行視窗上方有「停止」按鈕：執行器在子行程跑起來後呼叫 `CodeWindow.run_started()` 打開它，`run_ended()` 關掉它，按下去走 `stop_runner()`（`stop_tree` 停掉子行程和它開的所有行程）；關掉執行視窗不會停止執行。
- `CodeWindow.append_output(text, is_error, own_line=False)`（`show_code_window/code_window.py`，輸出是上限 10,000 行的 `QPlainTextEdit`：`QTextEdit` 到上限後每寫一行要花約 15 ms 丟掉最舊的一行）— 一律寫在文件**尾端**（不用 widget 自己的游標：那個游標跟著使用者的點擊與選取走，寫在那裡會把輸出插進中間、或蓋掉使用者選取的文字）。終端機控制碼（CSI 顏色與游標移動、OSC 等控制字串、`ESC ( B` 這類 nF 與其他兩位元組 escape）先拿掉、backspace 套用到前一個字元、tab、換行、`\r` 以外的控制字元丟掉（與 SSH terminal 共用 `utils/terminal_text.strip_terminal_controls()`；讀取切斷在 escape 中間時，reader 把尾巴留給下一段，`queue_pump` 的 `split_incomplete_escape()`），`\r\n` 是換行，單獨的 `\r` 像終端機一樣回到行首、由後面的文字取代這一行（`_insert_rewinding()`；結尾的 `\r` 記在 `_rewind_pending`，等下一段來才套用：接著是 `\n` 就是換行，否則回捲，跑完的進度條不會被清掉）；換行只出現在文字本身有換行的地方，所以超過 buffer 被切段的長行會接回同一行。`own_line=True` 給視窗自己的狀態訊息（`Task exit with code …`），程式留下沒換行的半行時先補一個換行。捲軸在最底時畫面跟著輸出走（像終端機）；使用者往上捲去讀時就停在原處

---

## 5. 選單層 `pybreeze_ui/menu/`

`build_menubar.py:add_menu_to_menubar()` 是唯一入口，依序建構 15 個選單建構器。`menu_utils.py` 的 `open_web_browser()` 讓各選單的 Help 連結開成內嵌瀏覽器分頁；`extend_jeditor_tab_menu/jupyter_lab_tab.py` 的 `extend_tab_tools_menu()` 把 JupyterLab 分頁加進 JEditor 的分頁選單。

### 5.1 `automation_menu_factory.py` — 選單工廠

`build_automation_menu(ui, spec)` 依一份 `AutomationMenu` 描述組出標準自動化子選單：`Run` 子選單（`RunAction` 列表）/ `Help`（`HelpLink` 列表，文件＋GitHub，開內嵌瀏覽器分頁）/ `Project`（建立範本目錄）/ GUI 分頁，每一段各由一個小函式建（`_add_run_menu` 等），沒有項目的段落不建。三個描述都是 frozen dataclass。六個自動化模組全部靠它，`build_*_menu.py` 只剩一份 `AutomationMenu(...)`。每個 QAction 都以它所在的選單為 parent，由 Qt 持有；AutoControl 額外的 `Record` 子選單也一樣；它的停止錄製不論前面是哪個分頁都會停，把動作以 AutoControl 執行器讀的 JSON 插在編輯分頁的游標處（沒有編輯分頁就放剪貼簿），沒錄到東西就告知。

`safe_create_project(ui, import_name)` 回傳延遲 import 的 closure：專案建在 IDE 開著的資料夾（`working_dir`，沒開就用行程的工作目錄）；套件的資料夾（`create_project_dir` 的 `parent_name` 預設值）已存在時先問（預設否），因為各套件一律覆寫範本檔；模組沒裝、寫入失敗都跳警告並記 log，成功時說出建在哪裡。

| 選單 | 文件 | GUI 分頁 |
|---|---|---|
| APITestka | apitestka.readthedocs.io | `APITestkaWidget` |
| AutoControl | autocontrol.readthedocs.io | `AutoControlGUIWidget` |
| WebRunner | webrunner.readthedocs.io | — |
| LoadDensity | loaddensity.readthedocs.io | `LoadDensityWidget` |
| FileAutomation | fileautomation.readthedocs.io | — |
| MailThunder | mailthunder.readthedocs.io | — |

### 5.2 非工廠的兩個選單

- **`test_pioneer_menu/`** — 建範本目錄（寫在 IDE 的工作目錄，已有範本先問是否取代，寫入失敗跳警告）+ `QFileDialog` 選 `.yml` / `.yaml`（副檔名清單與語法高亮共用 `syntax_keyword.TEST_PIONEER_SUFFIXES`；會驗副檔名，選錯跳 `QMessageBox`）
- **`prthinker_menu/`** — 審查目前檔案（先照 Run with... 的方式存檔：`save_current_file_for_run()`）/ 審查 PR（`QInputDialog` 問編號，範圍 1–1,000,000）/ 設定對話框 / Help

### 5.3 `tools/tools_menu.py` — 表格驅動的工具註冊

這是全專案設計最乾淨的一塊。三張表把 20 個工具的「建構」「分頁開啟」「dock 開啟」完全解耦：

- `_WIDGET_FACTORIES: dict[str, Callable]` — widget key → 建構 lambda
- `_TAB_ACTIONS: tuple[...]` — (widget key, 主視窗屬性, 選單屬性, action 語言鍵, 分頁標籤鍵)
- `_DOCK_ACTIONS` / `_DOCK_TITLES` — 同一組 widget 也能開成右側 dock（`closing.AskingDock`：關 dock 前先問 widget 的 `may_close()`，有未存變更的提示詞與架構圖編輯器不會被 dock 的關閉鈕直接丟掉）

`_register_action()` 有一段關鍵註解：QAction 必須 `setattr` 掛回主視窗，否則 Qt 不持有它、被 GC 後選單項就失效。另一種做法是建構時把選單當 parent（自動化選單工廠、插件選單用這種）。`test_started_menus.py` 在子行程啟動真的 IDE、GC 後走訪整條選單列，任何子選單變空就失敗（JEditor 的兩個字型選單除外：offscreen 平台沒有字型）。

### 5.4 插件選單

- **`build_plugin_menu.py`** — 讀 `je_editor.plugins.get_all_plugin_metadata()`，每個插件一個子選單（About + 一個 Run 動作，多個副檔名時一併列在標籤裡，動作直接呼叫 `run_current_file_with()`）；另有「Plugin Browser」分頁入口。插件是第三方程式：不是 dict 的 metadata 或 run config 略過並記 log，名稱經 `plugin_text()` 轉成文字（`addMenu(None)` 會讓 Qt access violation），每個插件的選單各自建、失敗只少它自己那一項
- **`build_run_with_menu.py`** — 讀 `get_all_plugin_run_configs()`，在 Run 選單下加「Run with…」。`run_config_suffixes()` 把插件登記的副檔名正規化成 `Path.suffix` 的樣子（小寫、一個前導點；JEditor 原樣保存，`.R`、`r` 以前永遠比對不上）。`run_current_file_with()` 先經 `save_current_file_for_run()` 存檔（已有檔名的分頁照 JEditor 自己存檔的方式寫：`write_file_with_encoding()` 用分頁的編碼與行尾，寫成功後才 `mark_ignore_next_file_change()` 與 `mark_saved()`；存檔失敗跳警告、不執行；沒檔名的走 JEditor 的另存新檔），再驗副檔名、交給 `FileRunnerProcess`。Plugins 選單的 Run 動作也走這一條

### 5.5 安裝選單

`install_utils.install_packages()` 用 `build_task_process()` 開一個執行視窗，`start_module_process("pip", ["install", "-U", *packages])`：參數清單、不經 shell（以前借 JEditor 的 `ShellManager`，它用 `shell=True` 交給 `cmd.exe`，使用者選的資料夾名稱裡有 `&` 就會把指令切開）。多個套件一次 pip（建置工具以前是三個 pip 同時對同一個環境跑）。pip 用 IDE 選定的直譯器，沒選時照一般執行的退路。`install_package()` 是單一套件的寫法

- `automation_menu/` — 七個自動化套件的一鍵安裝。**prthinker 例外**：不在 PyPI 上，第一次會問來源資料夾、記進設定，之後裝 `<path>[runner]`
- `tools_menu/` — 安裝 setuptools / build / wheel

---

## 6. 工具分頁 `pybreeze_ui/tools_gui/`（13 個工具 widget + 2 個共用機制）

每個工具都是 `QWidget`，UI 極薄，真正邏輯全在 `pybreeze/utils/` 對應的純函式套件裡（所以測得動、也測了）。

| 工具 widget | 對應 utils | 功能 |
|---|---|---|
| `CurlImportGUI` | `utils/curl_import/` | 貼上 curl 指令 → 產生 requests / pytest / APITestka(py & json) / LoadDensity 腳本 |
| `HarImportGUI` | `utils/har_import/` | 開 `.har` → 列出錄到的請求（可只看 API-like）→ 批次產生腳本 |
| `JwtDecoderGUI` | `utils/jwt_tools/` | 解 JWT header/payload（不驗簽），時間戳轉可讀 UTC；貼上的文字先去掉空白，不是單純的 token 就取出裡面第一個（`Bearer `、引號、換行都可以），base64url 嚴格解碼 |
| `TimestampGUI` | `utils/timestamp_tools/` | epoch（依大小自動判秒／毫秒／微秒／奈秒；整數用 `int()`、小數用 `Decimal` 精確換算，一律往過去截到微秒）↔ ISO-8601（`_ISO_RE` 自己解析，3.10 到 3.14 讀法一致：`Z`/`z`、`±HH`、`±HHMM`、任意位數小數、basic 格式；八位數而且是合法日期就當 `YYYYMMDD`）。epoch 換算用 `utc_from_epoch_seconds()`（epoch + `timedelta`；`datetime.fromtimestamp` 在 Windows 上拒絕 1970 年前幾小時以外的值），JWT 的時間戳 claim 也用它 |
| `HashGUI` | `utils/hash_tools/` | 多演算法摘要 |
| `QueryJsonGUI` | `utils/query_tools/` | query string ↔ JSON 雙向 |
| `UrlBuilderGUI` | `utils/url_tools/` | URL 拆成 JSON 元件 / 由元件組回 URL |
| `RegexGUI` | `utils/regex_tools/` | regex 測試，flag 勾選、列出每個 match 與群組。pattern 在另一個行程裡跑（`find_matches_bounded()`：從原始碼執行時是 `python -I -S -c` 跑一段只用標準函式庫的固定腳本，工作用 JSON 從 stdin 進、結果從 stdout 出，5 秒後 kill；打包版沒有直譯器可用，仍是 multiprocessing spawn），分頁用 `RegexMatchThread` 等它：`re` 開始比對後就停不下來，災難性回溯只有整個行程能停。spawn 會重新匯入啟動 IDE 的腳本，README 那種沒有 `__main__` 防護的腳本會每跑一次就再開一個 IDE。還在跑的 worker 記在 `_RUNNING`，分頁關閉時 `stop_running_workers()` 結束它（IDE 以 `os._exit` 結束，子行程不會跟著走）；執行中不能存檔，列到 `MAX_MATCHES` 上限時會註明可能還有更多 |
| `HttpStatusGUI` | `utils/http_reference/` | 狀態碼參考，可依碼前綴或描述搜尋 |
| `DiffGUI` | `utils/diff_tools/` | unified diff + 增刪統計，`compare_texts()` 的統計與 diff 共用同一次比對（`_TrimmedMatcher`：先把相同的開頭結尾放一邊再比對中間，長而重複的文字改一行就是一行；放一邊有時反而比對得更差（`b b a b a` 對 `b a c b`），所以有放一邊、且兩段合計不超過 2,000 行時，`_closest_match` 也照原樣比一次，取改動行數少的（更大的文字再比一次會讓等待加倍）；autojunk 照 difflib 的預設，關掉的話重複的文字比對時間隨行數平方成長；diff 照 `difflib.unified_diff` 的格式從它的 grouped opcodes 寫出），在 `DiffThread` 上算、不佔 UI 執行緒（4 萬行要四秒多），比對中按鈕停用、關閉時交給 `let_run_out()`。逐行比不出差別、文字卻不同時（最後少一個換行、`\r\n` 對 `\n`），改成連行尾一起比：少換行的那行下面標 `\ No newline at end of file`，其他行尾寫出來 |
| `JsonFormatGUI` | `utils/json_format/` | 美化 / 壓縮 / 驗證 |
| `HeaderAnalyzerGUI` | `utils/header_tools/` | HTTP header 安全稽核（HSTS、CSP、CORS、Set-Cookie、banner…）|
| `ResponseInspectorGUI` | `utils/response_inspector/` | 貼整包 response → 拆狀態列/headers/body，順便挖出 JWT；`curl -i` 印出的多段回應（`100 Continue`、proxy 的 `Connection established`、`-L` 的轉址）取最後一段；只有一行又沒有狀態列就當 body |

### 兩個橫向共用機制

- **`tool_tabs.open_tool_tab()`** — 工具之間互相「轉交」：Response Inspector 把狀態碼丟給 HTTP Status、headers 丟給 Header Analyzer、JWT 丟給 JWT Decoder、JSON body 丟給 JSON Format；curl 匯入把 URL 丟給 URL Builder。開新分頁並自動聚焦。
- **`output_actions.OutputActions`** — 統一的「複製 / 在編輯器開啟 / 存檔」三顆按鈕，綁在工具的唯讀輸出 `QTextEdit` 上，輸出也經 `exact_text()` 讀（不讓 U+00A0、U+2028 被改掉）；副檔名與檔名可傳 callable 動態決定。存檔經 `replace_text()` 整檔替換，失敗（唯讀資料夾、被鎖住的檔案、磁碟滿）時原檔不動、會跳警告，說出檔名與原因。Qt 的文字元件留不住貼上的 CR，換行一律讀成 LF

---

## 7. `pybreeze_ui/diagram_editor/` — 架構圖編輯器（3,963 行，最大子系統）

| 檔案 | 職責 |
|---|---|
| `diagram_editor_widget.py` (678) | 外層 widget：兩排工具列（工具模式列 + 檔案/undo/對齊/格線/匯出/縮放列）、canvas 與屬性面板的 splitter、快捷鍵（只在編輯器有焦點時作用，當 dock 開著也不搶程式碼編輯器的按鍵）；PNG/SVG 匯出；Mermaid 匯入對話框。「從 URL 加入圖片」也交給 `ImageDownloadThread`，圖片回來才放上畫布，失敗或不是圖片就跳警告；關閉時還在跑的下載交給 `let_run_out()`。存檔經 `replace_text()` 先寫 `<name>.saving` 再換上去，存檔失敗不會毀掉上一份 |
| `diagram_scene.py` (888) | `DiagramScene(QGraphicsScene)`：**State pattern** 的 `ToolMode` 決定滑鼠行為；undo/redo、複製貼上（節點、連線與圖片）、多選對齊與分佈、z-order、序列化 `to_dict()` / `load_from_dict()`。`get_all_nodes/connections/images()` 由下往上列出（`_bottom_first()`），存檔與 undo 還原時同 z 值的重疊項目維持原本的上下；右鍵選單先選取點到的項目；置頂／置底放到所有其他節點與圖片之上／之下；`to_dict()` 給每個節點與圖片記下它在兩者之間由下往上的位置（`stack`），載入後 `_restore_stacking()` 照這個順序重新加回場景（同 z 值時後加的在上面），圖片也存 `z`。`load_from_dict()` 先用 `_check_is_a_diagram()` 確認資料形狀才清空畫布（不合就丟 `ValueError`，畫布原封不動），每一筆節點／連線／圖片再各自容錯；清空前先 `to_dict()` 留一份，載入途中還是出錯就放回原樣再往上丟——載入要嘛成功、要嘛什麼都沒變（編輯器存檔寫回上次開的檔案，半途清空的畫布會蓋掉使用者的檔）。圖片的 `source` 不是字串就丟掉。`undo_scope` 用 `try/finally`，本體丟例外也一定收掉快照；圖片來源先看副檔名、拒絕 UNC（`_is_on_this_machine()`）才碰檔案系統；URL 圖片交給 `ImageDownloadThread(QThread)` 下載並快取在 `_pixmap_cache`，undo/redo 重建項目時直接用快取，不會再連一次網路；編輯器關閉時 `let_image_downloads_run_out()` 把還在跑的下載交給 `let_run_out()`，不在 UI 執行緒等 |
| `diagram_items.py` (960) | 圖元：`DiagramNode`（矩形/圓角/橢圓/菱形 4 種 body + 置中標籤 + 4 個 `ResizeHandle`；填色、框線色、字級收在 frozen dataclass `NodeStyle`）、`DiagramConnection`（三次貝茲 + 箭頭，連到節點邊界交點）、`DiagramImage`。`_EditableLabel` 刻意預設唯讀、雙擊才進編輯（對應 CLAUDE.md 的 Qt 規範）；雙擊時記下場景快照，失去焦點時經 `DiagramScene.record_change()` 記成一步「Edit Text」undo（有改才記）。`DiagramScene.add_image()`（`diagram_scene.py`）把圖放進 scene 的 `_pixmap_cache`，undo 重建時不必重讀檔案或重新下載。檔案裡的字級經 `_clamped_font_size()`：不是有限數字（`1e999` 讀進來是無限大、NaN、字串）就用預設字級；位置經 `_coordinate()`：不是有限數字就跳過這一筆，超過 `MAX_COORDINATE`（一百萬）就夾回來；連線建好所有東西之後才掛到兩端節點上 |
| `diagram_mermaid_parser.py` (603) | Mermaid flowchart → diagram dict。切箭頭與 `;` 之前先用 `_protect()` 把引號與括號裡的標籤換成佔位符，解析節點時再 `_restore()`（標籤裡的 `-->`、`;` 不會被當成語法）。含 **Sugiyama 風格自動排版**：分層 → 交叉最小化掃描 → 交叉軸偏移解析 |
| `diagram_property_panel.py` (453) | 右側屬性側欄，依選取型別切換 node / connection / image 三組表單；每記一步 undo（場景的 `recorded`）就重新整理（在畫布上拖把手改大小時選取沒變）；寬、高各自只改自己那一邊；數字欄位不追鍵盤、輸入完才套用 |
| `diagram_view.py` (195) | `QGraphicsView`：滾輪與按鈕縮放都經 `_step_zoom()`（有上下界，界外時仍可往界內走；橫向滾輪不縮放），`fit()` 把「符合視窗」夾在上下界內、中鍵平移、`drawBackground` 畫格線 |
| `diagram_commands.py` (48) | `DiagramSnapshotCommand(QUndoCommand)` — 快照式 undo，存變更前後完整場景狀態；有 `merge_key` 的連續步驟（同一個項目的同一個屬性：大小、字級、線寬）合併成一步（`id()` / `mergeWith`） |
| `diagram_net_utils.py` (112) | **SSRF 防護參考實作**：scheme 白名單、DNS 解析後比對私有/迴環/link-local/reserved 網段、`_ValidatingRedirectHandler` 對每一跳重驗（驗過就關掉轉址回應，urllib 不會把轉址的內容整個讀完）、`_OPENER` 用 `PublicHTTPHandler` / `PublicHTTPSHandler`（連線當下再檢查一次並只連到那個位址）、20 MB 大小上限、每次等資料 15 秒 timeout，整個下載另有 `overall_deadline(DOWNLOAD_DEADLINE_SECONDS)` 120 秒上限（慢慢送位元組的伺服器原本可以一直卡住下載執行緒） |

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
│   └── cot_code_review_gui.py    UI（工具 → AI 的分頁與 dock）；URL 只由 worker 驗證，UI 執行緒不查 DNS；每次送出先清掉上一輪的回覆；關閉時請審查停在目前這一步，交給 let_run_out()，不等
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

### `ssh/`（2,035 行）

| 檔案 | 職責 |
|---|---|
| `ssh_main_widget.py` | 組合視圖：上方共用登入表單，下方 splitter 左 30% 檔案樹、右 70% 終端。兩半各自連線、各自發 `state_changed`，共用的狀態列每次有一半連上或斷開就重報兩者的狀態（不是按下按鈕時）。`closeEvent` 把關閉往下傳給兩半（Qt 只會送給被關的那個 widget） |
| `ssh_login_widget.py` | 登入表單（密碼欄用 `EchoMode.Password`；任一欄按 Enter 就按下連線；金鑰欄旁的「瀏覽...」從 `~/.ssh` 開檔案對話框，選了檔就勾起金鑰驗證） |
| `ssh_command_widget.py` | 互動式 shell。連線和開 shell 的 channel（`open_shell_channel()`：開 session 最多等 paramiko 的 `channel_timeout` 一小時，pty 與 shell 沒有逾時）都在 `SshConnectThread` 上做，UI 執行緒只接手啟動 reader；連線中再按 Connect 不理，連線中關掉 widget 時執行緒交給 `let_run_out()`，晚到的連線一結束就關掉。`SSHReaderThread(QThread)` 輪詢 channel（shell 結束時先把緩衝裡剩下的讀完；伺服器那端結束 shell 時 `_on_closed()` 一樣 `_cleanup()` 關掉連線並發 `state_changed`，共用狀態列照兩半的實際狀態重報），`TerminalDecoder` 把每次讀到的 bytes 轉成文字：UTF-8 字元、escape 與結尾的 `\r` 被讀取切斷時留到下一次接上（`split_unfinished_end()`，`\r\n` 被切開不會多一行空行），escape（CSI、OSC/DCS/SOS/PM/APC 控制字串、`ESC ( B` 這類 nF、其他兩位元組 escape）用 regex 剝除，backspace 套用到前一個字元、其餘 C0 控制字元丟掉（`utils/terminal_text.py` 的 `strip_terminal_controls()`；切斷的 escape 由 `split_incomplete_escape()` 留到下一次）；送出指令走 `send_all()`：整串 UTF-8 bytes 用 `sendall` 送完（`Channel.send` 一次只送一個封包），只在這次送出時給 channel 5 秒逾時；輸出接在最後一行後面（不用 `appendPlainText`，那會讓每次讀取都另起一行），自己的提示訊息才另起一行，terminal 有 block 上限，keepalive。`closeEvent` 一律 `_cleanup()`：執行緒不能活得比 widget 久（QThread 還在跑就被銷毀會讓 Qt abort） |
| `ssh_file_viewer_widget.py` (722) + `sftp_session.py` (473) | `SSHFileTreeManager`（樹與右鍵選單，只看執行緒的 signal 做事）＋ `sftp_session.py` 的 `SFTPClientWrapper`、`SftpListThread` / `SftpTransferThread` / `SftpCallThread` 與純路徑工具（`remote_join`、`plain_remote_name`、`sort_entries`）：延遲載入的遠端檔案樹、右鍵選單（重新整理/建資料夾/改名/刪除/下載/上傳；新名稱只能是單一項目，`plain_remote_name()` 擋掉 `/`、`.`、`..`；改名已載入的資料夾會用新路徑重列子項；從檔案項目建資料夾或上傳時重新整理它所在的資料夾，`folder_item()`）、目錄優先 + 自然排序（項目是資料夾還是檔案記在 `KIND_ROLE`，`is_folder()` / `is_file()` 讀它，不看類型欄的字）；列目錄時符號連結用 `stat` 換成它指向的東西的類型與大小（`_follow_link`，伺服器列目錄用的是 `lstat`，連到資料夾的連結原本當成檔案），指不到東西的連結照舊當檔案。每個 SFTP 操作都經 `_session()`：拿 `_in_use` 鎖（paramiko 的 SFTP client 會把別的執行緒的回覆讀走丟掉，送出那個請求的執行緒就永遠等下去）、再 `_require_connection()`；列目錄與傳輸在工作執行緒上一直等，右鍵選單的建資料夾／改名／刪除交給 `SftpCallThread`（SFTP 回覆沒有逾時，放在 UI 執行緒會凍到 TCP 放棄），等 session 最多 `UI_WAIT_SECONDS`（1 秒），等不到就丟 `SftpBusy`（「連線忙碌」），完成後才更新樹（樹被清掉就不動）；下載先寫到同資料夾的暫存檔（`.<檔名>.*.part`），完整了才 `os.replace` 換上，失敗就刪掉暫存檔、原檔不動；上傳同理：先 `stat` 目標，已存在又沒說要取代就什麼都不傳、發 `exists` 讓樹先問（預設「否」），再 `put` 到 `.<檔名>.<亂數>.part`，完整了才 `posix_rename`（伺服器沒有這個擴充就先刪再 `rename`）換上；連線交給 `SshConnectThread`，成功後才列出根目錄；`SFTPClientWrapper.connect()` 用區域變數建連線，登入完如果 wrapper 已經被 `close()`（Disconnect 或關分頁）就自己關掉這條連線、丟 `ConnectAbandoned`，失敗時也只關自己的；連線中按 Disconnect 會把連線執行緒交給 `let_run_out()`（不跳「連線失敗」），可以再按 Connect；每次列目錄（根目錄、展開、重新整理）交給 `SftpListThread`，先顯示「載入中」，結果回來時只在樹沒被清掉（`_tree_generation`）、而且該項目等的還是這一次（`LISTING_ROLE` 序號，重新整理會取代前一次）時才填進去；下載／上傳交給 `SftpTransferThread(QThread)`（傳輸沒有自己的逾時，跑在 UI 執行緒會把整個 IDE 凍到傳完），一次只允許一個，傳輸中右鍵選單多一項「取消傳輸」（`SftpTransferThread.cancel()`：paramiko `get` / `put` 的進度回呼每塊都檢查，丟 `TransferCancelled`，暫存檔照失敗處理刪掉、要被取代的檔案不動，發 `cancelled`）；傳輸中按 Connect 不重連檔案樹（連線一開始就 `close()`，會把傳輸砍斷），只提示正在傳輸，`_refused_while_transferring()`；`closeEvent` 不等它也不打斷它（打斷會留下半個檔案），交給 `let_run_out()`，傳完才關掉 SFTP 連線 |
| `ssh_host_key_policy.py` | **`InteractiveHostKeyPolicy`** — 取代 `AutoAddPolicy`。首次連線顯示 SHA256 指紋要使用者確認，確認後寫入 `~/.pybreeze/ssh_known_hosts`（TOFU）。查詢、詢問、寫入都在模組層的 `_DECISION_LOCK` 裡一次一個（只有連線執行緒會拿，UI 執行緒不等它）；問之前先重讀檔案（同一次 Connect 的另一半剛接受過就不再問），使用者拒絕的 (host, 指紋) 記 10 秒，另一半直接拒絕；寫入時在檔案現況後面加一行（`_store()`），不用 `client.save_host_keys()`（那會用 Connect 時讀到的舊副本蓋掉別的分頁剛接受的主機），也不用 `HostKeys.save()`（paramiko 讀不懂的行，壞行或 `ssh-dss`，會被寫掉）。兩個 known_hosts 都經 `load_known_hosts()` 逐行讀，讀不懂的行跳過（`HostKeys.load` 遇到非 base64 的 key 丟 `InvalidHostKey`，整個 Connect 就失敗）。問題由 `HostKeyAsker`（住在 UI 執行緒的 QObject，`host_key_asker()` 取得，兩個 SSH widget 建立時先建好）顯示：從連線執行緒問時走 `BlockingQueuedConnection`，連線執行緒等答案、UI 不等。每個問題都從「否」開始；發問的面板已經關掉（dock 關閉即刪除）就答「否」，不會沿用上一題的答案 |
| `ssh_connect_thread.py` | `SshConnectThread(QThread)`：在自己的執行緒上跑一次會阻塞的 `connect()`，發 `connected` 或 `failed(message)`。`CONNECT_ERRORS` 是連線會丟的例外；`SHA1_ALGORITHMS` 是每個 `connect()` 都帶上的 `disabled_algorithms`，拒絕 SHA-1 的 RSA 簽章與金鑰交換（paramiko 5 已移除，paramiko 4 仍會提供；CVE-2026-44405）。TCP 10 秒、banner 15 秒、auth 30 秒逾時加起來，連不到的主機以前會把 IDE 凍住將近一分鐘 |
| `ssh_key_loader.py` | 依序嘗試各種私鑰型別，回傳第一個能解析的；都不行時 `unloadable_key_reason()` 分辨是密語沒給／給錯（檔案有加密，而且給的密語解不開它；用 `cryptography` 試解）還是不支援的私鑰（例如加密的 DSA） |

### `url/ai_code_review_gui.py`

獨立的 HTTP client widget：送出程式碼給審查端點、接受/拒絕回覆並記錄統計到 `~/.pybreeze/response_stats.txt`（開啟時用 `read_stats()` 讀回上次的總數接著算；檔案不是這個格式或讀不了就從 0 開始）。

- 請求走 `ReviewRequestThread(QThread)`，只有 `answered` / `failed` 兩個 signal 碰 UI（和 `SkillsSendGUI` 同一套）；送出中再按不會重送；`closeEvent` 不等它，交給 `thread_keeper.let_run_out()`：斷開它和面板的連線、留著參考直到它結束（等它會讓 IDE 凍住最長一個讀取逾時）
- `urls.txt` 只存 URL 的 SHA-256 指紋（`url_fingerprint()`）：API URL 可能帶權杖，依 CLAUDE.md 要當憑證看待；舊版留下的明文檔會在下次送出時改寫成指紋
- 非 2xx（含不跟隨的轉址）走 `failed`，狀態碼寫進面板，不會只留空白
- 接受/拒絕只在收到回答（`answered`）後可按，每個回答只能評一次；Send 按鈕由執行緒的 `finished` 恢復，請求不論怎麼結束都回得來

---

## 10. `pybreeze_ui/jupyter_lab_gui/`

- `jupyter_lab_thread.py` — `JupyterLauncherThread(QThread)`：`find_free_port()`（綁 127.0.0.1 讓核心挑空 port）→ `choose_python()`（IDE 選定的直譯器優先，其次 venv 的，最後 IDE 自己的）→ `is_jupyter_installed()`（問直譯器 `find_spec('jupyterlab')`，不問 pip；缺就自動裝）→ 啟動 server（`_start_server()`，在 `_process_lock` 裡先看 `_stopped`：`stop()` 之後就不再啟動，即使還在安裝）→ `_wait_until_ready()` 輪詢 port（60 秒 timeout）→ emit `server_ready(url)`。server 的輸出寫進暫存檔而不是管線（server 起來後沒人讀管線，緩衝區滿了它會卡在 `write()`）；提早結束時錯誤訊息取這個檔案的尾巴。失敗時 `error_occurred` 送的是原因（例外訊息，最多 2,000 字），traceback 只進 log；已經 `stop()`（分頁關了）的失敗不算失敗，只記 debug
- `jupyter_lab_widget.py` — 設 `WA_DeleteOnClose`：分頁關閉就刪掉（`close_tab` 只移除分頁、不刪 widget，網頁檢視與它的 Chromium renderer 會一直留到 IDE 結束）。收到 URL 後用 `QWebEngineView.setUrl()` 載入；失敗時在狀態列顯示「初始化失敗：原因」（純文字、可選取、自動換行）；`closeEvent` 一律關掉 server（launcher 執行緒在 lab 載入完就結束了，只停「還在跑的執行緒」等於從不停 server）；還在安裝或啟動的 launcher 交給 `let_run_out()`，不在 UI 執行緒等（安裝可能要好幾分鐘），也不用 `blockSignals`（那會連 `finished` 一起擋掉，keeper 永遠放不掉它）。IDE 關閉時 `PyBreezeMainWindow._close_tool_tabs_and_docks()` 會關掉所有非編輯器分頁與 `DestroyDock`，這個 `closeEvent` 才會被呼叫到

安全前提（CLAUDE.md 已明列）：server 只綁 localhost，因此 token/password 刻意留空、`disable_check_xsrf=True` 才能內嵌。`--ServerApp.port_retries=0`：port 被占就直接結束（走「提早結束」的回報），不讓它默默換 port。**不設 `allow_origin`**：loopback 擋不住瀏覽器，開放來源的話使用者逛到的任何網頁都能操作這個沒有 token 的 server。

---

## 11. `pybreeze_ui/syntax/`

- `syntax_keyword.py`（625 行）— 七份關鍵字清單，彙整成 `package_keyword_list`：
  `je_auto_control` / `je_load_density` / `je_api_testka` / `je_web_runner` / `automation_file` / `mail_thunder` / `test_pioneer`
- `syntax_extend.py` — 把前六個註冊到 `.json`（黃色 `#FFFF00`），`test_pioneer` 註冊到 `TEST_PIONEER_SUFFIXES` 的每個副檔名（`.yml`、`.yaml`，橘色 `#FF9900`），然後重置當前編輯器的 highlighter

`PackageManager.syntax_check_list` 決定要註冊哪些；用 `package_keyword_list.get(pkg, [])` 取值，套件沒有關鍵字清單時註冊空集合而不是炸掉。

---

## 12. `pybreeze/utils/` — 基礎工具（18 個子套件）

| 套件 | 內容 |
|---|---|
| `app_dirs.py` | `pybreeze_data_dir()` → `~/.pybreeze`，所有持久化資料的單一位置，建立時為 `0700`（`DATA_DIR_MODE`）；`pybreeze_data_path()` 只給路徑、不建立 |
| `terminal_text.py` | 終端輸出的 escape 與控制字元：`strip_terminal_controls()`（CSI、OSC/DCS 等控制字串、nF、兩位元組 escape 剝除，backspace 套用，其餘 C0 丟掉）、`split_incomplete_escape()`（讀取切斷在 escape 中間時把尾巴留給下一次）、`split_unfinished_end()`（再加上它前面或最後的 `\r`）、`take_leading_backspaces()`（一段開頭的 backspace 留給畫面，擦掉前一段已經顯示的字，不越過行首）。SSH terminal 與執行視窗共用 |
| `subprocess_util.py` | `utf8_subprocess_env()`（釘 `PYTHONIOENCODING`，解 Windows cp950 亂碼）、`no_window_creationflags()`（`CREATE_NO_WINDOW`，避免 GUI 程式彈出黑窗） |
| `logging/logger.py` | `pybreeze_logger`（具名 logger，**不動 root logger**）+ `PyBreezeLogger(RotatingFileHandler)`：寫到 `~/.pybreeze/logs/PyBreeze.log`（`PYBREEZE_LOG_FILE` 可改），UTF-8、附加模式、每行帶行程編號，第一筆紀錄才開檔；只在開檔時輪替，門檻 `PYBREEZE_LOG_MAX_BYTES`（預設 100 MB）；開不了檔就改寫 `os.devnull` 並警告一次。與 JEditor、FrontEngine 同一套做法（工作區 X-6） |
| `exception/` | `ITEException` 為根的 17 個例外類別 + `exception_tags.py` 訊息常數；`error_templates.py` 把名稱以 `_error` 結尾的常數變成語言字典的 `error_text_<名稱>`（英文字典直接取常數本身） |
| `network/url_validation.py` | `validate_url()`：先拒絕 `urlparse` 與 `urllib3` 讀出不同主機的 URL（反斜線、空白、控制字元，或兩者主機不同；`_check_one_reading`），再做 scheme 白名單、私有/迴環/link-local/reserved 阻擋、額外處理 CGNAT 與 NAT64 網段、IPv6 內嵌 IPv4 的偵測 |
| `network/public_http.py` | 只連到剛檢查過的位址（防 DNS rebinding）：`public_session()`（`_NoRedirectSession`：不跟也不準備轉址，3xx 原封不讀地回來；`PublicAddressAdapter`，連線開 socket 時把 urllib3 的 `_dns_host` 依序暫換成 `public_addresses()` 回傳的每個位址，連得上就用，全部失敗才丟最後一個錯誤）、`PublicHTTPHandler` / `PublicHTTPSHandler`（`http.client` 的 `_create_connection`）。主機名仍是連線的 host，所以 SNI、憑證檢查與 `Host` 標頭照舊；經 proxy 的連線不釘住。`overall_deadline(seconds)`：這個執行緒在區塊內的請求總共最多這麼久，釘住的連線等回應時把 socket 登記上去，時間到就 shutdown，丟 `ReadTimeout`（讀取逾時每來一個位元組就重算，慢慢送標頭的伺服器原本可以一直拖）；AI 審查、Skill、CoT 每一步都包在 `overall_deadline(DEFAULT_MAX_READ_SECONDS)` 裡。`test_http_goes_through_public_connections.py` 擋下直接呼叫 `requests.*` / `urlopen` |
| `network/http_client.py` | `read_capped_text()`（串流讀取有上限，超出丟 `ResponseTooLargeError`；照 `Content-Type` 明寫的 charset 解碼，沒寫就 UTF-8，不用 requests 給 `text/*` 的 ISO-8859-1，`named_charset()`；整個回應最多讀 `DEFAULT_MAX_READ_SECONDS`（300 秒），時間到由 `_Watchdog` 關掉連線（urllib3 的 `HTTPResponse.shutdown()` 能中斷別的執行緒上正在等的讀取），丟 `ReadTimeout`：讀取逾時只管每一塊之間，一次送一個位元組的伺服器可以一直拖下去；狀態列與標頭由呼叫端的 `public_http.overall_deadline()` 涵蓋）、`describe_request_error()`（給使用者看的失敗原因：逾時、連不上、URL 不合法等，不含 URL；requests 的錯誤訊息會引用含 token 的完整 URL）、`succeeded()`（只有 2xx 算回答；`response.ok` 連 3xx 都算，這些請求又不跟隨轉址）、`truncate_for_display()`、`CONNECT_TIMEOUT` |
| `curl_import/` | `curl_parser.py`(600) 完整 curl 解析（`-I` 是 HEAD、`--oauth2-bearer` 變成 `Authorization`（`-H` 給的優先）、URL 的 `#fragment` 丟掉、URL 拆不開（沒關的 `[`、不是數字的 port）就是 `CurlParseException`，`url_is_well_formed()` 也給 HAR 用：這種 entry 跳過；同名的 `-F` 全留（`request_body.py` 的 `form_parts()` 回傳 list，產生的程式寫成 `files=[(…), …]`）；表單一律以 multipart 送出：文字欄位也放進 `files=`，寫成 `(None, 文字)`（`form_entries()`），複製來的 `Content-Type: multipart/...` 不寫進 headers（`sent_headers()`，requests 要自己帶 boundary）；APITestka JSON action 遇到上傳檔案、`@file` body 或 `-b` cookie 檔就丟 `CurlParseException`；`@file` body 一律以位元組讀（`--data-binary` 原樣、`-d` 去掉 CR/LF，和 curl 一樣），和其他 `-d` 片段照命令列的順序接起來（`data_file_positions`）；`-b <檔案>` 存進 `cookie_files`，產生的程式以註解說明沒有讀它；`-G` 搭 `@file` 拒絕；bash 的 `$'...'` 先展開成一般引號字串再交給 `shlex`、短旗標叢集展開、`--data-urlencode`、`-F`、`--form-string`、`-b`、`-G`）；`-F` 的值照 curl 語法（`@` 開頭是上傳檔案），`--form-string` 與 HAR 的文字欄位進 `form_strings`、照字面；URL 的 query 只有「解碼再編碼會一模一樣」時才拆進 `params`（`query_tools.query_round_trips()`，URL Builder 也用它決定 query 顯示成 dict 還是原字串；否則照原樣留在 URL，`requests` 原封送出，簽章 URL 才不會壞），query 參數 `params` 同一個 key 出現多次時存成值的清單（`add_repeated_value()`），URL 的在前、`-G` 的在後，和 curl 實際送出的一樣；`http_method()` 只收 RFC 9110 的 token（HAR 也用它），方法會寫進產生的程式碼，不是 token 就拒絕；`request_body.py` 判斷 body 型別（`body_kind()`：JSON 物件要能原樣送回才走 `json=`，重複的 key、float 裝不下的數字、`NaN`、巢狀超過 100 層都照原字串送）；`request_codegen.py` 產 requests 程式（字串一律經 `python_string()`：`json.dumps` 預設把 BMP 以外的字元寫成兩個 surrogate，Python 讀成兩個字；JSON body 經 `python_literal()` 寫成 Python，`true`/`null` 在 Python 裡是未定義的名稱）；`script_templates.py`(293) 產 APITestka/LoadDensity/pytest 模板 |
| `har_import/` | `har_parser.py`(354) HAR → `CurlRequest`（重用 curl 那套 codegen；建不出請求的 entry 跳過，含半個字元（JSON 的 `\ud800`）的也跳過，同名 cookie 改走 `Cookie` header）；`is_api_like()` 濾掉靜態資源；`har_codegen.py` 批次產生單一腳本、函式名去重，每段開頭註解裡的控制字元寫成 `\xNN`（URL 裡的換行不會結束註解） |
| `header_tools/` | `header_analyzer.py`(318) 安全稽核；`header_merge.py` 依 HTTP 規則合併重複 header（Cookie 用 `; ` 其餘用 `, `） |
| `jwt_tools/`、`hash_tools/`、`timestamp_tools/`、`regex_tools/`、`query_tools/`、`url_tools/`、`diff_tools/`、`http_reference/`、`json_format/`、`response_inspector/` | 對應 §6 工具分頁的純邏輯。`json_format` 的 Format / Minify 不改內容：數字保留原文（先換成帶隨機標記的佔位字串、輸出後一次換回）、非 ASCII 原樣輸出、同一物件重複的 key 與 `NaN`/`Infinity` 報錯；`pretty_json_or_none()` 是同一套解析、不記 log 的版本，Response Inspector 的 body 與 JWT 各段（`jwt_decoder.shown_json()`）用它排版。`json_format/view_safe.py` 的 `dumps_for_view()` / `escape_for_view()`：工具顯示的 JSON 把文字框還不回原樣的字元（U+2029、U+FDD0、U+FDD1 會變換行，落單的 surrogate 會消失；U+2028 經 `toPlainText()`、U+0085 經 `splitlines()` 也會斷行）寫成 `\uXXXX`，JSON Format、Query/URL 轉 JSON、JWT、Response Inspector、cURL/HAR 產生的 JSON 與 Python 字串都經過它。`query_tools` 與 `url_tools` 讀 JSON 也保留數字原文、拒收 `NaN` 與同一物件重複的 key（`load_json_verbatim()`，用 `json_process.unique_pairs`），Query 轉 JSON 遇到不是 UTF-8 的 percent-escape 報錯而不換成 U+FFFD，`urlencode` 經 `encode_pairs()`：寫不進 URL 的字元（落單的 surrogate）報自己的錯，不從分頁的 slot 漏出去 |
| `file_process/get_dir_file_list.py` | 遞迴收集指定副檔名的檔案（大小寫不敏感） |
| `file_process/read_capped.py` | `read_text_capped(path, encoding, max_bytes=None)`：先看大小，超過 `MAX_OPEN_BYTES`（100 MB）丟 `FileTooLargeError`（`OSError`，`strerror` 說明大小與上限），HAR 分頁與架構圖編輯器開檔都經它，不在 UI 執行緒讀好幾 GB 的檔案 |
| `file_process/replace_file.py` | `replace_text(path, text, private=False)`：寫到旁邊的 `<名稱>.saving` 再 `os.replace` 過去，失敗時原檔不動、半成品刪掉；`private` 以 `0600` 建立（存金鑰的檔案用）；`replace_written(path, write)` 給別人寫的檔案（圖片、SVG）：`write` 拿到旁邊的 `<主檔名>.saving<副檔名>`（副檔名不變，看副檔名決定格式的寫入器照樣用），寫完才換上 |
| `manager/package_manager/` | `PackageManager`（單例 `package_manager`）持有 `syntax_check_list` |

**分層原則**：`utils/` 不 import Qt 或 JEditor，由 `test_utils_has_no_qt.py` 守著，所以全部是不需要視窗的純邏輯測試。

---

## 13. `pybreeze/extend_multi_language/`

`extend_english.py` 與 `extend_traditional_chinese.py` 各 733 個鍵，`update_language_dict()` 把它們併進 `je_editor` 的字典，並把 `application_name`（「PyBreeze」）寫進 `language_wrapper.choose_language_dict` 裡每一個語言：這是 PyBreeze 唯一覆寫而非新增的 JEditor 鍵，日文、簡中等 PyBreeze 沒翻譯的語言自帶「JEditor」，不寫的話會蓋過英文退回值。`test_language_parity.py` 守住兩邊鍵值必須對齊，也檢查每個已註冊語言都解得出程式用到的每個鍵；`test_startup_language.py` 在子行程裡用存好的繁中／日文真的啟動主視窗。

---

## 14. `pybreeze/extend/prthinker_extend/prthinker_setting.py`

純邏輯、無 Qt，值得單獨一節，因為它示範了本專案處理祕密的方式：

- 設定存 `~/.pybreeze/prthinker_setting.json`（經 `replace_text(..., private=True)` 整檔替換，只有擁有者讀得到；讀取時什麼都不建立，存檔失敗時對話框會說；「額外參數」斷不了詞（引號沒關）就不存，`read_extra_arguments()` 與執行時用同一套斷詞）
- `environment_for()` 把設定轉成 `PRTHINKER_*` 環境變數交給子行程，**命令列只留「這次要審什麼」** — API key 不會出現在工作管理員或執行紀錄
- `SECRET_SETTINGS` 四個欄位在 `loggable()` 中一律縮成 `(set)` / 空字串
- 模型名稱依後端交給不同變數（`MODEL_ENVIRONMENT`）：`remote` / `local` 是 `PRTHINKER_MODEL_NAME`，其他後端是各自的 `PRTHINKER_<BACKEND>_MODEL`。prthinker 只有 local 讀 `PRTHINKER_MODEL_NAME`（remote 由伺服器決定模型，只拿來標示）
- `extra_arguments()` 經 `split_arguments()` 以命令列規則斷詞（引號內空白不拆，`#` 不當註解）；反斜線是路徑分隔字元的平台（Windows）上反斜線不當跳脫字元，`C:\reviews` 才不會變成 `C:reviews`。解析失敗當作沒有而不是讓整次審查失敗
- `install_target()` 回傳 `<path>[runner]`，因為 prthinker 不在 PyPI 上；資料夾要有 `pyproject.toml` 且專案名稱是 prthinker，否則不給目標、也不記住
- 規則檢索（`rag`，`RAG_MODES = ("off", "remote")`）**永遠明講**，而且兩個變數都送：`off` 給 `PRTHINKER_RAG_ENABLED=false` + `PRTHINKER_REMOTE_RAG=false`，`remote` 兩個都 `true`（走伺服器的 `/rag`），認不得的值當 `off`。子行程繼承 IDE 的環境，少送一個就會被使用者 shell 裡的設定決定。prthinker 的預設是本機 FAISS 檢索，但那份索引（`codes/`）只在它的原始碼庫、被排除在套件外，從這裡裝的 prthinker 一跑就 `ModuleNotFoundError: codes`

支援的後端：`remote / local / openai / anthropic / gemini / cohere / mistral / claude-cli / codex-cli`；平台：`github / gitlab / gitea`。

---

## 15. 設計模式落點

| 模式 | 落點 |
|---|---|
| **Facade** | `pybreeze/__init__.py` — 對外只暴露 `start_editor`、`PyBreezeMainWindow`、`EDITOR_EXTEND_TAB` 與轉出的插件 API；第一次用到才 import（PEP 562 `__getattr__`），所以 `import pybreeze.utils.*` 不會連帶載入 PySide6 與 JEditor |
| **Strategy** | 六個自動化模組共用 `build_process()`，差別只在 `_PACKAGE` |
| **Template Method** | `TaskProcessManager` 固定 spawn → read threads → QTimer poll → drain → exit 的骨架 |
| **Observer** | Queue + QTimer 把子行程輸出橋接到 UI 執行緒；Qt Signal/Slot（`SenderThread.update_response`、`JupyterLauncherThread.server_ready`） |
| **Factory** | `build_automation_menu()`；`tools_menu._WIDGET_FACTORIES` |
| **Registry / Table-driven** | `_TAB_ACTIONS`、`_DOCK_ACTIONS`、`package_keyword_list`、`EDITOR_EXTEND_TAB`、`TEMPLATE_TARGETS` |
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
    ├── daemon Thread: pybreeze-report-mail（send_after_test → send_report，結果經 _MailNotice queued signal 寫回執行視窗；_MailNotice 掛在 QApplication 底下、送達後 deleteLater，在 GUI 執行緒上刪除）
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

另有 `~/.pybreeze/logs/PyBreeze.log`（`PYBREEZE_LOG_FILE` 可改；開檔時超過 100 MB 就輪替成 `.1`）與各自動化套件自己的 log。

---

## 18. 測試與 CI

- **單元測試** `test/test_utils/` — 127 個 `test_*.py`、2285 個測試（14 個 prthinker 契約測試在沒有 prthinker 的直譯器上跳過）。純邏輯 + headless Qt widget 測試（`QT_QPA_PLATFORM=offscreen`）。涵蓋 curl/HAR 解析、SSRF 驗證、SSH 安全、process reader EOF、queue pump、語言對齊、mermaid parser、diagram 序列化、prthinker 設定、JEditor 內部介面契約（`test_jeditor_contract.py`）、`except Exception` 只能重拋或註明理由（`test_no_blind_except.py`）等。有 hypothesis fuzz 測試（`test_fuzz_pure_logic.py`）。
- **整合測試** `test/unit_test/start_automation/` — 以 `debug_mode=True` 啟動 IDE，10 秒後自動關閉，驗證啟動流程與 extend tab
- **CI** `.github/workflows/{dev,stable}.yml` — `unit-tests` job 跑 Windows runner、Python 3.10–3.14 矩陣，3.12 那一腳額外上傳 `coverage-xml` artifact；`sonarcloud` job 跑 ubuntu、`needs: unit-tests`。每日 02:00 排程 + push/PR 觸發。`stable.yml` 另有 `publish` job 負責版號遞增與 PyPI 發布
- **覆蓋率** `.coveragerc` — `relative_files = True` 是必要的：報告在 Windows 產生、由 Linux 上的 scanner 讀取，路徑不能帶機器資訊。目前整體 60%（`utils/`、`tools_gui`、`dialog` 95–100%；`editor_main` 58%、`menu` 54%；仍低的是 `diagram_editor` 45%、`process_executor` 39%、`connect_gui` 28%）
- **靜態分析** SonarCloud（`sonar-project.properties`，CI-based analysis；Automatic Analysis 已關閉且必須維持關閉，兩種模式互斥）+ Codacy（`.codacy.yml`）+ Bandit（`pyproject.toml` 中排除 test、skip B101/B404）
- **SonarCloud 方案限制** 該組織的方案只開放 `main` 與 PR 的分析結果。非 main 分支的分析送得出去、CE 任務也會成功，但結果讀回來是 403（組織內每個專案都只有 `main` 一條分支）。因此 `dev.yml` 只在 PR 時掃描，`stable.yml` 另外掃 push to `main`

---

## 19. 掃描過程中發現的事實記錄

以下是客觀觀察，不是缺陷判定，但值得留意：

1. **`file_tree_context_menu.setup_file_tree_context_menu()` 用 monkey patch** — 直接覆寫 `main_window.tab_widget.addTab` 來攔截新分頁。可行但脆弱，若他處也包裝 `addTab` 會疊加。

2. **`PyBreezeMainWindow.__init__` 的 `extend` 參數語意分歧** — 對 `super()` 恆傳 `extend=True`，而參數本身只用來決定要不要設定 Windows AppUserModelID 與視窗圖示。

3. **`start_editor()` 以 `os._exit(ret)` 收場** — 繞過 atexit 與 Qt 拆解。對 GUI 主程式常見（避免殘留執行緒卡住），但 `closeEvent` 之後的清理路徑等於不存在。

4. **`PackageManager` 名實不符** — 類別名暗示 pip 管理，實際只承載 `syntax_check_list` 六個項目；pip 安裝落在 `install_utils.install_package()`。

---

## 20. 一句話總結

PyBreeze 的架構骨幹是 **「薄 UI + 表格化註冊 + 純邏輯 utils + 子行程隔離執行」**：選單與工具用宣告式表格組裝，業務邏輯下沉到無 Qt 依賴的 `utils/` 以便測試，任何會跑使用者程式碼的東西一律推到子行程，再用 Queue + QTimer 這條單向管線把輸出安全地送回 UI 執行緒。
