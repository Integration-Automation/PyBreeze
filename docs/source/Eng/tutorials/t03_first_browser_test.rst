3. First Browser Test with WebRunner
====================================

**You will**: have a real browser open the tutorial site and close again, with each step
recorded.

Before you start
----------------

- :doc:`t01_install_first_launch`, with the site running.
- Google Chrome installed (or change ``"chrome"`` to ``"firefox"`` or ``"edge"``).
- The internet, the first time: WebRunner downloads the browser's driver once.

The example
-----------

.. literalinclude:: ../../examples/first_browser_test.json
   :language: json
   :caption: first_browser_test.json

``WR_set_record_enable`` switches the recording of steps on, without which the report
at the end would be empty. ``WR_get_webdriver_manager`` starts the browser,
``WR_to_url`` visits a page, ``WR_quit`` closes it.

Steps
-----

1. Open ``first_browser_test.json`` in the editor.
2. Choose **Automation > WebRunner > Run > Run WebRunner Script**.

Expected result
---------------

A Chrome window opens, shows *Hello from the tutorial site*, and closes. The run window
lists the five actions in order, each ``execute:`` line followed by what the action
returned, and ends with ``Task exit with code 0``:

.. code-block:: text

   execute: ['WR_set_record_enable', {'set_enable': True}]
   execute: ['WR_get_webdriver_manager', {'webdriver_name': 'chrome'}]
   execute: ['WR_to_url', {'url': 'http://127.0.0.1:8765/'}]
   execute: ['WR_quit']
   execute: ['WR_generate_json_report', {'json_file_name': 'web_report'}]

The project folder gets ``web_report_success.json`` and ``web_report_failure.json``.

.. note::

   This is the one example of these tutorials that was not run while they were written:
   it needs a browser on the machine. Its keywords and parameters are checked against
   the installed WebRunner by a test (``test_tutorial_examples.py``).

If it does not work
-------------------

- The driver cannot be downloaded: the machine is offline, or behind a proxy WebRunner's
  downloader does not know. Run it once with the network available.
- A keyword is underlined in the editor before you run: the editor checks ``.json``
  action scripts against the installed WebRunner (:doc:`t09_keywords_language_service`).
- The browser stays open after a failed run: an action failed before ``WR_quit``; close
  the window, fix the action, run again.

Next
----

:doc:`t04_first_desktop_automation`
