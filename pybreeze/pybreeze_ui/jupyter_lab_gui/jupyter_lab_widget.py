import sys

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from pybreeze.pybreeze_ui.jupyter_lab_gui.jupyer_lab_thread import JupyterServerThread


class JupyterLabWidget(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        self.browser = QWebEngineView()
        layout.addWidget(self.browser)

        # 啟動 Jupyter server thread
        self.thread = JupyterServerThread()
        self.thread.server_ready.connect(self.load_lab)
        self.thread.start()

    def load_lab(self, url: str):
        """Load JupyterLab URL into WebEngine"""

        if not url:
            print("Invalid JupyterLab URL")
            return

        print("JupyterLab running at:", url)

        qurl = QUrl(url)

        if not qurl.isValid():
            print("Invalid QUrl:", url)
            return

        self.browser.setUrl(qurl)

    def closeEvent(self, event):

        if hasattr(self, "thread") and self.thread.isRunning():
            self.thread.stop()
            self.thread.quit()
            self.thread.wait()

        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    win = JupyterLabWidget()
    win.show()

    sys.exit(app.exec())
