Plugins 選單
============

PyBreeze 支援外掛系統以擴充功能。外掛會自動從工作目錄中的
``jeditor_plugins/`` 目錄探索載入。

外掛瀏覽器
----------

開啟外掛瀏覽器介面，您可以：

- 瀏覽可用的外掛
- 查看外掛詳細資訊
- 安裝新外掛

已載入外掛
----------

啟動後，在 ``jeditor_plugins/`` 中找到的任何外掛都會自動載入，
並列在 Plugins 選單下。每個已載入的外掛都會顯示為一個選單項目。

Run With 選單
-------------

**Run With** 選單提供使用不同編譯器和直譯器執行目前檔案的選項。
此選單根據可用的語言支援動態建立。

支援的語言包括：

- **C** -- 使用 gcc/clang 編譯並執行
- **C++** -- 使用 g++/clang++ 編譯並執行
- **Go** -- 使用 go run 執行
- **Java** -- 使用 javac/java 編譯並執行
- **Rust** -- 使用 rustc 編譯並執行

.. note::

   可用的「Run With」選項取決於系統上安裝了哪些編譯器/直譯器，
   以及它們是否可透過系統 PATH 找到。

建立外掛
--------

關於建立自訂外掛的詳細資訊，包括語法高亮外掛和 UI 翻譯外掛，
請參閱 `外掛指南 <https://github.com/Intergration-Automation-Testing/AutomationEditor/blob/main/PLUGIN_GUIDE.md>`_。

語法高亮外掛範例
^^^^^^^^^^^^^^^^

外掛可以使用自訂關鍵字擴充語法高亮：

.. code-block:: python

   # jeditor_plugins/my_syntax_plugin.py
   from je_editor import syntax_word_dict

   syntax_word_dict.update({
       "my_keyword": "keyword_format",
       "my_function": "function_format",
   })

UI 翻譯外掛範例
^^^^^^^^^^^^^^^^

外掛可以新增新的 UI 翻譯：

.. code-block:: python

   # jeditor_plugins/my_language_plugin.py
   from je_editor import language_wrapper

   language_wrapper.language_word_dict.update({
       "application_name": "我的自訂名稱",
       # ... 更多翻譯
   })
