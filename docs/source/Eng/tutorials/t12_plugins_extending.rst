12. Plugins and Extending the IDE
=================================

**You will**: add a tab of your own to PyBreeze, and load a plugin that colours a kind
of file the editor does not know.

Before you start
----------------

:doc:`t01_install_first_launch`. Both examples are in ``docs/source/examples/``.

A tab of your own
-----------------

A tab is any ``QWidget``. It is registered before the editor starts.

.. literalinclude:: ../../examples/hello_tab.py
   :language: python
   :caption: hello_tab.py

Run it from the project folder, in place of ``python -m pybreeze``:

.. code-block:: bash

   python hello_tab.py

**Expected result**: PyBreeze starts with one more tab, **Hello**, beside the editor.
Type a name, press **Greet**, and the tab greets you. A widget whose constructor raises
costs only its own tab: the IDE starts without it and the error is in the log.

A plugin
--------

A plugin is a ``.py`` file in a folder called ``jeditor_plugins`` inside the folder
PyBreeze is started in. It is loaded once, as the IDE starts.

.. literalinclude:: ../../examples/jeditor_plugins/todo_notes.py
   :language: python
   :caption: jeditor_plugins/todo_notes.py

1. Copy ``jeditor_plugins/`` from the examples into your project folder.
2. Restart PyBreeze.
3. Make a file ``notes.todo`` in the project and type:

   .. code-block:: text

      # this week
      TODO write the report
      DONE install PyBreeze

**Expected result**: ``TODO`` and ``DONE`` are coloured as keywords and the first line as
a comment. **Plugins > Plugin Browser** lists what else can be installed.

To also **run** a kind of file, a plugin gives a ``PLUGIN_RUN_CONFIG`` (the program to
start and its arguments); it then appears under **Run with...**. See :doc:`../menu_plugins`
for the keys, and :doc:`../how_to_extend_ui` for a tab that asks before it closes.

Adding a tool to PyBreeze itself
--------------------------------

For a change to PyBreeze's own source, a tool is one line in a table. The widget goes in
``pybreeze/pybreeze_ui/tools_gui/``, its logic (no Qt) in ``pybreeze/utils/``, and:

.. code-block:: python

   # pybreeze/pybreeze_ui/menu/tools/tools_menu.py
   _tool("MyTool", "my_tool", lambda win: MyToolGUI(win)),

The Tools menu, the Dock menu and the navigation panel are built from that table. The
four words of the entry (``extend_tools_menu_my_tool_tab_action`` and its three
siblings) go in both dictionaries under ``pybreeze/extend_multi_language/``; the tests
fail on a key that is in one and not the other. ``architecture.md`` §5 lists the other
extension points: an import target, a report format, a framework for the language
service, an MCP transport.

If it does not work
-------------------

- The plugin is not loaded: the folder must be called ``jeditor_plugins`` and be in the
  folder PyBreeze was **started** in; files whose name starts with ``_`` or ``.`` are
  skipped; plugins are read at start-up only.
- The colours do not show: the editor colours C, C++, Go, Java and Rust itself, and a
  plugin's keywords are used only for a suffix it does not colour.

Next
----

:doc:`t13_troubleshooting`
