6. From cURL and HAR to Tests
=============================

**You will**: turn a request copied from a browser into a test, and a whole recorded
session into a test suite, without writing either by hand.

Before you start
----------------

:doc:`t01_install_first_launch`, with the site running. ``pytest`` to run what is
generated: ``python -m pip install pytest``.

cURL to a test
--------------

A browser's developer tools copy any request as a ``curl`` command (*Copy as cURL*).
The example is one such command, for the tutorial site:

.. literalinclude:: ../../examples/request.curl
   :language: bash
   :caption: request.curl

1. Open **Tools > cURL Import Tab** and paste the command.
2. In **Generate for**, choose **pytest test**, and press **Generate pytest test**.

**Expected result**: the generated code is

.. code-block:: python

   import requests


   def test_get_users_json():
       url = "http://127.0.0.1:8765/users.json"
       headers = {
           "Accept": "application/json",
           "X-Trace": "tutorial",
       }
       response = requests.request("GET", url, headers=headers)
       assert response.status_code == 200
       # Add assertions on response.json() / response.text as needed

3. Press **Save to file...**, save it as ``test_users.py``, and run it:

   .. code-block:: bash

      python -m pytest test_users.py

   **Expected result**: ``1 passed``.

The same request for the other targets
--------------------------------------

**Generate for** lists six targets. For **APITestka (JSON action)** the same command
gives a script the Automation menu runs as it is (:doc:`t02_first_api_test`):

.. code-block:: json

   [
       [
           "AT_test_api_method",
           {
               "http_method": "GET",
               "test_url": "http://127.0.0.1:8765/users.json",
               "headers": {
                   "Accept": "application/json",
                   "X-Trace": "tutorial"
               }
           }
       ]
   ]

For **WebRunner (JSON action)** it gives a browser visit of the URL. A browser sends its
own headers, so a line under the generated code says what the target leaves out: here
the headers.

HAR to a suite
--------------

A HAR file is a browser's export of everything a page requested (*Save all as HAR* in
the network panel). The example holds two requests to the tutorial site.

1. Open **Tools > HAR Import Tab**, press **Open .har file...** and choose
   ``session.har``. The summary reads ``2 request(s), 2 API-like — 127.0.0.1`` and
   both requests are listed.
2. Choose **pytest test** and press **Generate for all listed**.
3. Save it as ``test_session.py`` and run ``python -m pytest test_session.py``.

**Expected result**: a file with ``test_get_users_json`` and ``test_get_127_0_0_1``,
and ``2 passed``.

If it does not work
-------------------

- *Could not parse the curl command*: paste the whole command, from ``curl`` on, in the
  form *Copy as cURL (bash)* gives.
- A HAR of a real site lists hundreds of requests: tick **Only API-like requests**, or
  select the ones you want and press **Generate for selection**.
- The generated test fails with a connection error: the site is not running.

Next
----

:doc:`t07_header_sarif_ci`
