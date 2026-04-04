Automation 選單
===============

**Automation** 選單是 PyBreeze 的核心功能選單。它提供所有整合的自動化模組，
包括 Web、API、GUI、負載測試、檔案自動化和郵件自動化。

每個自動化模組都遵循一致的選單結構：

- **RUN** 子選單 -- 執行腳本（單檔或多檔，可選擇是否以郵件發送結果）
- **HELP** 子選單 -- 連結到文件和 GitHub 儲存庫
- **Project** 子選單 -- 建立新的專案範本
- **GUI Tab** -- 開啟嵌入式 GUI 元件（部分模組可用）

AutoControl 選單
-----------------

**AutoControl** 是桌面應用程式測試的 GUI 自動化模組，
可以錄製和重播滑鼠/鍵盤操作。

RUN 子選單
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 選單項目
     - 說明
   * - **Run AutoControl Script**
     - 將目前編輯器內容作為 AutoControl 腳本執行。
   * - **Run AutoControl Script With Send**
     - 執行腳本並透過郵件發送結果（使用 MailThunder）。
   * - **Run Multi AutoControl Script**
     - 從選定的目錄執行多個 AutoControl 腳本。
   * - **Run Multi AutoControl Script With Send**
     - 執行多個腳本並透過郵件發送結果。

HELP 子選單
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
   * - **Create Project**
     - 使用 ``je_auto_control`` 建立新的 AutoControl 專案結構。

Record 子選單
^^^^^^^^^^^^^

Record 子選單是 **AutoControl 獨有** 的功能，允許您錄製滑鼠和鍵盤操作以供重播。

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 選單項目
     - 說明
   * - **Start Record**
     - 開始錄製滑鼠和鍵盤操作。
   * - **Stop Record**
     - 停止錄製並將錄製的操作資料插入到程式碼編輯器中。

GUI Tab
^^^^^^^

在編輯器中開啟嵌入式 AutoControl GUI 元件作為新分頁，
提供 AutoControl 操作的視覺化介面。

APITestka 選單
--------------

**APITestka** 是 API 測試自動化模組，用於發送 HTTP 請求和驗證回應。

RUN 子選單
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 選單項目
     - 說明
   * - **Run APITestka Script**
     - 將目前編輯器內容作為 APITestka 腳本執行。
   * - **Run APITestka Script With Send**
     - 執行腳本並透過郵件發送結果。
   * - **Run Multi APITestka Script**
     - 從選定的目錄執行多個 APITestka 腳本。
   * - **Run Multi APITestka Script With Send**
     - 執行多個腳本並透過郵件發送結果。

HELP 子選單
^^^^^^^^^^^

- **Open APITestka Doc** -- 開啟 https://apitestka.readthedocs.io/
- **Open APITestka GitHub** -- 開啟 GitHub 儲存庫

Project 子選單
^^^^^^^^^^^^^^

- **Create Project** -- 使用 ``je_api_testka`` 建立新的 APITestka 專案結構。

GUI Tab
^^^^^^^

在編輯器中開啟嵌入式 APITestka GUI 元件作為新分頁，用於視覺化 API 測試。

WebRunner 選單
--------------

**WebRunner** 是網頁瀏覽器自動化模組，使用瀏覽器驅動程式（基於 Selenium）
測試網頁應用程式。

RUN 子選單
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 選單項目
     - 說明
   * - **Run WebRunner Script**
     - 將目前編輯器內容作為 WebRunner 腳本執行。
   * - **Run WebRunner Script With Send**
     - 執行腳本並透過郵件發送結果。
   * - **Run Multi WebRunner Script**
     - 從選定的目錄執行多個 WebRunner 腳本。
   * - **Run Multi WebRunner Script With Send**
     - 執行多個腳本並透過郵件發送結果。

HELP 子選單
^^^^^^^^^^^

- **Open WebRunner Doc** -- 開啟 https://webrunner.readthedocs.io/
- **Open WebRunner GitHub** -- 開啟 GitHub 儲存庫

Project 子選單
^^^^^^^^^^^^^^

- **Create Project** -- 使用 ``je_web_runner`` 建立新的 WebRunner 專案結構。

LoadDensity 選單
----------------

**LoadDensity** 是負載/效能測試模組，產生並行請求以測試系統容量。

RUN 子選單
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 選單項目
     - 說明
   * - **Run LoadDensity Script**
     - 將目前編輯器內容作為 LoadDensity 腳本執行。
   * - **Run LoadDensity Script With Send**
     - 執行腳本並透過郵件發送結果。
   * - **Run Multi LoadDensity Script**
     - 從選定的目錄執行多個 LoadDensity 腳本。
   * - **Run Multi LoadDensity Script With Send**
     - 執行多個腳本並透過郵件發送結果。

HELP 子選單
^^^^^^^^^^^

- **Open LoadDensity Doc** -- 開啟 https://loaddensity.readthedocs.io/
- **Open LoadDensity GitHub** -- 開啟 GitHub 儲存庫

Project 子選單
^^^^^^^^^^^^^^

- **Create Project** -- 使用 ``je_load_density`` 建立新的 LoadDensity 專案結構。

GUI Tab
^^^^^^^

在編輯器中開啟嵌入式 LoadDensity GUI 元件作為新分頁，用於視覺化負載測試設定。

FileAutomation 選單
--------------------

**FileAutomation** 是檔案操作自動化模組，用於自動化檔案系統任務，
如複製、移動、重新命名和處理檔案。

RUN 子選單
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 選單項目
     - 說明
   * - **Run FileAutomation Script**
     - 將目前編輯器內容作為 FileAutomation 腳本執行。
   * - **Run FileAutomation Script With Send**
     - 執行腳本並透過郵件發送結果。
   * - **Run Multi FileAutomation Script**
     - 從選定的目錄執行多個 FileAutomation 腳本。
   * - **Run Multi FileAutomation Script With Send**
     - 執行多個腳本並透過郵件發送結果。

HELP 子選單
^^^^^^^^^^^

- **Open FileAutomation Doc** -- 開啟 https://fileautomation.readthedocs.io/
- **Open FileAutomation GitHub** -- 開啟 GitHub 儲存庫

Project 子選單
^^^^^^^^^^^^^^

- **Create Project** -- 使用 ``automation_file`` 建立新的 FileAutomation 專案結構。

MailThunder 選單
-----------------

**MailThunder** 是郵件自動化模組，用於發送測試報告和自動化通知。

RUN 子選單
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 選單項目
     - 說明
   * - **Run MailThunder Script**
     - 將目前編輯器內容作為 MailThunder 腳本執行。

HELP 子選單
^^^^^^^^^^^

- **Open MailThunder Doc** -- 開啟 https://mailthunder.readthedocs.io/
- **Open MailThunder GitHub** -- 開啟 GitHub 儲存庫

Project 子選單
^^^^^^^^^^^^^^

- **Create Project** -- 建立新的 MailThunder 專案結構。

TestPioneer 選單
-----------------

**TestPioneer** 提供基於 YAML 的測試設定和執行。

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 選單項目
     - 說明
   * - **Create TestPioneer Yaml Template**
     - 產生用於定義測試案例的 YAML 範本檔案。
   * - **Execute Test Pioneer Yaml**
     - 開啟檔案對話框選擇 ``.yml`` 檔案，並執行其中定義的測試。

腳本執行流程
------------

當您執行任何自動化腳本時，會發生以下流程：

1. 擷取目前程式碼編輯器的內容。
2. 使用 ``TaskProcessManager`` 產生子程序。
3. 腳本在獨立的程序中執行（防止崩潰影響 IDE）。
4. 開啟 **程式碼輸出視窗** 即時顯示執行輸出。
5. 如果選擇了「With Send」，執行完成後透過 MailThunder 郵件發送結果。

.. note::

   每個自動化模組都在獨立的子程序中執行，確保穩定性。
   即使腳本崩潰，PyBreeze IDE 主程式仍不受影響。

多腳本執行
^^^^^^^^^^

使用「Run Multi」選項時：

1. 開啟目錄選擇對話框。
2. 收集選定目錄中所有符合的腳本檔案。
3. 每個腳本在各自的子程序中依序執行。
4. 彙整所有腳本的結果。

報告格式
^^^^^^^^

自動化模組可以產生多種格式的報告：

- **HTML** -- 視覺化報告，適合分享
- **JSON** -- 機器可讀的結果
- **XML** -- 標準測試結果格式
