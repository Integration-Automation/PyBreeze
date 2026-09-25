File、Run、Text 與其他基礎選單
==============================

這些選單來自 PyBreeze 所建構的 JEditor 編輯器引擎。幾乎每個項目都作用在前景的編輯分頁上，
前景不是編輯分頁時什麼都不做。

JEditor 把這些設定存在工作資料夾的 ``.jeditor/user_setting.json``，所以每個專案資料夾各有一份；
每分鐘與關閉 IDE 時儲存。已有檔案的編輯分頁也會每隔幾秒自動存回檔案。

File 選單
---------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 選單項目
     - 說明
   * - **New File**
     - 詢問名稱與位置，在那裡建立空檔案（不會開啟它）。
   * - **Open File**
     - 把檔案開進前景的編輯分頁，取代它原本顯示的內容，不會詢問那裡未存的文字（見 :doc:`ui_overview`）。
   * - **Open Folder**
     - 把一個資料夾設為工作資料夾：檔案樹顯示它，並載入它的設定（見 :doc:`getting_started`）。
   * - **Save File**
     - 開啟從工作資料夾開始的 **Save As** 對話框，把分頁寫到選定的位置。
   * - **Recent Files**
     - 最近開啟的檔案，點選後在新分頁開啟。清單在啟動時重建。
   * - **Font** / **Font Size**
     - 整個視窗的字型與大小：選單、樹狀檢視與面板。
   * - **Encodings**
     - 分頁檔案的編碼。分頁沒有未存的編輯時，會以這個編碼重新讀取檔案；下次存檔也用它寫入。
   * - **Line Endings**
     - 分頁檔案下次存檔用的 ``LF``、``CRLF`` 或 ``CR``。
   * - **Save All**
     - 寫入每個已有檔案的編輯分頁。

Run 選單
--------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 選單項目
     - 說明
   * - **Run Program > Run Program**
     - 開啟 **Save As** 對話框寫入分頁，再以 Python 執行檔案；輸出到分頁的 **Code result**。
       每個分頁一次只能執行一個程式。
   * - **Run Program > Show program input**
     - 一個小視窗，輸入的文字會送到執行中程式的標準輸入。
   * - **Run On Shell > Run On Shell**
     - 把分頁的文字原樣當成一個 Shell 指令執行（Windows 上是 ``cmd.exe``）；輸出到 **Code result**。
   * - **Run On Shell > Show shell input**
     - 同樣的輸入視窗，給 Shell 用。
   * - **Debugger > Run Debugger**
     - 開啟 **Save As** 對話框後，以 ``pdb`` 執行檔案，並帶入編輯器邊欄設定的中斷點；輸出在 **Debugger**
       分頁，輸入視窗會自動開啟。JEditor 1.0.27 中每個編輯分頁只能執行一次：要再除錯，請在另一個分頁開啟該檔案。
   * - **Debugger > Show debugger input**
     - 再次開啟除錯器的輸入視窗。
   * - **Clean Result**
     - 清空分頁的 **Code result**。
   * - **Stop current program**
     - 停止分頁的程式、Shell 指令與除錯器。
   * - **Stop All Program**
     - 停止從這些選單啟動、在任何分頁中執行的程式、Shell 指令、除錯器與 ``pip``，以及每個 PyBreeze
       執行視窗中的執行（自動化腳本、安裝、**Run with...**）；執行視窗與輸出會留著。
   * - **Run Help > Run Help** / **Shell Help**
     - 提示：確認直譯器，並讓編碼與 Shell 的一致。
   * - **Run with...**
     - 只在有外掛註冊了執行設定時出現（見 :doc:`menu_plugins`）。

Run Program、Run Debugger、**Python Env** 的項目與 PyBreeze 的自動化執行，都使用在
**Python Env > Choose python interpreter** 選的直譯器。沒有選時，Run Program 與 Run Debugger 用工作資料夾中的
``venv/``，否則用 ``PATH`` 上的 Python；PyBreeze 的自動化執行與 JupyterLab 用那裡的 ``venv/`` 或 ``.venv/``，
否則用執行 PyBreeze 的那個 Python。Run On Shell 不使用直譯器。

Text 選單
---------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 選單項目
     - 說明
   * - **Font** / **Font Size**
     - 每個編輯分頁中編輯器與 **Code result** 的字型與大小。
   * - **Word Wrap**
     - 在每個編輯分頁中自動換行（下次啟動時又會關閉）。
   * - **Indent Size**
     - 2、4 或 8 個空白：Tab 寬度與縮排單位。檔案本身的縮排優先。
   * - **Trim Trailing Whitespace**、**Convert Indentation to Spaces** / **to Tabs**
     - 整份文件。
   * - **Remove Duplicate Lines**、**Reverse Lines**、**Sort Lines (Natural)**、
       **Remove Blank Lines**、**Align by Delimiter...**
     - 選取範圍涵蓋的行，至少兩行。**Align by Delimiter...** 會詢問分隔符號（預設 ``=``）。
   * - **Uppercase Selection**、**Lowercase Selection**、**Swap Case**、**Title Case**、
       **Naming Style**、**Number Base**、**Encode / Decode**
     - 選取的文字；沒有選取、或無法轉換時什麼都不做。**Naming Style** 轉成 ``snake_case``、``camelCase``、
       ``PascalCase`` 或 ``kebab-case``；**Number Base** 轉成十六進位、十進位或二進位；**Encode / Decode**
       做 Base64、URL、HTML 與 JSON 字串的雙向跳脫。
   * - **Statistics**
     - 選取範圍或整份文件的行數、字數、字元數與不含空白的字元數。

Check Code Style 選單
---------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 選單項目
     - 說明
   * - **yapf**
     - 以 ``yapf``\ （Google 風格）重新排版整個分頁；有語法錯誤時不會改動。
   * - **Reformat JSON**
     - 把分頁改寫成 4 格縮排、鍵排序過的 JSON；錯誤顯示在 **Code result**。
   * - **Python format check**
     - 對存檔後的 ``.py`` 檔執行 ``pycodestyle``\ （不檢查未存的編輯），結果列在 **Format checker** 分頁。
   * - **Format on Save**
     - 開關：**Save File**、**Save All** 與 **Run Program** 寫入 ``.py`` 檔時，先以 ``yapf`` 排版。
       自動存檔不會排版。

Python Env 選單
---------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 選單項目
     - 說明
   * - **Create venv**
     - 在工作資料夾執行 ``python -m venv venv``，用選定的直譯器或 ``PATH`` 上的 Python；輸出到 **Code result**。
   * - **pip upgrade package** / **pip package**
     - 詢問套件名稱後執行 ``pip install``\ （升級時加 ``-U``），用選定的直譯器或 ``venv/`` 裡的那一個。
       工作資料夾中必須有 ``venv/``。
   * - **Choose python interpreter**
     - 選擇直譯器檔案。它會被儲存，並依上方 **Run 選單** 所述使用；**Install** 選單也安裝到它裡面。

Tab 與 Dock 選單
----------------

**Tab** 以分頁開啟面板，**Dock** 以停靠面板開啟（見 :doc:`ui_overview`）：

- **Add Editor Tab**、**Add Web Browser Tab**，以及停靠式編輯器（**Dock > Editor > New Dock Editor**，
  關閉停靠面板時寫回它的檔案）
- **Console Widget** -- 互動式 Shell（``cmd``、PowerShell、``bash`` 或 ``sh``）
- **Toggle Split View**\ （同一份文件顯示兩次）與 **Toggle Minimap**，作用在前景分頁
- **Snippet Editor** -- ``.jeditor/snippets.json`` 中的程式碼片段
- **Tools Tab** -- IPython（Jupyter，在 IDE 自己的 Python 中）、變數檢視器（JEditor 1.0.27 中是空的：沒有東西提供變數給它）、FrontEngine、ChatUI、TODO 面板、
  目前 Python 檔的大綱，以及 JupyterLab（見 :doc:`jupyter_lab`）
- **Git Tab** -- Git 用戶端、分支樹檢視器、程式碼差異檢視器，以及目前檔案與 ``HEAD`` 或暫存版本的差異
- **Dock > Tools** 另有 **Problems**\ （``ruff`` 找到的問題）與 **Tests**\ （在工作資料夾執行 ``pytest``）

UI Style 選單
-------------

Qt Material 主題（見 :doc:`ui_overview`）：點選後立即套用，並儲存供下次啟動使用。**Show Indent Guides** 與
**Show Trailing Whitespace** 開關編輯器中的這兩種標示，**Keyboard Shortcuts...** 可重新綁定編輯器的指令。
