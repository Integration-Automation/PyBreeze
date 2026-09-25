快速開始
========

系統需求
--------

- Python 3.10 到 3.14
- pip（Python 套件管理器）
- Windows、macOS 或 Linux；PySide6 會隨 PyBreeze 一起安裝

安裝
----

透過 PyPI 安裝 PyBreeze：

.. code-block:: bash

   pip install pybreeze

或從原始碼安裝：

.. code-block:: bash

   git clone https://github.com/Integration-Automation/PyBreeze.git
   cd PyBreeze
   pip install -r requirements.txt

兩種方式都會一併安裝自動化模組（AutoControl、APITestka、WebRunner、LoadDensity、FileAutomation、
MailThunder、TestPioneer）、paramiko 與 JupyterLab。之後可以從 **Install** 選單把它們升級到執行時使用的直譯器
（見 :doc:`menu_install`）。

啟動 PyBreeze
-------------

**方法一：命令列**

.. code-block:: bash

   python -m pybreeze

**方法二：Python 腳本**

.. code-block:: python

   from pybreeze import start_editor

   start_editor()

**方法三：自訂選項**

.. code-block:: python

   from pybreeze import start_editor

   # UI Style 選單列出的任何主題：dark_teal.xml、
   # dark_blue.xml、light_blue.xml……它會取代從 UI Style 選的主題。
   start_editor(theme="dark_teal.xml")

參數說明
^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 20 15 20 45

   * - 參數
     - 類型
     - 預設值
     - 說明
   * - ``debug_mode``
     - bool
     - ``False``
     - 10 秒後自行關閉（用於啟動測試）
   * - ``theme``
     - str 或 None
     - ``None``
     - Qt Material 主題名稱。它會取代從 **UI Style** 選的主題，並成為選定的主題。``None`` 表示用選定的主題
       （還沒選過時是 ``dark_amber.xml``）。

工作資料夾
----------

請從你的專案資料夾啟動 PyBreeze。它啟動時所在的資料夾，或之後以 **File > Open Folder** 開啟的資料夾，就是：

- 檔案樹開啟的位置；
- 尋找 ``venv/`` 或 ``.venv/`` 的位置，在 **Python Env** 沒有選直譯器時用它執行腳本；
- **Create ... Project** 與 TestPioneer 範本寫入的位置。

外掛只在啟動時載入一次，來源是 PyBreeze 啟動時所在資料夾中的 ``jeditor_plugins/``\ （見 :doc:`menu_plugins`）。

首次啟動
--------

PyBreeze 啟動後，主視窗會以最大化方式開啟，包含：

1. **選單列** -- 位於頂部，包含所有可用選單
2. **檔案樹** -- 位於左側，用於專案導覽
3. **程式碼編輯器**\ （分頁式）-- 位於中央，用於編輯檔案
4. **輸出面板** -- 位於編輯器下方，其中的 **Code result** 分頁顯示 **Run Program** 與 **Run On Shell** 的輸出

PyBreeze 繼承了 **JEditor** 的核心編輯器功能，並擴充了自動化專用的選單、工具和整合功能。
