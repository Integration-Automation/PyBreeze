Automation Menu
===============

The **Automation** menu is the core feature menu of PyBreeze. It provides access to
all integrated automation modules for Web, API, GUI, load testing, file automation,
and email automation.

Each automation module follows a consistent menu structure:

- **RUN** submenu -- Execute scripts (single or multi-file, with or without email reporting)
- **HELP** submenu -- Links to documentation and GitHub repository
- **Project** submenu -- Create new project templates
- **GUI Tab** -- Open an embedded GUI widget (available for some modules)

AutoControl Menu
----------------

**AutoControl** is a GUI automation module for desktop application testing.
It can record and replay mouse/keyboard actions.

RUN Submenu
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Menu Item
     - Description
   * - **Run AutoControl Script**
     - Executes the current editor content as an AutoControl script.
   * - **Run AutoControl Script With Send**
     - Executes the script and sends the results via email (using MailThunder).
   * - **Run Multi AutoControl Script**
     - Runs multiple AutoControl scripts from a selected directory.
   * - **Run Multi AutoControl Script With Send**
     - Runs multiple scripts and sends the results via email.

HELP Submenu
^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Menu Item
     - Description
   * - **Open AutoControl Doc**
     - Opens the AutoControl documentation (https://autocontrol.readthedocs.io/).
   * - **Open AutoControl GitHub**
     - Opens the AutoControl GitHub repository.

Project Submenu
^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Menu Item
     - Description
   * - **Create Project**
     - Creates a new AutoControl project structure using ``je_auto_control``.

Record Submenu
^^^^^^^^^^^^^^

The Record submenu is **unique to AutoControl** and allows you to record
mouse and keyboard actions for playback.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Menu Item
     - Description
   * - **Start Record**
     - Starts recording mouse and keyboard actions.
   * - **Stop Record**
     - Stops recording and inserts the recorded action data into the code editor.

GUI Tab
^^^^^^^

Opens an embedded AutoControl GUI widget as a new tab in the editor,
providing a visual interface for AutoControl operations.

APITestka Menu
--------------

**APITestka** is an API testing automation module for sending HTTP requests
and validating responses.

RUN Submenu
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Menu Item
     - Description
   * - **Run APITestka Script**
     - Executes the current editor content as an APITestka script.
   * - **Run APITestka Script With Send**
     - Executes the script and sends results via email.
   * - **Run Multi APITestka Script**
     - Runs multiple APITestka scripts from a selected directory.
   * - **Run Multi APITestka Script With Send**
     - Runs multiple scripts and sends results via email.

HELP Submenu
^^^^^^^^^^^^

- **Open APITestka Doc** -- Opens https://apitestka.readthedocs.io/
- **Open APITestka GitHub** -- Opens the GitHub repository

Project Submenu
^^^^^^^^^^^^^^^

- **Create Project** -- Creates a new APITestka project structure using ``je_api_testka``.

GUI Tab
^^^^^^^

Opens an embedded APITestka GUI widget as a new tab for visual API testing.

WebRunner Menu
--------------

**WebRunner** is a web browser automation module for testing web applications
using browser drivers (Selenium-based).

RUN Submenu
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Menu Item
     - Description
   * - **Run WebRunner Script**
     - Executes the current editor content as a WebRunner script.
   * - **Run WebRunner Script With Send**
     - Executes the script and sends results via email.
   * - **Run Multi WebRunner Script**
     - Runs multiple WebRunner scripts from a selected directory.
   * - **Run Multi WebRunner Script With Send**
     - Runs multiple scripts and sends results via email.

HELP Submenu
^^^^^^^^^^^^

- **Open WebRunner Doc** -- Opens https://webrunner.readthedocs.io/
- **Open WebRunner GitHub** -- Opens the GitHub repository

Project Submenu
^^^^^^^^^^^^^^^

- **Create Project** -- Creates a new WebRunner project structure using ``je_web_runner``.

LoadDensity Menu
----------------

**LoadDensity** is a load/performance testing module that generates concurrent
requests to test system capacity.

RUN Submenu
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Menu Item
     - Description
   * - **Run LoadDensity Script**
     - Executes the current editor content as a LoadDensity script.
   * - **Run LoadDensity Script With Send**
     - Executes the script and sends results via email.
   * - **Run Multi LoadDensity Script**
     - Runs multiple LoadDensity scripts from a selected directory.
   * - **Run Multi LoadDensity Script With Send**
     - Runs multiple scripts and sends results via email.

HELP Submenu
^^^^^^^^^^^^

- **Open LoadDensity Doc** -- Opens https://loaddensity.readthedocs.io/
- **Open LoadDensity GitHub** -- Opens the GitHub repository

Project Submenu
^^^^^^^^^^^^^^^

- **Create Project** -- Creates a new LoadDensity project structure using ``je_load_density``.

GUI Tab
^^^^^^^

Opens an embedded LoadDensity GUI widget as a new tab for visual load test configuration.

FileAutomation Menu
-------------------

**FileAutomation** is a file operation automation module for automating
file system tasks such as copying, moving, renaming, and processing files.

RUN Submenu
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Menu Item
     - Description
   * - **Run FileAutomation Script**
     - Executes the current editor content as a FileAutomation script.
   * - **Run FileAutomation Script With Send**
     - Executes the script and sends results via email.
   * - **Run Multi FileAutomation Script**
     - Runs multiple FileAutomation scripts from a selected directory.
   * - **Run Multi FileAutomation Script With Send**
     - Runs multiple scripts and sends results via email.

HELP Submenu
^^^^^^^^^^^^

- **Open FileAutomation Doc** -- Opens https://fileautomation.readthedocs.io/
- **Open FileAutomation GitHub** -- Opens the GitHub repository

Project Submenu
^^^^^^^^^^^^^^^

- **Create Project** -- Creates a new FileAutomation project structure using ``automation_file``.

MailThunder Menu
----------------

**MailThunder** is an email automation module for sending test reports
and automated notifications.

RUN Submenu
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Menu Item
     - Description
   * - **Run MailThunder Script**
     - Executes the current editor content as a MailThunder script.

HELP Submenu
^^^^^^^^^^^^

- **Open MailThunder Doc** -- Opens https://mailthunder.readthedocs.io/
- **Open MailThunder GitHub** -- Opens the GitHub repository

Project Submenu
^^^^^^^^^^^^^^^

- **Create Project** -- Creates a new MailThunder project structure.

TestPioneer Menu
----------------

**TestPioneer** provides YAML-based test configuration and execution.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Menu Item
     - Description
   * - **Create TestPioneer Yaml Template**
     - Generates a YAML template file for defining test cases.
   * - **Execute Test Pioneer Yaml**
     - Opens a file dialog to select a ``.yml`` file and executes the test
       definitions within it.

Script Execution Flow
---------------------

When you run any automation script, the following process occurs:

1. The current code editor content is captured.
2. A subprocess is spawned using the ``TaskProcessManager``.
3. The script runs in an isolated process (preventing crashes from affecting the IDE).
4. A **Code Output Window** opens to display real-time execution output.
5. If "With Send" was selected, results are sent via MailThunder email after execution.

.. note::

   Each automation module runs in a separate subprocess for stability.
   If a script crashes, the main PyBreeze IDE remains unaffected.

Multi-Script Execution
^^^^^^^^^^^^^^^^^^^^^^

When using the "Run Multi" options:

1. A directory selection dialog opens.
2. All matching script files in the selected directory are collected.
3. Each script is executed sequentially in its own subprocess.
4. Results from all scripts are aggregated.

Report Formats
^^^^^^^^^^^^^^

Automation modules can generate reports in multiple formats:

- **HTML** -- Visual reports for sharing
- **JSON** -- Machine-readable results
- **XML** -- Standard test result format
