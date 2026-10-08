4. First Desktop Automation with AutoControl
============================================

**You will**: run a script that asks the desktop two things, your screen's size and where
the mouse is, and records both. It moves and clicks nothing.

Before you start
----------------

- :doc:`t01_install_first_launch`.
- A desktop session. On macOS, the permission described in :doc:`t13_troubleshooting`.

The example
-----------

.. literalinclude:: ../../examples/first_desktop_automation.json
   :language: json
   :caption: first_desktop_automation.json

``AC_set_record_enable`` switches the recording of steps on. ``AC_screen_size`` and
``AC_get_mouse_position`` take no arguments, so each action is the keyword alone.

Steps
-----

1. Open ``first_desktop_automation.json`` in the editor.
2. Choose **Automation > AutoControl > Run > Run AutoControl Script**.

Expected result
---------------

The run window shows, with your own numbers:

.. code-block:: text

   execute: ['AC_set_record_enable', {'set_enable': True}]
   None
   execute: ['AC_screen_size']
   [1920, 1080]
   execute: ['AC_get_mouse_position']
   (477, 1079)
   execute: ['AC_generate_json_report', {'json_file_name': 'desktop_report'}]
   None
   Task exit with code 0

``desktop_report_success.json`` holds two records, named after the functions behind the
keywords (``size`` and ``get_mouse_position``), each with the time it ran.

From here, the keywords that act are the same shape: ``["AC_set_mouse_position",
{"x": 100, "y": 200}]``, ``["AC_click_mouse", {"mouse_keycode": "mouse_left"}]``,
``["AC_write", {"write_string": "hello"}]``. **Tools > Automation Keywords Tab** lists
all of them with their parameters, and **Automation > AutoControl > Record** writes a
script from what you do.

.. warning::

   A script that moves the mouse or types does it for real, in whatever window is in
   front. Try one on a desktop where a stray click costs nothing.

If it does not work
-------------------

- macOS reports the process is not trusted: grant the Accessibility permission.
- Linux without a display (a server, a container): AutoControl needs one.

Next
----

:doc:`t05_first_load_scenario`
