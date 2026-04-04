JupyterLab 整合
================

PyBreeze 包含嵌入式 JupyterLab 環境，讓您可以直接在 IDE 中使用 Jupyter 筆記本。

開啟 JupyterLab
----------------

JupyterLab 可從分頁選單中使用。開啟時，它會建立一個新分頁，
透過 Qt 的 Web 引擎呈現完整的 JupyterLab 介面。

首次設定
^^^^^^^^

首次啟動時，如果 JupyterLab 尚未安裝，PyBreeze 會自動使用 pip 安裝。
狀態標籤會顯示初始化進度。

介面
----

JupyterLab 分頁包含：

- **狀態標籤** -- 顯示初始化狀態（「Starting JupyterLab...」、「Ready」等）
- **Web 引擎檢視** -- 在 ``QWebEngineView`` 中呈現的完整 JupyterLab 介面

嵌入式 JupyterLab 提供所有標準 Jupyter 功能：

- 建立和編輯筆記本（``.ipynb`` 檔案）
- 互動式執行 Python 程式碼儲存格
- Markdown 文件儲存格
- 豐富的輸出顯示（圖表、表格、圖片）
- 終端機存取
- 檔案瀏覽器
- 擴充套件支援

運作原理
--------

1. PyBreeze 在背景啟動 ``JupyterLauncherThread``
2. 執行緒啟動 JupyterLab 伺服器程序
3. 伺服器準備就緒後，訊號通知元件
4. ``QWebEngineView`` 載入 JupyterLab URL
5. 您可以像在瀏覽器中一樣與 JupyterLab 互動

.. note::

   JupyterLab 伺服器作為背景程序執行。當您關閉 JupyterLab 分頁或退出
   PyBreeze 時，伺服器會自動停止。

使用提示
--------

- JupyterLab 在本地連接埠上執行；不需要外部網路存取
- 您可以在 JupyterLab 自己的分頁系統中開啟多個筆記本
- 使用 JupyterLab 進行資料分析、原型開發和互動式測試
- 嵌入式 JupyterLab 與 PyBreeze 共用相同的 Python 環境
