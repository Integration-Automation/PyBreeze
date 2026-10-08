Getting Started
===============

Requirements
------------

- Python 3.10 to 3.14
- pip (Python package manager)
- Windows, macOS or Linux; PySide6 is installed with PyBreeze

Installation
------------

Install PyBreeze from PyPI:

.. code-block:: bash

   pip install pybreeze

Or from source:

.. code-block:: bash

   git clone https://github.com/Integration-Automation/PyBreeze.git
   cd PyBreeze
   pip install -r requirements.txt

Either way the automation modules (AutoControl, APITestka, WebRunner, LoadDensity,
FileAutomation, MailThunder, TestPioneer), paramiko and JupyterLab are installed with it.
The **Install** menu upgrades them later, into the interpreter runs use (see
:doc:`menu_install`).

Launching PyBreeze
------------------

**Method 1: Command Line**

.. code-block:: bash

   python -m pybreeze

**Method 2: Python Script**

.. code-block:: python

   from pybreeze import start_editor

   start_editor()

**Method 3: With Options**

.. code-block:: python

   from pybreeze import start_editor

   # Any theme the UI Style menu lists: dark_teal.xml, dark_blue.xml,
   # light_blue.xml, ... It replaces the theme picked from UI Style.
   start_editor(theme="dark_teal.xml")

Parameters
^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 20 15 20 45

   * - Parameter
     - Type
     - Default
     - Description
   * - ``debug_mode``
     - bool
     - ``False``
     - Close by itself after 10 seconds (for start-up tests)
   * - ``theme``
     - str or None
     - ``None``
     - Qt Material theme name. It replaces the theme picked from **UI Style** and is kept
       as the picked one. ``None`` starts with the picked theme (``dark_amber.xml`` until
       one is picked).

The Working Folder
------------------

Start PyBreeze from your project folder. The folder it starts in, or the one opened
later with **File > Open Folder**, is where:

- the file tree opens;
- a ``venv/`` or ``.venv/`` is looked for, to run scripts with when no interpreter is
  chosen under **Python Env**;
- **Create ... Project** and the TestPioneer template are written.

Plugins are loaded once, at start-up, from ``jeditor_plugins/`` in the folder PyBreeze
starts in (see :doc:`menu_plugins`).

First Launch
------------

When PyBreeze starts, the main window opens maximized with:

1. **Menu Bar** at the top with all available menus
2. **File Tree** on the left side for project navigation
3. **Code Editor** (tabbed) in the center for editing files
4. **Output panel** below the editor, whose **Code result** tab shows the output of **Run Program** and
   **Run On Shell**

PyBreeze inherits its core editor functionality from **JEditor** and extends it
with automation-specific menus, tools, and integrations.

The Log File
------------

PyBreeze writes its log to ``~/.pybreeze/logs/PyBreeze.log``: UTF-8, appended to by every
run, each line carrying the process ID. Only warnings and errors also appear in the
**Code result** tab. Two environment variables change this:

``PYBREEZE_LOG_FILE``
   The log file to write instead.

``PYBREEZE_LOG_MAX_BYTES``
   When a PyBreeze process first writes to the log and the file is larger than this many
   bytes, the file is first renamed with ``.1`` appended, replacing the previous one.
   The default is 104857600 (100 MB); ``0`` never renames it.
