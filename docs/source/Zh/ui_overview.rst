UI 總覽
=======

.. image:: images/ui.png

PyBreeze 提供基於分頁和停靠面板的介面，使用 PySide6（Qt for Python）建構。
主視窗由以下幾個主要區域組成。

主視窗佈局
----------

選單列
^^^^^^

位於視窗頂部，包含所有檔案操作、程式碼執行、自動化模組、工具安裝、
SSH、AI 工具、外掛等選單。

選單列包含以下頂層選單（由左至右）：

- **File** -- 開啟、儲存檔案，設定編碼
- **Run** -- 執行程式碼、在 Shell 中執行、停止程式
- **Text** -- 字型和字型大小設定
- **Check Code Style** -- 程式碼格式化工具（yapf、JSON）
- **Venv** -- 虛擬環境管理
- **UI Style** -- 主題切換
- **Automation** -- 所有自動化模組選單（AutoControl、APITestka、WebRunner 等）
- **Install** -- 安裝自動化套件和建置工具
- **Tools** -- SSH 用戶端、AI 工具
- **Plugins** -- 外掛瀏覽器和已載入外掛
- **Run With** -- 使用不同編譯器/直譯器執行檔案

檔案樹
^^^^^^

位於視窗左側，提供檔案瀏覽器用於導覽專案目錄。您可以：

- 瀏覽檔案和資料夾
- 雙擊在編輯器中開啟檔案
- 右鍵開啟功能選單

程式碼編輯器（分頁元件）
^^^^^^^^^^^^^^^^^^^^^^^^

中央區域使用分頁介面。每個開啟的檔案都有自己的分頁。
額外的工具分頁（SSH、AI、JupyterLab、自動化 GUI）也可以在此開啟。

功能：

- Python 和自動化模組關鍵字的語法高亮
- 多檔案分頁編輯
- 可透過 ``EDITOR_EXTEND_TAB`` 擴充自訂分頁

輸出面板
^^^^^^^^

位於視窗底部，顯示：

- 程式執行輸出
- Shell 命令結果
- 錯誤訊息

程式碼輸出視窗
^^^^^^^^^^^^^^

執行自動化腳本時，會開啟獨立的 **程式碼輸出視窗** 顯示執行結果。此視窗：

- 即時顯示子程序的執行輸出
- 唯讀模式
- 根據螢幕大小自動調整尺寸
- 可獨立於主視窗關閉

停靠面板
^^^^^^^^

以下工具可以作為 **停靠面板** 開啟（而非分頁），讓您自由排列：

- SSH 用戶端停靠面板
- AI 程式碼審查停靠面板
- CoT 提示詞編輯器停靠面板
- Skill 提示詞編輯器停靠面板
- Skill 傳送 GUI 停靠面板

停靠面板可以拖曳、調整大小，並固定到主視窗的任何邊緣。

主題系統
--------

PyBreeze 使用 `qt_material <https://github.com/UN-GCPDS/qt-material>`_ 進行主題設定。
可用主題包括：

- ``dark_amber.xml``（預設）
- ``dark_teal.xml``
- ``dark_blue.xml``
- ``dark_cyan.xml``
- ``dark_lightgreen.xml``
- ``dark_pink.xml``
- ``dark_purple.xml``
- ``dark_red.xml``
- ``dark_yellow.xml``
- ``light_amber.xml``
- ``light_blue.xml``
- ``light_cyan.xml``
- ``light_lightgreen.xml``
- ``light_pink.xml``
- ``light_purple.xml``
- ``light_red.xml``
- ``light_yellow.xml``

您可以透過選單列中的 **UI Style** 選單切換主題，或在啟動時設定：

.. code-block:: python

   start_editor(theme="dark_teal.xml")

多語言支援
----------

PyBreeze 支援多種 UI 語言：

- **English**（預設）
- **繁體中文**
- 可透過外掛新增其他語言

所有 UI 字串透過集中式語言字典管理，可擴充自訂翻譯。
