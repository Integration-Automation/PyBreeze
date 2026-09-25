Automation 選單
===============

**Automation** 選單是 PyBreeze 的核心功能選單。它提供所有整合的自動化模組，
包括 Web、API、GUI、負載測試、檔案自動化和郵件自動化。

每個自動化模組都遵循一致的選單結構：

- **Run** 子選單 -- 執行腳本（單檔或多檔，可選擇是否以郵件發送結果）
- **Help** 子選單 -- 在 IDE 內的瀏覽器分頁開啟文件和 GitHub 儲存庫
- **Project** 子選單 -- 在 IDE 的工作目錄建立新的專案範本
- **<模組> GUI** -- 以分頁開啟該模組的 GUI（**APITestka GUI**、**AutoControl GUI**、**LoadDensity GUI**）

**TestPioneer** 與 **Code Review (prthinker)** 的選單另有結構，見下文。

AutoControl 選單
-----------------

**AutoControl** 是桌面應用程式測試的 GUI 自動化模組，
可以錄製和重播滑鼠/鍵盤操作。

Run 子選單
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 選單項目
     - 說明
   * - **Run AutoControl Script**
     - 將目前編輯器內容作為 AutoControl 腳本執行。
   * - **Run AutoControl With Send**
     - 執行腳本並透過郵件發送結果（使用 MailThunder）。
   * - **Run Multi AutoControl Script**
     - 從選定的目錄執行多個 AutoControl 腳本。
   * - **Run Multi AutoControl Script With Send**
     - 執行多個腳本並透過郵件發送結果。

Help 子選單
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 選單項目
     - 說明
   * - **Open AutoControl Doc**
     - 開啟 AutoControl 文件（https://autocontrol.readthedocs.io/）。
   * - **Open AutoControl GitHub**
     - 開啟 AutoControl GitHub 儲存庫。

Project 子選單
^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 選單項目
     - 說明
   * - **Create AutoControl Project**
     - 在 IDE 的工作目錄建立 AutoControl 專案範本（``je_auto_control``），已存在時會先詢問是否取代。

Record 子選單
^^^^^^^^^^^^^

Record 子選單是 **AutoControl 獨有** 的功能，允許您錄製滑鼠和鍵盤操作以供重播。

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 選單項目
     - 說明
   * - **Record Start**
     - 開始錄製滑鼠和鍵盤操作。
   * - **Record Stop**
     - 停止錄製，並把錄到的操作以 AutoControl 執行器讀得懂的 JSON 插入到前景編輯分頁的游標處；
       前景不是編輯分頁時改為複製到剪貼簿。沒有錄到任何東西時會提示。

AutoControl GUI
^^^^^^^^^^^^^^^

在編輯器中開啟嵌入式 AutoControl GUI 元件作為新分頁，
提供 AutoControl 操作的視覺化介面。

APITestka 選單
--------------

**APITestka** 是 API 測試自動化模組，用於發送 HTTP 請求和驗證回應。

Run 子選單
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 選單項目
     - 說明
   * - **Run APITestka Script**
     - 將目前編輯器內容作為 APITestka 腳本執行。
   * - **Run APITestka With Send**
     - 執行腳本並透過郵件發送結果。
   * - **Run Multi APITestka Script**
     - 從選定的目錄執行多個 APITestka 腳本。
   * - **Run Multi APITestka Script With Send**
     - 執行多個腳本並透過郵件發送結果。

Help 子選單
^^^^^^^^^^^

- **Open APITestka Doc** -- 開啟 https://apitestka.readthedocs.io/
- **Open APITestka GitHub** -- 開啟 GitHub 儲存庫

Project 子選單
^^^^^^^^^^^^^^

- **Create APITestka Project** -- 在 IDE 的工作目錄建立 APITestka 專案範本（``je_api_testka``），已存在時會先詢問是否取代。

APITestka GUI
^^^^^^^^^^^^^

在編輯器中開啟嵌入式 APITestka GUI 元件作為新分頁，用於視覺化 API 測試。

WebRunner 選單
--------------

**WebRunner** 是網頁瀏覽器自動化模組，使用瀏覽器驅動程式（基於 Selenium）
測試網頁應用程式。

Run 子選單
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 選單項目
     - 說明
   * - **Run WebRunner Script**
     - 將目前編輯器內容作為 WebRunner 腳本執行。
   * - **Run WebRunner With Send**
     - 執行腳本並透過郵件發送結果。
   * - **Run Multi WebRunner Script**
     - 從選定的目錄執行多個 WebRunner 腳本。
   * - **Run Multi WebRunner Script With Send**
     - 執行多個腳本並透過郵件發送結果。

Help 子選單
^^^^^^^^^^^

- **Open WebRunner Doc** -- 開啟 https://webrunner.readthedocs.io/
- **Open WebRunner GitHub** -- 開啟 GitHub 儲存庫

Project 子選單
^^^^^^^^^^^^^^

- **Create WebRunner Project** -- 在 IDE 的工作目錄建立 WebRunner 專案範本（``je_web_runner``），已存在時會先詢問是否取代。

LoadDensity 選單
----------------

**LoadDensity** 是負載/效能測試模組，產生並行請求以測試系統容量。

Run 子選單
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 選單項目
     - 說明
   * - **Run LoadDensity Script**
     - 將目前編輯器內容作為 LoadDensity 腳本執行。
   * - **Run LoadDensity With Send**
     - 執行腳本並透過郵件發送結果。
   * - **Run Multi LoadDensity Script**
     - 從選定的目錄執行多個 LoadDensity 腳本。
   * - **Run Multi LoadDensity Script With Send**
     - 執行多個腳本並透過郵件發送結果。

Help 子選單
^^^^^^^^^^^

- **Open LoadDensity Doc** -- 開啟 https://loaddensity.readthedocs.io/
- **Open LoadDensity GitHub** -- 開啟 GitHub 儲存庫

Project 子選單
^^^^^^^^^^^^^^

- **Create LoadDensity Project** -- 在 IDE 的工作目錄建立 LoadDensity 專案範本（``je_load_density``），已存在時會先詢問是否取代。

LoadDensity GUI
^^^^^^^^^^^^^^^

在編輯器中開啟嵌入式 LoadDensity GUI 元件作為新分頁，用於視覺化負載測試設定。

FileAutomation 選單
--------------------

**FileAutomation** 是檔案操作自動化模組，用於自動化檔案系統任務，
如複製、移動、重新命名和處理檔案。

Run 子選單
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 選單項目
     - 說明
   * - **Run FileAutomation Script**
     - 將目前編輯器內容作為 FileAutomation 腳本執行。
   * - **Run FileAutomation With Send**
     - 執行腳本並透過郵件發送結果。
   * - **Run Multi FileAutomation Script**
     - 從選定的目錄執行多個 FileAutomation 腳本。
   * - **Run Multi FileAutomation Script With Send**
     - 執行多個腳本並透過郵件發送結果。

Help 子選單
^^^^^^^^^^^

- **Open FileAutomation Doc** -- 開啟 https://fileautomation.readthedocs.io/
- **Open FileAutomation GitHub** -- 開啟 GitHub 儲存庫

Project 子選單
^^^^^^^^^^^^^^

- **Create FileAutomation Project** -- 在 IDE 的工作目錄建立 FileAutomation 專案範本（``automation_file``），已存在時會先詢問是否取代。

MailThunder 選單
-----------------

**MailThunder** 是郵件自動化模組，用於發送測試報告和自動化通知。

Run 子選單
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 選單項目
     - 說明
   * - **Run MailThunder Script**
     - 將目前編輯器內容作為 MailThunder 腳本執行。

Help 子選單
^^^^^^^^^^^

- **Open MailThunder Doc** -- 開啟 https://mailthunder.readthedocs.io/
- **Open MailThunder GitHub** -- 開啟 GitHub 儲存庫

Project 子選單
^^^^^^^^^^^^^^

- **Create MailThunder Project** -- 在 IDE 的工作目錄建立 MailThunder 專案範本（``je_mail_thunder``），已存在時會先詢問是否取代。

TestPioneer 選單
-----------------

**TestPioneer** 提供基於 YAML 的測試設定和執行。

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 選單項目
     - 說明
   * - **Create TestPioneer YAML Template**
     - 在 IDE 的工作目錄建立 ``.TestPioneer/.TestPioneer.yml``，已存在時會先詢問是否取代。
   * - **Run TestPioneer YAML**
     - 開啟檔案對話框選擇 ``.yml`` 或 ``.yaml`` 檔案，並執行其中定義的測試。
   * - **Help > Open TestPioneer GitHub**
     - 在瀏覽器分頁開啟 TestPioneer GitHub 儲存庫（它的 README 就是手冊）。

Code Review (prthinker) 選單
----------------------------

執行 prthinker 思維鏈程式碼審查，輸出串流到執行視窗。請先用
**Install > Automation > Install prthinker (code review)** 安裝 prthinker。

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 選單項目
     - 說明
   * - **Review the current file**
     - 先儲存前景編輯分頁的檔案，再審查它。
   * - **Review a Pull Request**
     - 詢問 Pull Request 編號，審查 **Settings** 中設定之儲存庫的該 Pull Request。
   * - **Settings**
     - 開啟 prthinker 設定：推論後端、模型、程式碼託管平台、儲存庫、金鑰與權杖。
   * - **Help > Open prthinker documentation**
     - 在瀏覽器分頁開啟 https://code-review-framework.readthedocs.io/ 。
   * - **Help > Open prthinker GitHub**
     - 在瀏覽器分頁開啟 prthinker GitHub 儲存庫。

腳本執行流程
------------

當您執行任何自動化腳本時，會發生以下流程：

1. 擷取目前程式碼編輯器的內容。
2. 使用 ``TaskProcessManager`` 產生子程序。
3. 腳本在獨立的程序中執行（防止崩潰影響 IDE）。
4. 開啟執行視窗即時顯示執行輸出，標題是套件名稱與它執行的檔案，並有 **Stop** 按鈕。
5. 如果選擇了「With Send」，執行完成後透過 MailThunder 郵件發送結果。

.. note::

   每個自動化模組都在獨立的子程序中執行，確保穩定性。
   即使腳本崩潰，PyBreeze IDE 主程式仍不受影響。

多腳本執行
^^^^^^^^^^

使用「Run Multi」選項時：

1. 開啟資料夾選擇對話框。
2. 收集該資料夾及其子資料夾中所有 ``.json`` 動作檔；沒有時會提示。
3. 檔案依序執行，每個都在自己的子程序與自己的執行視窗中。
4. 每次執行各自回報結果（選「With Send」時各自寄出報告）；停止其中一次執行會結束整批。

報告格式
^^^^^^^^

自動化模組可以產生多種格式的報告：

- **HTML** -- 視覺化報告，適合分享
- **JSON** -- 機器可讀的結果
- **XML** -- 標準測試結果格式
