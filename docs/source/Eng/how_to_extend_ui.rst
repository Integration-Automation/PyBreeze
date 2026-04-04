How to Extend the UI
====================

PyBreeze supports extending the UI with custom tabs using the ``EDITOR_EXTEND_TAB``
dictionary. You can add any PySide6 ``QWidget`` as a new tab in the editor.

Basic Example
-------------

.. code-block:: python

   from PySide6.QtWidgets import QWidget, QGridLayout, QLineEdit, QPushButton, QLabel
   from pybreeze import start_editor, EDITOR_EXTEND_TAB


   class TestUI(QWidget):
       """A simple custom tab widget."""

       def __init__(self):
           super().__init__()
           self.grid_layout = QGridLayout(self)
           self.grid_layout.setContentsMargins(0, 0, 0, 0)
           self.label = QLabel("")
           self.line_edit = QLineEdit()
           self.submit_button = QPushButton("Submit")
           self.submit_button.clicked.connect(self.show_input_text)
           self.grid_layout.addWidget(self.label, 0, 0)
           self.grid_layout.addWidget(self.line_edit, 1, 0)
           self.grid_layout.addWidget(self.submit_button, 2, 0)

       def show_input_text(self):
           self.label.setText(self.line_edit.text())


   # Register the custom tab
   EDITOR_EXTEND_TAB.update({"My Custom Tab": TestUI})

   # Start the editor with the custom tab
   start_editor()

How It Works
------------

1. Import ``EDITOR_EXTEND_TAB`` from ``pybreeze``.
2. Create a class that extends ``QWidget`` (or any QWidget subclass).
3. Add your widget class to the ``EDITOR_EXTEND_TAB`` dictionary with a display name as the key.
4. Call ``start_editor()`` -- your tab will appear alongside the default tabs.

.. note::

   You must register your custom tabs in ``EDITOR_EXTEND_TAB`` **before** calling
   ``start_editor()``, as the tabs are loaded during window initialization.

Advanced: Plugin-Based Tabs
----------------------------

You can also add custom tabs via the plugin system by placing a plugin file
in the ``jeditor_plugins/`` directory:

.. code-block:: python

   # jeditor_plugins/my_custom_tab.py
   from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit
   from pybreeze import EDITOR_EXTEND_TAB


   class MyToolWidget(QWidget):
       def __init__(self):
           super().__init__()
           layout = QVBoxLayout(self)
           self.text_edit = QTextEdit()
           self.text_edit.setPlaceholderText("My custom tool...")
           layout.addWidget(self.text_edit)


   EDITOR_EXTEND_TAB.update({"My Tool": MyToolWidget})

This plugin will be auto-discovered and loaded when PyBreeze starts.
