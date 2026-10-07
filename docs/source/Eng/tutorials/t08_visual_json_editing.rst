8. Visual JSON Editing
======================

**You will**: change a JSON file as a tree, see the text follow, undo, and save it laid
out as it was.

Before you start
----------------

:doc:`t01_install_first_launch`. The file is ``settings.json`` from the examples.

The example
-----------

.. literalinclude:: ../../examples/settings.json
   :language: json
   :caption: settings.json

Steps
-----

1. Open **Tools > JSON Editor Tab**, press **Open...** and choose ``settings.json``.
   The **Tree** shows ``(document)`` with ``name``, ``servers`` and ``retries`` under it.
2. Select ``servers`` and press **Add**. A new server appears at the end of the list as
   ``null``. With it selected, choose **object** in the **Type** box, then press **Add**
   again: the object gets a member called ``new_key``.
3. Double-click ``new_key`` and type ``host``. Its value is ``null``, which cannot be
   typed over: with it selected choose **string** in **Type**, then double-click the
   value and type ``127.0.0.1``.
4. Select ``retries``, double-click its value and type ``three``. The line under the
   views says it is not a JSON number, and the value stays ``3``. Type ``5`` instead.
5. Select ``name`` and press **Move Down** twice: it is now the last member.
6. Open the **Text** view. Remove the last ``}``: the line under the views says where
   the text stops being JSON, and the tree, if you turn to it, is empty until you put
   the brace back.
7. Press **Ctrl+Z** a few times, in either view: each press takes back one step,
   whichever view made it. **Ctrl+Y** brings it back.
8. Press **Save**.

Expected result
---------------

After step 5 the **Text** view reads:

.. code-block:: json

   {
     "servers": [
       {
         "host": "127.0.0.1",
         "port": 8765
       },
       {
         "host": "127.0.0.1"
       }
     ],
     "retries": 5,
     "name": "demo"
   }

- The indent is the file's own two spaces. The first server, written on one line in the
  file, is now written like the rest: an edit in the tree writes the whole text again,
  so alignment done by hand is not kept.
- The name over the views carries a ``*`` while there are unsaved changes, and loses it
  on **Save**, or when Undo is back at what was saved.
- Closing the tab, or opening another file, with unsaved changes asks first.

If it does not work
-------------------

- **Add** is greyed out: nothing is selected, or the text is not JSON at the moment
  (look at the line under the views).
- A cell does not open for typing: only a member's name and a string, number or boolean
  value are typed into. An item of an array has no name, and ``null``, objects and
  arrays get a value through **Type** and **Add**.

Next
----

:doc:`t09_keywords_language_service`. The reference is in :doc:`../menu_tools`.
