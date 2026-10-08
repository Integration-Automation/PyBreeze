10. The MCP Client
==================

**You will**: set up a Model Context Protocol server, connect to it, call one of its
tools after being asked, and see the call in the session's log.

Before you start
----------------

:doc:`t01_install_first_launch`. The server is one file from the examples; any MCP
server that is started as a local program works the same way.

The example
-----------

A minimal server: it reads one JSON message a line on its standard input and answers
on its standard output. It offers two tools, ``now`` and ``add``.

.. literalinclude:: ../../examples/mcp_time_server.py
   :language: python
   :caption: mcp_time_server.py

Steps
-----

1. Open **Tools > MCP Client Tab** and press **Add...**.
2. Fill in the server:

   - **Name**: ``time``
   - **Command**, one argument a line, the program first:

     .. code-block:: text

        python
        mcp_time_server.py

   - **Start in**: your project folder (**Browse...**).

   Press **Save**.
3. With ``time`` selected, press **Connect**.
4. On the **Tools** page select ``add``. The server's description and the tool's
   schema are shown, and the arguments start with the ones it requires. Fill them in:

   .. code-block:: json

      {
        "a": 2,
        "b": 3
      }

5. Press **Call**. A question shows the tool, the server and the arguments as they will
   be sent. Answer **Yes**.
6. Open the **Calls** page, then press **Open in Report Viewer**.

Expected result
---------------

- After step 3 the status line reads
  ``Connected to tutorial-time-server 1.0.0: 2 tools, 0 resources, 0 prompts``.
- The question of step 5 reads ``Call add on time?``, says what the server claims of
  the tool (*The server says this tool changes nothing.*), and has **No** as its
  default button. With **Yes**, the result box shows ``5`` and the status line
  ``add answered in 0.00 s`` (your time will differ).
- The **Calls** page has one row: the time, ``add``, *answered*, the seconds. The
  report viewer opens with a run called ``time`` holding that call.
- Call ``add`` again and tick **Do not ask again for add on time** before **Yes**: from
  then on that tool of that server is called without the question, in later sessions
  too. Other tools still ask.

Keys and tokens
---------------

A server that needs a key gets it as an **environment variable**, in the table of the
set-up window, never in the command: the values are shown as dots, kept in
``~/.pybreeze/mcp_servers.json`` (readable by you alone), and taken out of the log, of
error messages and of exported sessions wherever they turn up.

A server that comes with a project
----------------------------------

A ``.mcp.json`` in the project folder is how a project names the servers it uses:

.. code-block:: json

   {
     "mcpServers": {
       "clock": {"command": "python", "args": ["mcp_time_server.py"]}
     }
   }

Such a server is listed as ``clock (from this project)`` and is **not** started by being
found. **Connect** shows its command and asks first; **Edit...** and **Save** make it
one of your own. A project's server with the name of one of yours is not listed: yours
is the one that is used.

If it does not work
-------------------

- *The MCP server could not be started*: the first line of the command must be a
  program on ``PATH`` or a full path. Use the full path of your environment's
  ``python`` if ``python`` alone is not found.
- *The MCP server closed the connection*: the program started and ended. The status
  line ends with its last log line; for the example, a wrong path to
  ``mcp_time_server.py`` in **Command** or **Start in**.
- A call does not come back: press **Cancel**. A server is given the seconds set in
  its profile (30 by default) before the call is given up on.
- Servers reached over HTTP are not supported: only servers started as a local program.

Next
----

:doc:`t11_reports_ci`
