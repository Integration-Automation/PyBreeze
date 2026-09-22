from __future__ import annotations

import sys

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget, QLabel
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.jupyter_lab_gui.jupyter_lab_thread import JupyterLauncherThread
from pybreeze.pybreeze_ui.thread_keeper import let_run_out
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
        # status_label is removed once the lab loads; a late status/error signal
        # could still arrive, so guard against the None it leaves behind.
        if self.status_label:
            self.status_label.setText(text)

    def load_lab(self, url):
        if self.status_label:
            self.status_label.setParent(None)
            self.status_label.deleteLater()
            self.status_label = None

        self.browser.setUrl(QUrl(url))
        self.browser.show()

    def show_error(self, msg):
        if self.status_label:
            self.status_label.setText(language_wrapper.language_word_dict.get("jupyterlab_init_failed"))
        pybreeze_logger.error(msg)

    def closeEvent(self, event):
        """Stop the server with the tab.

        The server outlives the launcher thread, which ends as soon as the lab
        is ready, so stopping only a thread that is still running left a
        JupyterLab process behind for every tab that had finished loading --
        holding its port, and reachable for as long as the machine was up.
        """
        if self.thread.isRunning():
            # Still installing or starting: cut off from this tab first, so a
            # late status or error cannot reach it, and kept until it ends
            # rather than waited for -- an install can take minutes, and a
            # QThread destroyed while running aborts the process. (Not
            # blockSignals: that would also block the ``finished`` that lets
            # the keeper release it.)
            let_run_out(self.thread, self.thread.status_update,
                        self.thread.server_ready, self.thread.error_occurred)
        # After this the launcher starts no server, even one still installing.
        self.thread.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    win = JupyterLabWidget()
    win.showMaximized()

    sys.exit(app.exec())
