5. 用 LoadDensity 做第一個壓力情境
==================================

**你會做的事**：讓五個模擬使用者對教學網站的首頁請求五秒鐘，並讀出它撐得如何。

開始之前
--------

:doc:`t01_install_first_launch`，而且網站正在執行。只對你自己的東西做壓力測試：
這裡是你自己電腦上的伺服器。

範例
----

.. literalinclude:: ../../examples/first_load_scenario.json
   :language: json
   :caption: first_load_scenario.json

啟動 ``user_count`` 個使用者，每秒啟動 ``spawn_rate`` 個，每個使用者重複執行 ``tasks``
（這裡是一個 ``GET``），直到過了 ``test_time`` 秒。

步驟
----

1. 在編輯器開啟 ``first_load_scenario.json``。
2. 選擇 **Automation > LoadDensity > Run > Run LoadDensity Script**。
3. 等五秒。

預期結果
--------

執行視窗會顯示這次測試的設定，並在測試結束時顯示一張請求的統計表。數字依你的電腦而定；
這裡五個使用者在五秒內送出 127 個請求，沒有任何失敗：

.. code-block:: text

   execute: ['LD_start_test', {'user_detail_dict': {'user': 'fast_http_user'}, 'user_count': 5, 'spawn_rate': 5, 'test_time': 5, 'tasks': {'get': {'request_url': 'http://127.0.0.1:8765/'}}}]
   {'user_detail': {'user': 'fast_http_user'}, 'user_count': 5, 'spawn_rate': 5, 'test_time': 5, 'web_ui': None}
   execute: ['LD_generate_json_report', {'json_file_name': 'load_report'}]
   ('load_report_success.json', 'load_report_failure.json')

   GET      http://127.0.0.1:8765/        127     0(0.00%) |      3       1      29      3 |   26.50        0.00
            Aggregated                    127     0(0.00%) |      3       1      29      3 |   26.50        0.00

表格的欄位依序是請求數、失敗數，回應時間的平均、最小、最大與中位數（毫秒），以及每秒請求數。
``load_report_success.json`` 裡，每個成功的請求各有一筆紀錄。

如果不成功
----------

- 每個請求都失敗：網站沒有在腳本指定的 port 上執行。
- 第二個終端機被一行行文字洗版：那是 ``http.server`` 在記錄每個請求，本來就該如此。
- 用編輯器的 **Run Program** 而不是這個選單來啟動 locust 腳本時，使用者看起來是一個接一個執行的：
  請用 Automation 選單，它會用壓力測試需要的環境來啟動。

下一步
------

:doc:`t06_curl_har_to_tests`。要把這 127 個請求當成報告來看，請見 :doc:`t11_reports_ci`。
