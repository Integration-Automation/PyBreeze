Plugins Menu
============

PyBreeze supports a plugin system for extending functionality. Plugins are
auto-discovered from the ``jeditor_plugins/`` directory in your working directory.

Plugin Browser
--------------

Opens the plugin browser interface where you can:

- Browse available plugins
- View plugin details
- Install new plugins

Loaded Plugins
--------------

After startup, any plugins found in ``jeditor_plugins/`` are automatically loaded
and listed under the Plugins menu. Each loaded plugin appears as a menu entry.

Run With Menu
-------------

The **Run With** menu provides options to run the current file using different
compilers and interpreters. This is dynamically built based on available
language support.

Supported languages include:

- **C** -- Compile and run with gcc/clang
- **C++** -- Compile and run with g++/clang++
- **Go** -- Run with go run
- **Java** -- Compile and run with javac/java
- **Rust** -- Compile and run with rustc

.. note::

   The available "Run With" options depend on which compilers/interpreters are
   installed on your system and discoverable via the system PATH.

Creating Plugins
----------------

For detailed information on creating custom plugins, including syntax highlighting
plugins and UI translation plugins, see the
`Plugin Guide <https://github.com/Intergration-Automation-Testing/AutomationEditor/blob/main/PLUGIN_GUIDE.md>`_.

Syntax Highlighting Plugin Example
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Plugins can extend syntax highlighting with custom keywords:

.. code-block:: python

   # jeditor_plugins/my_syntax_plugin.py
   from je_editor import syntax_word_dict

   syntax_word_dict.update({
       "my_keyword": "keyword_format",
       "my_function": "function_format",
   })

UI Translation Plugin Example
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Plugins can add new UI translations:

.. code-block:: python

   # jeditor_plugins/my_language_plugin.py
   from je_editor import language_wrapper

   language_wrapper.language_word_dict.update({
       "application_name": "My Custom Name",
       # ... more translations
   })
