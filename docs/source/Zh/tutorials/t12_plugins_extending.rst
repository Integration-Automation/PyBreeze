12. 外掛與擴充 IDE
==================

**你會做的事**：替 PyBreeze 加上一個你自己的分頁，並載入一個外掛，讓編輯器替它原本不認得的檔案上色。

開始之前
--------

:doc:`t01_install_first_launch`。兩個範例都在 ``docs/source/examples/`` 裡。

你自己的分頁
------------

分頁可以是任何 ``QWidget``，要在編輯器啟動之前註冊。

.. literalinclude:: ../../examples/hello_tab.py
   :language: python
   :caption: hello_tab.py

在專案資料夾裡執行它，取代 ``python -m pybreeze``：

.. code-block:: bash

   python hello_tab.py

**預期結果**：PyBreeze 啟動後，編輯器旁邊多了一個 **Hello** 分頁。輸入名字、按 **Greet**，
分頁就會向你問好。某個 widget 的建構子丟出例外時，只會少掉它自己的分頁：IDE 照常啟動，
錯誤會寫進日誌檔。

外掛
----

外掛是放在 ``jeditor_plugins`` 資料夾裡的 ``.py`` 檔，這個資料夾要在啟動 PyBreeze 的那個資料夾裡。
外掛只在 IDE 啟動時載入一次。

.. literalinclude:: ../../examples/jeditor_plugins/todo_notes.py
   :language: python
   :caption: jeditor_plugins/todo_notes.py

1. 把範例裡的 ``jeditor_plugins/`` 複製到你的專案資料夾。
2. 重新啟動 PyBreeze。
3. 在專案裡建立 ``notes.todo`` 並輸入：

   .. code-block:: text

      # this week
      TODO write the report
      DONE install PyBreeze

**預期結果**：``TODO`` 與 ``DONE`` 以關鍵字的顏色顯示，第一行以註解的顏色顯示。
**Plugins > Plugin Browser** 會列出其他可以安裝的外掛。

如果還想 **執行** 某種檔案，外掛要提供 ``PLUGIN_RUN_CONFIG`` （要啟動的程式與它的引數），
它就會出現在 **Run with...** 底下。各個鍵見 :doc:`../menu_plugins`；
會在關閉前先詢問的分頁見 :doc:`../how_to_extend_ui`。

替 PyBreeze 本身加一個工具
--------------------------

如果是修改 PyBreeze 自己的原始碼，一個工具就是表格裡的一行。Widget 放在
``pybreeze/pybreeze_ui/tools_gui/``，它的邏輯（不含 Qt）放在 ``pybreeze/utils/``，然後：

.. code-block:: python

   # pybreeze/pybreeze_ui/menu/tools/tools_menu.py
   _tool("MyTool", "my_tool", lambda win: MyToolGUI(win)),

Tools 選單、Dock 選單與導覽面板都是從這張表建出來的。這個項目的四個字串
（``extend_tools_menu_my_tool_tab_action`` 與另外三個）要加進
``pybreeze/extend_multi_language/`` 底下的兩份字典；只加了其中一份，測試會失敗。
``architecture.md`` 第 5 節列出其他擴充點：匯入目標、報告格式、語言服務的框架、MCP 傳輸。

如果不成功
----------

- 外掛沒有載入：資料夾必須叫 ``jeditor_plugins``，而且要在 **啟動** PyBreeze 的那個資料夾裡；
  檔名以 ``_`` 或 ``.`` 開頭的檔案會被略過；外掛只在啟動時讀取。
- 顏色沒有出現：編輯器自己會替 C、C++、Go、Java 與 Rust 上色，外掛的關鍵字只用在它沒有上色的副檔名。

下一步
------

:doc:`t13_troubleshooting`
