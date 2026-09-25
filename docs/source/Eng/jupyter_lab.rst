JupyterLab Integration
======================

PyBreeze includes an embedded JupyterLab environment, allowing you to work with
Jupyter notebooks directly within the IDE.

Opening JupyterLab
-------------------

Open it from **Tab > Tools Tab > JupyterLab**. It opens a new tab (titled
``JupyterLab <n>``) containing a full JupyterLab interface rendered via Qt's web engine.

First-Time Setup
^^^^^^^^^^^^^^^^

If the interpreter the lab runs in cannot import ``jupyterlab``, PyBreeze first
installs it there with ``pip install -U jupyterlab``. A status label shows the progress.

Interface
---------

The JupyterLab tab contains:

- **Status Label** -- Shows the startup status ("Initializing...", "Downloading..." while
  JupyterLab is installed, "Loading... (Ns / 60s)" while the server starts) and is removed
  once the lab loads; if the lab cannot start it reads "JupyterLab init failed: <reason>"
- **Web Engine View** -- A full JupyterLab interface rendered in a ``QWebEngineView``

The embedded JupyterLab provides all standard Jupyter features:

- Create and edit notebooks (``.ipynb`` files)
- Run Python code cells interactively
- Markdown documentation cells
- Rich output display (charts, tables, images)
- Terminal access
- File browser
- Extension support

How It Works
------------

1. PyBreeze launches a ``JupyterLauncherThread`` in the background
2. The thread starts a JupyterLab server process
3. Once the server is ready, a signal notifies the widget
4. The ``QWebEngineView`` loads the JupyterLab URL
5. You interact with JupyterLab as if it were running in a browser

.. note::

   The JupyterLab server runs as a background process. When you close
   the JupyterLab tab or exit PyBreeze, the server is automatically stopped.

Usage Tips
----------

- JupyterLab listens on a free port on localhost only; network access is needed only to
  install JupyterLab when it is missing
- You can open multiple notebooks in JupyterLab's own tab system
- Use JupyterLab for data analysis, prototyping, and interactive testing
- JupyterLab and its kernels run in the interpreter a script run uses: the one chosen under
  **Python Env > Choose python interpreter**; with none chosen, a ``venv`` or ``.venv`` in
  the working folder, else the interpreter PyBreeze itself runs on
