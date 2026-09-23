Install Menu
============

The **Install** menu provides one-click installation of automation packages
and build tools directly from the PyBreeze IDE.

Automation Submenu
------------------

Installs the automation module packages via pip.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Menu Item
     - Description
   * - **Install AutoControl**
     - Runs ``pip install -U je_auto_control``
   * - **Install APITestka**
     - Runs ``pip install -U je_api_testka``
   * - **Install LoadDensity**
     - Runs ``pip install -U je_load_density``
   * - **Install WebRunner**
     - Runs ``pip install -U je_web_runner``
   * - **Install Automation File**
     - Runs ``pip install -U automation_file``
   * - **Install MailThunder**
     - Runs ``pip install -U je_mail_thunder``
   * - **Install prthinker (code review)**
     - prthinker is not on PyPI. The first time, asks for its source folder and
       remembers it; then runs ``pip install -U <folder>[runner]``

Tools Submenu
-------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Menu Item
     - Description
   * - **Install Build Tools**
     - Runs ``pip install -U setuptools build wheel`` to install Python
       packaging and build tools.

.. note::

   Each install opens a run window of its own and runs ``python -m pip`` there,
   with no shell in between, so a folder name holding ``&`` or ``|`` reaches pip
   unchanged. pip runs with the interpreter chosen in the Python environment
   menu; when none is chosen, with a ``venv`` or ``.venv`` in the working
   directory, and otherwise with the Python found on ``PATH``.
