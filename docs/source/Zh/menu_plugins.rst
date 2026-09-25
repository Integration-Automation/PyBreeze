Plugins 選單
============

PyBreeze 使用 JEditor 的外掛系統。外掛在啟動時從工作目錄中的 ``jeditor_plugins/`` 資料夾載入
（若是 JEditor 的開發用 checkout，也會讀它套件旁的那一個）：

- ``.py`` 檔是一個外掛，含 ``__init__.py`` 的資料夾也是；
- 沒有 ``__init__.py`` 的資料夾只用來分組，會往裡面找；
- 名稱以 ``_`` 或 ``.`` 開頭的會略過。

每個外掛都定義一個 ``register()`` 函式，載入時呼叫一次。也可以設定 ``PLUGIN_NAME``、``PLUGIN_AUTHOR``、
``PLUGIN_VERSION`` 與 ``PLUGIN_RUN_CONFIG``。

外掛瀏覽器
----------

**Plugins > Plugin Browser** 會開一個分頁，列出 GitHub 儲存庫中的外掛（預設是
``https://github.com/Jeffrey-Plugin-Repos/IDE_Plugins``；也可以在 **Repository URL** 輸入任何
``https://github.com/owner/repo`` 或 ``owner/repo``，再按 **Fetch Plugins** 讀取）。選一個外掛可看它的
詳細資訊與原始碼，按 **Download & Install** 會把它存進工作目錄的 ``jeditor_plugins/``，已有同名外掛時會先詢問是否取代。
裝好的外掛在下次啟動時載入。

還沒裝任何外掛時，這個項目也在。

已載入外掛
----------

在 Plugin Browser 下方，每個已載入的外掛各有一個項目：

- 沒有執行設定的外掛（翻譯、語法外掛）：它的名稱，點了會顯示名稱、版本與作者；
- 有執行設定的外掛：以執行設定命名的子選單，內有 **About** 與 **Run with** *<名稱>*\ （能執行多種副檔名時，
  標籤會一併列出）。

Run with... 選單
----------------

只要有外掛註冊了執行設定，**Run** 選單就會出現 **Run with...** 子選單：每個執行設定一項，標籤是它的名稱與副檔名。
它執行前景編輯分頁中的檔案：

1. 先存檔，用分頁自己的編碼與行尾；還沒有檔案的分頁會走 **Save As**。存檔失敗會告知，而且不執行。
2. 副檔名不在執行設定清單中的檔案會被拒絕。
3. 檔案在執行視窗中執行，標題是執行設定的名稱與檔名，並有 **Stop** 按鈕：``compiler [args...] file``；
   編譯式語言則先編譯（限時 60 秒），再執行編出的程式。編譯產物放在暫存資料夾，執行後刪除。

.. note::

   執行設定只指定編譯器或直譯器的名稱，它必須已經安裝並在 ``PATH`` 上，否則執行視窗會說找不到指令。

執行設定是一個字典：

.. code-block:: python

   PLUGIN_RUN_CONFIG = {
       "name": "Go",            # 選單標籤
       "suffixes": (".go",),    # 它執行的檔案
       "compiler": "go",        # 啟動的程式
       "args": ("run",),        # 放在編譯器與檔案之間的參數
       # 編譯式語言：
       # "compile_then_run": True, "output_flag": "-o",
       # 只有 PyBreeze 讀：程式輸出的編碼（"locale" 表示這台電腦自己的）
       # "encoding": "locale",
   }

建立外掛
--------

完整的外掛 API 與實作範例在 JEditor 的
`Plugin Guide <https://github.com/Integration-Automation/JEDITOR/blob/main/PLUGIN_GUIDE.md>`_；
PyBreeze 的 `PLUGIN_GUIDE.md <https://github.com/Integration-Automation/PyBreeze/blob/main/PLUGIN_GUIDE.md>`_
說明 PyBreeze 額外提供的部分。現成的外掛放在
`IDE_Plugins <https://github.com/Jeffrey-Plugin-Repos/IDE_Plugins>`_。

語法高亮外掛範例
^^^^^^^^^^^^^^^^

外掛可以依副檔名為一種語言的關鍵字上色：

.. code-block:: python

   # jeditor_plugins/lua_syntax.py
   from PySide6.QtGui import QColor
   from je_editor.plugins import register_programming_language

   PLUGIN_NAME = "Lua syntax"
   PLUGIN_VERSION = "1.0"


   def register() -> None:
       register_programming_language(
           suffix=".lua",
           syntax_words={
               "keywords": {"words": ("function", "local", "end", "return"),
                            "color": QColor(86, 156, 214)},
           },
           syntax_rules={
               "comments": {"rules": (r"--[^\n]*",), "color": QColor(106, 153, 85)},
           },
       )

.. note::

   註冊的關鍵字只用在 JEditor 自己不上色的副檔名。``.c``、``.cpp``、``.go``、``.h``、``.hpp``、``.java``、
   ``.js``、``.json``、``.rs``、``.sh``、``.sql``、``.toml``、``.ts``、``.yaml`` 與 ``.yml``
   用的是 JEditor 自己的規則，外掛為它們註冊的關鍵字不會顯示。

介面翻譯外掛範例
^^^^^^^^^^^^^^^^

外掛可以新增一種介面語言，列在 **Language** 選單中：

.. code-block:: python

   # jeditor_plugins/french.py
   from je_editor.plugins import register_natural_language

   PLUGIN_NAME = "French"


   def register() -> None:
       register_natural_language("French", "Français", {
           "file_menu_label": "Fichier",
           # ... 其他翻譯字串
       })

鍵與 JEditor 的英文字典和 PyBreeze 的（``pybreeze/extend_multi_language/extend_english.py``）相同。
外掛沒有提供的鍵會以英文顯示。
