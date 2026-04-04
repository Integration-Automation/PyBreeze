import sys

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget, QLabel
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.jupyter_lab_gui.jupyter_lab_thread import JupyterLauncherThread
from pybreeze.utils.logging.logger import pybreeze_logger


class JupyterLabWidget(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        self.status_label = QLabel(language_wrapper.language_word_dict.get("jupyterlab_init"))
        layout.addWidget(self.status_label)

        self.browser = QWebEngineView()
        self.browser.hide()
        layout.addWidget(self.browser)

        self.thread = JupyterLauncherThread()
        self.thread.status_update.connect(self.update_status)
        self.thread.server_ready.connect(self.load_lab)
        self.thread.error_occurred.connect(self.show_error)
        self.thread.start()

    def update_status(self, text):
        self.status_label.setText(text)

    def load_lab(self, url):
        if self.status_label:
            self.status_label.setParent(None)
            self.status_label.deleteLater()
            self.status_label = None

        self.browser.setUrl(QUrl(url))
        self.browser.show()

    def show_error(self, msg):
        self.status_label.setText(language_wrapper.language_word_dict.get("jupyterlab_init_failed"))
        pybreeze_logger.error(msg)

    def closeEvent(self, event):
        if self.thread.isRunning():
            self.thread.stop()
            self.thread.quit()
            self.thread.wait()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    win = JupyterLabWidget()
    win.showMaximized()

    sys.exit(app.exec())
