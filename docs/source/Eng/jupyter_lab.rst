JupyterLab Integration
======================

PyBreeze includes an embedded JupyterLab environment, allowing you to work with
Jupyter notebooks directly within the IDE.

Opening JupyterLab
-------------------

JupyterLab is available from the tab menu. When opened, it creates a new tab
containing a full JupyterLab interface rendered via Qt's web engine.

First-Time Setup
^^^^^^^^^^^^^^^^

On first launch, if JupyterLab is not installed, PyBreeze will automatically
install it using pip. A status label shows the initialization progress.

Interface
---------

The JupyterLab tab contains:

- **Status Label** -- Shows initialization status ("Starting JupyterLab...", "Ready", etc.)
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

- JupyterLab runs on a local port; no external network access is needed
- You can open multiple notebooks in JupyterLab's own tab system
- Use JupyterLab for data analysis, prototyping, and interactive testing
- The embedded JupyterLab shares the same Python environment as PyBreeze
