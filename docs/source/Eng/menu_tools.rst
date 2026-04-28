Tools Menu
==========

The **Tools** menu provides access to the SSH client, AI-powered development
tools, and the built-in WYSIWYG architecture-diagram editor. Each tool can be
opened either as a **Tab** (in the main tab widget) or as a **Dock** (a
floating/dockable panel).

SSH
---

SSH Client Tab
^^^^^^^^^^^^^^

Opens an SSH client interface as a new tab. See :doc:`ssh_client` for full details.

SSH Client Dock
^^^^^^^^^^^^^^^

Opens the same SSH client as a dockable widget that can be positioned
around the edges of the main window.

AI Tools
--------

AI Code-Review Tab / Dock
^^^^^^^^^^^^^^^^^^^^^^^^^^

Opens the AI Code Review client, which allows you to send code to an AI API
endpoint for automated code review. See :doc:`ai_tools` for full details.

CoT Prompt Editor Tab / Dock
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Opens the Chain-of-Thought (CoT) Prompt Editor for creating and managing
structured prompt templates. See :doc:`ai_tools` for full details.

Skill Prompt Editor Tab / Dock
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Opens the Skill-based Prompt Editor for creating task-specific prompt templates
(e.g., code review prompts, code explanation prompts). See :doc:`ai_tools` for full details.

Skill Send GUI Tab / Dock
^^^^^^^^^^^^^^^^^^^^^^^^^^

Opens the Skill Prompt Sender interface for sending prompts to an LLM API
and viewing responses. See :doc:`ai_tools` for full details.

Diagram Editor
--------------

Diagram Editor Tab / Dock
^^^^^^^^^^^^^^^^^^^^^^^^^

Opens the built-in WYSIWYG architecture-diagram editor. Use it to sketch
flowcharts and architecture diagrams directly inside PyBreeze without
switching to an external tool.

Drawing tools
"""""""""""""

- **Select** -- pick, move, multi-select with rubber-band
- **Rectangle / Rounded Rectangle / Ellipse / Diamond** -- node shapes
- **Connection** -- connect two nodes with a labelled line
- **Text** -- free-floating text annotation
- **Image (file)** -- insert a local image file
- **Image (URL)** -- download and insert an image from a URL (validated
  against private/loopback IP ranges and capped at 20 MB to prevent SSRF)

File operations
"""""""""""""""

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Action
     - Description
   * - **New**
     - Discards the current diagram (with confirmation if non-empty).
   * - **Open**
     - Loads a previously saved ``.diagram.json`` file.
   * - **Save** / **Save As** (``Ctrl+S`` / ``Ctrl+Shift+S``)
     - Saves the diagram as ``.diagram.json``.
   * - **Import Mermaid**
     - Pastes Mermaid ``flowchart`` / ``graph`` source and converts it to
       editable nodes and edges.
   * - **Export PNG / SVG**
     - Renders the canvas to a raster (PNG) or vector (SVG) image.

Editing helpers
"""""""""""""""

- **Undo / Redo** (``Ctrl+Z`` / ``Ctrl+Y``) -- full undo stack with named
  commands (Add, Move, Delete, Import, etc.)
- **Copy / Paste / Duplicate / Select All** -- standard shortcuts plus
  ``Ctrl+D`` to duplicate selected items
- **Align** -- align selection by left, right, top, bottom, horizontal
  centre, or vertical centre
- **Distribute** -- distribute three or more selected items evenly
  horizontally or vertically
- **Grid** -- toggle background grid rendering
- **Snap** -- snap node positions to grid while dragging
- **Property Panel** (right side) -- edit text, colours, line width,
  shape, and connection style of the selected item
- **Zoom** -- zoom in/out (``Ctrl+=`` / ``Ctrl+-``), reset to 100%
  (``Ctrl+0``), or fit-to-content

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
