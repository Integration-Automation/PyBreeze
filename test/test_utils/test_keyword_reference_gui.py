"""The Automation Keywords tab: each framework's keywords as the installed package gives them."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication
from je_editor import JEditorExecException, language_wrapper

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.design.tokens import State
from pybreeze.pybreeze_ui.tools_gui import keyword_reference_gui
from pybreeze.pybreeze_ui.tools_gui.keyword_reference_gui import KeywordReadThread, KeywordReferenceGUI
from pybreeze.utils.exception.exception_tags import language_probe_not_installed_error
from pybreeze.utils.exception.exceptions import LanguageServiceException
from pybreeze.utils.language_service.framework_profiles import PROFILES, profile_of
from pybreeze.utils.language_service.keyword_metadata import metadata_from_dict

FIXTURES = Path(__file__).parent / "fixtures" / "language_service"
METADATA = {
    profile.framework: metadata_from_dict(json.loads(
        (FIXTURES / f"{profile.framework}.metadata.json").read_text(encoding="utf-8")))
    for profile in PROFILES
}


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


def _word(key: str) -> str:
    return language_wrapper.language_word_dict.get(key)


def _until(condition, seconds: float = 10) -> None:
    """Let the application run until *condition* holds."""
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, "what was waited for did not happen"
        QApplication.processEvents()
        time.sleep(0.005)


class _Frameworks:
    """Stands in for the installed frameworks: what each answers, and who asked."""

    def __init__(self) -> None:
        self.asked: list[tuple[str, str]] = []
        self.missing: set[str] = set()
        self.hold = threading.Event()
        self.hold.set()

    def read(self, profile, interpreter):
        self.asked.append((profile.framework, interpreter))
        self.hold.wait(10)
        if profile.framework in self.missing:
            raise LanguageServiceException(language_probe_not_installed_error.format(framework=profile.framework))
        return METADATA[profile.framework]


class _Main:
    python_compiler = "the-chosen-python"


@pytest.fixture
def frameworks(monkeypatch) -> _Frameworks:
    stand_in = _Frameworks()
    monkeypatch.setattr(keyword_reference_gui, "read_metadata", stand_in.read)
    return stand_in


@pytest.fixture
def tab(app, frameworks):
    gui = KeywordReferenceGUI(_Main())
    yield gui
    frameworks.hold.set()
    _until(lambda: not gui.is_reading() and not keyword_reference_gui._READING)
    gui.close()
    gui.deleteLater()


def _shown(tab: KeywordReferenceGUI) -> KeywordReferenceGUI:
    """Show *tab* and wait for the keywords it reads at first sight."""
    tab.show()
    _until(lambda: tab.status.state is not State.NEUTRAL)
    return tab


def _listed(tab: KeywordReferenceGUI) -> list[str]:
    return [tab.keyword_list.item(row).text() for row in range(tab.keyword_list.count())]


def _choose(tab: KeywordReferenceGUI, framework: str) -> None:
    tab.framework_select.setCurrentIndex(tab.framework_select.findData(profile_of(framework)))


# ----------------------------------------------------------------------
# Reading
# ----------------------------------------------------------------------

def test_nothing_is_read_before_the_tab_is_seen(tab, frameworks):
    assert frameworks.asked == []
    assert _listed(tab) == []
    assert [tab.framework_select.itemText(row) for row in range(tab.framework_select.count())] == [
        "WebRunner", "AutoControl", "LoadDensity"]


def test_the_first_framework_is_read_when_the_tab_is_first_seen(tab, frameworks):
    _shown(tab)

    assert frameworks.asked == [("je_web_runner", "the-chosen-python")]
    assert _listed(tab) == ["WR_SaveTestObject", "WR_add_cookie", "WR_get_webdriver_manager", "WR_quit",
                            "WR_set_page_load_timeout", "WR_to_url"]


def test_the_status_says_the_version_the_count_and_what_the_editor_offers(tab):
    _shown(tab)

    assert tab.status.state is State.SUCCESS
    assert tab.status.text() == _word("keyword_reference_ready").format(
        framework="WebRunner 0.0.66", count=6,
        capabilities=" · ".join(_word(f"keyword_reference_capability_{name}")
                                for name in ("completion", "diagnostics", "hover", "definition")))


def test_showing_the_tab_again_reads_nothing_again(tab, frameworks):
    _shown(tab)
    tab.hide()
    tab.show()
    QApplication.processEvents()

    assert len(frameworks.asked) == 1


def test_another_framework_is_read_when_it_is_chosen_and_kept_once_read(tab, frameworks):
    _shown(tab)

    _choose(tab, "je_auto_control")
    _until(lambda: "AC_write" in _listed(tab))
    _choose(tab, "je_web_runner")
    _choose(tab, "je_auto_control")
    QApplication.processEvents()

    assert [framework for framework, _interpreter in frameworks.asked] == ["je_web_runner", "je_auto_control"]
    assert _listed(tab)[0] == "AC_click_mouse"
    assert "AutoControl 0.0.178" in tab.status.text()


def test_a_framework_that_is_not_installed_is_said_in_the_status_and_lists_nothing(tab, frameworks):
    frameworks.missing.add("je_web_runner")

    _shown(tab)

    assert tab.status.state is State.ERROR
    assert "je_web_runner" in tab.status.text()
    assert _listed(tab) == []
    assert not tab.copy_button.isEnabled()


def test_read_again_asks_the_framework_once_more(tab, frameworks):
    frameworks.missing.add("je_web_runner")
    _shown(tab)
    frameworks.missing.clear()

    tab.refresh_button.click()
    _until(lambda: tab.status.state is State.SUCCESS)

    assert len(frameworks.asked) == 2
    assert "WR_quit" in _listed(tab)


def test_one_framework_is_read_at_a_time_and_the_one_chosen_meanwhile_comes_next(tab, frameworks):
    frameworks.hold.clear()
    tab.show()
    _until(lambda: frameworks.asked == [("je_web_runner", "the-chosen-python")])

    _choose(tab, "je_load_density")
    QApplication.processEvents()
    assert len(frameworks.asked) == 1
    assert tab.status.text() == _word("keyword_reference_loading").format(framework="LoadDensity")

    frameworks.hold.set()
    _until(lambda: "LD_start_test" in _listed(tab))

    assert [framework for framework, _interpreter in frameworks.asked] == ["je_web_runner", "je_load_density"]


def test_a_framework_chosen_the_moment_another_answers_is_still_read(tab, frameworks):
    # The reader's thread is still running for a moment after it has answered
    _shown(tab)
    for _round in range(20):
        for framework in ("je_auto_control", "je_load_density"):
            tab._metadata.clear()
            _choose(tab, framework)
            _until(lambda: not tab.is_reading())
            _until(lambda: tab.status.state is State.SUCCESS)
            assert tab.selected_keyword().name.startswith(profile_of(framework).keyword_prefix)


def test_without_a_chosen_interpreter_the_one_a_run_would_use_is_asked(app, frameworks, monkeypatch):
    monkeypatch.setattr(keyword_reference_gui, "default_interpreter", lambda: "the-default-python")
    gui = KeywordReferenceGUI(None)
    try:
        assert gui.read() is True
        _until(lambda: gui.status.state is State.SUCCESS)

        assert frameworks.asked == [("je_web_runner", "the-default-python")]
    finally:
        gui.close()
        gui.deleteLater()


def test_with_no_interpreter_to_ask_the_tab_says_so_and_starts_nothing(app, frameworks, monkeypatch):
    def none_found():
        raise JEditorExecException("no Python on PATH")

    monkeypatch.setattr(keyword_reference_gui, "default_interpreter", none_found)
    gui = KeywordReferenceGUI(None)
    try:
        assert gui.read() is False

        assert gui.status.state is State.ERROR
        assert gui.status.text() == _word("keyword_reference_no_interpreter")
        assert frameworks.asked == []
    finally:
        gui.close()
        gui.deleteLater()


def test_a_reader_outlives_a_tab_that_goes_while_it_reads(app, frameworks):
    frameworks.hold.clear()
    gui = KeywordReferenceGUI(_Main())
    gui.read()
    (reader,) = keyword_reference_gui._READING
    _until(lambda: frameworks.asked != [])

    gui.close()
    gui.deleteLater()
    del gui
    QApplication.processEvents()

    assert reader.isRunning()
    assert reader in keyword_reference_gui._READING
    frameworks.hold.set()
    _until(lambda: reader not in keyword_reference_gui._READING)
    assert reader.wait(5000)


def test_the_reader_says_what_it_read_or_why_it_could_not(app, frameworks):
    answers: list = []
    read = KeywordReadThread(profile_of("je_load_density"), "python")
    read.loaded.connect(answers.append)
    read.start_kept()
    _until(lambda: answers != [])
    assert answers == [METADATA["je_load_density"]]

    frameworks.missing.add("je_load_density")
    failures: list = []
    failed = KeywordReadThread(profile_of("je_load_density"), "python")
    failed.failed.connect(lambda framework, reason: failures.append((framework, reason)))
    failed.start_kept()
    _until(lambda: failures != [])
    assert failures == [("je_load_density", language_probe_not_installed_error.format(framework="je_load_density"))]
    _until(lambda: not keyword_reference_gui._READING)


# ----------------------------------------------------------------------
# Showing
# ----------------------------------------------------------------------

def test_the_selected_keyword_shows_its_signature_documentation_and_where_it_is_defined(tab):
    _shown(tab)
    tab.keyword_list.setCurrentRow(_listed(tab).index("WR_to_url"))

    keyword = METADATA["je_web_runner"].keyword("WR_to_url")
    shown = tab.detail_view.toPlainText()
    assert shown.startswith("WR_to_url(url: str)\n\n")
    assert keyword.doc.strip() in shown
    assert shown.endswith(_word("keyword_reference_defined_in").format(
        file=keyword.source_file, line=keyword.source_line))


def test_the_first_keyword_is_selected_so_the_tab_is_never_blank(tab):
    _shown(tab)

    assert tab.selected_keyword().name == "WR_SaveTestObject"
    assert tab.detail_view.toPlainText() != ""
    assert tab.copy_button.isEnabled()


@pytest.mark.parametrize(("typed", "listed"), [
    ("cookie", ["WR_add_cookie"]),
    ("QUIT", ["WR_quit"]),
    ("webdriver", ["WR_get_webdriver_manager"]),
    ("  to_url ", ["WR_to_url"]),
    ("no keyword says this", []),
])
def test_the_filter_keeps_the_keywords_whose_name_or_documentation_has_what_is_typed(tab, typed, listed):
    _shown(tab)

    tab.search_edit.setText(typed)

    assert [name for name in _listed(tab) if name in listed] == listed
    if not listed:
        assert _listed(tab) == []
        assert tab.detail_view.toPlainText() == ""
        assert not tab.copy_button.isEnabled()


def test_clearing_the_filter_lists_every_keyword_again(tab):
    _shown(tab)
    tab.search_edit.setText("cookie")

    tab.search_edit.clear()

    assert len(_listed(tab)) == 6


@pytest.mark.parametrize(("keyword", "action"), [
    ("WR_to_url", '["WR_to_url", {"url": null}]'),
    ("WR_quit", '["WR_quit"]'),
    ("WR_get_webdriver_manager", '["WR_get_webdriver_manager", {"webdriver_name": null}]'),
])
def test_a_keyword_is_copied_as_an_action_with_its_required_parameters_named(tab, keyword, action):
    _shown(tab)
    tab.keyword_list.setCurrentRow(_listed(tab).index(keyword))

    assert tab.copy_action() == action
    assert QApplication.clipboard().text() == action
    assert json.loads(action)[0] == keyword


def test_with_no_keyword_selected_nothing_is_copied(tab):
    assert tab.copy_action() is None


def test_the_tab_is_one_of_the_tools(app):
    from pybreeze.pybreeze_ui.menu.tools import tools_menu

    widget = tools_menu.build_tool_widget(_Main(), "KeywordReference")
    try:
        assert isinstance(widget, KeywordReferenceGUI)
    finally:
        widget.close()
        widget.deleteLater()
