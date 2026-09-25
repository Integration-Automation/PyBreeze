Plugins Menu
============

PyBreeze uses JEditor's plugin system. Plugins are loaded at start-up from the
``jeditor_plugins/`` folder in the working directory (and, for a development checkout of
JEditor, the one beside its package):

- a ``.py`` file is a plugin, and so is a folder with an ``__init__.py``;
- a folder without ``__init__.py`` only groups plugins, and is searched inside;
- names that start with ``_`` or ``.`` are skipped.

Each plugin defines a ``register()`` function, called once as it loads. It may also set
``PLUGIN_NAME``, ``PLUGIN_AUTHOR``, ``PLUGIN_VERSION`` and ``PLUGIN_RUN_CONFIG``.

Plugin Browser
--------------

**Plugins > Plugin Browser** opens a tab that lists the plugins in a GitHub repository
(``https://github.com/Jeffrey-Plugin-Repos/IDE_Plugins`` by default; any
``https://github.com/owner/repo`` or ``owner/repo`` can be entered in **Repository URL**
and read with **Fetch Plugins**). Select a plugin to see its details and source, then
**Download & Install** saves it into ``jeditor_plugins/`` in the working directory, asking
before it replaces a plugin of the same name. An installed plugin loads at the next start.

The entry is there before any plugin is installed.

Loaded Plugins
--------------

Below the Plugin Browser, each loaded plugin has an entry:

- a plugin without a run configuration (a translation, a syntax plugin): its name, which
  shows its name, version and author;
- a plugin with a run configuration: a submenu named after the configuration, with
  **About** and **Run with** *<name>* (the suffixes it runs are listed in the label when
  there are several).

Run with... Menu
----------------

The **Run** menu has a **Run with...** submenu once a plugin has registered a run
configuration: one entry per configuration, labelled with its name and suffixes. It runs
the file in the editor tab in front:

1. The tab is saved first, in its own encoding and line ending; a tab without a file goes
   through **Save As**. A save that fails is reported and nothing runs.
2. A file whose suffix the configuration does not list is refused.
3. The file runs in a run window titled with the configuration's name and the file, with a
   **Stop** button: ``compiler [args...] file``, or, for a compiled language, the compiler
   first (limited to 60 seconds) and then the program it built. The build goes into a
   temporary folder that is removed afterwards.

.. note::

   A run configuration only names the compiler or interpreter; it has to be installed and
   on ``PATH``. Otherwise the run window says the command was not found.

A run configuration is a dictionary:

.. code-block:: python

   PLUGIN_RUN_CONFIG = {
       "name": "Go",            # the menu label
       "suffixes": (".go",),    # the files it runs
       "compiler": "go",        # the program started
       "args": ("run",),        # arguments between the compiler and the file
       # For a compiled language:
       # "compile_then_run": True, "output_flag": "-o",
       # PyBreeze only: the encoding the program writes ("locale" is the machine's own)
       # "encoding": "locale",
   }

Creating Plugins
----------------

The full plugin API, with worked examples, is JEditor's
`Plugin Guide <https://github.com/Integration-Automation/JEDITOR/blob/main/PLUGIN_GUIDE.md>`_;
PyBreeze's `PLUGIN_GUIDE.md <https://github.com/Integration-Automation/PyBreeze/blob/main/PLUGIN_GUIDE.md>`_
covers what PyBreeze adds. Ready-made plugins are in
`IDE_Plugins <https://github.com/Jeffrey-Plugin-Repos/IDE_Plugins>`_.

Syntax Highlighting Plugin Example
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A plugin can colour the keywords of a language, by file suffix:

.. code-block:: python

   # jeditor_plugins/lua_syntax.py
   from PySide6.QtGui import QColor
   from je_editor.plugins import register_programming_language

   PLUGIN_NAME = "Lua syntax"
   PLUGIN_VERSION = "1.0"


   def register() -> None:
       register_programming_language(
           suffix=".lua",
           syntax_words={
               "keywords": {"words": ("function", "local", "end", "return"),
                            "color": QColor(86, 156, 214)},
           },
           syntax_rules={
               "comments": {"rules": (r"--[^\n]*",), "color": QColor(106, 153, 85)},
           },
       )

.. note::

   Registered keywords are used only for a suffix JEditor does not colour itself. For
   ``.c``, ``.cpp``, ``.go``, ``.h``, ``.hpp``, ``.java``, ``.js``, ``.json``, ``.rs``,
   ``.sh``, ``.sql``, ``.toml``, ``.ts``, ``.yaml`` and ``.yml`` JEditor's own rules apply,
   and a plugin's keywords for them are not shown.

UI Translation Plugin Example
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A plugin can add an interface language, listed in the **Language** menu:

.. code-block:: python

   # jeditor_plugins/french.py
   from je_editor.plugins import register_natural_language

   PLUGIN_NAME = "French"


   def register() -> None:
       register_natural_language("French", "Français", {
           "file_menu_label": "Fichier",
           # ... the translated strings
       })

The keys are those of JEditor's English dictionary and of PyBreeze's
(``pybreeze/extend_multi_language/extend_english.py``). A key the plugin leaves out is
shown in English.
