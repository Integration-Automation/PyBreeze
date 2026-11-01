# 程式審核：PyBreeze

## 審核者

- 審核者：工作區程式審核
- 日期：2026-10-22
- 對象：`PyBreeze`（套件目錄 `pybreeze/`；工作樹熱點，自動化 IDE 如何以子行程呼叫其他框架）
- 結論：通過

## 審核規範

共通規範在工作區 repo [JE-Chen/Codes](https://github.com/JE-Chen/Codes) 的 `docs/code-review-standard.md`。下面留下 2026-10-22 這次審核所用的條款，讓審核紀錄的依據對得上那一次。之後的審核以工作區那份為準。本專案更嚴的條款仍以本節與本專案的 `CLAUDE.md` 為準。

本輪依下列十條。數值與專案規則衝突時從嚴（見審核紀錄「本專案加嚴」）。

1. 設計：分層與責任是否清楚；子行程是否為呼叫自動化框架的邊界，而不是在 IDE 行程內執行使用者腳本。
2. 可讀性：函式圈複雜度 ≤ 15、函式長度從嚴 ≤ 75 行、巢狀 ≤ 4、參數 ≤ 7、行寬 ≤ 120。超過即記，不另放寬。
3. 錯誤處理：不吞例外；不可裸 `except:`；`except Exception` 僅能記錄後再拋，並帶上下文。
4. 死碼：無未使用匯入、到不了的分支、註解掉的程式、`_old_` 殘留。舊旗標若仍是契約，不算死碼。
5. 型別與 docstring：公開函式有型別與說明；註解與呼叫須一致。
6. 安全：參數清單、明確 `shell=False`、`subprocess.run` 有逾時；不把使用者輸入拼進命令字串；機密走環境變數。禁止對不受信任資料 `eval` / `exec` / `pickle`，YAML 只用安全載入，不設 `verify=False`。
7. 測試：熱點應有契約或行為測試可對照。本輪不執行測試。
8. 效能：子行程與讀取不得堵住 UI 執行緒；長時間行程以佇列與計時器回寫。
9. 跨專案邊界（`architecture.md` §6）：命令列協定、JEditor 內部名稱、prthinker 與語言伺服器的啟動方式須與該節一致。直接改寫 JEditor 內部字典只列建議：契約未公開，不當成已壞。
10. 文件同步：§6、專案規則與程式對同一條命令列協定的說法須相同。

嚴重度：缺陷（未關閉則結論為需修正）、建議、備註。通過＝無未關閉缺陷；有條件通過＝無立即損害；需修正＝有未關閉缺陷。

## 審核紀錄

### 方法

讀 `architecture.md` §6、`CLAUDE.md` 的 Architecture、Conventions、Security（Subprocess、JupyterLab、Language server）、Code quality gates，以及 `progress.md` 前 80 行。範圍只含套件 `pybreeze/**/*.py`，排除 `test/`、`build/`、`__pycache__`。以文字搜尋 `eval(`、`exec(`、`shell=True`、`pickle`、`yaml.load`、`verify=False`、裸 `except:`、`subprocess`、`shell=`，以及 JEditor 字典的寫入。每一則發現都先讀過對應原始碼。未執行測試、未啟動 IDE、未匯入 `je_editor` 或 `frontengine`。

### 總評

自動化框架仍由子行程以引數清單啟動，沒有 `shell=True`，也沒有把使用者輸入拼成 shell 字串。`--execute_str`、`--execute_file` 與 TestPioneer 的 `-e` 仍在，而且仍是 `architecture.md` §6 寫明的協定，不是該刪的殘留。直接改寫 JEditor 內部字典的位置都在，依本輪規範列為建議、不列缺陷。註解寫了 `shell=False` 但呼叫未帶該關鍵字的幾處，預設即為 `shell=False` 且引數是清單，沒有命令注入，列為建議。無未關閉缺陷。

### 發現

無未關閉缺陷。共 3 則（建議 2、備註 1）。

#### CR-01

- 位置：
  - `pybreeze/extend_multi_language/update_language_dict.py` 第 27–36 行：`choose_language_dict` 裡維護中語言的字典就地 `update`，再把 `application_name` 寫進該對照表的每一份字典。呼叫點在 `pybreeze/pybreeze_ui/editor_main/main_ui.py` 第 78 行，於 `EditorMain.__init__` 之前。
  - `pybreeze/extend/language_server/launch.py` 第 42 行：`DEFAULT_SERVERS[".json"]` 被設成動作語言伺服器的命令。
  - `pybreeze/pybreeze_ui/editor_main/main_ui.py` 第 318 行：`user_setting_dict["ui_style"]` 被改成這次給的主題。
  - `pybreeze/pybreeze_ui/editor_main/file_tree_context_menu.py` 第 307–308、314 行：重新命名時 `pop`／寫入 `auto_save_manager_dict` 與 `file_is_open_manager_dict`。
- 說明：這四處改的是 JEditor 行程內的字典，不是 PyBreeze 自己的副本。`actually_color_dict` 只讀，不算改寫。
- 依據：`architecture.md` §6 把這些名稱列為 JEditor 未承諾保留的內部路徑，並寫明字串是就地併進 `choose_language_dict`。本輪規範：直接改寫 JEditor 內部字典列為建議，契約未公開，不要當成已壞。
- 狀態：建議（不列缺陷）
- 建議：維持現有呼叫，直到上游公開這些名稱。不要在未改 JEditor 與 §6 的情況下改成另一套私有字典或另註冊語言（`update_language_dict` 的說明已寫明，再註冊會換掉物件、編輯器自己的字串會不見）。

#### CR-02

- 位置：
  - `pybreeze/extend/process_executor/python_task_process_manager.py` 第 193–209 行：註解寫引數清單且 `shell=False`，`Popen` 未帶 `shell=`。
  - `pybreeze/pybreeze_ui/jupyter_lab_gui/jupyter_lab_thread.py` 第 75–86、116–127、210–237 行：三處註解或說明寫 `shell=False`，`subprocess.run`／`Popen` 都未帶該關鍵字。
  - `pybreeze/pybreeze_ui/editor_main/file_tree_context_menu.py` 第 481–483 行：註解寫 `shell=False`，`Popen(command, env=child_environment())` 未帶該關鍵字。`reveal_command`（第 460–474 行）回傳的是清單。
- 說明：上述呼叫的引數都是清單，`Popen`／`run` 的預設就是 `shell=False`，使用者路徑、腳本與套件名沒有進 shell。同一套件裡已明確寫上 `shell=False` 的有 `file_runner_process.py` 第 178 行、`utils/subprocess_util.py` 第 79 行、`utils/regex_tools/regex_tester.py` 第 262 行、`utils/language_service/metadata_probe.py` 第 144 行、`utils/mcp/mcp_transport.py` 第 76 行。
- 依據：專案規則 Security › Subprocess 要求引數清單並且明確 `shell=False`。註解與呼叫不一致，違反的是寫法，不是執行時把字串交給 shell。
- 狀態：建議（不列缺陷；無命令注入、無立即損害）
- 建議：在這三處補上 `shell=False`，讓註解與呼叫一致，之後用搜尋就能對完。不要改成命令字串。

#### CR-03

- 位置：
  - `pybreeze/extend/process_executor/python_task_process_manager.py` 第 131、134、166–171 行：`python -m <package> --execute_str`；Windows 命令列超過 30,000 字元時改 `--execute_file`。檔案與目錄執行固定走 `--execute_file`。
  - `pybreeze/extend/process_executor/test_pioneer/test_pioneer_process_manager.py` 第 23 行：`python -m test_pioneer -e <yaml>`。
  - `pybreeze/pybreeze_ui/jupyter_lab_gui/jupyter_lab_thread.py` 第 228–235 行：除了 `--IdentityProvider.token=` 與 `--PasswordIdentityProvider.hashed_password=`，仍帶 `--ServerApp.token=` 與 `--ServerApp.password=`。
  - 對照：`pybreeze/extend/prthinker_extend/prthinker_setting.py` 第 318、335 行的 `review-file` 與 `review-pr --pr-number` 與 §6 相同，不是另一套舊旗標。`pybreeze/__main__.py` 沒有自己的旗標。
- 說明：舊式旗標仍在。`--execute_file` 在 `docs/updates/2026-09-b.md`（U-20260923-203）被稱為各套件都接受的 legacy flag，但 `architecture.md` §4 與 §6 仍把 `--execute_str`／`--execute_file` 以及 TestPioneer 的 `-e` 訂為現行協定。Jupyter 的舊旗標是刻意留下：說明寫明只留新旗標時，忽略新旗標的伺服器會自己產生 token。程式裡沒有第二套已廢棄、無人閱讀的旗標分支。
- 依據：`architecture.md` §6（約第 283–289、319–320 行）；專案規則 Security › JupyterLab；Security › Subprocess（長腳本改走檔案，仍是引數清單）。
- 狀態：備註
- 建議：不要把這些旗標當死碼刪除。上游若改旗標，須同一輪改這裡的呼叫者並更新 §6。`progress.md` #92（嵌入式 Jupyter 改為每次產生 token）是既有未完項目，不在本輪改判為缺陷。

### 已核對

- 框架怎麼被叫起來：`TaskProcessManager._spawn_and_pump` 以 `[直譯器, "-m", 套件, …]`、`stdin=DEVNULL`、`utf8_subprocess_env()` 啟動。WebRunner、AutoControl、APITestka、LoadDensity、FileAutomation、MailThunder 的腳本走 `start_test_process`／`start_test_process_file`。TestPioneer 與 prthinker 走 `start_module_process`；prthinker 的金鑰與權杖只經 `environment_for`，不進 argv。pip 安裝（`install_utils.py`）同樣是引數清單；註解寫明已不再借 JEditor 的 `ShellManager`（那個路徑會 `shell=True` 交給 `cmd.exe`）。
- 語言服務：`metadata_probe.probe_command` 是固定的 `[直譯器, "-c", 腳本, …]`，`shell=False`、有逾時、工作目錄是直譯器所在資料夾。動作語言伺服器由 `launch.server_command` 以 `__main__.py` 的路徑啟動，不是 `python -m`（`extend/language_server/__main__.py` 會把匯入路徑換掉）。
- MCP：`StdioTransport.start` 使用設定檔上的命令清單、`shell=False`、`utf8_subprocess_env()` 再疊環境變數。
- 外掛執行其他語言：`FileRunnerProcess` 把 compiler、args 與檔案路徑組成清單，`shell=False`。檔案總管是 `reveal_command` 的固定清單。
- 搜尋結果（套件 `*.py`）：`shell=True` 無；`pickle`、`yaml.load`、`verify=False`、裸 `except:` 無。命中的 `exec(` 都是 Qt 的 `QDialog.exec`／`QApplication.exec`，不是 Python `exec`。`eval(` 無。
- `metadata_probe.py` 第 63、89 行的 `except Exception` 在子行程腳本字串裡，失敗時回傳空版號或空來源，不是 IDE 行程的裸 `except`。IDE 側的 `subprocess.run`（探測、Jupyter 查版本與 pip、`stop_tree` 的 `taskkill`）都有逾時。長時間的 `Popen` 由停止與計時器收尾，不是 `run` 漏了逾時。
- 熱點函式目視未超過圈複雜度 15、長度 75、巢狀 4、參數 7。未用度量工具。
- §6 與程式對命令列協定一致；`progress.md` 前 80 行為既有決策與上游阻擋項，本熱點沒有把它們重開成新缺陷。

### 未涵蓋

未執行測試（含 `test_long_scripts.py`、`test_task_process_manager.py`、`test_child_process_environment.py`、`test_jeditor_contract.py`）。未審 `test/`、`exe/`、文件站與圖編輯器本體。未核對上游套件目前是否仍接受這些旗標（只審本儲存庫；§6 即契約）。未逐函式度量全套件複雜度，也未重跑覆蓋率。`syntax_keyword.py` 裡標成 legacy 的是排程關鍵字名稱，不是本輪的 CLI 旗標。

### 本專案加嚴

專案品質閘門的函式長度是 75 行，嚴於本清單的 80，本輪以 75 為準。圈複雜度以 15 為準（規則另有硬上限 20，不採用較寬的那一檔）。檔案上限 1000 行依專案規則，本熱點檔案未超過。行寬依本清單 120；專案規則要求 PEP 8，但沒有把更短的行寬寫成可執行閘門，本輪不因既有長行另開缺陷。JEditor 內部字典的改寫只當建議，不當缺陷。

### 結論

通過。未關閉缺陷 0。發現 3 則：建議 2（CR-01 內部字典、CR-02 未寫上的 `shell=False`）、備註 1（CR-03 舊式旗標仍是現行契約）。沒有 `shell=True` 拼使用者輸入。
