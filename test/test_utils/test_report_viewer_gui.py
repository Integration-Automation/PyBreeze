"""The report viewer: runs of any package in one tree, filtered together, and exported."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QTabWidget, QTreeWidgetItem
from je_editor import language_wrapper

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.design.tokens import State
from pybreeze.pybreeze_ui.report_gui.report_viewer_gui import ReportViewerGUI
from pybreeze.utils.execution_report.report_files import EXPORT_FORMATS, read_report
from pybreeze.utils.execution_report.report_schema import (
    Attachment,
    ErrorDetail,
    ExecutionReport,
    ExecutionResult,
    Status,
)

FIXTURES = Path(__file__).parent / "fixtures" / "reports"
SHOWN = Path(FIXTURES / "pytest.junit.xml")


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture
def viewer(app):
    gui = ReportViewerGUI()
    yield gui
    gui.deleteLater()


def _word(key: str) -> str:
    return language_wrapper.language_word_dict.get(key)


def _open(viewer: ReportViewerGUI, *names: str) -> int:
    return viewer.open_files([str(FIXTURES / name) for name in names])


def _names(item: QTreeWidgetItem) -> list[str]:
    return [item.child(row).text(0) for row in range(item.childCount())]


def _runs(viewer: ReportViewerGUI) -> list[QTreeWidgetItem]:
    tree = viewer.result_tree
    return [tree.topLevelItem(row) for row in range(tree.topLevelItemCount())]


def _export_format(key: str) -> str:
    wanted = next(each for each in EXPORT_FORMATS if each.key == key)
    return f"{_word(wanted.label_key)} (*.{wanted.extension})"


# ----------------------------------------------------------------------
# Opening
# ----------------------------------------------------------------------

def test_with_nothing_open_the_viewer_says_what_it_opens(viewer):
    assert viewer.result_tree.topLevelItemCount() == 0
    assert viewer.summary.text() == _word("report_viewer_nothing_open")
    assert not viewer.export_button.isEnabled() and not viewer.close_button.isEnabled()
    assert viewer.export_report() is None and viewer.close_report() is False


def test_runs_of_different_packages_are_opened_into_one_tree(viewer):
    assert _open(viewer, "api_success.json", "web_failure.json", "desktop_success.xml", "load_success.json",
                 "pytest.junit.xml") == 5

    assert [run.text(0) for run in _runs(viewer)] == ["api", "web", "desktop", "load", "pytest tests"]
    assert [run.text(1) for run in _runs(viewer)] == [
        _word("report_status_failed"), _word("report_status_error"), _word("report_status_error"),
        _word("report_status_failed"), _word("report_status_error")]
    assert [report.framework for report in viewer.reports()] == [
        "je_api_testka", "je_web_runner", "je_auto_control", "je_load_density", "junit"]


def test_a_run_is_open_to_its_results_and_a_suite_is_filled_when_it_is_opened(viewer):
    _open(viewer, "pytest.junit.xml")
    (run,) = _runs(viewer)

    assert run.isExpanded() and _names(run) == ["pytest"]
    suite = run.child(0)
    assert suite.childCount() == 0
    assert suite.childIndicatorPolicy() is QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator

    suite.setExpanded(True)

    assert _names(suite) == ["test_logs_in", "test_wrong_password", "test_avatar", "test_export", "slow"]
    assert [suite.child(row).text(1) for row in range(4)] == [
        _word("report_status_passed"), _word("report_status_failed"), _word("report_status_error"),
        _word("report_status_skipped")]
    assert suite.child(1).text(2) == "0.30"


def test_the_files_are_asked_for_and_opened(viewer, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", staticmethod(lambda *_a, **_k: (
        [str(FIXTURES / "api_success.json"), str(FIXTURES / "load_failure.json")], "")))

    assert viewer.open_reports() == 2
    assert len(_runs(viewer)) == 2

    monkeypatch.setattr(QFileDialog, "getOpenFileNames", staticmethod(lambda *_a, **_k: ([], "")))
    assert viewer.open_reports() == 0


def test_a_file_that_is_no_report_is_said_by_its_name_and_the_others_are_opened(viewer, tmp_path):
    (tmp_path / "notes.json").write_text('{"just": "notes"}', encoding="utf-8")

    opened = viewer.open_files([str(tmp_path / "notes.json"), str(FIXTURES / "api_success.json"),
                                str(tmp_path / "gone.xml")])

    assert opened == 1 and len(_runs(viewer)) == 1
    assert viewer.summary.state is State.ERROR
    assert viewer.summary.text().startswith("gone.xml")
    assert str(tmp_path) not in viewer.summary.text()


# ----------------------------------------------------------------------
# What is selected
# ----------------------------------------------------------------------

def test_a_run_shows_what_ran_it_how_it_ended_and_how_many_of_each(viewer):
    _open(viewer, "pytest.junit.xml")

    shown = viewer.details.detail_view.toPlainText().splitlines()

    assert shown[:3] == ["pytest tests", "junit", _word("report_status_error")]
    assert f"{_word('report_status_passed')}: 2" in shown and f"{_word('report_status_skipped')}: 1" in shown


def test_a_result_shows_how_it_ended_why_and_what_it_printed(viewer):
    _open(viewer, "pytest.junit.xml")
    suite = _runs(viewer)[0].child(0)
    suite.setExpanded(True)

    viewer.result_tree.setCurrentItem(suite.child(1))

    details = viewer.details.detail_view.toPlainText()
    assert details.startswith("test_wrong_password\n\ntest · " + _word("report_status_failed"))
    assert "AssertionError: assert 200 == 401" in details and "E       assert 200 == 401" in details
    assert viewer.details.output_view.toPlainText() == "POST /login -> 200"
    assert '"classname": "tests.test_login"' in viewer.details.raw_view.toPlainText()


def test_a_packages_own_record_is_kept_beside_the_result(viewer):
    _open(viewer, "web_success.json")

    viewer.result_tree.setCurrentItem(_runs(viewer)[0].child(0))

    raw = viewer.details.raw_view.toPlainText()
    assert '"function_name": "web runner manager new_driver"' in raw
    assert "'webdriver_name': 'chrome'" in raw


def test_what_a_result_left_behind_is_listed_and_markup_in_a_report_stays_text(viewer):
    viewer.show_report(ExecutionReport("mcp", name="<b>session</b>", results=(ExecutionResult(
        id="1", name="<img src=x>", status=Status.FAILED, stdout="<script>alert(1)</script>",
        error=ErrorDetail("<i>bad</i>"),
        attachments=(Attachment("screenshot", "C:/runs/shot.png", "image/png"), Attachment("log", "run.log"))),)))

    viewer.result_tree.setCurrentItem(_runs(viewer)[0].child(0))

    assert _runs(viewer)[0].text(0) == "<b>session</b>"
    assert viewer.details.attachments_view.toPlainText() == "screenshot · C:/runs/shot.png · image/png\nlog · run.log"
    assert viewer.details.output_view.toPlainText() == "<script>alert(1)</script>"
    assert "<i>bad</i>" in viewer.details.detail_view.toPlainText()


# ----------------------------------------------------------------------
# Filtering
# ----------------------------------------------------------------------

def test_the_summary_counts_what_is_shown(viewer):
    _open(viewer, "pytest.junit.xml", "load_success.json")

    assert viewer.summary.state is State.ERROR
    assert viewer.summary.text().startswith(_word("report_viewer_summary").format(
        shown=8, every=8, runs=2, seconds="1.25"))
    assert f"{_word('report_status_failed')}: 2" in viewer.summary.text()


def test_unticking_an_ending_takes_those_results_out_of_every_run(viewer):
    _open(viewer, "pytest.junit.xml", "load_success.json")

    viewer.filter_bar.status_boxes[Status.PASSED].setChecked(False)

    runs = _runs(viewer)
    assert [run.text(0) for run in runs] == ["pytest tests", "load"]
    assert _names(runs[1]) == ["POST /login"]
    assert viewer.summary.text().startswith(_word("report_viewer_summary").format(
        shown=4, every=8, runs=2, seconds="0.35"))


def test_a_run_with_nothing_left_to_show_is_not_listed(viewer):
    _open(viewer, "pytest.junit.xml", "load_success.json")

    viewer.filter_bar.text_edit.setText("WRONG_password")

    (run,) = _runs(viewer)
    assert run.text(0) == "pytest tests"
    run.child(0).setExpanded(True)
    assert _names(run.child(0)) == ["test_wrong_password"]


def test_only_what_took_long_enough_is_shown(viewer):
    _open(viewer, "pytest.junit.xml")

    viewer.filter_bar.seconds_spin.setValue(0.45)

    suite = _runs(viewer)[0].child(0)
    suite.setExpanded(True)
    assert _names(suite) == ["slow"]
    assert viewer.summary.state is State.SUCCESS


def test_the_packages_of_the_open_runs_are_offered_and_one_can_be_chosen(viewer):
    _open(viewer, "pytest.junit.xml", "load_success.json", "web_success.json")
    choices = viewer.filter_bar.framework_select

    assert [choices.itemText(row) for row in range(choices.count())] == [
        _word("report_viewer_every_framework"), "je_load_density", "je_web_runner", "junit"]

    choices.setCurrentIndex(choices.findData("je_web_runner"))

    assert [run.text(0) for run in _runs(viewer)] == ["web"]
    assert viewer.filter_bar.wanted().frameworks == {"je_web_runner"}


def test_with_every_ending_unticked_nothing_is_shown_and_the_runs_stay_open(viewer):
    _open(viewer, "load_success.json")

    for box in viewer.filter_bar.status_boxes.values():
        box.setChecked(False)

    assert _runs(viewer) == []
    assert viewer.details.detail_view.toPlainText() == ""
    assert len(viewer.reports()) == 1 and viewer.export_button.isEnabled()


# ----------------------------------------------------------------------
# Closing and exporting
# ----------------------------------------------------------------------

def test_the_selected_run_is_closed_and_its_package_is_no_longer_offered(viewer):
    _open(viewer, "pytest.junit.xml", "load_success.json")
    viewer.result_tree.setCurrentItem(_runs(viewer)[1])

    assert viewer.close_report() is True

    assert [report.framework for report in viewer.reports()] == ["junit"]
    assert viewer.filter_bar.framework_select.count() == 2


@pytest.mark.parametrize(("wanted", "suffix"), [("json", ".json"), ("junit", ".xml"), ("html", ".html")])
def test_the_selected_run_is_exported_in_the_format_chosen(viewer, monkeypatch, tmp_path, wanted, suffix):
    _open(viewer, "pytest.junit.xml", "web_success.json")
    viewer.result_tree.setCurrentItem(_runs(viewer)[1])
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(
        lambda *_a, **_k: (str(tmp_path / "exported"), _export_format(wanted))))

    saved = viewer.export_report()

    assert saved == str(tmp_path / f"exported{suffix}")
    back = read_report(Path(saved))
    assert [result.name for result in back.walk() if not result.children] == [
        result.name for result in viewer.reports()[1].results]
    assert viewer.summary.text() == _word("report_viewer_exported").format(file=f"exported{suffix}")


def test_the_export_dialog_offers_the_three_formats_and_starts_with_the_runs_name(viewer, monkeypatch):
    seen: list = []

    def dialog(_parent, title, name, filters):
        seen.append((title, name, filters))
        return "", ""

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(dialog))
    _open(viewer, "web_success.json")

    assert viewer.export_report() is None

    assert seen == [(_word("report_viewer_export_title"), "web",
                     ";;".join(_export_format(key) for key in ("json", "junit", "html")))]


def test_an_export_that_cannot_be_written_is_said_without_its_path(viewer, monkeypatch, tmp_path):
    _open(viewer, "web_success.json")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(
        lambda *_a, **_k: (str(tmp_path / "no_such_folder" / "out.json"), _export_format("json"))))

    assert viewer.export_report() is None
    assert viewer.summary.state is State.ERROR
    assert str(tmp_path) not in viewer.summary.text()


def test_with_one_run_open_it_is_the_one_exported_whatever_is_selected(viewer, monkeypatch, tmp_path):
    _open(viewer, "load_success.json")
    viewer.result_tree.setCurrentItem(None)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(
        lambda *_a, **_k: (str(tmp_path / "load.json"), _export_format("json"))))

    assert viewer.export_report() == str(tmp_path / "load.json")


# ----------------------------------------------------------------------
# From other tools
# ----------------------------------------------------------------------

class _Main:
    def __init__(self) -> None:
        self.tab_widget = QTabWidget()


def test_an_mcp_session_is_opened_in_the_viewer(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from pybreeze.pybreeze_ui.mcp_gui.mcp_client_gui import McpClientGUI
    from pybreeze.utils.mcp.mcp_profile import McpServerProfile, save_profiles

    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(QMessageBox, "exec", lambda box: QMessageBox.StandardButton.Yes)
    save_profiles([McpServerProfile("fake", (sys.executable, str(
        Path(__file__).parent / "fixtures" / "mcp" / "fake_server.py")), timeout_seconds=20.0)])
    main = _Main()
    tab = McpClientGUI(main)
    try:
        assert tab.open_in_report_viewer() is None
        tab.connect_server()
        _wait(lambda: not tab.is_busy())
        tab.tools_panel.arguments_edit.setPlainText('{"text": "hello"}')
        tab.call_tool()
        _wait(lambda: not tab.is_busy())

        opened = tab.open_in_report_viewer()

        assert isinstance(opened, ReportViewerGUI)
        assert main.tab_widget.currentWidget() is opened
        assert main.tab_widget.tabText(0) == _word("extend_tools_menu_report_viewer_tab_label")
        (report,) = opened.reports()
        assert (report.framework, [result.name for result in report.results]) == ("mcp", ["echo"])
    finally:
        tab.close()
        tab.deleteLater()


def test_without_a_window_to_open_it_in_a_session_is_not_handed_over(app, tmp_path, monkeypatch):
    from pybreeze.pybreeze_ui.mcp_gui.mcp_client_gui import McpClientGUI
    from pybreeze.utils.mcp.mcp_call_log import McpCallLog
    from pybreeze.utils.mcp.mcp_profile import McpServerProfile

    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    tab = McpClientGUI(None)
    try:
        tab._log = McpCallLog(McpServerProfile("s", ("server",)))

        assert tab.open_in_report_viewer() is None
    finally:
        tab.deleteLater()


def _wait(condition, seconds: float = 20) -> None:
    import time

    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, "what was waited for did not happen"
        QApplication.processEvents()
        time.sleep(0.005)


def test_the_viewer_is_a_tool_of_the_reports_category(app):
    from pybreeze.pybreeze_ui.menu.tools import tools_menu

    assert tools_menu.TOOLS["ReportViewer"].category == "reports"
    widget = tools_menu.build_tool_widget(None, "ReportViewer")
    try:
        assert isinstance(widget, ReportViewerGUI)
    finally:
        widget.deleteLater()


def test_a_run_of_many_results_makes_items_only_for_what_is_open(viewer, tmp_path):
    shutil.copy(FIXTURES / "load_failure.json", tmp_path / "many_failure.json")
    record = '{"Method": "GET", "test_url": "https://example.com/", "name": "/", "status_code": "200", "text": ""}'
    (tmp_path / "many_success.json").write_text(
        "{" + ", ".join(f'"Success_Test{number}": {record}' for number in range(1, 3001)) + "}", encoding="utf-8")

    viewer.open_files([str(tmp_path / "many_success.json")])

    (run,) = _runs(viewer)
    assert run.childCount() == 3001
    assert viewer.summary.text().startswith(_word("report_viewer_summary").format(
        shown=3001, every=3001, runs=1, seconds="0.00"))
