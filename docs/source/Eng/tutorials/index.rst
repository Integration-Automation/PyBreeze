Tutorials
=========

Thirteen short tutorials, in the order they build on each other. Each one has a
minimal example you can run as it is, and says what you should see when it worked.

The first one installs PyBreeze and starts a small web site on your own machine
(``http://127.0.0.1:8765``) that the later ones test, so nothing here needs an
account anywhere. Only the browser tutorial needs the internet, once, to fetch the
browser's driver.

.. list-table::
   :header-rows: 1
   :widths: 6 34 60

   * - #
     - Tutorial
     - You end up with
   * - 1
     - :doc:`t01_install_first_launch`
     - PyBreeze running in a project folder, and a local site to test
   * - 2
     - :doc:`t02_first_api_test`
     - An API test that passes, and its report
   * - 3
     - :doc:`t03_first_browser_test`
     - A browser that opens a page and closes again
   * - 4
     - :doc:`t04_first_desktop_automation`
     - A script that reads your screen size and mouse position
   * - 5
     - :doc:`t05_first_load_scenario`
     - Five users requesting a page for five seconds
   * - 6
     - :doc:`t06_curl_har_to_tests`
     - A test generated from a ``curl`` command and from a HAR export
   * - 7
     - :doc:`t07_header_sarif_ci`
     - Header findings as SARIF, and a CI step that fails on them
   * - 8
     - :doc:`t08_visual_json_editing`
     - A JSON file edited as a tree, with undo
   * - 9
     - :doc:`t09_keywords_language_service`
     - Completion and diagnostics for your action scripts
   * - 10
     - :doc:`t10_mcp_client`
     - A tool of an MCP server called from the IDE
   * - 11
     - :doc:`t11_reports_ci`
     - Every run in one viewer, and JUnit XML for CI
   * - 12
     - :doc:`t12_plugins_extending`
     - A tab of your own and a plugin
   * - 13
     - :doc:`t13_troubleshooting`
     - Answers for when something above did not work

The examples are in the repository under ``docs/source/examples/``.

.. toctree::
   :maxdepth: 1
   :hidden:

   t01_install_first_launch
   t02_first_api_test
   t03_first_browser_test
   t04_first_desktop_automation
   t05_first_load_scenario
   t06_curl_har_to_tests
   t07_header_sarif_ci
   t08_visual_json_editing
   t09_keywords_language_service
   t10_mcp_client
   t11_reports_ci
   t12_plugins_extending
   t13_troubleshooting
