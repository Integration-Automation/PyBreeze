13. 疑難排解與各平台的設定
==========================

**你會做的事**：找出前面教學裡某件事為什麼不成功，並替某個平台做好 PyBreeze 需要的設定。

先看哪裡
--------

- **執行視窗**。一次執行會用它自己的幾行說明出了什麼錯：``[錯誤] 找不到指令``、
  ``[錯誤] 找不到 Python 直譯器``、套件的 traceback。
- **日誌檔**：``~/.pybreeze/logs/PyBreeze.log`` （見 :doc:`../getting_started` 的「日誌檔」）。
  每一行都有行程 ID；語言伺服器與關鍵字探測也寫在這裡。
- **Tools > Automation Keywords Tab**：對每個框架說明執行腳本的直譯器裝的是哪個版本，
  或為什麼拿不到關鍵字。

最小的檢查
----------

這個檢查不需要視窗，可以知道安裝本身是否完整。

.. code-block:: bash

   python -c "import pybreeze, PySide6; print(PySide6.__version__)"
   python -m pybreeze.extend.language_server --help

**預期結果**：一個 PySide6 版本號，以及語言伺服器的用法說明。這裡出現 ``ImportError``
是安裝的問題，不是 IDE 的問題：請在全新的虛擬環境裡重新安裝
（:doc:`t01_install_first_launch`）。

Windows
-------

- ``python`` 開啟了 Microsoft Store，或什麼都沒印就結束：那是 Store 的替身。
  用 ``py -3.12`` 建立虛擬環境，啟用之後再用環境自己的 ``python``。
- 執行視窗裡的文字是亂碼：程式用主控台的字碼頁輸出。外掛的執行設定請加上
  ``"encoding": "locale"`` （:doc:`../menu_plugins`）。
- 自動化套件自己的 XML 報告是用本機的字碼頁寫的；報告檢視器會照那個編碼讀取。

macOS
-----

- AutoControl 需要控制電腦的權限： **系統設定 > 隱私權與安全性 > 輔助使用**
  （截圖還需要 **螢幕錄製**），對象是啟動 PyBreeze 的終端機或應用程式。
- 請從終端機在專案資料夾裡啟動 PyBreeze：按兩下的啟動器會在別的資料夾啟動，
  專案的 ``.venv`` 與 ``jeditor_plugins`` 就找不到了。

Linux
-----

- 視窗沒有出現，或 Qt 回報找不到 ``xcb`` 外掛。請安裝 Qt 需要的系統函式庫；
  在 Debian 與 Ubuntu 上：

  .. code-block:: bash

     sudo apt-get install libegl1 libgl1 libxkbcommon0 libdbus-1-3 libfontconfig1 \
         libnss3 libxcomposite1 libxdamage1 libxrandr2 libxkbfile1

- 在沒有顯示器的機器上（CI），PyBreeze 自己的測試是以 ``QT_QPA_PLATFORM=offscreen`` 執行的。
  IDE 本身需要顯示器，AutoControl 也是。

依現象查
--------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 你看到的
     - 該怎麼做
   * - 執行用了錯的 Python
     - 執行會使用 **Python Env** 選的直譯器，沒選就用工作資料夾裡的 ``venv`` 或 ``.venv``，
       再沒有才用 IDE 自己的。請從專案資料夾啟動 PyBreeze，或選好直譯器。
   * - ``.json`` 腳本沒有補全
     - 檔案必須以 ``.json`` 的檔名存檔。開啟 **Automation Keywords**：如果該框架顯示
       「執行腳本的直譯器沒有安裝」，請把它安裝到那個直譯器（ **Install** 選單）並重新啟動 PyBreeze。
   * - 瀏覽器測試無法啟動瀏覽器
     - WebRunner 需要電腦上裝有那個瀏覽器；驅動程式在第一次使用時下載，那一次需要網路。
   * - MCP 伺服器「無法啟動」
     - 指令的第一行必須是 ``PATH`` 上找得到的程式或完整路徑；每個引數各佔一行。
       伺服器啟動後又停止時，狀態列的結尾是它自己記錄的最後一行。
   * - 報告檢視器說某個檔案「不是報告」
     - 它讀的是套件的 ``_success`` ／ ``_failure`` 檔（JSON 或 XML）、JUnit XML，
       以及從 PyBreeze 匯出的報告。套件的 HTML 報告不會讀：請開它旁邊的 JSON。
   * - AI 審查或架構圖的圖片下載拒絕連到 ``127.0.0.1``
     - 這是刻意的：PyBreeze 自己對你輸入的 URL 送出的請求，會拒絕 loopback 與私有位址。
       你 **執行** 的測試（自動化套件）不受影響。
   * - 主視窗比螢幕還寬
     - 視窗的最小寬度來自編輯器的 Git 面板；請用較大的螢幕或較小的介面字型
       （ **UI Style** 與字型設定）。

還是卡住
--------

請到 https://github.com/Integration-Automation/PyBreeze/issues 開 issue，附上版本
（``pip show pybreeze``）、平台、你做了什麼，以及日誌檔在那個時間附近的幾行。
貼上之前，請先檢查日誌檔裡有沒有金鑰或 token。

回到 :doc:`index`。
