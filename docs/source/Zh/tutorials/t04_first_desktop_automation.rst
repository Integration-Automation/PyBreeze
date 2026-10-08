4. 用 AutoControl 做第一個桌面自動化
====================================

**你會做的事**：執行一支腳本，向桌面問兩件事（螢幕多大、滑鼠在哪裡）並把它們記錄下來。
它不會移動滑鼠，也不會點任何東西。

開始之前
--------

- :doc:`t01_install_first_launch`。
- 一個桌面工作階段。在 macOS 上還需要 :doc:`t13_troubleshooting` 說明的權限。

範例
----

.. literalinclude:: ../../examples/first_desktop_automation.json
   :language: json
   :caption: first_desktop_automation.json

``AC_set_record_enable`` 開啟步驟的記錄。 ``AC_screen_size`` 與 ``AC_get_mouse_position``
不需要引數，所以這兩個動作只有關鍵字本身。

步驟
----

1. 在編輯器開啟 ``first_desktop_automation.json``。
2. 選擇 **Automation > AutoControl > Run > Run AutoControl Script**。

預期結果
--------

執行視窗會顯示下面的內容，數字是你自己電腦的：

.. code-block:: text

   execute: ['AC_set_record_enable', {'set_enable': True}]
   None
   execute: ['AC_screen_size']
   [1920, 1080]
   execute: ['AC_get_mouse_position']
   (477, 1079)
   execute: ['AC_generate_json_report', {'json_file_name': 'desktop_report'}]
   None
   Task exit with code 0

``desktop_report_success.json`` 裡有兩筆紀錄，名稱是關鍵字背後的函式（ ``size`` 與
``get_mouse_position`` ），各自帶著執行的時間。

會實際動作的關鍵字也是同樣的形狀： ``["AC_set_mouse_position", {"x": 100, "y": 200}]``、
``["AC_click_mouse", {"mouse_keycode": "mouse_left"}]``、
``["AC_write", {"write_string": "hello"}]``。 **Tools > Automation Keywords Tab**
列出全部的關鍵字與它們的參數； **Automation > AutoControl > Record** 會把你的操作寫成腳本。

.. warning::

   會移動滑鼠或打字的腳本是真的會做，而且是對當時在最前面的視窗做。
   請在不小心點錯也沒關係的桌面上嘗試。

如果不成功
----------

- macOS 回報這個行程不受信任：請授予「輔助使用」權限。
- 沒有顯示器的 Linux（伺服器、容器）：AutoControl 需要顯示器。

下一步
------

:doc:`t05_first_load_scenario`
