Automation Menu
===============

The **Automation** menu is the core feature menu of PyBreeze. It provides access to
all integrated automation modules for Web, API, GUI, load testing, file automation,
and email automation.

Each automation module follows a consistent menu structure:

- **Run** submenu -- Execute scripts (single or multi-file, with or without email reporting)
- **Help** submenu -- Links to documentation and GitHub repository, opened as browser tabs inside the IDE
- **Project** submenu -- Create a new project template in the IDE's working directory
- **<Module> GUI** -- Open the module's GUI as a tab (**APITestka GUI**, **AutoControl GUI**, **LoadDensity GUI**)

**TestPioneer** and **Code Review (prthinker)** have menus of their own, described below.

AutoControl Menu
----------------

**AutoControl** is a GUI automation module for desktop application testing.
It can record and replay mouse/keyboard actions.

Run Submenu
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Menu Item
     - Description
   * - **Run AutoControl Script**
     - Executes the current editor content as an AutoControl script.
   * - **Run AutoControl With Send**
     - Executes the script and sends the results via email (using MailThunder).
   * - **Run Multi AutoControl Script**
     - Runs multiple AutoControl scripts from a selected directory.
   * - **Run Multi AutoControl Script With Send**
     - Runs multiple scripts and sends the results via email.

Help Submenu
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
   * - **Create AutoControl Project**
     - Creates a AutoControl project template (``je_auto_control``) in the IDE's working directory, asking before it replaces one that is already there.

Record Submenu
^^^^^^^^^^^^^^

The Record submenu is **unique to AutoControl** and allows you to record
mouse and keyboard actions for playback.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Menu Item
     - Description
   * - **Record Start**
     - Starts recording mouse and keyboard actions.
   * - **Record Stop**
     - Stops recording and inserts the recorded actions, as the JSON the AutoControl runner
       reads, at the cursor of the editor tab in front; with no editor tab in front they are
       copied to the clipboard. If nothing was recorded, it says so.

AutoControl GUI
^^^^^^^^^^^^^^^

Opens an embedded AutoControl GUI widget as a new tab in the editor,
providing a visual interface for AutoControl operations.

APITestka Menu
--------------

**APITestka** is an API testing automation module for sending HTTP requests
and validating responses.

Run Submenu
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Menu Item
     - Description
   * - **Run APITestka Script**
     - Executes the current editor content as an APITestka script.
   * - **Run APITestka With Send**
     - Executes the script and sends results via email.
   * - **Run Multi APITestka Script**
     - Runs multiple APITestka scripts from a selected directory.
   * - **Run Multi APITestka Script With Send**
     - Runs multiple scripts and sends results via email.

Help Submenu
^^^^^^^^^^^^

- **Open APITestka Doc** -- Opens https://apitestka.readthedocs.io/
- **Open APITestka GitHub** -- Opens the GitHub repository

Project Submenu
^^^^^^^^^^^^^^^

- **Create APITestka Project** -- Creates a APITestka project template (``je_api_testka``) in the IDE's working directory, asking before it replaces one that is already there.

APITestka GUI
^^^^^^^^^^^^^

Opens an embedded APITestka GUI widget as a new tab for visual API testing.

WebRunner Menu
--------------

**WebRunner** is a web browser automation module for testing web applications
using browser drivers (Selenium-based).

Run Submenu
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Menu Item
     - Description
   * - **Run WebRunner Script**
     - Executes the current editor content as a WebRunner script.
   * - **Run WebRunner With Send**
     - Executes the script and sends results via email.
   * - **Run Multi WebRunner Script**
     - Runs multiple WebRunner scripts from a selected directory.
   * - **Run Multi WebRunner Script With Send**
     - Runs multiple scripts and sends results via email.

Help Submenu
^^^^^^^^^^^^

- **Open WebRunner Doc** -- Opens https://webrunner.readthedocs.io/
- **Open WebRunner GitHub** -- Opens the GitHub repository

Project Submenu
^^^^^^^^^^^^^^^

- **Create WebRunner Project** -- Creates a WebRunner project template (``je_web_runner``) in the IDE's working directory, asking before it replaces one that is already there.

LoadDensity Menu
----------------

**LoadDensity** is a load/performance testing module that generates concurrent
requests to test system capacity.

Run Submenu
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Menu Item
     - Description
   * - **Run LoadDensity Script**
     - Executes the current editor content as a LoadDensity script.
   * - **Run LoadDensity With Send**
     - Executes the script and sends results via email.
   * - **Run Multi LoadDensity Script**
     - Runs multiple LoadDensity scripts from a selected directory.
   * - **Run Multi LoadDensity Script With Send**
     - Runs multiple scripts and sends results via email.

Help Submenu
^^^^^^^^^^^^

- **Open LoadDensity Doc** -- Opens https://loaddensity.readthedocs.io/
- **Open LoadDensity GitHub** -- Opens the GitHub repository

Project Submenu
^^^^^^^^^^^^^^^

- **Create LoadDensity Project** -- Creates a LoadDensity project template (``je_load_density``) in the IDE's working directory, asking before it replaces one that is already there.

LoadDensity GUI
^^^^^^^^^^^^^^^

Opens an embedded LoadDensity GUI widget as a new tab for visual load test configuration.

FileAutomation Menu
-------------------

**FileAutomation** is a file operation automation module for automating
file system tasks such as copying, moving, renaming, and processing files.

Run Submenu
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Menu Item
     - Description
   * - **Run FileAutomation Script**
     - Executes the current editor content as a FileAutomation script.
   * - **Run FileAutomation With Send**
     - Executes the script and sends results via email.
   * - **Run Multi FileAutomation Script**
     - Runs multiple FileAutomation scripts from a selected directory.
   * - **Run Multi FileAutomation Script With Send**
     - Runs multiple scripts and sends results via email.

Help Submenu
^^^^^^^^^^^^

- **Open FileAutomation Doc** -- Opens https://fileautomation.readthedocs.io/
- **Open FileAutomation GitHub** -- Opens the GitHub repository

Project Submenu
^^^^^^^^^^^^^^^

- **Create FileAutomation Project** -- Creates a FileAutomation project template (``automation_file``) in the IDE's working directory, asking before it replaces one that is already there.

MailThunder Menu
----------------

**MailThunder** is an email automation module for sending test reports
and automated notifications.

Run Submenu
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Menu Item
     - Description
   * - **Run MailThunder Script**
     - Executes the current editor content as a MailThunder script.

Help Submenu
^^^^^^^^^^^^

- **Open MailThunder Doc** -- Opens https://mailthunder.readthedocs.io/
- **Open MailThunder GitHub** -- Opens the GitHub repository

Project Submenu
^^^^^^^^^^^^^^^

- **Create MailThunder Project** -- Creates a MailThunder project template (``je_mail_thunder``) in the IDE's working directory, asking before it replaces one that is already there.

TestPioneer Menu
----------------

**TestPioneer** provides YAML-based test configuration and execution.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Menu Item
     - Description
   * - **Create TestPioneer YAML Template**
     - Creates ``.TestPioneer/.TestPioneer.yml`` in the IDE's working directory, asking
       before it replaces one that is already there.
   * - **Run TestPioneer YAML**
     - Opens a file dialog to select a ``.yml`` or ``.yaml`` file and executes the test
       definitions within it.
   * - **Help > Open TestPioneer GitHub**
     - Opens the TestPioneer GitHub repository (its README is its manual) in a browser tab.

Code Review (prthinker) Menu
----------------------------

Runs the prthinker chain-of-thought code review; output streams into a run window.
Install prthinker first with **Install > Automation > Install prthinker (code review)**.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Menu Item
     - Description
   * - **Review the current file**
     - Saves the file in the editor tab in front, then reviews it.
   * - **Review a Pull Request**
     - Asks for the pull request number and reviews that pull request of the repository
       set in **Settings**.
   * - **Settings**
     - Opens the prthinker settings: inference backend, model, code host, repository,
       keys and tokens.
   * - **Help > Open prthinker documentation**
     - Opens https://code-review-framework.readthedocs.io/ in a browser tab.
   * - **Help > Open prthinker GitHub**
     - Opens the prthinker GitHub repository in a browser tab.

Script Execution Flow
---------------------

When you run any automation script, the following process occurs:

1. The current code editor content is captured.
2. A subprocess is spawned using the ``TaskProcessManager``.
3. The script runs in an isolated process (preventing crashes from affecting the IDE).
4. A run window opens to display real-time execution output, titled with the package
   and the file it runs, with a **Stop** button.
5. If "With Send" was selected, results are sent via MailThunder email after execution.

.. note::

   Each automation module runs in a separate subprocess for stability.
   If a script crashes, the main PyBreeze IDE remains unaffected.

Multi-Script Execution
^^^^^^^^^^^^^^^^^^^^^^

When using the "Run Multi" options:

1. A folder selection dialog opens.
2. Every ``.json`` action file in the folder and its subfolders is collected; a folder with none says so.
3. The files run one after another, each in its own subprocess and its own run window.
4. Each run reports on its own (and, with "With Send", mails its own report); stopping one run ends the batch.

Report Formats
^^^^^^^^^^^^^^

Automation modules can generate reports in multiple formats:

- **HTML** -- Visual reports for sharing
- **JSON** -- Machine-readable results
- **XML** -- Standard test result format
