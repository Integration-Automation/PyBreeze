"""Start PyBreeze with one more tab of your own: the tutorial's smallest extension."""
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from pybreeze import EDITOR_EXTEND_TAB, start_editor


class HelloTab(QWidget):
    """Type a name, press the button, be greeted."""

    def __init__(self) -> None:
        super().__init__()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Your name")
        self.greet_button = QPushButton("Greet")
        self.greet_button.clicked.connect(self.greet)
        self.greeting = QLabel("")
        layout = QVBoxLayout(self)
        layout.addWidget(self.name_edit)
        layout.addWidget(self.greet_button)
        layout.addWidget(self.greeting)
        layout.addStretch(1)

    def greet(self) -> None:
        self.greeting.setText(f"Hello, {self.name_edit.text() or 'world'}!")


if __name__ == "__main__":
    # Registered before the editor starts: the tabs are added as the window is built
    EDITOR_EXTEND_TAB["Hello"] = HelloTab
    start_editor()
