Tools Menu
==========

The **Tools** menu opens the SSH client, the AI tools, the built-in WYSIWYG
architecture-diagram editor and the HTTP / API utilities, each as a **Tab** in the
main tab widget. Each of them also opens as a **Dock** (a floating or dockable
panel) from the **Dock** menu:

.. list-table::
   :header-rows: 1
   :widths: 25 40 35

   * - Tool
     - Tab
     - Dock
   * - SSH client
     - **Tools > SSH > SSH Client Tab**
     - **Dock > SSH > SSH Client Dock**
   * - AI tools
     - **Tools > AI >** *<tool>* **Tab**
     - **Dock > AI >** *<tool>* **Dock**
   * - Diagram editor
     - **Tools > Diagram Editor Tab**
     - **Dock > Diagram Editor Dock**
   * - HTTP / API utilities
     - **Tools >** *<tool>* **Tab**
     - **Dock >** *<tool>* **Dock**

SSH
---

**SSH Client Tab** opens an SSH client (a terminal and an SFTP file tree) as a new tab;
**SSH Client Dock** opens the same client as a dockable panel. See :doc:`ssh_client`
for full details.

AI Tools
--------

The **AI** submenus of **Tools** and **Dock** hold five tools. See :doc:`ai_tools` for full
details.

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Tool
     - Description
   * - **AI Code Review**
     - Sends code to an LLM endpoint for review, then accept or reject the suggestion.
   * - **CoT Prompt Editor**
     - Edits the Chain-of-Thought (CoT) review prompt templates.
   * - **CoT Code Review**
     - Runs the CoT review: each step's prompt goes to the endpoint in turn.
   * - **Skill Prompt Editor**
     - Edits the task-specific (skill) prompt templates, such as code review or code
       explanation.
   * - **Skill Send**
     - Sends a skill prompt, with your code, to an LLM endpoint and shows the answer.

HTTP and API Utilities
----------------------

Thirteen tools, each opened from **Tools** as a tab or from **Dock** as a dock. None of
them sends a request: they parse, convert and generate text. In a tool with one main
button, **Ctrl+Enter** anywhere in it presses that button (its text boxes take Enter as a
new line); in Query / JSON and the URL parser / builder, which convert both ways, it goes
the way the input reads: from JSON when the input is a JSON object.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tool
     - Description
   * - **cURL Import**
     - Turns a ``curl`` command copied from a browser's dev tools into a Python
       ``requests`` script, a pytest test, APITestka (Python or a JSON action list) or a
       LoadDensity Locust load test.
   * - **HAR Import**
     - Lists the requests in a browser's HAR export and turns the ones selected into one
       test script, with the same targets as cURL Import.
   * - **JWT Decoder**
     - Shows a token's header and payload, with its time claims in UTC. The signature is
       never verified.
   * - **Timestamp Converter**
     - Takes a Unix epoch (seconds to nanoseconds) or an ISO-8601 date-time and gives
       every representation in UTC.
   * - **Hash Generator**
     - SHA-256, SHA-512, SHA-1 and MD5 of the text at once.
   * - **Query / JSON**
     - ``application/x-www-form-urlencoded`` to JSON and back.
   * - **URL Parser / Builder**
     - A URL as an editable JSON object of its parts, and back again.
   * - **Regex Tester**
     - Every match with its offsets and groups, with the ``IGNORECASE``, ``MULTILINE``,
       ``DOTALL`` and ``VERBOSE`` flags.
   * - **HTTP Status Reference**
     - The status code table, searched by code or keyword.
   * - **Text Diff**
     - A unified diff of two texts, with an added / removed summary.
   * - **JSON Format**
     - Pretty-prints or minifies JSON.
   * - **HTTP Header Analyzer**
     - Reports repeated headers, cookie flags, CORS, HSTS and CSP weaknesses, and missing
       security headers. Headers carrying credentials are reported by name only.
   * - **Response Inspector**
     - Reads a pasted HTTP response: status, headers, a JSON body and any JWT in it, each
       one a click away from its own tool.

Diagram Editor
--------------

**Diagram Editor Tab** / **Diagram Editor Dock** open the built-in WYSIWYG
architecture-diagram editor. Use it to sketch flowcharts and architecture diagrams
directly inside PyBreeze without switching to an external tool. Its keyboard shortcuts
apply only while it has the focus, so as a dock it leaves the code editor's own alone.

Drawing tools
"""""""""""""

The toolbar's first row:

- **Select** -- click to select, drag to move, drag on the empty canvas to select with a
  rubber band
- **Rect** / **Rounded** / **Ellipse** / **Diamond** -- click the canvas to place a node
  of that shape; the tool then goes back to **Select**
- **Connect** -- click the source node, then the target node; a click on the empty canvas
  or **Esc** cancels
- **Text** -- click the canvas to place a text node
- **Image** -- insert a local image file
- **URL Image** -- download and insert an image from an ``http`` / ``https`` URL. The
  address is checked (private, loopback and other non-public addresses are refused), the
  connection goes only to the address checked, and the download is capped at 20 MB and
  120 seconds; it runs in the background, so a slow host does not hold the IDE.

Double-click a node to edit its text; the edit is one undo step.

File operations
"""""""""""""""

The second row starts with the file buttons:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Button
     - Description
   * - **New**
     - Clears the canvas, asking first when anything is on it.
   * - **Open**
     - Loads a previously saved ``.diagram.json`` file, asking first when the diagram
       has changes that are not saved. A file that is not a diagram changes nothing.
   * - **Save** (``Ctrl+S``)
     - Saves to the file last opened or saved; the first time, it asks where, as
       **Save As** does.
   * - **Save As** (``Ctrl+Shift+S``)
     - Saves the diagram as a new ``.diagram.json`` file.
   * - **Import**
     - Pastes Mermaid ``flowchart`` / ``graph`` source and converts it to editable,
       automatically laid out nodes and connections. It replaces the canvas as one undo
       step.
   * - **PNG** / **SVG**
     - Exports the canvas to a raster (PNG) or vector (SVG) image.

Images in a saved diagram come back from where they were: a local path only if it is an
image file on this machine, and a URL through the same checks as **URL Image**.

Closing the tab, the dock or the IDE with unsaved changes asks first as well.

Editing helpers
"""""""""""""""

- **Undo** / **Redo** (``Ctrl+Z`` / ``Ctrl+Y``) -- every change is one step
- **Delete** (or **Backspace**) removes the selection; ``Ctrl+C`` / ``Ctrl+V`` copy and
  paste it, ``Ctrl+D`` duplicates it and ``Ctrl+A`` selects everything
- **Right-click** an item for **Delete**, **Duplicate** (nodes), **Bring to Front** and
  **Send to Back**; the empty canvas for **Paste** (once something is copied) and
  **Select All**
- **Align** -- **Align Left**, **Align Right**, **Align Top**, **Align Bottom**,
  **Center Horizontal** and **Center Vertical** for the selected nodes, and
  **Distribute Horizontal** / **Distribute Vertical** for three or more
- **Grid** -- shows the background grid
- **Snap** -- snaps nodes to the grid while dragging
- **Properties** panel (right side) -- the selected node's text, width, height, shape,
  fill, border and font size; a connection's label, style (solid, dashed, dotted),
  colour and width; an image's caption, width and height, and its source (read only)
- **Zoom** -- the mouse wheel, the **-** and **+** buttons or ``Ctrl+-`` / ``Ctrl+=``;
  ``Ctrl+0`` resets to 100% and **Fit** shows the whole diagram. Drag with the right or
  middle mouse button to pan.

Tab vs. Dock
------------

- **Tab**: Opens as a new tab alongside your code editor tabs. Best when you want
  to focus on a single tool at a time.
- **Dock**: Opens as a floating or snapped panel. Best when you want to see the
  tool alongside your code editor. Dock widgets can be:

  - Dragged to any edge of the main window
  - Resized freely
  - Floated as independent windows
  - Stacked with other dock widgets
