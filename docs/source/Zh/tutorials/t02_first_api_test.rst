2. 用 APITestka 寫第一個 API 測試
=================================

**你會做的事**：對教學網站送出一個請求、檢查它的狀態碼，並寫出這次執行的報告。

開始之前
--------

:doc:`t01_install_first_launch`：PyBreeze 已在專案資料夾裡啟動，網站在 8765 port 上執行。

範例
----

APITestka 的腳本是一個 JSON 動作清單：先是關鍵字，再是它的引數。

.. literalinclude:: ../../examples/first_api_test.json
   :language: json
   :caption: first_api_test.json

``AT_test_api_method`` 送出請求；``result_check_dict`` 指定的內容和實際回來的不一樣時，
這個動作就算失敗。``AT_generate_json_report`` 把這次執行的紀錄寫出來。

步驟
----

1. 在檔案樹開啟 ``first_api_test.json``，它會開在編輯器分頁裡。
2. 讓那個分頁在最前面，選擇 **Automation > APITestka > Run > Run APITestka Script**。
3. 執行視窗會開啟並顯示輸出。

預期結果
--------

執行視窗會顯示每個動作與它的回傳值：

.. code-block:: text

   execute: ['AT_test_api_method', {'http_method': 'get', 'test_url': 'http://127.0.0.1:8765/users.json', 'result_check_dict': {'status_code': 200}}]
   {'response': <Response [200]>, 'response_data': {'status_code': 200, 'text': '[\n  {"id": 1, "name": "Ada"}, ...
   execute: ['AT_generate_json_report', {'json_file_name': 'api_report'}]
   None
   Task exit with code 0

專案資料夾裡會多出兩個檔案： ``api_report_success.json`` （一筆紀錄，就是上面那個請求）與
``api_report_failure.json`` （內容是 ``{}``：沒有東西失敗）。套件也會寫出它自己的日誌
``APITestka.log``。

接著把它弄壞：把腳本裡的 ``200`` 改成 ``404`` 再執行一次。執行視窗會印出
``value should be 404 but value was 200``，這個動作回傳 ``None``，而
``api_report_failure.json`` 裡會有這個請求與
``APIAssertException('value should be 404 but value was 200')``。

.. note::

   這次執行仍然以 ``Task exit with code 0`` 結束：沒有通過的檢查會被記錄下來，
   但不會讓行程失敗。要分辨一次執行是通過還是失敗，要看報告（:doc:`t11_reports_ci`）。

如果不成功
----------

- ``[錯誤] ... 執行的是最前面那個編輯分頁裡的腳本``：選選單項目時，腳本的分頁不在最前面。
- 出現連線錯誤而不是 ``<Response [200]>``：教學 1 的網站沒有在執行，或用的是別的 port。
- 一次執行有好幾個失敗，但 ``api_report_failure.json`` 裡只有一個：APITestka 把每個失敗都寫在
  同一個名稱底下，所以檔案只留下最後一個。

下一步
------

:doc:`t03_first_browser_test`。要看這份報告，請見 :doc:`t11_reports_ci`。
