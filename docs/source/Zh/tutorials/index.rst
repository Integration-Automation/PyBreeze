教學
====

十三篇簡短的教學，依照先後順序一篇接著一篇。每一篇都有一個可以直接執行的最小範例，
並說明成功時應該看到什麼。

第一篇會安裝 PyBreeze，並在你自己的電腦上啟動一個小網站（``http://127.0.0.1:8765``），
後面的教學就是對它做測試，所以這裡的內容都不需要任何帳號。只有瀏覽器那一篇需要連上網路一次，
用來下載瀏覽器的驅動程式。

.. list-table::
   :header-rows: 1
   :widths: 6 34 60

   * - #
     - 教學
     - 完成後你會有
   * - 1
     - :doc:`t01_install_first_launch`
     - 在專案資料夾裡執行的 PyBreeze，以及一個可以測試的本機網站
   * - 2
     - :doc:`t02_first_api_test`
     - 一個通過的 API 測試與它的報告
   * - 3
     - :doc:`t03_first_browser_test`
     - 一個會開啟頁面再關閉的瀏覽器
   * - 4
     - :doc:`t04_first_desktop_automation`
     - 一支讀出螢幕大小與滑鼠位置的腳本
   * - 5
     - :doc:`t05_first_load_scenario`
     - 五個使用者對一個頁面請求五秒鐘
   * - 6
     - :doc:`t06_curl_har_to_tests`
     - 從 ``curl`` 指令與 HAR 匯出檔產生的測試
   * - 7
     - :doc:`t07_header_sarif_ci`
     - SARIF 格式的 header 檢查結果，以及會因此失敗的 CI 步驟
   * - 8
     - :doc:`t08_visual_json_editing`
     - 以樹狀方式編輯、可以復原的 JSON 檔
   * - 9
     - :doc:`t09_keywords_language_service`
     - 動作腳本的補全與診斷
   * - 10
     - :doc:`t10_mcp_client`
     - 從 IDE 呼叫 MCP 伺服器的工具
   * - 11
     - :doc:`t11_reports_ci`
     - 所有執行結果都在同一個檢視器裡，以及給 CI 用的 JUnit XML
   * - 12
     - :doc:`t12_plugins_extending`
     - 你自己的分頁與一個外掛
   * - 13
     - :doc:`t13_troubleshooting`
     - 上面任何一步不成功時的解答

範例檔都在儲存庫的 ``docs/source/examples/`` 底下。

教學裡的選單與右鍵選單項目以英文介面的名稱稱呼（和其他參考頁一樣）；工具裡的按鈕以繁體中文介面的名稱稱呼。
執行視窗的輸出是英文介面的：最後一行 ``Task exit with code 0`` 在繁體中文介面是「執行結束，結束代碼 0」。

.. toctree::
   :maxdepth: 1
   :hidden:

   t01_install_first_launch
   t02_first_api_test
   t03_first_browser_test
   t04_first_desktop_automation
   t05_first_load_scenario
   t06_curl_har_to_tests
   t07_header_sarif_ci
   t08_visual_json_editing
   t09_keywords_language_service
   t10_mcp_client
   t11_reports_ci
   t12_plugins_extending
   t13_troubleshooting
