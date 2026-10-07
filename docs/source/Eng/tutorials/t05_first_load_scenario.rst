5. First Load Scenario with LoadDensity
=======================================

**You will**: have five simulated users request the tutorial site's front page for five
seconds, and read how it held up.

Before you start
----------------

:doc:`t01_install_first_launch`, with the site running. Load-test only what is yours:
here, a server on your own machine.

The example
-----------

.. literalinclude:: ../../examples/first_load_scenario.json
   :language: json
   :caption: first_load_scenario.json

``user_count`` users are started, ``spawn_rate`` of them a second, and each repeats the
``tasks`` (here one ``GET``) until ``test_time`` seconds have passed.

Steps
-----

1. Open ``first_load_scenario.json`` in the editor.
2. Choose **Automation > LoadDensity > Run > Run LoadDensity Script**.
3. Wait the five seconds.

Expected result
---------------

The run window shows the test's settings, and, as the test ends, a table of what was
requested. The counts depend on your machine; here five users made 127 requests in
five seconds and none failed:

.. code-block:: text

   execute: ['LD_start_test', {'user_detail_dict': {'user': 'fast_http_user'}, 'user_count': 5, 'spawn_rate': 5, 'test_time': 5, 'tasks': {'get': {'request_url': 'http://127.0.0.1:8765/'}}}]
   {'user_detail': {'user': 'fast_http_user'}, 'user_count': 5, 'spawn_rate': 5, 'test_time': 5, 'web_ui': None}
   execute: ['LD_generate_json_report', {'json_file_name': 'load_report'}]
   ('load_report_success.json', 'load_report_failure.json')

   GET      http://127.0.0.1:8765/        127     0(0.00%) |      3       1      29      3 |   26.50        0.00
            Aggregated                    127     0(0.00%) |      3       1      29      3 |   26.50        0.00

The table's columns are the number of requests, the failures, the average, least, most
and median response time in milliseconds, and requests a second.
``load_report_success.json`` holds one record for every request that succeeded.

If it does not work
-------------------

- Every request fails: the site is not running on the port the script names.
- The second terminal fills with lines: that is ``http.server`` logging each request,
  as it should.
- Users seem to run one after another when a locust script is started with the
  editor's **Run Program** instead of this menu: use the Automation menu, which starts
  the load test with the environment it needs.

Next
----

:doc:`t06_curl_har_to_tests`. To see the 127 requests as a report,
:doc:`t11_reports_ci`.
