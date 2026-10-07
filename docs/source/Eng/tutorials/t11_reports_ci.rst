11. Unified Reports and CI
==========================

**You will**: open the runs of the earlier tutorials in one viewer, filter them, and
export one as JUnit XML, the format a CI service reads.

Before you start
----------------

The reports written by :doc:`t02_first_api_test`, :doc:`t04_first_desktop_automation`
and :doc:`t05_first_load_scenario`: ``api_report_*.json``, ``desktop_report_*.json`` and
``load_report_*.json`` in the project folder.

Steps
-----

1. Open **Tools > Report Viewer Tab** and press **Open...**.
2. Select ``api_report_success.json``, ``desktop_report_success.json`` and
   ``load_report_success.json`` (Ctrl-click) and open them. Either file of a run opens
   the whole run: the ``_failure`` file is read with it.
3. Click through the tree. For a result, the tabs at the right show its details, its
   output, and **Own record**: the package's record of it, untouched.
4. Untick **passed** in the filter bar; tick it again. Choose ``je_load_density`` in
   the package box; choose **Every package** again. Type ``users`` in the text box.
5. Select the ``api_report`` run, press **Export...**, choose **JUnit XML** as the file
   type and save ``api_report.xml``.

Expected result
---------------

- Three runs are listed, ``api_report``, ``desktop_report`` and ``load_report``, each
  with how it ended. The line under the tree counts what is shown, for example
  ``130 of 130 results shown, from 3 reports, 0.05 s · passed: 130`` (one request, two
  desktop steps and the load test's requests; your load count will differ).
- With **passed** unticked nothing is listed, because nothing failed. With ``users``
  typed, only the API request is.
- The API request's details give its time (``0.05 s`` here); its output is the response
  body; its own record has the status code, the headers and the rest.
- ``api_report.xml`` is:

  .. code-block:: xml

     <?xml version="1.0" encoding="UTF-8"?>
     <testsuites name="api_report" tests="1" failures="0" errors="0" skipped="0" time="0.049">
       <testsuite name="api_report" tests="1" failures="0" errors="0" skipped="0" time="0.049">
         <testcase name="GET http://127.0.0.1:8765/users.json" classname="api_report" time="0.049">
           <system-out>[
       {"id": 1, "name": "Ada"},
       {"id": 2, "name": "Grace"}
     ]
     </system-out>
         </testcase>
       </testsuite>
     </testsuites>

What the viewer reads and writes
--------------------------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Reads
     - Notes
   * - ``<name>_success.json`` / ``<name>_failure.json``, or the ``.xml`` pair
     - APITestka, AutoControl, WebRunner, LoadDensity. Told apart by what a record holds.
   * - JUnit XML
     - pytest's ``--junitxml``, and most other test runners.
   * - A report exported from PyBreeze
     - JSON, or the HTML page.
   * - An MCP session
     - From the MCP Client's **Calls** page (:doc:`t10_mcp_client`).

**Export...** writes the selected run as an **Execution report** (JSON, read back as it
was), **JUnit XML**, or an **HTML page**: one file, no script, which can be mailed or
attached to a build, and opened here again.

In a CI workflow
----------------

A run of an automation package ends with exit code 0 whether its checks held or not
(:doc:`t02_first_api_test`), so CI has to read the report. JUnit XML is what CI services
read. With pytest the file comes straight from the runner:

.. code-block:: yaml

   - name: Run the tests
     run: python -m pytest --junitxml=test-results.xml
   - name: Keep the results
     if: always()
     uses: actions/upload-artifact@v4
     with:
       name: test-results
       path: test-results.xml

Download ``test-results.xml`` from a failed build and open it in the Report Viewer to
see what failed, with its message, its trace and what it printed. For a package's own
run, convert its record files with the viewer's **Export...**, or in a script:

.. code-block:: python

   from pathlib import Path

   from pybreeze.utils.execution_report.junit_xml import junit_from_report
   from pybreeze.utils.execution_report.report_files import read_report
   from pybreeze.utils.execution_report.report_schema import Status

   report = read_report(Path("api_report_success.json"))
   Path("api_report.xml").write_text(junit_from_report(report), encoding="utf-8")
   raise SystemExit(1 if report.status in (Status.FAILED, Status.ERROR) else 0)

**Expected result**: ``api_report.xml`` as above, and an exit code of ``0``; ``1`` for
the failing run of tutorial 2.

If it does not work
-------------------

- *This page holds no execution report*: a package's **HTML** report is not read; open
  the JSON or XML files beside it.
- *This file is not a report PyBreeze reads*, for a package's own ``_success.json``:
  both files of the run are empty (``{}``), which is what the packages write when
  nothing was recorded. Switch recording on in the script (``WR_set_record_enable``,
  ``AC_set_record_enable``).
- The paths under **Attachments** do not open: they are listed, not opened. A report is
  a file from somewhere.

Next
----

:doc:`t12_plugins_extending`
