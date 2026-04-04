如何擴充 UI
============

PyBreeze 支援使用 ``EDITOR_EXTEND_TAB`` 字典擴充 UI 自訂分頁。
您可以將任何 PySide6 ``QWidget`` 作為新分頁加入編輯器。

基本範例
--------

.. code-block:: python

   from PySide6.QtWidgets import QWidget, QGridLayout, QLineEdit, QPushButton, QLabel
   from pybreeze import start_editor, EDITOR_EXTEND_TAB


   class TestUI(QWidget):
       """一個簡單的自訂分頁元件。"""

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


   # 註冊自訂分頁
   EDITOR_EXTEND_TAB.update({"我的自訂分頁": TestUI})

   # 啟動編輯器，包含自訂分頁
   start_editor()

運作原理
--------

1. 從 ``pybreeze`` 匯入 ``EDITOR_EXTEND_TAB``。
2. 建立繼承 ``QWidget``（或任何 QWidget 子類別）的類別。
3. 將您的元件類別加入 ``EDITOR_EXTEND_TAB`` 字典，以顯示名稱作為鍵值。
4. 呼叫 ``start_editor()`` -- 您的分頁將與預設分頁一起顯示。

.. note::

   您必須在呼叫 ``start_editor()`` **之前** 在 ``EDITOR_EXTEND_TAB`` 中註冊自訂分頁，
   因為分頁在視窗初始化時載入。

進階：基於外掛的分頁
---------------------

您也可以透過外掛系統新增自訂分頁，將外掛檔案放在 ``jeditor_plugins/`` 目錄中：

.. code-block:: python

   # jeditor_plugins/my_custom_tab.py
   from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit
   from pybreeze import EDITOR_EXTEND_TAB


   class MyToolWidget(QWidget):
       def __init__(self):
           super().__init__()
           layout = QVBoxLayout(self)
           self.text_edit = QTextEdit()
           self.text_edit.setPlaceholderText("我的自訂工具...")
           layout.addWidget(self.text_edit)


   EDITOR_EXTEND_TAB.update({"我的工具": MyToolWidget})

此外掛會在 PyBreeze 啟動時自動探索並載入。
