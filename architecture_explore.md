# PyBreeze 架構探勘 / Architecture Exploration

> 掃描範圍：`pybreeze/`（189 個 `.py`、約 16,300 行）＋ `test/`、`exe/`、`docs/`、CI 設定
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
   │  tools_gui     19 個工具分頁（curl、HAR、JWT、diff、regex…）             │
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
   │  mail_thunder_extend/  測試後寄報告 hook                                 │
   │  prthinker_extend/     prthinker 設定與指令組裝（純邏輯）                │
   └────────────────────────────────┬────────────────────────────────────────┘
                                    ▼
   ┌─────────────────────────────────────────────────────────────────────────┐
   │ 基礎層 Foundation                                                        │
   │  pybreeze/utils/              14 個工具子套件（純邏輯，可單測）           │
   │  pybreeze/extend_multi_language/  內建 i18n（英 / 繁中，各 571 鍵）      │
   └─────────────────────────────────────────────────────────────────────────┘
                                    ▼
   外部子行程：python -m je_api_testka / je_auto_control / je_web_runner /
               je_load_density / automation_file / je_mail_thunder /
               test_pioneer / prthinker
```

---

## 3. 啟動流程

`pybreeze/pybreeze_ui/editor_main/main_ui.py:100` 的 `start_editor()`：

1. 取得（或建立）`QApplication`
2. 建立 `PyBreezeMainWindow`，其 `__init__` 依序：
   - `update_language_dict()` 併入 PyBreeze 的 571 條翻譯——**必須在 `super().__init__` 之前**：JEditor 在那裡依設定挑啟動語言，英文以外的語言讀的是當下合併出來的一份副本，之後才加進去的字串它看不到，選單拿到 `None` 標題就讓 Qt 當掉（access violation）
   - `super().__init__(..., extend=True)` — JEditor 在此已呼叫 `load_external_plugins()`，自動掃描 CWD 下的 `jeditor_plugins/`
   - 刪掉 JEditor 原本的 Help 選單
   - 設定標題、Windows AppUserModelID、圖示
   - `add_menu_to_menubar()` — 建構全部選單（見 §5）
   - `syntax_extend_package()` — 註冊 `.json` / `.yml` 自動化關鍵字高亮
   - 依 `EDITOR_EXTEND_TAB` 註冊表加入外部擴充分頁
   - `setup_file_tree_context_menu()` — 掛上檔案樹右鍵選單
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
| 解譯器解析 | `renew_path()` → 執行視窗帶著 IDE 選定的直譯器（`python_compiler`，由 `build_task_process()` 從主視窗抄過來）就用它；沒選才用 `find_venv_path()` 找 `venv/`、`.venv/`，交給 `check_and_choose_venv()`；找不到時**不拋例外**，直接把錯誤寫進執行視窗並回傳 `False` |
| 啟動 | `subprocess.Popen(args, shell=False, creationflags=CREATE_NO_WINDOW, env=PYTHONIOENCODING=...)` |
| 讀取 | 兩條 daemon Thread 各自經 `queue_pump.read_stream_into_queue()` 對 stdout / stderr `readline()`，原樣塞進 `Queue`（保留縮排、行尾與空行）；**空讀 = EOF 立刻 break**（否則會 100% CPU 空轉） |
| 送 UI | `QTimer` 每 100 ms 呼叫 `pull_text()`，經 `pump_message_queue()` 每 tick 最多抽 256 則，交給 `CodeWindow.append_output()` |
| 收尾 | `exit_program()`：join 執行緒（timeout 2s）→ drain queue（`max_messages=None` 一次抽乾）→ `terminate()` → 呼叫 `task_done_trigger_function`（例如寄信） |

三種啟動介面：

- `start_test_process(package, exec_str)` — 腳本內容直接走 `--execute_str`（Windows 上先 `json.dumps` 逃逸）
- `start_test_process_file(package, file_path)` — 走 `--execute_file`，避開 Windows ~32K 命令列上限
- `start_module_process(package, arguments, environment)` — 通用形式；**祕密（API key、token）走 environment 不走命令列**，工作管理員看不到

### 4.2 `process_executor_utils.py` — 工廠函式

| 函式 | 用途 |
|---|---|
| `build_process()` | 取當前分頁的程式碼（或傳入的 `exec_str`）→ `start_process()` |
| `start_process()` | 建 `CodeWindow` + `TaskProcessManager` → `start_test_process()` |
| `build_process_from_file()` | 以檔案路徑執行單一檔案 |
| `run_dir_files_with_package()` | 問使用者選資料夾，對每個 `.json` 開一個執行視窗批次跑 |
| `build_task_process()` | 共用建構：建 `CodeWindow` 並帶上主視窗選定的直譯器、掛進 `main_window.current_run_code_window`、決定要不要接 `send_after_test`。建好的 `TaskProcessManager` 掛在執行視窗的 `runner` 上，所以呼叫端可以不留參考。prthinker 審查也走這裡 |

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
  - 編譯式：`compiler file -o out` → 執行 `out` → 執行完 `os.remove()` 清掉產物
  - 編譯有 60 秒 timeout，QTimer 間隔 50 ms（比 Python 執行器更快）
  - 讀取、pump、drain 與寫進視窗都用 §4.5 的共用函式
  - `run_current_file_with()` 建好後同樣掛在執行視窗的 `runner` 上

### 4.5 `queue_pump.py` 與 `CodeWindow.append_output()`

子行程輸出到執行視窗的整條管線，兩個執行器（`TaskProcessManager`、`FileRunnerProcess`）共用：

- `read_stream_into_queue(stream, queue, buffer_size, encoding, keep_reading)` — reader 執行緒用。行**原樣**進 queue（縮排、行尾、空行都留著）；空讀 = EOF 即停，管線被關掉的 `OSError` / `ValueError` 記 debug 後停
- `pump_message_queue(q, append_fn, is_error, max_messages)` — UI 執行緒用。`MAX_MESSAGES_PER_PUMP = 256`：每 tick 只抽一則的話輸出上限只有 ~10 行/秒，聒噪的腳本會爬行；有上界則避免洪水輸出卡住 UI 執行緒。`max_messages=None` 是收尾時一次抽乾。只跳過空字串
- `CodeWindow.append_output(text, is_error, own_line=False)`（`show_code_window/code_window.py`）— 一律寫在文件**尾端**（不用 widget 自己的游標：那個游標跟著使用者的點擊與選取走，寫在那裡會把輸出插進中間、或蓋掉使用者選取的文字）。`\r\n` 與單獨的 `\r` 轉成換行；換行只出現在文字本身有換行的地方，所以超過 buffer 被切段的長行會接回同一行。`own_line=True` 給視窗自己的狀態訊息（`Task exit with code …`），程式留下沒換行的半行時先補一個換行。捲軸在最底時畫面跟著輸出走（像終端機）；使用者往上捲去讀時就停在原處

---

## 5. 選單層 `pybreeze_ui/menu/`

`build_menubar.py:add_menu_to_menubar()` 是唯一入口，依序建構 14 個選單建構器。

### 5.1 `automation_menu_factory.py` — 選單工廠

`build_automation_menu()` 用宣告式參數組出標準自動化子選單：`Run` 子選單 / `Help`（文件＋GitHub，開內嵌瀏覽器分頁）/ `Project`（建立範本目錄）/ GUI 分頁。六個自動化模組全部靠它，`build_*_menu.py` 只剩一份設定表。每個 QAction 都以它所在的選單為 parent，由 Qt 持有；AutoControl 額外的 `Record` 子選單也一樣。

`safe_create_project(import_name)` 回傳延遲 import 的 closure，模組沒裝時只記 log 不炸選單。

| 選單 | 文件 | GUI 分頁 |
|---|---|---|
| APITestka | apitestka.readthedocs.io | `APITestkaWidget` |
| AutoControl | autocontrol.readthedocs.io | `AutoControlGUIWidget` |
| WebRunner | webrunner.readthedocs.io | — |
| LoadDensity | loaddensity.readthedocs.io | `LoadDensityWidget` |
| FileAutomation | fileautomation.readthedocs.io | — |
| MailThunder | mailthunder.readthedocs.io | — |

### 5.2 非工廠的兩個選單

- **`test_pioneer_menu/`** — 建範本目錄 + `QFileDialog` 選 `.yml`（會驗副檔名，選錯跳 `QMessageBox`）
- **`prthinker_menu/`** — 審查目前檔案 / 審查 PR（`QInputDialog` 問編號，範圍 1–1,000,000）/ 設定對話框 / Help

### 5.3 `tools/tools_menu.py` — 表格驅動的工具註冊

這是全專案設計最乾淨的一塊。三張表把 19 個工具的「建構」「分頁開啟」「dock 開啟」完全解耦：

- `_WIDGET_FACTORIES: dict[str, Callable]` — widget key → 建構 lambda
- `_TAB_ACTIONS: tuple[...]` — (widget key, 主視窗屬性, 選單屬性, action 語言鍵, 分頁標籤鍵)
- `_DOCK_ACTIONS` / `_DOCK_TITLES` — 同一組 widget 也能開成右側 dock

`_register_action()` 有一段關鍵註解：QAction 必須 `setattr` 掛回主視窗，否則 Qt 不持有它、被 GC 後選單項就失效。另一種做法是建構時把選單當 parent（自動化選單工廠、插件選單用這種）。`test_started_menus.py` 在子行程啟動真的 IDE、GC 後走訪整條選單列，任何子選單變空就失敗（JEditor 的兩個字型選單除外：offscreen 平台沒有字型）。

### 5.4 插件選單

- **`build_plugin_menu.py`** — 讀 `je_editor.plugins.get_all_plugin_metadata()`，每個插件一個子選單（About + 每個副檔名一個 Run 動作，動作直接呼叫 `run_current_file_with()`）；另有「Plugin Browser」分頁入口
- **`build_run_with_menu.py`** — 讀 `get_all_plugin_run_configs()`，在 Run 選單下加「Run with…」。`run_current_file_with()` 先經 `save_current_file_for_run()` 存檔（已有檔名的分頁照 JEditor 自己存檔的方式寫：`write_file_with_encoding()` 用分頁的編碼與行尾，寫之前 `mark_ignore_next_file_change()`、寫完 `mark_saved()`；沒檔名的走 JEditor 的另存新檔），再驗副檔名、交給 `FileRunnerProcess`。Plugins 選單的 Run 動作也走這一條

### 5.5 安裝選單

`install_utils.install_package()` 借用 JEditor 的 `ShellManager` 跑 `pip install -U`，輸出進 shell 面板。

- `automation_menu/` — 七個自動化套件的一鍵安裝。**prthinker 例外**：不在 PyPI 上，第一次會問來源資料夾、記進設定，之後裝 `<path>[runner]`
- `tools_menu/` — 安裝 setuptools / build / wheel

---

## 6. 工具分頁 `pybreeze_ui/tools_gui/`（13 個工具 widget + 2 個共用機制）

每個工具都是 `QWidget`，UI 極薄，真正邏輯全在 `pybreeze/utils/` 對應的純函式套件裡（所以測得動、也測了）。

| 工具 widget | 對應 utils | 功能 |
|---|---|---|
| `CurlImportGUI` | `utils/curl_import/` | 貼上 curl 指令 → 產生 requests / pytest / APITestka(py & json) / LoadDensity 腳本 |
| `HarImportGUI` | `utils/har_import/` | 開 `.har` → 列出錄到的請求（可只看 API-like）→ 批次產生腳本 |
| `JwtDecoderGUI` | `utils/jwt_tools/` | 解 JWT header/payload（不驗簽），時間戳轉可讀 UTC |
| `TimestampGUI` | `utils/timestamp_tools/` | epoch（自動判秒／毫秒）↔ ISO-8601 |
| `HashGUI` | `utils/hash_tools/` | 多演算法摘要 |
| `QueryJsonGUI` | `utils/query_tools/` | query string ↔ JSON 雙向 |
| `UrlBuilderGUI` | `utils/url_tools/` | URL 拆成 JSON 元件 / 由元件組回 URL |
| `RegexGUI` | `utils/regex_tools/` | regex 測試，flag 勾選、列出每個 match 與群組 |
| `HttpStatusGUI` | `utils/http_reference/` | 狀態碼參考，可依碼前綴或描述搜尋 |
| `DiffGUI` | `utils/diff_tools/` | unified diff + 增刪統計 |
| `JsonFormatGUI` | `utils/json_format/` | 美化 / 壓縮 / 驗證 |
| `HeaderAnalyzerGUI` | `utils/header_tools/` | HTTP header 安全稽核（HSTS、CSP、CORS、Set-Cookie、banner…）|
| `ResponseInspectorGUI` | `utils/response_inspector/` | 貼整包 response → 拆狀態列/headers/body，順便挖出 JWT |

### 兩個橫向共用機制

- **`tool_tabs.open_tool_tab()`** — 工具之間互相「轉交」：Response Inspector 把狀態碼丟給 HTTP Status、headers 丟給 Header Analyzer、JWT 丟給 JWT Decoder、JSON body 丟給 JSON Format；curl 匯入把 URL 丟給 URL Builder。開新分頁並自動聚焦。
- **`output_actions.OutputActions`** — 統一的「複製 / 在編輯器開啟 / 存檔」三顆按鈕，綁在工具的唯讀輸出 `QTextEdit` 上；副檔名與檔名可傳 callable 動態決定。

---

## 7. `pybreeze_ui/diagram_editor/` — 架構圖編輯器（3,310 行，最大子系統）

| 檔案 | 職責 |
|---|---|
| `diagram_editor_widget.py` (584) | 外層 widget：兩排工具列（工具模式列 + 檔案/undo/對齊/格線/匯出/縮放列）、canvas 與屬性面板的 splitter、快捷鍵；PNG/SVG 匯出；Mermaid 匯入對話框 |
| `diagram_scene.py` (648) | `DiagramScene(QGraphicsScene)`：**State pattern** 的 `ToolMode` 決定滑鼠行為；undo/redo、複製貼上、多選對齊與分佈、z-order、序列化 `to_dict()` / `load_from_dict()` |
| `diagram_items.py` (830) | 圖元：`DiagramNode`（矩形/圓角/橢圓/菱形 4 種 body + 置中標籤 + 4 個 `ResizeHandle`）、`DiagramConnection`（三次貝茲 + 箭頭，連到節點邊界交點）、`DiagramImage`。`_EditableLabel` 刻意預設唯讀、雙擊才進編輯（對應 CLAUDE.md 的 Qt 規範） |
| `diagram_mermaid_parser.py` (520) | Mermaid flowchart → diagram dict。含 **Sugiyama 風格自動排版**：分層 → 交叉最小化掃描 → 交叉軸偏移解析 |
| `diagram_property_panel.py` (421) | 右側屬性側欄，依選取型別切換 node / connection / image 三組表單 |
| `diagram_view.py` (175) | `QGraphicsView`：滾輪縮放（有上下界）、中鍵平移、`drawBackground` 畫格線 |
| `diagram_commands.py` (28) | `DiagramSnapshotCommand(QUndoCommand)` — 快照式 undo，存變更前後完整場景狀態 |
| `diagram_net_utils.py` (104) | **SSRF 防護參考實作**：scheme 白名單、DNS 解析後比對私有/迴環/link-local/reserved 網段、`_ValidatingRedirectHandler` 對每一跳重驗、20 MB 大小上限、15 秒 timeout |

`diagram_net_utils` 是 CLAUDE.md 指定的網路安全參考實作，其他 HTTP 呼叫端則統一走 `utils/network/url_validation.py`。

---

## 8. `pybreeze_ui/extend_ai_gui/` — AI 輔助

```
extend_ai_gui/
├── ai_gui_global_variable.py     模板檔名清單 + 檔名→內建模板內容對照表
├── prompt_store.py               編輯過的 prompt 檔案解析（~/.pybreeze/prompts/）
├── code_review/
│   ├── cot_chain.py              接線表（純邏輯，無 Qt）：哪步引用哪步
│   ├── code_review_thread.py     SenderThread(QThread)：跑八步審查鏈
│   └── cot_code_review_gui.py    UI
├── prompt_edit_gui/
│   ├── prompt_editor_widget.py         共用編輯器（QFileSystemWatcher 熱更新）
│   ├── cot_prompt_editor_widget.py     8 個 CoT 模板的檔案清單＋語言鍵
│   ├── skills_prompt_editor_widget.py  2 個 Skill 模板的檔案清單＋語言鍵
│   ├── prompt_file_io.py               共用存檔（失敗跳警告對話框）
│   ├── cot_code_review_prompt_templates/   8 個模板常數＋global_rule
│   └── skills_prompt_templates/            2 個模板常數
└── skills/skills_send_gui.py     單次 prompt 發送（RequestThread）
```

**CoT 審查鏈**（`cot_chain.py` 定義接線，`code_review_thread.py` 執行）八個步驟：

```
first_summary → first_code_review → judge_single_review ┐（評分前一步的審查）
              → linter → code_smell_detector → step_by_step_analysis ┐（走過每條發現）
              → total_summary → judge（帶 linter/code smell 脈絡評分總結）
```

**編輯過的 prompt 會生效**（`prompt_store.py`）：每個模板都以程式碼常數出貨，`~/.pybreeze/prompts/<名稱>.md` 存在且非空時覆寫它。編輯器讀寫的就是這個位置，所以在編輯器裡改 prompt 會改變審查實際送出的內容 —— 這正是編輯器存在的理由。檔案缺失、空白、讀不到都退回內建版本；編輯過的 prompt 若含有鏈填不了的 placeholder，記 log 後退回內建，不讓整次審查倒在使用者無法從 UI 診斷的 `KeyError` 上。讀取不會建目錄，只有存檔才會。

`cot_chain.py` 用兩張表描述接線：`STEP_RESULT_KEY`（每步答案存在哪個 key）與 `STEP_ARGUMENTS`（每步的 placeholder 由哪個 key 填）。**順序即相依順序** —— 每步只能引用它上面的步驟，`test_cot_chain.py` 有結構性測試守住這件事。步驟失敗時錯誤訊息只顯示給使用者、不會被存進 results，避免後續步驟把「傳送失敗」當成審查內容引用。每步都套 `build_global_rule_template()` 包一層全域規則。

安全處理：送出前 `validate_url()`、`allow_redirects=False`、`stream=True` 搭配 `read_capped_text()` 限制回應大小、單一 `requests.Session` 重用 TCP/TLS 連線、`isInterruptionRequested()` 讓 widget 關閉時能中止。

---

## 9. `pybreeze_ui/connect_gui/`

### `ssh/`（1,116 行）

| 檔案 | 職責 |
|---|---|
| `ssh_main_widget.py` | 組合視圖：上方共用登入表單，下方 splitter 左 30% 檔案樹、右 70% 終端 |
| `ssh_login_widget.py` | 登入表單（密碼欄用 `EchoMode.Password`） |
| `ssh_command_widget.py` | 互動式 shell。`SSHReaderThread(QThread)` 輪詢 channel，ANSI escape 用 regex 剝除，terminal 有 block 上限，keepalive |
| `ssh_file_viewer_widget.py` (572) | `SFTPClientWrapper` + `SSHFileTreeManager`：延遲載入的遠端檔案樹、右鍵選單（重新整理/建資料夾/改名/刪除/下載/上傳）、目錄優先 + 自然排序 |
| `ssh_host_key_policy.py` | **`InteractiveHostKeyPolicy`** — 取代 `AutoAddPolicy`。首次連線顯示 SHA256 指紋要使用者確認，確認後寫入 `~/.pybreeze/ssh_known_hosts`（TOFU） |
| `ssh_key_loader.py` | 依序嘗試各種私鑰型別，回傳第一個能解析的 |

### `url/ai_code_review_gui.py`

獨立的 HTTP client widget：送出程式碼給審查端點、接受/拒絕回覆並記錄統計到 `~/.pybreeze/response_stats.txt`、URL 歷史存 `urls.txt`。

---

## 10. `pybreeze_ui/jupyter_lab_gui/`

- `jupyter_lab_thread.py` — `JupyterLauncherThread(QThread)`：`find_free_port()`（綁 127.0.0.1 讓核心挑空 port）→ `get_venv_python()` → `is_jupyter_installed()`（缺就自動裝）→ 啟動 server → `_wait_until_ready()` 輪詢 port（60 秒 timeout）→ emit `server_ready(url)`
- `jupyter_lab_widget.py` — 收到 URL 後用 `QWebEngineView.setUrl()` 載入；`closeEvent` 負責關掉 server

安全前提（CLAUDE.md 已明列）：server 只綁 localhost，因此 token/password 刻意留空、`disable_check_xsrf=True` 才能內嵌。

---

## 11. `pybreeze_ui/syntax/`

- `syntax_keyword.py`（625 行）— 七份關鍵字清單，彙整成 `package_keyword_list`：
  `je_auto_control` / `je_load_density` / `je_api_testka` / `je_web_runner` / `automation_file` / `mail_thunder` / `test_pioneer`
- `syntax_extend.py` — 把前六個註冊到 `.json`（黃色 `#FFFF00`），`test_pioneer` 註冊到 `.yml`（橘色 `#FF9900`），然後重置當前編輯器的 highlighter

`PackageManager.syntax_check_list` 決定要註冊哪些；用 `package_keyword_list.get(pkg, [])` 取值，套件沒有關鍵字清單時註冊空集合而不是炸掉。

---

## 12. `pybreeze/utils/` — 基礎工具（14 個子套件）

| 套件 | 內容 |
|---|---|
| `app_dirs.py` | `pybreeze_data_dir()` → `~/.pybreeze`，所有持久化資料的單一位置 |
| `subprocess_util.py` | `utf8_subprocess_env()`（釘 `PYTHONIOENCODING`，解 Windows cp950 亂碼）、`no_window_creationflags()`（`CREATE_NO_WINDOW`，避免 GUI 程式彈出黑窗） |
| `logging/logger.py` | `pybreeze_logger`（具名 logger，**不動 root logger**）+ `PyBreezeLogger(RotatingFileHandler)`，上限由 `PYBREEZE_LOG_MAX_BYTES` 控制（預設 100 MB） |
| `exception/` | `ITEException` 為根的 17 個例外類別 + `exception_tags.py` 訊息常數 |
| `network/url_validation.py` | `validate_url()`：scheme 白名單、私有/迴環/link-local/reserved 阻擋、額外處理 CGNAT 與 NAT64 網段、IPv6 內嵌 IPv4 的偵測 |
| `network/http_client.py` | `read_capped_text()`（串流讀取有上限，超出丟 `ResponseTooLargeError`）、`truncate_for_display()`、`CONNECT_TIMEOUT` |
| `curl_import/` | `curl_parser.py`(401) 完整 curl 解析（短旗標叢集展開、`--data-urlencode`、`-F`、`-b`、`-G`）；`request_body.py` 判斷 body 型別；`request_codegen.py` 產 requests 程式；`script_templates.py`(271) 產 APITestka/LoadDensity/pytest 模板 |
| `har_import/` | `har_parser.py`(304) HAR → `CurlRequest`（重用 curl 那套 codegen）；`is_api_like()` 濾掉靜態資源；`har_codegen.py` 批次產生單一腳本、函式名去重 |
| `header_tools/` | `header_analyzer.py`(318) 安全稽核；`header_merge.py` 依 HTTP 規則合併重複 header（Cookie 用 `; ` 其餘用 `, `） |
| `jwt_tools/`、`hash_tools/`、`timestamp_tools/`、`regex_tools/`、`query_tools/`、`url_tools/`、`diff_tools/`、`http_reference/`、`json_format/`、`response_inspector/` | 對應 §6 工具分頁的純邏輯 |
| `file_process/get_dir_file_list.py` | 遞迴收集指定副檔名的檔案（大小寫不敏感）+ 資料夾選擇對話框包裝 |
| `manager/package_manager/` | `PackageManager`（單例 `package_manager`）持有 `syntax_check_list` |

**分層原則很一致**：`utils/` 幾乎不 import Qt（例外只有 `get_dir_file_list` 的 QFileDialog），所以 61 個單元測試全部跑得動。

---

## 13. `pybreeze/extend_multi_language/`

`extend_english.py` 與 `extend_traditional_chinese.py` 各 571 個鍵，`update_language_dict()` 把它們併進 `je_editor` 的字典，並把 `application_name`（「PyBreeze」）寫進 `language_wrapper.choose_language_dict` 裡每一個語言：這是 PyBreeze 唯一覆寫而非新增的 JEditor 鍵，日文、簡中等 PyBreeze 沒翻譯的語言自帶「JEditor」，不寫的話會蓋過英文退回值。`test_language_parity.py` 守住兩邊鍵值必須對齊，也檢查每個已註冊語言都解得出程式用到的每個鍵；`test_startup_language.py` 在子行程裡用存好的繁中／日文真的啟動主視窗。

---

## 14. `pybreeze/extend/prthinker_extend/prthinker_setting.py`

純邏輯、無 Qt，值得單獨一節，因為它示範了本專案處理祕密的方式：

- 設定存 `~/.pybreeze/prthinker_setting.json`
- `environment_for()` 把設定轉成 `PRTHINKER_*` 環境變數交給子行程，**命令列只留「這次要審什麼」** — API key 不會出現在工作管理員或執行紀錄
- `SECRET_SETTINGS` 四個欄位在 `loggable()` 中一律縮成 `(set)` / 空字串
- `extra_arguments()` 經 `split_arguments()` 以命令列規則斷詞（引號內空白不拆）；反斜線是路徑分隔字元的平台（Windows）上反斜線不當跳脫字元，`C:\reviews` 才不會變成 `C:reviews`。解析失敗當作沒有而不是讓整次審查失敗
- `install_target()` 回傳 `<path>[runner]`，因為 prthinker 不在 PyPI 上
- 規則檢索（`rag`，`RAG_MODES = ("off", "remote")`）**永遠明講**：`off` 給 `PRTHINKER_RAG_ENABLED=false`，`remote` 給 `PRTHINKER_REMOTE_RAG=true`（走伺服器的 `/rag`），認不得的值當 `off`。prthinker 的預設是本機 FAISS 檢索，但那份索引（`codes/`）只在它的原始碼庫、被排除在套件外，從這裡裝的 prthinker 一跑就 `ModuleNotFoundError: codes`

支援的後端：`remote / local / openai / anthropic / gemini / cohere / mistral / claude-cli / codex-cli`；平台：`github / gitlab / gitea`。

---

## 15. 設計模式落點

| 模式 | 落點 |
|---|---|
| **Facade** | `pybreeze/__init__.py` — 對外只暴露 `start_editor`、`PyBreezeMainWindow`、`EDITOR_EXTEND_TAB` 與轉出的插件 API |
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
    ├── QTimer (100ms / 50ms) ──► pull_text() ──► pump_message_queue() ──► QTextEdit
    │                                  ▲
    │                          thread-safe Queue
    │                                  ▲
    ├── daemon Thread: stdout readline ┤
    ├── daemon Thread: stderr readline ┘
    │
    ├── QThread: SSHReaderThread      ──Signal──► terminal widget
    ├── QThread: SenderThread (CoT)   ──Signal──► review UI
    ├── QThread: RequestThread(Skills)──Signal──► result UI
    └── QThread: JupyterLauncherThread──Signal──► QWebEngineView
```

鐵律：worker thread 一律不碰 UI。普通執行緒走 Queue + QTimer，`QThread` 走 Signal/Slot。

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

另有工作目錄下的 `PyBreeze.log`（rotating，預設 100 MB）與各自動化套件自己的 log。

---

## 18. 測試與 CI

- **單元測試** `test/test_utils/` — 72 個 `test_*.py`、1068 個測試（5 個 prthinker 契約測試在沒有 prthinker 的直譯器上跳過）。純邏輯 + headless Qt widget 測試（`QT_QPA_PLATFORM=offscreen`）。涵蓋 curl/HAR 解析、SSRF 驗證、SSH 安全、process reader EOF、queue pump、語言對齊、mermaid parser、diagram 序列化、prthinker 設定、JEditor 內部介面契約（`test_jeditor_contract.py`）等。有 hypothesis fuzz 測試（`test_fuzz_pure_logic.py`）。
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

4. **`mail_thunder_setting.send_after_test()` 捕捉裸 `Exception`** — 最後一個 `except Exception` 只記 log，符合「不讓寄信失敗炸掉測試」的意圖，但與 CLAUDE.md「避免捕捉 Exception 除非立即重拋」有張力。

5. **`PackageManager` 名實不符** — 類別名暗示 pip 管理，實際只承載 `syntax_check_list` 六個項目；pip 安裝落在 `install_utils.install_package()`。

---

## 20. 一句話總結

PyBreeze 的架構骨幹是 **「薄 UI + 表格化註冊 + 純邏輯 utils + 子行程隔離執行」**：選單與工具用宣告式表格組裝，業務邏輯下沉到無 Qt 依賴的 `utils/` 以便測試，任何會跑使用者程式碼的東西一律推到子行程，再用 Queue + QTimer 這條單向管線把輸出安全地送回 UI 執行緒。
