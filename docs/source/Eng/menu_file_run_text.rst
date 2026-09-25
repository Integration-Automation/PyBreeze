File, Run, Text & Other Base Menus
===================================

These menus come from the JEditor editor engine PyBreeze is built on. Almost every entry
acts on the editor tab in front, and does nothing when the tab in front is not an editor.

JEditor keeps these settings in ``.jeditor/user_setting.json`` in the working folder, so
each project folder has its own; they are saved every minute and when the IDE closes. An
editor tab that has a file is also saved to it every few seconds.

File Menu
---------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Menu Item
     - Description
   * - **New File**
     - Asks for a name and a place, and creates an empty file there (it is not opened).
   * - **Open File**
     - Opens a file into the editor tab in front, replacing what it shows.
   * - **Open Folder**
     - Makes a folder the working folder: the file tree shows it, and its settings are
       loaded (see :doc:`getting_started`).
   * - **Save File**
     - Opens a **Save As** dialog, starting in the working folder, and writes the tab there.
   * - **Recent Files**
     - The last files opened; one opens in a new tab. The list is rebuilt at start-up.
   * - **Font** / **Font Size**
     - The font and size of the whole window: menus, trees and panels.
   * - **Encodings**
     - The encoding of the tab's file. The file is read again in it when the tab has no
       unsaved edits, and the next save writes it.
   * - **Line Endings**
     - ``LF``, ``CRLF`` or ``CR`` for the next save of the tab's file.
   * - **Save All**
     - Writes every editor tab that has a file.

Run Menu
--------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Menu Item
     - Description
   * - **Run Program > Run Program**
     - Opens a **Save As** dialog, writes the tab, then runs the file with Python; the
       output goes to the tab's **Code result**. One program at a time per tab.
   * - **Run Program > Show program input**
     - A small window whose line is sent to the running program's standard input.
   * - **Run On Shell > Run On Shell**
     - Runs the tab's text, as it is, as one shell command (``cmd.exe`` on Windows); the
       output goes to **Code result**.
   * - **Run On Shell > Show shell input**
     - The same input window, for the shell.
   * - **Debugger > Run Debugger**
     - Opens a **Save As** dialog, then runs the file under ``pdb`` with the breakpoints set
       in the editor's gutter, output in the **Debugger** tab and the input window open.
       With JEditor 1.0.27 it runs once per editor tab: to debug again, open the file in
       another tab.
   * - **Debugger > Show debugger input**
     - Opens the debugger's input window again.
   * - **Clean Result**
     - Empties the tab's **Code result**.
   * - **Stop current program**
     - Stops the tab's program, shell command and debugger.
   * - **Stop All Program**
     - Stops every program, shell command, debugger and ``pip`` run started from these
       menus, in any tab. PyBreeze's own runs have their run window's **Stop** button.
   * - **Run Help > Run Help** / **Shell Help**
     - Tips: check the interpreter, and match the encoding to the shell's.
   * - **Run with...**
     - Only when a plugin has registered a run configuration (see :doc:`menu_plugins`).

Run Program, Run Debugger, the **Python Env** entries and PyBreeze's automation runs use
the interpreter chosen under **Python Env > Choose python interpreter**. With none chosen,
Run Program and Run Debugger use a ``venv/`` in the working folder, else Python on
``PATH``; PyBreeze's automation runs and JupyterLab use a ``venv/`` or ``.venv/`` there,
else the Python PyBreeze runs on. Run On Shell uses no interpreter.

Text Menu
---------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Menu Item
     - Description
   * - **Font** / **Font Size**
     - The font and size of the editors and their **Code result**, in every editor tab.
   * - **Word Wrap**
     - Wraps long lines in every editor tab (off again at the next start).
   * - **Indent Size**
     - 2, 4 or 8 spaces: the tab width and indent unit. A file's own indentation wins.
   * - **Trim Trailing Whitespace**, **Convert Indentation to Spaces** / **to Tabs**
     - The whole document.
   * - **Remove Duplicate Lines**, **Reverse Lines**, **Sort Lines (Natural)**,
       **Remove Blank Lines**, **Align by Delimiter...**
     - The lines the selection covers, at least two. **Align by Delimiter...** asks for the
       delimiter (``=`` by default).
   * - **Uppercase Selection**, **Lowercase Selection**, **Swap Case**, **Title Case**,
       **Naming Style**, **Number Base**, **Encode / Decode**
     - The selected text; nothing happens without a selection, or when it cannot be
       converted. **Naming Style** gives ``snake_case``, ``camelCase``, ``PascalCase`` or
       ``kebab-case``; **Number Base** hexadecimal, decimal or binary; **Encode / Decode**
       Base64, URL, HTML and JSON string escaping both ways.
   * - **Statistics**
     - Lines, words, characters and characters without spaces, of the selection or the
       whole document.

Check Code Style Menu
---------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Menu Item
     - Description
   * - **yapf**
     - Reformats the whole tab with ``yapf`` (Google style); nothing changes on a syntax
       error.
   * - **Reformat JSON**
     - Rewrites the tab as JSON with a 4-space indent and sorted keys; an error is shown in
       **Code result**.
   * - **Python format check**
     - Runs ``pycodestyle`` on the saved ``.py`` file (unsaved edits are not checked) and
       lists what it found in the **Format checker** tab.
   * - **Format on Save**
     - On or off: ``.py`` files are reformatted with ``yapf`` as **Save File**, **Save All**
       and **Run Program** write them. The automatic save does not format.

Python Env Menu
---------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Menu Item
     - Description
   * - **Create venv**
     - Runs ``python -m venv venv`` in the working folder, with the chosen interpreter or
       Python on ``PATH``; the output goes to **Code result**.
   * - **pip upgrade package** / **pip package**
     - Ask for a package name and run ``pip install`` (``-U`` to upgrade) with the chosen
       interpreter, or the one in ``venv/``. They need a ``venv/`` in the working folder.
   * - **Choose python interpreter**
     - Picks the interpreter file. It is saved, and used as described under **Run Menu**
       above; the **Install** menu installs into it too.

Tab and Dock Menus
------------------

**Tab** opens a panel as a tab, **Dock** as a dock (see :doc:`ui_overview`):

- **Add Editor Tab**, **Add Web Browser Tab**, and a docked editor (**Dock > Editor >
  New Dock Editor**, which writes its file back when the dock closes)
- **Console Widget** -- an interactive shell (``cmd``, PowerShell, ``bash`` or ``sh``)
- **Toggle Split View** (the same document twice) and **Toggle Minimap**, for the tab in
  front
- **Snippet Editor** -- the snippets in ``.jeditor/snippets.json``
- **Tools Tab** -- IPython (Jupyter, inside the IDE's own Python), the variable inspector,
  FrontEngine, ChatUI, the TODO panel, the outline of the current Python file, and
  JupyterLab (see :doc:`jupyter_lab`)
- **Git Tab** -- the Git client, the branch tree viewer, the code diff viewer, and the
  current file's diff against ``HEAD`` or the staged version
- **Dock > Tools** also has **Problems** (``ruff`` findings) and **Tests** (``pytest`` in
  the working folder)

UI Style Menu
-------------

The Qt Material themes (see :doc:`ui_overview`): clicking one applies it at once, and it
is saved for the next start. **Show Indent Guides** and **Show Trailing Whitespace** turn
those marks in the editors on and off, and **Keyboard Shortcuts...** rebinds the editor's
commands.
