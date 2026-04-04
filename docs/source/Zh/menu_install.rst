Install 選單
============

**Install** 選單提供一鍵安裝自動化套件和建置工具的功能，
直接在 PyBreeze IDE 中完成安裝。

Automation 子選單
-----------------

透過 pip 安裝自動化模組套件。

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 選單項目
     - 說明
   * - **Install AutoControl**
     - 執行 ``pip install -U je_auto_control``
   * - **Install APITestka**
     - 執行 ``pip install -U je_api_testka``
   * - **Install LoadDensity**
     - 執行 ``pip install -U je_load_density``
   * - **Install WebRunner**
     - 執行 ``pip install -U je_web_runner``
   * - **Install Automation File**
     - 執行 ``pip install -U automation_file``
   * - **Install MailThunder**
     - 執行 ``pip install -U je_mail_thunder``

Tools 子選單
------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 選單項目
     - 說明
   * - **Install Build Tools**
     - 執行 ``pip install -U setuptools build wheel`` 以安裝 Python
       打包和建置工具。

.. note::

   所有安裝命令都在 Shell 運行器中執行，並遵循目前啟用的虛擬環境。
   如果偵測到 ``.venv`` 或 ``venv`` 目錄，套件將安裝到該環境中。
