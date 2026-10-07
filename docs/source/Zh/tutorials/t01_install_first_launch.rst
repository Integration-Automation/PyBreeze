1. 安裝與第一次啟動
===================

**你會做的事**：安裝 PyBreeze、在專案資料夾裡啟動它，並啟動後面教學要測試的小網站。

開始之前
--------

- Python 3.10 到 3.14，以及 ``pip``。
- 有桌面環境的 Windows、macOS 或 Linux。在 Linux 上，Qt 需要
  :doc:`t13_troubleshooting` 列出的系統函式庫。

步驟
----

1. 建立一個專案資料夾，在裡面建立虛擬環境，並把 PyBreeze 安裝進去。

   .. code-block:: bash

      mkdir pybreeze-tutorial
      cd pybreeze-tutorial
      python -m venv .venv

      # Windows
      .venv\Scripts\activate
      # macOS、Linux
      source .venv/bin/activate

      python -m pip install pybreeze

   教學會用到的自動化套件（APITestka、WebRunner、AutoControl、LoadDensity）會一起安裝。

2. 把範例複製到這個資料夾。它們在儲存庫的 ``docs/source/examples/`` 底下；
   複製那個資料夾的內容，讓 ``site/`` 與那些 ``.json`` 檔都在 ``pybreeze-tutorial`` 裡。

3. 開 **第二個** 終端機，在同一個資料夾裡啟動教學要測試的網站，並讓它一直開著。

   .. code-block:: bash

      python -m http.server 8765 --bind 127.0.0.1 --directory site

4. 回到第一個終端機，**在專案資料夾裡** 啟動 PyBreeze。

   .. code-block:: bash

      python -m pybreeze

範例
----

這個網站只有兩個檔案：

.. literalinclude:: ../../examples/site/index.html
   :language: html
   :caption: site/index.html

.. literalinclude:: ../../examples/site/users.json
   :language: json
   :caption: site/users.json

預期結果
--------

- 主視窗以最大化開啟：最上方是選單列，左邊是 **導覽面板** 與檔案樹（裡面是你的資料夾），
  中間是編輯器，下方是輸出面板。
- 導覽面板把各選單的內容列在 **Automation**、**Tools**、**MCP**、**Reports** 與
  **Settings** 底下；在它的輸入框打字可以篩選，按兩下就會開啟該項目。
- 用瀏覽器開啟 ``http://127.0.0.1:8765/`` 會看到 *Hello from the tutorial site*，
  開啟 ``http://127.0.0.1:8765/users.json`` 會看到那兩位使用者。
- 因為資料夾裡有 ``.venv``，從 IDE 啟動的執行會使用那個直譯器
  （見 :doc:`../getting_started` 的「工作資料夾」）。

如果不成功
----------

- 找不到 ``python``，或它不是你要的那一個：用 ``py -3.12``（Windows）或 ``python3``
  來建立虛擬環境。
- 在 Linux 上視窗沒有出現：見 :doc:`t13_troubleshooting`。
- 8765 這個 port 已經被佔用：換一個，並把範例裡的 URL 一起改掉。

下一步
------

:doc:`t02_first_api_test`
