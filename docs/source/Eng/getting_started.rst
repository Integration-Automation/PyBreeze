Getting Started
===============

Requirements
------------

- Python 3.10 or higher
- pip (Python package manager)

Installation
------------

Install PyBreeze from PyPI:

.. code-block:: bash

   pip install pybreeze

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

   # Available themes: dark_amber.xml (default), dark_teal.xml,
   # dark_blue.xml, light_blue.xml, etc.
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
     - Auto-close after 10 seconds (for CI testing)
   * - ``theme``
     - str
     - ``"dark_amber.xml"``
     - Qt Material theme name

First Launch
------------

When PyBreeze starts, the main window opens maximized with:

1. **Menu Bar** at the top with all available menus
2. **File Tree** on the left side for project navigation
3. **Code Editor** (tabbed) in the center for editing files
4. **Output Panel** at the bottom for execution results

PyBreeze inherits its core editor functionality from **JEditor** and extends it
with automation-specific menus, tools, and integrations.
