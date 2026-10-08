3. 用 WebRunner 寫第一個瀏覽器測試
==================================

**你會做的事**：讓真正的瀏覽器開啟教學網站再關閉，並記錄每一個步驟。

開始之前
--------

- :doc:`t01_install_first_launch`，而且網站正在執行。
- 已安裝 Google Chrome（或把 ``"chrome"`` 改成 ``"firefox"`` 或 ``"edge"``）。
- 第一次執行需要網路：WebRunner 會下載一次瀏覽器的驅動程式。

範例
----

.. literalinclude:: ../../examples/first_browser_test.json
   :language: json
   :caption: first_browser_test.json

``WR_set_record_enable`` 開啟步驟的記錄，沒有它，最後的報告會是空的。
``WR_get_webdriver_manager`` 啟動瀏覽器， ``WR_to_url`` 前往一個頁面， ``WR_quit`` 關閉它。

步驟
----

1. 在編輯器開啟 ``first_browser_test.json``。
2. 選擇 **Automation > WebRunner > Run > Run WebRunner Script**。

預期結果
--------

Chrome 視窗開啟，顯示 *Hello from the tutorial site*，然後關閉。執行視窗依序列出五個動作，
每一行 ``execute:`` 後面是該動作的回傳值，最後以 ``Task exit with code 0`` 結束：

.. code-block:: text

   execute: ['WR_set_record_enable', {'set_enable': True}]
   execute: ['WR_get_webdriver_manager', {'webdriver_name': 'chrome'}]
   execute: ['WR_to_url', {'url': 'http://127.0.0.1:8765/'}]
   execute: ['WR_quit']
   execute: ['WR_generate_json_report', {'json_file_name': 'web_report'}]

專案資料夾裡會多出 ``web_report_success.json`` 與 ``web_report_failure.json``。

.. note::

   這是這些教學裡唯一一個在撰寫時沒有實際執行過的範例：它需要電腦上有瀏覽器。
   它的關鍵字與參數由測試（``test_tutorial_examples.py``）對照已安裝的 WebRunner 檢查。

如果不成功
----------

- 驅動程式下載不下來：電腦沒有連上網路，或在 WebRunner 的下載器不認得的 proxy 後面。
  請在有網路的情況下執行一次。
- 還沒執行，編輯器就在某個關鍵字底下畫了線：編輯器會依照已安裝的 WebRunner 檢查 ``.json``
  動作腳本（:doc:`t09_keywords_language_service`）。
- 執行失敗後瀏覽器還開著：某個動作在 ``WR_quit`` 之前就失敗了；關掉視窗、修正該動作，再執行一次。

下一步
------

:doc:`t04_first_desktop_automation`
