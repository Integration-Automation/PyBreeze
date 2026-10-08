7. Header 分析器與 CI 裡的 SARIF
================================

**你會做的事**：在 IDE 裡檢查一個回應的 header 有哪些安全弱點、把結果匯出成 SARIF，
並從命令列執行同樣的檢查，讓 CI 因為這些結果而失敗。

開始之前
--------

:doc:`t01_install_first_launch`。範例是一個回應的狀態列與 header，
就是 ``curl -i`` 或瀏覽器網路面板顯示的樣子。

範例
----

.. literalinclude:: ../../examples/response_headers.txt
   :language: http
   :caption: response_headers.txt

在 IDE 裡
---------

1. 開啟 **Tools > HTTP Header Analyzer Tab** 並貼上範例。
2. 按 **分析標頭**。會列出十項發現，每一項都說明是哪個 header、哪裡有弱點。
3. 按 **將發現匯出為 SARIF** 並存成 ``headers.sarif``。

從命令列
--------

同樣的分析不需要 IDE 也能執行，CI 就是這樣用它：

.. code-block:: bash

   python -m pybreeze.utils.header_tools.header_sarif response_headers.txt -o headers.sarif --fail-on-warning

檔名的位置寫 ``-`` 會讀取標準輸入，所以可以把 header 直接接進來：
``curl -sI https://your.site/ | python -m pybreeze.utils.header_tools.header_sarif - -o headers.sarif``。

預期結果
--------

``headers.sarif`` 是一份 SARIF 2.1.0 記錄，有十個結果。其中兩個是 warning，都和檔案第 4 行的 cookie 有關，
另外八個是 note：

.. code-block:: text

   note     missing_content_type_options  line 1  X-Content-Type-Options: not set, so a browser may MIME-sniff the response.
   note     missing_csp                   line 1  Content-Security-Policy: not set, so nothing limits where scripts may be loaded from.
   note     missing_frame_options         line 1  X-Frame-Options: not set; it (or CSP frame-ancestors) controls who may frame the page.
   note     missing_hsts                  line 1  Strict-Transport-Security: not set, so a browser may fall back to plain HTTP.
   note     missing_referrer_policy       line 1  Referrer-Policy: not set, so full URLs may leak to other sites.
   note     server_banner                 line 3  Server: 'nginx/1.25.3' reveals the software in use.
   note     cookie_no_samesite            line 4  Set-Cookie: cookie 'session' has no SameSite attribute; browsers default it to Lax.
   warning  cookie_not_httponly           line 4  Set-Cookie: cookie 'session' has no HttpOnly attribute, so scripts can read it.
   warning  cookie_not_secure             line 4  Set-Cookie: cookie 'session' has no Secure attribute, so it can travel over plain HTTP.
   note     cors_wildcard_origin          line 5  Access-Control-Allow-Origin: every origin is allowed (*).

這個指令不會印出任何東西，它的 **結束代碼** 就是答案：加上 ``--fail-on-warning`` 時是 ``1``，
因為有 warning；不加這個選項時是 ``0``；檔案讀不到時是 ``2``。

在 CI workflow 裡
-----------------

在 GitHub Actions 上，SARIF 檔會出現在 **Security > Code scanning**，每項發現都標在被檢查檔案的那一行：

.. code-block:: yaml

   - name: Check response headers
     run: |
       python -m pip install pybreeze
       python -m pybreeze.utils.header_tools.header_sarif response_headers.txt -o headers.sarif --fail-on-warning
   - name: Upload the findings
     if: always()
     uses: github/codeql-action/upload-sarif@v3
     with:
       sarif_file: headers.sarif

``if: always()`` 讓前一個步驟失敗時也會上傳結果，而那正是需要它們的時候。
在你自己的 workflow 裡，請把每個 action 固定到某個 commit。

如果不成功
----------

- 沒有任何關於缺少 header 的發現：這段文字被當成請求了。開頭是狀態列（ ``HTTP/1.1 200 OK`` ），
  或含有只有回應才有的 header（ ``Set-Cookie``、 ``Server`` 等）時，才會當成回應。請保留狀態列。
- 帶有憑證的 header（ ``Authorization``、cookie 的值）在 IDE 與 SARIF 檔裡都只以名稱回報。

下一步
------

:doc:`t08_visual_json_editing`
