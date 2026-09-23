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
   * - **Install prthinker (code review)**
     - prthinker 不在 PyPI 上。第一次會詢問它的原始碼資料夾並記下來，
       之後執行 ``pip install -U <資料夾>[runner]``

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

   每次安裝都會開一個自己的執行視窗，在裡面執行 ``python -m pip``，中間不經過 shell，
   所以資料夾名稱裡有 ``&`` 或 ``|`` 也會原樣交給 pip。pip 使用 Python 環境選單選定的
   直譯器；沒有選的話，使用工作目錄下的 ``venv`` 或 ``.venv``，再沒有就用 ``PATH`` 上找到的 Python。
