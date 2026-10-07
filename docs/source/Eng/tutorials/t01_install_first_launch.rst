1. Installation and First Launch
================================

**You will**: install PyBreeze, start it in a project folder, and start the small web
site the later tutorials test.

Before you start
----------------

- Python 3.10 to 3.14, with ``pip``.
- Windows, macOS or Linux with a desktop. On Linux, Qt needs the system libraries listed
  in :doc:`t13_troubleshooting`.

Steps
-----

1. Make a project folder with a virtual environment in it, and install PyBreeze there.

   .. code-block:: bash

      mkdir pybreeze-tutorial
      cd pybreeze-tutorial
      python -m venv .venv

      # Windows
      .venv\Scripts\activate
      # macOS, Linux
      source .venv/bin/activate

      python -m pip install pybreeze

   The automation packages the tutorials use (APITestka, WebRunner, AutoControl,
   LoadDensity) are installed with it.

2. Copy the examples into the folder. They are in the repository under
   ``docs/source/examples/``; copy that folder's contents, so that ``site/`` and the
   ``.json`` files are in ``pybreeze-tutorial``.

3. In a **second** terminal, in the same folder, start the site the tutorials test.
   Leave it running.

   .. code-block:: bash

      python -m http.server 8765 --bind 127.0.0.1 --directory site

4. In the first terminal, start PyBreeze **from the project folder**.

   .. code-block:: bash

      python -m pybreeze

The example
-----------

The site is two files:

.. literalinclude:: ../../examples/site/index.html
   :language: html
   :caption: site/index.html

.. literalinclude:: ../../examples/site/users.json
   :language: json
   :caption: site/users.json

Expected result
---------------

- The main window opens maximized: the menu bar on top, the **navigation panel** and the
  file tree at the left with your folder in it, the editor in the middle, the output
  panel below.
- The navigation panel lists what the menus hold under **Automation**, **Tools**,
  **MCP**, **Reports** and **Settings**; typing in its box filters it, and a
  double-click opens an entry.
- ``http://127.0.0.1:8765/`` in a browser shows *Hello from the tutorial site*, and
  ``http://127.0.0.1:8765/users.json`` the two users.
- Because the folder has a ``.venv``, runs started from the IDE use that interpreter
  (see *The Working Folder* in :doc:`../getting_started`).

If it does not work
-------------------

- ``python`` is not found, or is the wrong one: use ``py -3.12`` (Windows) or
  ``python3`` to make the virtual environment.
- The window does not open on Linux: see :doc:`t13_troubleshooting`.
- Port 8765 is taken: pick another, and use it in the examples' URLs too.

Next
----

:doc:`t02_first_api_test`
