AI 工具
=======

PyBreeze 有五個 AI 輔助程式碼審查與提示詞的工具，都可以從 **Tools > AI** 以分頁開啟，或從
**Dock > AI** 以停靠面板開啟。用 prthinker 審查檔案或 Pull Request 則在 **Automation** 選單
（見 :doc:`menu_automation`）。

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 工具
     - 用途
   * - **AI Code Review**
     - 以一次請求把程式碼送到端點審查，再接受或拒絕回答。
   * - **CoT Code Review**
     - 執行八個步驟的思維鏈（CoT）審查：每個步驟一次請求。
   * - **CoT Prompt Editor**
     - 編輯八個 CoT 提示詞。
   * - **Skill Prompt Editor**
     - 編輯兩個技能提示詞（程式碼審查、程式碼解釋）。
   * - **Skill Send**
     - 送出一個放入你程式碼的技能提示詞，並顯示回答。

在 AI Code Review、CoT Code Review 與 Skill Send 中，於面板任何位置按 **Ctrl+Enter** 就會按下送出按鈕。
請求在背景執行，送出按鈕在請求結束前會維持停用。

.. note::

   端點 URL 必須是公開的 ``http`` / ``https`` 位址。送出前會先檢查，而且只連線到檢查過的位址：
   位於本機或私有網路的端點（例如本機的模型伺服器）會被拒絕。不會跟隨重新導向，回答上限為 16 MB，
   超過五分鐘的請求會被中止。只有 AI Code Review 會記錄用過的 URL，而且只記指紋（見下文），
   因為 API URL 可能夾帶權杖。

AI Code Review
--------------

**選單：** Tools > AI > AI Code Review Tab／Dock > AI > AI Code Review Dock

介面佈局
^^^^^^^^

- **URL** -- 端點 URL
- **Method** -- ``GET``、``POST``\ （預設）、``PUT`` 或 ``DELETE``
- **Code to Send**\ （左側）-- 要審查的程式碼
- **Response**\ （右側，唯讀）-- 回答，或沒有回答的原因
- **Send Request** -- 送出請求
- **Accept Response** / **Reject Response** -- 你對回答的評價

使用方式
^^^^^^^^

1. 輸入端點 URL 並選擇方法。``POST`` 與 ``PUT`` 會把程式碼放在本文的表單欄位 ``code``；
   ``GET`` 與 ``DELETE`` 只送 URL。
2. 在左側貼上要審查的程式碼（``POST`` 與 ``PUT`` 必須有內容）。
3. 點擊 **Send Request**。回應區先說明這個 URL 是否用過，回答到達後再顯示回答。
   不是成功的回答（HTTP 錯誤，或不會跟隨的重新導向）會連同狀態碼以錯誤顯示。
4. 點擊 **Accept Response** 或 **Reject Response**。兩者在回答到達後才能按，每個回答只能評一次。

檔案
^^^^

- ``~/.pybreeze/response_stats.txt`` -- 接受與拒絕的累計次數，所有 AI Code Review 面板共用
- ``~/.pybreeze/urls.txt`` -- 用過的 URL 的 SHA-256 指紋：URL 本身從不寫入磁碟

CoT Code Review
---------------

**選單：** Tools > AI > CoT Code Review Tab／Dock > AI > CoT Code Review Dock

介面佈局
^^^^^^^^

- **API URL** -- 端點 URL
- **Code to Review** -- 要審查的程式碼
- **Response Area** -- **Step** 選單（列出已收到回答的步驟），旁邊顯示所選步驟的回答（唯讀）
- **Start Sending** -- 開始審查

審查如何進行
^^^^^^^^^^^^

八個步驟依下列順序執行，因為每一步都可能引用前面步驟的回答：

1. ``first_summary_prompt.md`` -- 程式碼的初步摘要
2. ``first_code_review.md`` -- 初步審查
3. ``judge_single_review.md`` -- 評審這份審查
4. ``linter.md`` -- lint 發現
5. ``code_smell_detector.md`` -- 程式碼異味
6. ``step_by_step_analysis.md`` -- 逐一分析每個 lint 發現與程式碼異味
7. ``total_summary.md`` -- 以上所有內容的總結
8. ``judge.md`` -- 評審這份總結

每一步的提示詞會包上全域審查規則，以 JSON ``{"prompt": "..."}`` 的 ``POST`` 送出，回應本文（文字）
就是該步驟的回答。回答一到就出現在 **Step** 選單並立即顯示。失敗的步驟會顯示原因，之後的步驟不會引用這個失敗。
**Start Sending** 會清掉上一次的回答；關閉面板時，審查會在進行中的請求結束後停止。

提示詞來自 CoT Prompt Editor：編輯過的提示詞會取代內建的。

CoT Prompt Editor
-----------------

**選單：** Tools > AI > CoT Prompt Editor Tab／Dock > AI > CoT Prompt Editor Dock

介面佈局
^^^^^^^^

- **Edit File Content** -- 下方所選提示詞的內容
- 提示詞檔案所在的資料夾 ``~/.pybreeze/prompts/``
- 提示詞選單（每個步驟一項，如上表）
- **Reload** -- 從磁碟重新讀取檔案
- **Save** -- 把內容寫入檔案
- **Create File** -- 以內建提示詞建立檔案

提示詞如何保存
^^^^^^^^^^^^^^

每個提示詞都有內建版本。``~/.pybreeze/prompts/`` 中同名的檔案只要有內容就會取代它，
所以審查送出的是你存下的內容。檔案建立之前，編輯區是空的並會註明；**Create File** 會把內建提示詞寫進檔案，
當作起點。

提示詞中的佔位符（例如 ``{code_diff}``）會在審查執行時填入。編輯過的提示詞若用了該步驟填不了的佔位符，
那一次會改用內建提示詞。

檔案會被監看：在編輯器外的修改會立刻出現。只要換上另一份內容會失去沒存的編輯——選另一個提示詞、
**Reload**、**Create File**、外部修改，或關閉分頁、停靠面板或 IDE——編輯器都會先詢問，預設為 **No**。
不是 UTF-8 的檔案會把讀不出的部分替換後顯示並告知；存檔時會寫回 UTF-8。

Skill Prompt Editor
-------------------

**選單：** Tools > AI > Skill Prompt Editor Tab／Dock > AI > Skill Prompt Editor Dock

與 CoT Prompt Editor 相同的編輯器，用於兩個技能提示詞：``code_review_skill.md``\ （程式碼審查）與
``code_explainer_skill.md``\ （程式碼解釋）。檔案放在同一個資料夾，運作方式也相同。

Skill Send
----------

**選單：** Tools > AI > Skill Send Tab／Dock > AI > Skill Send Dock

介面佈局
^^^^^^^^

- **LLM API URL** -- 端點 URL
- **Select Prompt Template** -- 作為起點的技能提示詞
- **Prompt** -- 要送出的提示詞，可編輯
- **Send** -- 送出
- **Response**\ （唯讀）-- 回答，或沒有回答的原因

使用方式
^^^^^^^^

1. 輸入端點 URL。
2. 選擇範本。它的內容（有編輯過的檔案就用檔案，否則用內建提示詞）會填入 **Prompt**。
   編輯過提示詞後再選另一個範本時會先詢問。
3. 把提示詞中的 ``{code_diff}`` 換成你的程式碼。提示詞裡還有 ``{code_diff}`` 時不會送出。
4. 點擊 **Send**。提示詞以 JSON ``{"code": "..."}`` 的 ``POST`` 送出，回應本文原樣顯示。
   被拒絕的請求（401、403）與伺服器錯誤會以錯誤顯示；重新導向不會被跟隨，並說明它指向哪裡
   （只列出 scheme 與主機）。
