Tools 選單
==========

**Tools** 選單以 **分頁**\ （在主分頁元件中）開啟 SSH 用戶端、AI 工具、內建的 WYSIWYG 架構圖編輯器，
以及 HTTP / API 小工具。每一個也都能從 **Dock** 選單以 **停靠面板**\ （浮動/可停靠面板）開啟：

.. list-table::
   :header-rows: 1
   :widths: 25 40 35

   * - 工具
     - 分頁
     - 停靠面板
   * - SSH 用戶端
     - **Tools > SSH > SSH Client Tab**
     - **Dock > SSH > SSH Client Dock**
   * - AI 工具
     - **Tools > AI >** *<工具>* **Tab**
     - **Dock > AI >** *<工具>* **Dock**
   * - 架構圖編輯器
     - **Tools > Diagram Editor Tab**
     - **Dock > Diagram Editor Dock**
   * - HTTP / API 小工具
     - **Tools >** *<工具>* **Tab**
     - **Dock >** *<工具>* **Dock**

SSH
---

**SSH Client Tab** 以新分頁開啟 SSH 用戶端（終端機與 SFTP 檔案樹）；**SSH Client Dock**
以可停靠面板開啟同一個用戶端。詳細資訊請參閱 :doc:`ssh_client`。

AI 工具
-------

**Tools** 與 **Dock** 的 **AI** 子選單各有五個工具。詳細資訊請參閱 :doc:`ai_tools`。

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - 工具
     - 說明
   * - **AI Code Review**
     - 把程式碼送到 LLM 端點審查，再接受或拒絕它的建議。
   * - **CoT Prompt Editor**
     - 編輯思維鏈（CoT）審查的提示詞範本。
   * - **CoT Code Review**
     - 執行 CoT 審查：每一步的提示詞依序送到端點。
   * - **Skill Prompt Editor**
     - 編輯特定任務（技能）的提示詞範本，例如程式碼審查或程式碼解釋。
   * - **Skill Send**
     - 把技能提示詞連同你的程式碼送到 LLM 端點，並顯示回答。

HTTP 與 API 小工具
------------------

共十三個工具，都可以從 **Tools** 以分頁、或從 **Dock** 以停靠面板開啟。它們都不會送出請求，
只做解析、轉換與產生文字。在只有一個主要按鈕的工具裡，於任何位置按 **Ctrl+Enter** 就會按下那個按鈕
（文字框裡的 Enter 是換行）；Query / JSON 與 URL 解析／組建器可以雙向轉換，Ctrl+Enter 依輸入的內容決定方向：
輸入是 JSON 物件時從 JSON 轉回。

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 工具
     - 說明
   * - **cURL Import**
     - 把從瀏覽器開發者工具複製的 ``curl`` 指令轉成 Python ``requests`` 腳本、pytest 測試、
       APITestka（Python 或 JSON 動作清單），或 LoadDensity 的 Locust 負載測試。
   * - **HAR Import**
     - 列出瀏覽器 HAR 匯出檔裡的請求，把選取的請求轉成一份測試腳本，目標格式與 cURL Import 相同。
   * - **JWT Decoder**
     - 顯示權杖的 header 與 payload，時間欄位以 UTC 呈現。不會驗證簽章。
   * - **Timestamp Converter**
     - 輸入 Unix epoch（秒到奈秒）或 ISO-8601 日期時間，輸出所有 UTC 表示法。
   * - **Hash Generator**
     - 同時算出文字的 SHA-256、SHA-512、SHA-1 與 MD5。
   * - **Query / JSON**
     - ``application/x-www-form-urlencoded`` 與 JSON 互轉。
   * - **URL Parser / Builder**
     - 把 URL 拆成可編輯的 JSON 物件，也能組回 URL。
   * - **Regex Tester**
     - 列出每個符合項目的位置與群組，可用 ``IGNORECASE``、``MULTILINE``、``DOTALL``、
       ``VERBOSE`` 旗標。
   * - **HTTP Status Reference**
     - 以狀態碼或關鍵字搜尋狀態碼表。
   * - **Text Diff**
     - 兩段文字的 unified diff，附新增／刪除行數摘要。
   * - **JSON Format**
     - 美化或壓縮 JSON。
   * - **HTTP Header Analyzer**
     - 找出重複的標頭、Cookie 旗標、CORS、HSTS 與 CSP 的弱點，以及缺少的安全標頭。
       帶有憑證的標頭只列出名稱。
   * - **Response Inspector**
     - 解讀貼上的 HTTP 回應：狀態碼、標頭、JSON 本文與其中的 JWT，每一項都能一鍵在對應的工具中開啟。

架構圖編輯器
------------

**Diagram Editor Tab** / **Diagram Editor Dock** 開啟內建的 WYSIWYG 架構圖編輯器，
可直接在 PyBreeze 中繪製流程圖與架構圖，不需要切換到外部工具。它的快捷鍵只在它取得焦點時作用，
所以作為停靠面板時不會搶走程式碼編輯器自己的快捷鍵。

繪圖工具
""""""""

工具列的第一列：

- **Select** -- 點選以選取、拖曳以搬移，在空白畫布上拖曳可用橡皮筋框選
- **Rect** / **Rounded** / **Ellipse** / **Diamond** -- 點擊畫布放置該形狀的節點，之後工具回到 **Select**
- **Connect** -- 先點來源節點，再點目標節點；點空白畫布或按 **Esc** 取消
- **Text** -- 點擊畫布放置文字節點
- **Image** -- 插入本機圖片檔
- **URL Image** -- 從 ``http`` / ``https`` URL 下載並插入圖片。會檢查位址（拒絕私有、loopback
  等非公開位址），只連線到檢查過的位址，下載上限為 20 MB 與 120 秒；在背景執行，主機回應慢也不會卡住 IDE。

雙擊節點可編輯它的文字；一次編輯是一個復原步驟。

檔案操作
""""""""

第二列開頭是檔案按鈕：

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - 按鈕
     - 說明
   * - **New**
     - 清空畫布；有沒存的變更時會先詢問。
   * - **Open**
     - 載入先前儲存的 ``.diagram.json`` 檔案；目前的架構圖有沒存的變更時會先詢問。
       不是架構圖的檔案不會改動任何東西。
   * - **Save**\ （``Ctrl+S``）
     - 儲存到上次開啟或儲存的檔案；第一次儲存時會像 **Save As** 一樣詢問位置。
   * - **Save As**\ （``Ctrl+Shift+S``）
     - 另存為新的 ``.diagram.json`` 檔案。
   * - **Import**
     - 貼上 Mermaid ``flowchart`` / ``graph`` 原始碼，轉換為自動排版、可編輯的節點與連線。
       標籤照 Mermaid 的顯示方式讀：``<br>`` 換行，實體碼（``#quot;``、``#9829;``）換成它代表的字元。
       Mermaid 11 的具名形狀（``A@{ shape: circle }``）會換成四種節點形狀中最接近的一種。
       它會取代整個畫布，並算作一個復原步驟。
   * - **PNG** / **SVG**
     - 將畫布輸出為點陣圖（PNG）或向量圖（SVG）。

已儲存架構圖裡的圖片會從原處載回：本機路徑只接受這台電腦上的圖片檔，URL 則經過與 **URL Image** 相同的檢查。

有沒存的變更時，關閉分頁、停靠面板或 IDE 也都會先詢問。

編輯輔助
""""""""

- **Undo** / **Redo**\ （``Ctrl+Z`` / ``Ctrl+Y``）-- 每個變更都是一個步驟
- **Delete**\ （或 **Backspace**）刪除選取項目；``Ctrl+C`` / ``Ctrl+V`` 複製與貼上，
  ``Ctrl+D`` 複製一份，``Ctrl+A`` 全選
- 在項目上 **按右鍵** 有 **Delete**、**Duplicate**\ （節點）、**Bring to Front**、**Send to Back**；
  在空白畫布上有 **Paste**\ （複製過東西之後）與 **Select All**
- **Align** -- 對選取的節點做 **Align Left**、**Align Right**、**Align Top**、**Align Bottom**、
  **Center Horizontal**、**Center Vertical**；選取三個以上時可 **Distribute Horizontal** /
  **Distribute Vertical**
- **Grid** -- 顯示背景格線
- **Snap** -- 拖曳節點時對齊格線
- **Properties** 面板（右側）-- 選取節點的文字、寬、高、形狀、填色、框線與字級；連線的標籤、
  樣式（實線、虛線、點線）、顏色與寬度；圖片的說明、寬、高，以及它的來源（唯讀）
- **縮放** -- 滑鼠滾輪、**-** 與 **+** 按鈕，或 ``Ctrl+-`` / ``Ctrl+=``；``Ctrl+0`` 回到 100%，
  **Fit** 顯示整張圖。按住滑鼠右鍵或中鍵拖曳可平移。

分頁 vs. 停靠面板
------------------

- **分頁**：作為新分頁開啟，與程式碼編輯器的分頁並列。適合一次專注於單一工具。
- **停靠面板**：作為浮動或固定的面板開啟。適合在編輯程式碼的同時查看工具。
  停靠面板可以：

  - 拖曳到主視窗的任何邊緣
  - 自由調整大小
  - 作為獨立視窗浮動
  - 與其他停靠面板堆疊
