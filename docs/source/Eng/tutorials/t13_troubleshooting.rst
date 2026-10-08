13. Troubleshooting and Platform Setup
======================================

**You will**: find out why something in the earlier tutorials did not work, and set a
platform up for PyBreeze.

Where to look first
-------------------

- **The run window.** A run says what went wrong in its own lines: ``[Error] Command
  not found``, ``[Error] No Python interpreter found``, the package's traceback.
- **The log**: ``~/.pybreeze/logs/PyBreeze.log`` (see *The Log File* in
  :doc:`../getting_started`). Each line carries a process ID; the language server and
  the keyword probe write there too.
- **Tools > Automation Keywords Tab**: says, for each framework, the version installed
  for the interpreter that runs your scripts, or why it gives no keywords.

A minimal check
---------------

This runs without a window and tells whether the installation itself is whole.

.. code-block:: bash

   python -c "import pybreeze, PySide6; print(PySide6.__version__)"
   python -m pybreeze.extend.language_server --help

**Expected result**: a PySide6 version, and the language server's usage text. An
``ImportError`` here is an installation problem, not an IDE one: reinstall into a fresh
virtual environment (:doc:`t01_install_first_launch`).

Windows
-------

- ``python`` opens the Microsoft Store, or prints nothing and exits: it is the Store's
  stub. Use ``py -3.12`` to make the virtual environment, and the environment's own
  ``python`` after activating it.
- Text in a run window is garbled: the program writes the console's code page. For a
  plugin's run configuration, set ``"encoding": "locale"`` (:doc:`../menu_plugins`).
- The automation packages' own XML reports are written in the machine's code page;
  the report viewer reads those as such.

macOS
-----

- AutoControl needs permission to control the computer: **System Settings > Privacy &
  Security > Accessibility** (and **Screen Recording** for screenshots), for the
  terminal or the application that starts PyBreeze.
- Start PyBreeze from a terminal in the project folder: a double-clicked launcher
  starts in another folder, and the project's ``.venv`` and ``jeditor_plugins`` are
  not found.

Linux
-----

- The window does not open, or Qt reports a missing ``xcb`` plugin. Install the system
  libraries Qt needs; on Debian and Ubuntu:

  .. code-block:: bash

     sudo apt-get install libegl1 libgl1 libxkbcommon0 libdbus-1-3 libfontconfig1 \
         libnss3 libxcomposite1 libxdamage1 libxrandr2 libxkbfile1

- On a machine without a display (CI), PyBreeze's own tests run with
  ``QT_QPA_PLATFORM=offscreen``. The IDE itself needs a display; AutoControl does too.

By symptom
----------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - What you see
     - What to do
   * - A run uses the wrong Python
     - Runs use the interpreter chosen under **Python Env**, else a ``venv`` or
       ``.venv`` in the working folder, else the IDE's own. Start PyBreeze from the
       project folder, or choose the interpreter.
   * - No completion in a ``.json`` script
     - The file must be saved with a ``.json`` name. Open **Automation Keywords**: if
       the framework is "not installed for the interpreter that runs the scripts",
       install it there (**Install** menu) and restart PyBreeze.
   * - The browser test cannot start a browser
     - WebRunner needs the browser itself installed; the driver is fetched on first
       use, which needs the network once.
   * - An MCP server "could not be started"
     - The command's first line must be a program found on ``PATH`` or a full path;
       each argument goes on a line of its own. The status line ends with the
       server's own last log line when it started and then stopped.
   * - The report viewer says a file "is not a report"
     - It reads a package's ``_success`` / ``_failure`` files (JSON or XML), JUnit XML,
       and reports exported from PyBreeze. A package's HTML report is not read: open
       the JSON beside it.
   * - A request to ``127.0.0.1`` is refused by the AI review or the diagram's image
       download
     - By design: requests PyBreeze itself sends to a URL you type are refused for
       loopback and private addresses. Tests you **run** (the automation packages)
       are not affected.
   * - The main window is wider than the screen
     - The window has a least width set by the editor's Git panel; use a larger
       display or a smaller UI font (**UI Style** and the font settings).

Still stuck
-----------

Open an issue at https://github.com/Integration-Automation/PyBreeze/issues with the
version (``pip show pybreeze``), the platform, what you did, and the lines of the log
around the time it happened. Check the log for keys or tokens before you paste it.

Back to :doc:`index`.
