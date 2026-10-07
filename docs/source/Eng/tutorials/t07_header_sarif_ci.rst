7. Header Analyzer to SARIF in CI
=================================

**You will**: check a response's headers for security weaknesses in the IDE, export the
findings as SARIF, and run the same check from a command line so that CI fails on them.

Before you start
----------------

:doc:`t01_install_first_launch`. The example is a response's status line and headers,
as ``curl -i`` or a browser's network panel shows them.

The example
-----------

.. literalinclude:: ../../examples/response_headers.txt
   :language: http
   :caption: response_headers.txt

In the IDE
----------

1. Open **Tools > HTTP Header Analyzer Tab** and paste the example.
2. Press **Analyze headers**. Ten findings are listed, each naming the header and what
   is weak about it.
3. Press **Export findings as SARIF** and save ``headers.sarif``.

From the command line
---------------------

The same analysis runs without the IDE, which is how CI uses it:

.. code-block:: bash

   python -m pybreeze.utils.header_tools.header_sarif response_headers.txt -o headers.sarif --fail-on-warning

``-`` in place of the file reads standard input, so the headers can be piped in:
``curl -sI https://your.site/ | python -m pybreeze.utils.header_tools.header_sarif - -o headers.sarif``.

Expected result
---------------

``headers.sarif`` is a SARIF 2.1.0 log with ten results. Two are warnings, both about
the cookie on line 4 of the file, and eight are notes:

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

The command prints nothing and its **exit code** is the answer: ``1`` with
``--fail-on-warning``, because there are warnings; ``0`` without the option; ``2`` when
the file cannot be read.

In a CI workflow
----------------

On GitHub Actions, the SARIF file shows up under **Security > Code scanning**, each
finding on its line of the checked file:

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

``if: always()`` uploads the findings also when the step before it failed, which is
when they are wanted. In a workflow of your own, pin each action to a commit.

If it does not work
-------------------

- No finding about a missing header: the block was read as a request. It is read as a
  response when it starts with a status line (``HTTP/1.1 200 OK``) or has a header only
  a response has (``Set-Cookie``, ``Server``, ...). Keep the status line.
- A header that carries credentials (``Authorization``, a cookie's value) is reported
  by name only, in the IDE and in the SARIF file.

Next
----

:doc:`t08_visual_json_editing`
