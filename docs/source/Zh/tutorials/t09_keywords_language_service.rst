9. 關鍵字與語言服務
===================

**你會做的事**：讓編輯器替動作腳本補全、在執行之前就指出錯誤，並查詢一個關鍵字。

開始之前
--------

:doc:`t01_install_first_launch`。範例是一支有兩處錯誤的 WebRunner 腳本。

範例
----

.. literalinclude:: ../../examples/broken_actions.json
   :language: json
   :caption: broken_actions.json

步驟
----

1. 在編輯器開啟 ``broken_actions.json``。有兩行被標示出來。
2. 把游標放到被標示的那一行：編輯器的工具提示會說那裡哪裡有錯。
3. 修正第 3 行：刪掉引號裡的 ``WR_to_urll``，輸入 ``WR_to``。輸入的同時會列出這樣開頭的關鍵字；
   選 ``WR_to_url``。
4. 修正第 4 行：在大括號裡，刪掉引號裡的 ``urls`` 並開始輸入。會列出 ``WR_to_url``
   還沒有給的參數： ``url``。
5. 在關鍵字上按右鍵，選 **Describe Symbol** 可以讀它的簽名與說明文件，選 **Go to Definition**
   可以開啟 WebRunner 裡定義它的那一行。
6. 開啟 **Tools > Automation Keywords Tab**。選 **WebRunner**，在篩選框輸入 ``cookie``，
   選取 ``WR_add_cookie`` 並按 **複製成動作**。

預期結果
--------

步驟 1 會標示出這三個問題（訊息使用 IDE 的語言，這裡是英文介面）：

.. code-block:: text

   line 3  WR_to_urll is not a keyword of WebRunner 0.0.66. Did you mean WR_to_url?
   line 4  WR_to_url has no parameter named urls. Did you mean url?
   line 4  WR_to_url needs url

其中 ``0.0.66`` 會是你安裝的版本。做完步驟 3 與 4 之後，沒有任何一行被標示。
步驟 6 會把 ``["WR_add_cookie", {"cookie_dict": null}]`` 放到剪貼簿，分頁的狀態列會顯示框架的版本、
關鍵字的數量，以及編輯器能提供的功能（補全、診斷、懸停說明、跳到定義）。

關鍵字從哪裡來
--------------

PyBreeze 不保存任何關鍵字資料。每個框架都由執行你腳本的那個直譯器，在獨立的行程裡詢問，
所以提供的就是已安裝版本實際有的東西。同一個服務也回答 AutoControl（ ``AC_...`` ）與
LoadDensity（ ``LD_...`` ）的腳本，任何支援 Language Server Protocol 的編輯器也都能啟動它：

.. code-block:: bash

   python -m pybreeze.extend.language_server --help

**預期結果**：用法說明，其中有 ``--interpreter`` （要詢問哪個 Python 裡安裝的框架）與
``--language`` （訊息的語言）。

如果不成功
----------

- 沒有任何標示，也沒有補全：檔名必須是 ``.json``，而且安裝框架之後要重新啟動 PyBreeze。
  **Automation Keywords** 會對每個框架說明它的版本，或為什麼拿不到關鍵字。
- 不是動作腳本的 JSON 檔，只會被告知它是不是 JSON。
- 啟動 PyBreeze 之後才在 **Python Env** 換了直譯器：Automation Keywords 分頁會立刻跟上，
  編輯器要重新啟動之後才會。
- 打包版（執行檔，而不是 ``python -m pybreeze`` ）沒有語言伺服器。

下一步
------

:doc:`t10_mcp_client`
