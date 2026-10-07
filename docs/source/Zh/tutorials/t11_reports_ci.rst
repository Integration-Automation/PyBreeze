11. 統一的報告與 CI
===================

**你會做的事**：把前面教學的執行結果開在同一個檢視器裡、篩選它們，並把其中一份匯出成
JUnit XML，也就是 CI 服務讀的格式。

開始之前
--------

:doc:`t02_first_api_test`、:doc:`t04_first_desktop_automation` 與
:doc:`t05_first_load_scenario` 寫出的報告：專案資料夾裡的 ``api_report_*.json``、
``desktop_report_*.json`` 與 ``load_report_*.json``。

步驟
----

1. 開啟 **Tools > Report Viewer Tab** 並按 **開啟...**。
2. 選取 ``api_report_success.json``、 ``desktop_report_success.json`` 與
   ``load_report_success.json`` （按住 Ctrl 點選）並開啟。一次執行的任一個檔案都會開啟整次執行：
   ``_failure`` 檔會一起讀進來。
3. 在樹裡逐一點選。選取一個結果時，右邊的分頁會顯示它的詳細資料、它的輸出，以及
   **原始紀錄**：套件自己對它的紀錄，原樣保留。
4. 在篩選列取消勾選 **通過**，再勾回來。在套件下拉選單選 ``je_load_density``，再選回 **所有套件**。
   在文字框輸入 ``users``。
5. 選取 ``api_report`` 這次執行，按 **匯出...**，檔案類型選 **JUnit XML**，存成 ``api_report.xml``。

預期結果
--------

- 列出三次執行： ``api_report``、 ``desktop_report`` 與 ``load_report``，各自顯示如何結束。
  樹下方的那一行統計目前顯示的內容，例如 130 個結果、來自 3 份報告、全部通過
  （一個請求、兩個桌面步驟，以及壓力測試的請求；你的壓力測試數量會不同）。
- 取消勾選 **通過** 時什麼都不列出，因為沒有東西失敗。輸入 ``users`` 時，只列出那個 API 請求。
- 那個 API 請求的詳細資料有它花的時間（這裡是 ``0.05`` 秒）；它的輸出是回應的內容；
  它的原始紀錄裡有狀態碼、header 與其他欄位。
- ``api_report.xml`` 的內容是：

  .. code-block:: xml

     <?xml version="1.0" encoding="UTF-8"?>
     <testsuites name="api_report" tests="1" failures="0" errors="0" skipped="0" time="0.049">
       <testsuite name="api_report" tests="1" failures="0" errors="0" skipped="0" time="0.049">
         <testcase name="GET http://127.0.0.1:8765/users.json" classname="api_report" time="0.049">
           <system-out>[
       {"id": 1, "name": "Ada"},
       {"id": 2, "name": "Grace"}
     ]
     </system-out>
         </testcase>
       </testsuite>
     </testsuites>

檢視器讀什麼、寫什麼
--------------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 讀取
     - 說明
   * - ``<name>_success.json`` ／ ``<name>_failure.json``，或 ``.xml`` 那一對
     - APITestka、AutoControl、WebRunner、LoadDensity。依紀錄裡的欄位分辨是哪一個。
   * - JUnit XML
     - pytest 的 ``--junitxml``，以及大多數其他測試執行器。
   * - 從 PyBreeze 匯出的報告
     - JSON，或 HTML 頁面。
   * - MCP 工作階段
     - 來自 MCP 用戶端的 **呼叫紀錄** 頁（:doc:`t10_mcp_client`）。

**匯出...** 會把選取的執行寫成 **執行報告** （JSON，讀回來和原本一樣）、 **JUnit XML**，
或 **HTML 頁面**：單一檔案、沒有 script，可以用郵件寄出或附在建置結果上，之後還能在這裡開啟。

在 CI workflow 裡
-----------------

自動化套件的執行不論檢查有沒有通過，結束代碼都是 0（:doc:`t02_first_api_test`），所以 CI 必須讀報告。
CI 服務讀的是 JUnit XML。用 pytest 時，這個檔案直接由執行器產生：

.. code-block:: yaml

   - name: Run the tests
     run: python -m pytest --junitxml=test-results.xml
   - name: Keep the results
     if: always()
     uses: actions/upload-artifact@v4
     with:
       name: test-results
       path: test-results.xml

從失敗的建置下載 ``test-results.xml``，在報告檢視器開啟，就能看到什麼失敗了，以及它的訊息、
追蹤與印出的內容。至於套件自己的執行，可以用檢視器的 **匯出...** 轉換它的紀錄檔，或寫成腳本：

.. code-block:: python

   from pathlib import Path

   from pybreeze.utils.execution_report.junit_xml import junit_from_report
   from pybreeze.utils.execution_report.report_files import read_report
   from pybreeze.utils.execution_report.report_schema import Status

   report = read_report(Path("api_report_success.json"))
   Path("api_report.xml").write_text(junit_from_report(report), encoding="utf-8")
   raise SystemExit(1 if report.status in (Status.FAILED, Status.ERROR) else 0)

**預期結果**：和上面一樣的 ``api_report.xml``，結束代碼是 ``0``；對教學 2 那次失敗的執行則是 ``1``。

如果不成功
----------

- 顯示這個頁面裡沒有執行報告：套件的 **HTML** 報告不會讀；請開它旁邊的 JSON 或 XML 檔。
- 開啟套件自己的 ``_success.json`` 時，顯示這個檔案不是 PyBreeze 讀得懂的報告：
  這次執行的兩個檔案都是空的（ ``{}`` ），套件在沒有記錄任何東西時就會這樣寫。請在腳本裡開啟記錄
  （ ``WR_set_record_enable``、 ``AC_set_record_enable`` ）。
- **附件** 底下的路徑打不開：它們只會被列出，不會被開啟。報告是從別處來的檔案。

下一步
------

:doc:`t12_plugins_extending`
