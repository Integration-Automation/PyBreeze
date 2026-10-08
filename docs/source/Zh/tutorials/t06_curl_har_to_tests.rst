6. 從 cURL 與 HAR 產生測試
==========================

**你會做的事**：把從瀏覽器複製出來的一個請求變成測試，並把整段錄下來的工作階段變成一組測試，
兩者都不用自己動手寫。

開始之前
--------

:doc:`t01_install_first_launch`，而且網站正在執行。執行產生出來的測試需要 ``pytest``：
``python -m pip install pytest``。

cURL 變成測試
-------------

瀏覽器的開發者工具可以把任何請求複製成 ``curl`` 指令（ *Copy as cURL* ）。
範例就是這樣的一個指令，對象是教學網站：

.. literalinclude:: ../../examples/request.curl
   :language: bash
   :caption: request.curl

1. 開啟 **Tools > cURL Import Tab** 並貼上這個指令。
2. 在 **產生目標** 選 **pytest 測試**，再按 **產生 pytest 測試**。

**預期結果**：產生的程式碼是

.. code-block:: python

   import requests


   def test_get_users_json():
       url = "http://127.0.0.1:8765/users.json"
       headers = {
           "Accept": "application/json",
           "X-Trace": "tutorial",
       }
       response = requests.request("GET", url, headers=headers)
       assert response.status_code == 200
       # Add assertions on response.json() / response.text as needed

3. 按 **存成檔案...**，存成 ``test_users.py``，然後執行它：

   .. code-block:: bash

      python -m pytest test_users.py

   **預期結果**： ``1 passed``。

同一個請求、其他的目標
----------------------

產生目標共有六種。選 **APITestka（JSON action）** 時，同一個指令會產生 Automation 選單可以直接執行的腳本
（:doc:`t02_first_api_test`）：

.. code-block:: json

   [
       [
           "AT_test_api_method",
           {
               "http_method": "GET",
               "test_url": "http://127.0.0.1:8765/users.json",
               "headers": {
                   "Accept": "application/json",
                   "X-Trace": "tutorial"
               }
           }
       ]
   ]

選 **WebRunner（JSON action）** 時，產生的是用瀏覽器前往這個 URL。瀏覽器會送出它自己的 header，
所以產生的程式碼下方有一行說明這個目標省略了什麼：這裡是 header。

HAR 變成一組測試
----------------

HAR 檔是瀏覽器把一個頁面送出的所有請求匯出的結果（網路面板的 *Save all as HAR* ）。
範例裡有兩個對教學網站的請求。

1. 開啟 **Tools > HAR Import Tab**，按 **開啟 .har 檔...** 並選擇 ``session.har``。
   摘要會顯示 ``2 個請求，其中 2 個像 API — 127.0.0.1``，兩個請求都列在清單裡。
2. 選 **pytest 測試**，再按 **為列出的全部產生**。
3. 存成 ``test_session.py`` 並執行 ``python -m pytest test_session.py``。

**預期結果**：檔案裡有 ``test_get_users_json`` 與 ``test_get_127_0_0_1``，結果是 ``2 passed``。

如果不成功
----------

- 顯示無法解析 curl 指令：請貼上完整的指令，從 ``curl`` 開始，用 *Copy as cURL (bash)* 給的形式。
- 真實網站的 HAR 會列出幾百個請求：勾選 **只列出像 API 的請求**，或選取你要的幾個再按 **為選取項產生**。
- 產生的測試因連線錯誤而失敗：網站沒有在執行。

下一步
------

:doc:`t07_header_sarif_ci`
