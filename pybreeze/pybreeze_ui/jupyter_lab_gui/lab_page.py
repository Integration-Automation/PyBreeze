"""The JupyterLab tab's web page: it stays on the lab, and a link elsewhere opens in the system's browser.

JupyterLab opens a notebook's links in a new tab (``target="_blank"``), and a
view with no ``createWindow`` of its own ignores that: a link in a notebook did
nothing. A link opened in the view itself took it away from the lab, to a site
the IDE then showed with none of a browser's own controls. Only ``http`` and
``https`` go to the system's browser; any other scheme is not opened.
"""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWebEngineCore import QWebEnginePage

from pybreeze.utils.logging.logger import pybreeze_logger

# The schemes a link may open in the system's browser with
_OPENED_OUTSIDE = ("http", "https")


def open_outside(url: QUrl) -> bool:
    """Open *url* in the system's browser when it is an ``http`` or ``https`` link; whether it was."""
    if url.scheme().lower() not in _OPENED_OUTSIDE:
        pybreeze_logger.info("JupyterLab link not opened: %s is no web link", url.scheme() or "no scheme")
        return False
    return QDesktopServices.openUrl(url)


class _NewTab(QWebEnginePage):
    """The page a link asks a new tab for, never shown: its first navigation opens outside, and it goes."""

    def acceptNavigationRequest(self, url: QUrl, _navigation_type, _is_main_frame: bool) -> bool:
        open_outside(url)
        self.deleteLater()
        return False


class LabPage(QWebEnginePage):
    """A page that keeps its view on the lab it was given (``lab_url``)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # Where the lab is served; until it is set, the view is only starting
        self.lab_url: QUrl | None = None

    def _in_lab(self, url: QUrl) -> bool:
        lab = self.lab_url
        return lab is None or (url.scheme(), url.host(), url.port()) == (lab.scheme(), lab.host(), lab.port())

    def acceptNavigationRequest(self, url: QUrl, navigation_type, is_main_frame: bool) -> bool:
        """The lab's own pages load here; a page elsewhere, in a frame of its own or not, is opened outside.

        A frame inside the lab (a notebook output) loads what it loads, as in a browser.
        """
        if not is_main_frame or self._in_lab(url):
            return True
        open_outside(url)
        return False

    def createWindow(self, _window_type) -> QWebEnginePage:
        """A link for a new tab opens in the system's browser, the lab's own included."""
        return _NewTab(self)
