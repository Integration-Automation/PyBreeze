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

   All installation commands run in the shell runner and respect the currently
   active virtual environment. If a ``.venv`` or ``venv`` directory is detected,
   packages will be installed into that environment.
