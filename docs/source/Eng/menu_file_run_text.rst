File, Run, Text & Other Base Menus
===================================

These menus are inherited from the JEditor base editor engine and provide
core editing and execution functionality.

File Menu
---------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Menu Item
     - Description
   * - **Open File**
     - Opens a file dialog to select a file. The file content is loaded into the code editor.
   * - **Save File**
     - Saves the current code editor content to the currently opened file.
   * - **Encoding**
     - Opens a dialog to choose the encoding for the program runner and shell runner
       (e.g., UTF-8, ASCII, Big5).

Run Menu
--------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Menu Item
     - Description
   * - **Run Program**
     - Executes the current code editor content using the program runner (Python interpreter).
   * - **Run On Shell**
     - Executes the current code editor content using the system shell.
   * - **Clean Result**
     - Clears the output panel (both program and shell results).
   * - **Stop Program**
     - Stops the currently running program process.

Run Help Submenu
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Menu Item
     - Description
   * - **Run Help**
     - Displays help information about the program runner.
   * - **Shell Help**
     - Displays help information about the shell runner.

Text Menu
---------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Menu Item
     - Description
   * - **Font**
     - Opens a font selection dialog to change the editor's default font.
   * - **Font Size**
     - Opens a dialog to change the editor's default font size.

Check Code Style Menu
---------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Menu Item
     - Description
   * - **yapf**
     - Checks and formats the current Python code using the ``yapf`` code formatter.
   * - **Reformat JSON**
     - Reformats and validates the current content as JSON, applying proper indentation.

Venv Menu
---------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Menu Item
     - Description
   * - **Create Venv**
     - Creates a Python virtual environment in the current working directory
       using the shell runner.
   * - **pip upgrade package**
     - Upgrades a specified package using pip within the virtual environment.
   * - **pip package**
     - Installs a specified package using pip within the virtual environment.

.. note::

   PyBreeze automatically detects ``.venv`` or ``venv`` directories in your
   project and uses the virtual environment's Python interpreter when available.

UI Style Menu
-------------

Contains a list of available Qt Material themes. Clicking any theme immediately
applies it to the entire application. See :doc:`ui_overview` for the full list
of available themes.
