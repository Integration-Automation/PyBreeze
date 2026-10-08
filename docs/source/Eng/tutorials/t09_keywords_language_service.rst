9. Keywords and the Language Service
====================================

**You will**: have the editor complete an action script and point out its mistakes
before it is run, and look a keyword up.

Before you start
----------------

:doc:`t01_install_first_launch`. The example is a WebRunner script with two mistakes
in it.

The example
-----------

.. literalinclude:: ../../examples/broken_actions.json
   :language: json
   :caption: broken_actions.json

Steps
-----

1. Open ``broken_actions.json`` in the editor. Two lines are marked.
2. Put the cursor on a marked line: the editor's tooltip says what is wrong there.
3. Fix line 3: delete ``WR_to_urll`` between its quotes and type ``WR_to``. As you type,
   the keywords that start so are offered; take ``WR_to_url``.
4. Fix line 4: inside the braces, delete ``urls`` between its quotes and start typing.
   The parameters of ``WR_to_url`` that are not given yet are offered: ``url``.
5. Right-click a keyword and choose **Describe Symbol** to read its signature and
   documentation, or **Go to Definition** to open the line of WebRunner that defines it.
6. Open **Tools > Automation Keywords Tab**. Choose **WebRunner**, type ``cookie`` in
   the filter, select ``WR_add_cookie`` and press **Copy as Action**.

Expected result
---------------

Step 1 marks these three problems:

.. code-block:: text

   line 3  WR_to_urll is not a keyword of WebRunner 0.0.66. Did you mean WR_to_url?
   line 4  WR_to_url has no parameter named urls. Did you mean url?
   line 4  WR_to_url needs url

with your installed version in place of ``0.0.66``. After steps 3 and 4 no line is
marked. Step 6 puts ``["WR_add_cookie", {"cookie_dict": null}]`` on the clipboard, and
the tab's status line reads, for example,
``WebRunner 0.0.66: 83 keywords. In a .json script the editor offers completion ·
diagnostics · hover · go to definition``.

Where the keywords come from
----------------------------

Nothing about a keyword is kept in PyBreeze. Each framework is asked, in a process of
its own, by the interpreter that runs your scripts, so what is offered is what the
installed version has. The same service answers for AutoControl (``AC_...``) and
LoadDensity (``LD_...``) scripts, and any editor that speaks the Language Server
Protocol can start it:

.. code-block:: bash

   python -m pybreeze.extend.language_server --help

**Expected result**: the usage text, with ``--interpreter`` (the Python whose installed
frameworks are asked) and ``--language`` (the language of the messages).

If it does not work
-------------------

- Nothing is marked and nothing is completed: the file must have a ``.json`` name, and
  PyBreeze must be restarted after a framework is installed. **Automation Keywords**
  says, for each framework, its version or why it gives no keywords.
- A JSON file that is not an action script is only told whether it is JSON.
- The interpreter was changed under **Python Env** after PyBreeze started: the
  Automation Keywords tab follows at once, the editor after a restart.
- A packaged build (an executable, not ``python -m pybreeze``) has no language server.

Next
----

:doc:`t10_mcp_client`
