快速開始
========

系統需求
--------

- Python 3.10 或更高版本
- pip（Python 套件管理器）

安裝
----

透過 PyPI 安裝 PyBreeze：

.. code-block:: bash

   pip install pybreeze

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

   # 可用主題：dark_amber.xml（預設）、dark_teal.xml、
   # dark_blue.xml、light_blue.xml 等
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
     - 10 秒後自動關閉（用於 CI 測試）
   * - ``theme``
     - str
     - ``"dark_amber.xml"``
     - Qt Material 主題名稱

首次啟動
--------

PyBreeze 啟動後，主視窗會以最大化方式開啟，包含：

1. **選單列** -- 位於頂部，包含所有可用選單
2. **檔案樹** -- 位於左側，用於專案導覽
3. **程式碼編輯器**（分頁式）-- 位於中央，用於編輯檔案
4. **輸出面板** -- 位於底部，顯示執行結果

PyBreeze 繼承了 **JEditor** 的核心編輯器功能，並擴充了自動化專用的選單、工具和整合功能。
