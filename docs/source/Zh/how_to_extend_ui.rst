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
2. 建立繼承 ``QWidget``\ （或任何 QWidget 子類別）的類別。
3. 將您的元件類別加入 ``EDITOR_EXTEND_TAB`` 字典，以顯示名稱作為鍵值。
4. 呼叫 ``start_editor()`` -- 您的分頁將與預設分頁一起顯示。

.. note::

   您必須在呼叫 ``start_editor()`` **之前** 在 ``EDITOR_EXTEND_TAB`` 中註冊自訂分頁，
   因為分頁在視窗初始化時載入。

建構子拋出例外的元件只會少掉它自己的分頁：錯誤會記入日誌，IDE 照常啟動。

關閉前先詢問
------------

可能有未儲存內容的分頁可以表明這一點。為元件加上 ``may_close()`` 方法，可以關閉時回傳 ``True``：
關閉它的分頁或 IDE 時會先問它，回傳 ``False`` 就保持開啟。在這裡詢問使用者，就像 PyBreeze
自己的提示詞編輯器與架構圖編輯器一樣：

.. code-block:: python

   from PySide6.QtWidgets import QMessageBox, QTextEdit, QVBoxLayout, QWidget


   class NotesTab(QWidget):
       def __init__(self):
           super().__init__()
           self.text = QTextEdit()
           QVBoxLayout(self).addWidget(self.text)

       def may_close(self) -> bool:
           if not self.text.document().isModified():
               return True
           reply = QMessageBox.question(self, "筆記未儲存", "要關閉並捨棄筆記嗎？")
           return reply == QMessageBox.StandardButton.Yes

拋出例外的 ``may_close()`` 視為同意（會記入日誌）：它不能讓 IDE 關不掉。

進階：基於外掛的分頁
---------------------

您也可以透過外掛系統新增自訂分頁，將外掛檔案放在 ``jeditor_plugins/`` 目錄中（見 :doc:`menu_plugins`）。
在外掛的 ``register()`` 裡註冊分頁：外掛在主視窗建立的過程中載入，早於分頁加入。

.. code-block:: python

   # jeditor_plugins/my_custom_tab.py
   from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit
   from pybreeze import EDITOR_EXTEND_TAB

   PLUGIN_NAME = "我的工具"


   class MyToolWidget(QWidget):
       def __init__(self):
           super().__init__()
           layout = QVBoxLayout(self)
           self.text_edit = QTextEdit()
           self.text_edit.setPlaceholderText("我的自訂工具...")
           layout.addWidget(self.text_edit)


   def register() -> None:
       EDITOR_EXTEND_TAB.update({"我的工具": MyToolWidget})

PyBreeze 從 ``jeditor_plugins/`` 中有這個外掛的資料夾啟動時，會自動探索並載入它。
