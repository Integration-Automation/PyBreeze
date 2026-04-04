File、Run、Text 及其他基礎選單
==============================

這些選單繼承自 JEditor 基礎編輯器引擎，提供核心的編輯和執行功能。

File 選單
---------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 選單項目
     - 說明
   * - **Open File**
     - 開啟檔案對話框選擇檔案，將檔案內容載入到程式碼編輯區。
   * - **Save File**
     - 將目前程式碼編輯區的內容儲存到檔案。
   * - **Encoding**
     - 開啟對話框選擇程式運行器和 Shell 運行器的編碼
       （如 UTF-8、ASCII、Big5）。

Run 選單
--------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 選單項目
     - 說明
   * - **Run Program**
     - 使用程式運行器（Python 直譯器）執行目前程式碼編輯區的內容。
   * - **Run On Shell**
     - 使用系統 Shell 執行目前程式碼編輯區的內容。
   * - **Clean Result**
     - 清除輸出面板（包含程式和 Shell 的結果）。
   * - **Stop Program**
     - 停止目前正在執行的程式。

Run Help 子選單
^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 選單項目
     - 說明
   * - **Run Help**
     - 顯示程式運行器的說明資訊。
   * - **Shell Help**
     - 顯示 Shell 運行器的說明資訊。

Text 選單
---------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 選單項目
     - 說明
   * - **Font**
     - 開啟字型選擇對話框，變更編輯器的預設字型。
   * - **Font Size**
     - 開啟對話框變更編輯器的預設字型大小。

Check Code Style 選單
---------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 選單項目
     - 說明
   * - **yapf**
     - 使用 ``yapf`` 程式碼格式化工具檢查並格式化目前的 Python 程式碼。
   * - **Reformat JSON**
     - 重新格式化並驗證目前內容為 JSON，套用適當的縮排。

Venv 選單
---------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 選單項目
     - 說明
   * - **Create Venv**
     - 在目前工作目錄中使用 Shell 運行器建立 Python 虛擬環境。
   * - **pip upgrade package**
     - 在虛擬環境中使用 pip 升級指定的套件。
   * - **pip package**
     - 在虛擬環境中使用 pip 安裝指定的套件。

.. note::

   PyBreeze 會自動偵測專案中的 ``.venv`` 或 ``venv`` 目錄，
   並在可用時使用虛擬環境的 Python 直譯器。

UI Style 選單
-------------

包含可用的 Qt Material 主題列表。點擊任何主題即可立即套用到整個應用程式。
完整的主題列表請參閱 :doc:`ui_overview`。
