2. First API Test with APITestka
================================

**You will**: send one request to the tutorial site, check its status, and write a
report of the run.

Before you start
----------------

:doc:`t01_install_first_launch`: PyBreeze started in the project folder, and the site
running on port 8765.

The example
-----------

An APITestka script is a JSON list of actions: a keyword, then its arguments.

.. literalinclude:: ../../examples/first_api_test.json
   :language: json
   :caption: first_api_test.json

``AT_test_api_method`` sends the request and fails the action when what
``result_check_dict`` names is not what came back. ``AT_generate_json_report`` writes
the run's records.

Steps
-----

1. In the file tree, open ``first_api_test.json``. It opens in an editor tab.
2. With that tab in front, choose **Automation > APITestka > Run > Run APITestka Script**.
3. A run window opens with the output.

Expected result
---------------

The run window shows each action and what it returned:

.. code-block:: text

   execute: ['AT_test_api_method', {'http_method': 'get', 'test_url': 'http://127.0.0.1:8765/users.json', 'result_check_dict': {'status_code': 200}}]
   {'response': <Response [200]>, 'response_data': {'status_code': 200, 'text': '[\n  {"id": 1, "name": "Ada"}, ...
   execute: ['AT_generate_json_report', {'json_file_name': 'api_report'}]
   None
   Task exit with code 0

and the project folder has two new files, ``api_report_success.json`` (one record, the
request above) and ``api_report_failure.json`` (``{}``: nothing failed). The package
also writes its own log, ``APITestka.log``.

Now break it: change ``200`` to ``404`` in the script and run it again. The run
window prints ``value should be 404 but value was 200``, the action returns ``None``,
and ``api_report_failure.json`` holds the request with
``APIAssertException('value should be 404 but value was 200')``.

.. note::

   The run still ends with ``Task exit with code 0``: a check that did not hold is
   recorded, it does not fail the process. What tells a failed run from a passed one is
   the report (:doc:`t11_reports_ci`).

If it does not work
-------------------

- ``[Error] ... runs the script in the editor tab in front``: the script's tab was not
  the one in front when you chose the menu entry.
- A connection error instead of ``<Response [200]>``: the site of tutorial 1 is not
  running, or runs on another port.
- More than one failure in a run and only one in ``api_report_failure.json``: APITestka
  writes every failure under the same name, so the file keeps the last one.

Next
----

:doc:`t03_first_browser_test`. To look at the report, :doc:`t11_reports_ci`.
