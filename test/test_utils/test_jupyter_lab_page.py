"""The JupyterLab tab's page stays on the lab; a link elsewhere opens in the system's browser."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWidgets import QApplication

from pybreeze.pybreeze_ui.jupyter_lab_gui import lab_page

_CLICKED = QWebEnginePage.NavigationType.NavigationTypeLinkClicked
_LAB = "http://localhost:8888/lab"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def opened(monkeypatch):
    """What was handed to the system's browser."""
    handed: list = []
    monkeypatch.setattr(lab_page.QDesktopServices, "openUrl", lambda url: handed.append(url.toString()) or True)
    return handed


@pytest.fixture
def page(app):
    made = lab_page.LabPage()
    made.lab_url = QUrl(_LAB)
    yield made
    made.deleteLater()


class TestInTheView:
    @pytest.mark.parametrize("url", [_LAB, "http://localhost:8888/lab/tree/notes.ipynb", "http://localhost:8888/api"])
    def test_the_lab_s_own_pages_load_here(self, page, opened, url):
        assert page.acceptNavigationRequest(QUrl(url), _CLICKED, True) is True
        assert opened == []

    @pytest.mark.parametrize("url", ["https://example.org/docs", "http://localhost:9999/lab", "https://localhost:8888/lab"])
    def test_a_page_elsewhere_opens_outside_and_not_here(self, page, opened, url):
        # Another site, another port, another scheme: none of them is the lab
        assert page.acceptNavigationRequest(QUrl(url), _CLICKED, True) is False
        assert opened == [url]

    def test_a_frame_inside_the_lab_loads_what_it_loads(self, page, opened):
        assert page.acceptNavigationRequest(QUrl("https://example.org/embed"), _CLICKED, False) is True
        assert opened == []

    def test_before_the_lab_is_there_the_view_may_start(self, app, opened):
        starting = lab_page.LabPage()

        assert starting.acceptNavigationRequest(QUrl("about:blank"), _CLICKED, True) is True
        assert opened == []
        starting.deleteLater()


class TestANewTab:
    """JupyterLab opens a notebook's links in a new tab: with no page to give it, the link did nothing."""

    @pytest.mark.parametrize("url", ["https://example.org/docs", "http://localhost:8888/lab/tree/other.ipynb"])
    def test_its_link_opens_outside(self, page, opened, url):
        new_tab = page.createWindow(QWebEnginePage.WebWindowType.WebBrowserTab)

        assert new_tab.acceptNavigationRequest(QUrl(url), _CLICKED, True) is False
        assert opened == [url]

    @pytest.mark.parametrize("url", ["file:///C:/Windows/System32/calc.exe", "javascript:alert(1)", "ms-settings:"])
    def test_what_is_no_web_link_is_not_opened(self, page, opened, url):
        new_tab = page.createWindow(QWebEnginePage.WebWindowType.WebBrowserTab)

        assert new_tab.acceptNavigationRequest(QUrl(url), _CLICKED, True) is False
        assert opened == []


def test_the_tab_s_view_uses_the_page_and_is_given_the_lab(app, monkeypatch):
    from pybreeze.pybreeze_ui.jupyter_lab_gui import jupyter_lab_widget

    monkeypatch.setattr(jupyter_lab_widget.JupyterLauncherThread, "start", lambda self: None)
    tab = jupyter_lab_widget.JupyterLabWidget()
    monkeypatch.setattr(tab.browser, "setUrl", lambda _url: None)

    tab.load_lab(_LAB)

    assert tab.browser.page() is tab.lab_page
    assert tab.lab_page.lab_url == QUrl(_LAB)
    tab.close()
