"""The MCP client tab, against a real server process: connecting, asking before a call, cancelling, the session's log."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QLineEdit, QMessageBox
from je_editor import language_wrapper

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.design.tokens import State
from pybreeze.pybreeze_ui.mcp_gui import mcp_panels
from pybreeze.pybreeze_ui.mcp_gui.mcp_client_gui import McpClientGUI
from pybreeze.pybreeze_ui.mcp_gui.mcp_profile_dialog import McpProfileDialog
from pybreeze.pybreeze_ui.mcp_gui.mcp_server_panel import McpServerPanel
from pybreeze.pybreeze_ui.plain_text import as_text
from pybreeze.pybreeze_ui.thread_keeper import running_kept
from pybreeze.utils.execution_report.report_schema import ExecutionReport, Status
from pybreeze.utils.mcp.mcp_profile import McpServerProfile, load_profiles, save_profiles

FAKE_SERVER = Path(__file__).parent / "fixtures" / "mcp" / "fake_server.py"
TOKEN = "tok-3f9a1c77e2"


def _profile(name: str = "fake", *options: str, timeout_seconds: float = 20.0, **more) -> McpServerProfile:
    return McpServerProfile(
        name=name, command=(sys.executable, str(FAKE_SERVER), *options), environment={"FAKE_TOKEN": TOKEN},
        timeout_seconds=timeout_seconds, **more)


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A home and a project folder of the test's own: the servers file is under one, ``.mcp.json`` in the other."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "project").mkdir()
    monkeypatch.chdir(tmp_path / "project")
    return tmp_path


def _word(key: str) -> str:
    return language_wrapper.language_word_dict.get(key)


def _asked(key: str, **fields: str) -> str:
    """A question as its box holds it: the words of *key*, escaped so that nothing in them is read as markup."""
    return as_text(_word(key).format(**fields))


def _until(condition, seconds: float = 20) -> None:
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, "what was waited for did not happen"
        QApplication.processEvents()
        time.sleep(0.005)


class _Answers:
    """Answers the tab's questions for the user, and keeps what was asked."""

    def __init__(self, monkeypatch) -> None:
        self.answer = QMessageBox.StandardButton.Yes
        self.tick = False
        self.asked: list[dict] = []
        # A function on the class is called with the box; a bound method would not be
        monkeypatch.setattr(QMessageBox, "exec", lambda box: self._exec(box))

    def _exec(self, box: QMessageBox) -> int:
        box_check = box.checkBox()
        self.asked.append({
            "text": box.text(), "more": box.informativeText(),
            "default": box.standardButton(box.defaultButton()) if box.defaultButton() is not None else None,
            "check": box_check.text() if box_check is not None else None})
        if self.tick and box_check is not None:
            box_check.setChecked(True)
        return self.answer


@pytest.fixture
def answers(monkeypatch) -> _Answers:
    return _Answers(monkeypatch)


@pytest.fixture
def tab(app, home, answers):
    save_profiles([_profile()])
    gui = McpClientGUI()
    yield gui
    gui.cancel()
    _until(lambda: not gui.is_busy())
    gui.close()
    gui.deleteLater()
    _until(lambda: not running_kept())


def _connected(tab: McpClientGUI) -> McpClientGUI:
    assert tab.connect_server() is True
    _until(lambda: not tab.is_busy())
    assert tab.is_connected(), tab.status.text()
    return tab


def _select_tool(tab: McpClientGUI, name: str, arguments: dict | None = None) -> None:
    tools = tab.tools_panel.tool_list
    row = next(row for row in range(tools.count()) if tools.item(row).text() == name)
    tools.setCurrentRow(row)
    if arguments is not None:
        tab.tools_panel.arguments_edit.setPlainText(json.dumps(arguments))


def _call(tab: McpClientGUI, name: str, arguments: dict | None = None) -> bool:
    _select_tool(tab, name, arguments)
    sent = tab.call_tool()
    _until(lambda: not tab.is_busy())
    return sent


def _calls(tab: McpClientGUI) -> list[tuple[str, str]]:
    table = tab.calls_panel.calls_table
    return [(table.item(row, 1).text(), table.item(row, 2).text()) for row in range(table.rowCount())]


# ----------------------------------------------------------------------
# The servers
# ----------------------------------------------------------------------

def test_with_no_server_set_up_there_is_nothing_to_connect_to(app, home):
    gui = McpClientGUI()
    try:
        assert gui.server_panel.server_list.count() == 0
        assert not gui.server_panel.connect_button.isEnabled()
        assert gui.connect_server() is False
        assert gui.status.text() == _word("mcp_client_not_connected")
    finally:
        gui.deleteLater()


def test_the_users_servers_are_listed_then_the_projects_marked_as_such(app, home):
    save_profiles([_profile("mine"), _profile("shared")])
    (home / "project" / ".mcp.json").write_text(json.dumps({"mcpServers": {
        "shared": {"command": "other"}, "theirs": {"command": "node", "args": ["server.js"]}}}), encoding="utf-8")
    gui = McpClientGUI()
    try:
        servers = gui.server_panel.server_list
        assert [servers.item(row).text() for row in range(servers.count())] == [
            "mine", "shared", _word("mcp_servers_found_label").format(name="theirs")]
        servers.setCurrentRow(2)
        assert gui.server_panel.selected()[1] is False
        assert not gui.server_panel.remove_button.isEnabled()
    finally:
        gui.deleteLater()


def test_a_servers_file_that_cannot_be_read_is_said_and_the_tab_still_opens(app, home):
    save_profiles([_profile()])
    (home / "home" / ".pybreeze" / "mcp_servers.json").write_text("{broken", encoding="utf-8")
    gui = McpClientGUI()
    try:
        assert gui.status.state is State.ERROR
        assert gui.server_panel.server_list.count() == 0
    finally:
        gui.deleteLater()


# ----------------------------------------------------------------------
# Connecting
# ----------------------------------------------------------------------

def test_connecting_lists_what_the_server_offers(tab):
    _connected(tab)

    assert tab.status.state is State.SUCCESS
    assert tab.status.text() == _word("mcp_client_connected").format(
        server="fake-server 1.2.3", tools=11, resources=2, prompts=1)
    assert tab.tools_panel.tool_list.count() == 11
    assert tab.resources_panel.item_list.count() == 2
    assert tab.prompts_panel.item_list.count() == 1
    assert tab.server_panel.disconnect_button.isEnabled()


def test_the_selected_tool_shows_what_the_server_says_of_it_and_starts_its_arguments(tab):
    _connected(tab)
    _select_tool(tab, "write_file")

    shown = tab.tools_panel.detail_view.toPlainText()
    assert shown.startswith("Write a file\n\nWrite content to a path.\n\n" + _word("mcp_tools_hint_destructive"))
    assert '"required"' in shown
    assert json.loads(tab.tools_panel.arguments_edit.toPlainText()) == {"path": "", "content": ""}


@pytest.mark.parametrize(("tool", "hint"), [
    ("echo", "mcp_tools_hint_read_only"), ("write_file", "mcp_tools_hint_destructive"),
    ("slow", "mcp_tools_hint_unknown"),
])
def test_what_the_server_says_a_tool_does_is_told_in_the_ides_words(tab, tool, hint):
    _connected(tab)
    _select_tool(tab, tool)

    assert _word(hint) in tab.tools_panel.detail_view.toPlainText()


def test_the_filter_keeps_the_tools_that_have_what_is_typed(tab):
    _connected(tab)

    tab.tools_panel.filter_edit.setText("token")

    tools = tab.tools_panel.tool_list
    assert [tools.item(row).text() for row in range(tools.count()) if not tools.item(row).isHidden()] == ["leak"]
    assert tab.tools_panel.selected_tool().name == "leak"
    tab.tools_panel.filter_edit.setText("no tool says this")
    assert tab.tools_panel.selected_tool() is None
    assert not tab.tools_panel.call_button.isEnabled()


def test_a_program_that_is_not_there_is_said_and_nothing_is_connected(app, home, answers):
    save_profiles([McpServerProfile("gone", (str(home / "no_such_server"),))])
    gui = McpClientGUI()
    try:
        gui.connect_server()
        _until(lambda: not gui.is_busy())

        assert gui.status.state is State.ERROR
        assert str(home) not in gui.status.text()
        assert not gui.is_connected()
        assert not gui.server_panel.disconnect_button.isEnabled()
    finally:
        gui.deleteLater()


def test_disconnecting_empties_the_pages_and_keeps_the_calls(tab):
    _connected(tab)
    _call(tab, "echo", {"text": "hello"})

    tab.disconnect_server()

    assert not tab.is_connected()
    assert tab.tools_panel.tool_list.count() == 0
    assert tab.status.text() == _word("mcp_client_disconnected").format(name="fake")
    assert _calls(tab) == [("echo", _word("mcp_calls_status_passed"))]
    assert tab.calls_panel.export_button.isEnabled()


def test_connecting_again_starts_a_new_session(tab):
    _connected(tab)
    _call(tab, "echo", {"text": "first session"})

    _connected(tab)

    assert _calls(tab) == []
    assert tab.tools_panel.tool_list.count() == 11


# ----------------------------------------------------------------------
# Asking before a call
# ----------------------------------------------------------------------

def test_a_call_is_asked_about_with_the_tool_the_server_and_the_arguments(tab, answers):
    _connected(tab)

    assert _call(tab, "write_file", {"path": "a.txt", "content": "hello"}) is True

    (asked,) = answers.asked
    assert asked["text"] == _asked("mcp_confirm_question", tool="write_file", server="fake")
    assert _word("mcp_tools_hint_destructive") in asked["more"]
    assert "&quot;path&quot;: &quot;a.txt&quot;" in asked["more"] or '"path": "a.txt"' in asked["more"]
    assert asked["default"] == QMessageBox.StandardButton.No
    assert asked["check"] == _word("mcp_confirm_trust").format(tool="write_file", server="fake")
    assert tab.tools_panel.result_view.toPlainText() == "wrote a.txt"


def test_a_tool_the_server_calls_read_only_is_asked_about_all_the_same(tab, answers):
    _connected(tab)

    _call(tab, "echo", {"text": "hi"})

    assert len(answers.asked) == 1


def test_a_no_sends_nothing_and_is_kept_as_not_called(tab, answers):
    _connected(tab)
    answers.answer = QMessageBox.StandardButton.No

    assert _call(tab, "write_file", {"path": "a.txt", "content": "x"}) is False

    assert _calls(tab) == [("write_file", _word("mcp_calls_status_skipped"))]
    assert tab.status.text() == _word("mcp_client_declined").format(tool="write_file")
    assert tab.tools_panel.result_view.toPlainText() == ""
    answers.answer = QMessageBox.StandardButton.Yes
    _call(tab, "seen", {})
    assert "write_file" not in tab.tools_panel.result_view.toPlainText()


def test_a_yes_with_the_box_ticked_is_kept_for_that_tool_of_that_server(tab, answers):
    _connected(tab)
    answers.tick = True

    _call(tab, "echo", {"text": "one"})
    _call(tab, "echo", {"text": "two"})
    _call(tab, "write_file", {"path": "a", "content": "b"})

    assert [asked["text"] for asked in answers.asked] == [
        _asked("mcp_confirm_question", tool="echo", server="fake"),
        _asked("mcp_confirm_question", tool="write_file", server="fake")]
    assert load_profiles()[0].trusted_tools == {"echo", "write_file"}


def test_a_trusted_tool_is_called_without_asking_in_a_later_session_too(app, home, answers):
    save_profiles([_profile(trusted_tools=frozenset({"echo"}))])
    gui = McpClientGUI()
    try:
        _connected(gui)
        _call(gui, "echo", {"text": "straight through"})

        assert answers.asked == []
        assert gui.tools_panel.result_view.toPlainText() == "straight through"
    finally:
        gui.close()
        gui.deleteLater()


@pytest.mark.parametrize("typed", ["[1, 2]", '"text"', "{not json", "5"])
def test_arguments_that_are_not_a_json_object_are_said_and_nothing_is_asked(tab, answers, typed):
    _connected(tab)
    _select_tool(tab, "echo")
    tab.tools_panel.arguments_edit.setPlainText(typed)

    assert tab.call_tool() is False

    assert tab.status.text() == _word("mcp_client_arguments_not_object")
    assert answers.asked == [] and _calls(tab) == []


def test_no_arguments_typed_is_no_arguments(tab):
    _connected(tab)
    _select_tool(tab, "fail")
    tab.tools_panel.arguments_edit.clear()

    assert tab.call_tool() is True
    _until(lambda: not tab.is_busy())


# ----------------------------------------------------------------------
# How a call ends
# ----------------------------------------------------------------------

def test_an_answered_call_shows_its_result_and_how_long_it_took(tab):
    _connected(tab)

    _call(tab, "echo", {"text": "héllo 你好"})

    assert tab.tools_panel.result_view.toPlainText() == "héllo 你好"
    assert tab.status.state is State.SUCCESS
    assert tab.status.text().startswith("echo ")
    assert _calls(tab) == [("echo", _word("mcp_calls_status_passed"))]


def test_a_tool_that_says_it_failed_is_shown_as_failed(tab):
    _connected(tab)

    _call(tab, "fail")

    assert tab.status.state is State.ERROR
    assert tab.status.text() == _word("mcp_client_tool_failed").format(tool="fail")
    assert tab.tools_panel.result_view.toPlainText() == "the disk is full\nno space left"
    assert _calls(tab) == [("fail", _word("mcp_calls_status_failed"))]


def test_a_refused_call_says_the_servers_words_without_its_secret(tab):
    _connected(tab)

    _call(tab, "refuse")

    assert tab.status.state is State.ERROR
    assert "not with these arguments" in tab.status.text()
    assert TOKEN not in tab.status.text()
    assert _calls(tab) == [("refuse", _word("mcp_calls_status_error"))]


def test_while_a_call_is_on_its_way_only_cancel_is_offered(tab):
    _connected(tab)
    _select_tool(tab, "slow", {"seconds": 30})

    tab.call_tool()

    assert tab.is_busy()
    assert not tab.tools_panel.call_button.isEnabled()
    assert tab.tools_panel.cancel_button.isEnabled()
    assert not tab.server_panel.isEnabled()
    assert tab.call_tool() is False and tab.connect_server() is False


def test_a_cancelled_call_ends_at_once_and_is_kept_as_not_called(tab):
    _connected(tab)
    _select_tool(tab, "slow", {"seconds": 30})
    tab.call_tool()
    started = time.monotonic()

    tab.tools_panel.cancel_button.click()
    _until(lambda: not tab.is_busy())

    assert time.monotonic() - started < 5
    assert _calls(tab) == [("slow", _word("mcp_calls_status_skipped"))]
    assert tab.status.state is State.ERROR
    assert tab.tools_panel.call_button.isEnabled() and tab.server_panel.isEnabled()
    assert tab.is_connected()


def test_a_call_that_takes_longer_than_the_servers_time_is_given_up_on(app, home, answers):
    save_profiles([_profile(timeout_seconds=1.0)])
    gui = McpClientGUI()
    try:
        _connected(gui)
        _call(gui, "slow", {"seconds": 3})

        assert _calls(gui) == [("slow", _word("mcp_calls_status_error"))]
        assert "1" in gui.status.text()
    finally:
        gui.close()
        gui.deleteLater()


def test_a_server_that_goes_away_is_said_with_its_last_words_and_the_tab_is_disconnected(tab):
    _connected(tab)
    _call(tab, "leak")

    _call(tab, "quit")

    assert not tab.is_connected()
    assert tab.status.state is State.ERROR
    assert tab.status.text().endswith("starting with token ***")
    assert tab.tools_panel.tool_list.count() == 0
    assert not tab.server_panel.disconnect_button.isEnabled()
    assert _calls(tab)[-1] == ("quit", _word("mcp_calls_status_error"))


def test_a_long_result_is_shown_cut_with_a_note(tab, monkeypatch):
    monkeypatch.setattr(mcp_panels, "MAX_SHOWN_CHARACTERS", 10)
    _connected(tab)

    _call(tab, "echo", {"text": "0123456789abcdefghij"})

    assert tab.tools_panel.result_view.toPlainText() == "0123456789\n" + _word("mcp_result_cut").format(
        shown=10, whole=20)


# ----------------------------------------------------------------------
# Resources and prompts
# ----------------------------------------------------------------------

def test_a_resource_is_read(tab):
    _connected(tab)
    assert "memo://greeting" in tab.resources_panel.detail_view.toPlainText()

    assert tab.read_resource() is True
    _until(lambda: not tab.is_busy())

    assert tab.resources_panel.content_view.toPlainText() == "hello there"
    assert tab.status.text() == _word("mcp_client_fetched")


def test_a_prompt_starts_with_its_required_arguments_and_is_filled_in(tab):
    _connected(tab)
    assert json.loads(tab.prompts_panel.arguments_edit.toPlainText()) == {"code": ""}
    assert "tone: How to say it." in tab.prompts_panel.detail_view.toPlainText()
    tab.prompts_panel.arguments_edit.setPlainText('{"code": "x = 1", "tone": "kind"}')

    assert tab.get_prompt() is True
    _until(lambda: not tab.is_busy())

    assert tab.prompts_panel.content_view.toPlainText() == (
        "user:\nPlease review: x = 1\n\nassistant:\nIn a kind tone.")


def test_a_prompts_arguments_have_to_be_an_object_too(tab):
    _connected(tab)
    tab.prompts_panel.arguments_edit.setPlainText("[1]")

    assert tab.get_prompt() is False
    assert tab.status.text() == _word("mcp_client_arguments_not_object")


def test_nothing_is_read_or_got_while_nothing_is_connected(tab):
    assert tab.read_resource() is False
    assert tab.get_prompt() is False
    assert tab.call_tool() is False
    assert tab.export_session() is None


# ----------------------------------------------------------------------
# The session as a report
# ----------------------------------------------------------------------

def test_the_session_is_exported_as_an_execution_report_without_its_secrets(tab, answers, home, monkeypatch):
    target = home / "session.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *_a, **_k: (str(target), "")))
    _connected(tab)
    _call(tab, "echo", {"text": "hello", "password": "hunter2"})
    _call(tab, "leak")
    _call(tab, "fail")

    assert tab.export_session() == str(target)

    text = target.read_text(encoding="utf-8")
    report = ExecutionReport.from_dict(json.loads(text))
    assert TOKEN not in text and "hunter2" not in text
    assert (report.framework, report.name) == ("mcp", "fake")
    assert [(result.name, result.status) for result in report.results] == [
        ("echo", Status.PASSED), ("leak", Status.PASSED), ("fail", Status.FAILED)]
    assert report.raw["server"]["name"] == "fake-server"
    assert tab.status.text() == _word("mcp_client_exported").format(file="session.json")


def test_a_cancelled_export_saves_nothing(tab, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *_a, **_k: ("", "")))
    _connected(tab)
    _call(tab, "echo", {"text": "x"})

    assert tab.export_session() is None


def test_an_export_that_cannot_be_written_is_said_without_its_path(tab, home, monkeypatch):
    target = home / "no_such_folder" / "session.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *_a, **_k: (str(target), "")))
    _connected(tab)
    _call(tab, "echo", {"text": "x"})

    assert tab.export_session() is None
    assert tab.status.state is State.ERROR
    assert str(home) not in tab.status.text()


# ----------------------------------------------------------------------
# A server the project brings
# ----------------------------------------------------------------------

def _project_server(home: Path, marker: Path) -> None:
    script = f"open({str(marker)!r}, 'w').close(); import runpy; runpy.run_path({str(FAKE_SERVER)!r})"
    (home / "project" / ".mcp.json").write_text(json.dumps({"mcpServers": {"theirs": {
        "command": sys.executable, "args": ["-c", script], "trustedTools": ["write_file"]}}}), encoding="utf-8")


def test_a_projects_server_is_not_started_without_a_yes(app, home, answers):
    marker = home / "started"
    _project_server(home, marker)
    answers.answer = QMessageBox.StandardButton.No
    gui = McpClientGUI()
    try:
        assert gui.connect_server() is False

        (asked,) = answers.asked
        assert asked["text"] == _asked("mcp_found_question", name="theirs")
        assert sys.executable in asked["more"] and "runpy" in asked["more"]
        assert asked["default"] == QMessageBox.StandardButton.No
        assert not marker.exists()
        assert not gui.is_busy()
    finally:
        gui.deleteLater()


def test_with_a_yes_it_is_started_and_none_of_its_tools_is_trusted_whatever_its_file_says(app, home, answers):
    marker = home / "started"
    _project_server(home, marker)
    gui = McpClientGUI()
    try:
        _connected(gui)
        assert marker.exists()

        _call(gui, "write_file", {"path": "a", "content": "b"})

        assert [asked["text"] for asked in answers.asked] == [
            _asked("mcp_found_question", name="theirs"),
            _asked("mcp_confirm_question", tool="write_file", server="theirs")]
        assert load_profiles() == []
    finally:
        gui.close()
        gui.deleteLater()


# ----------------------------------------------------------------------
# Setting a server up
# ----------------------------------------------------------------------

def _dialog(profile: McpServerProfile | None = None, taken: set[str] | None = None) -> McpProfileDialog:
    return McpProfileDialog(None, profile, taken or set())


def test_a_server_is_set_up_with_one_argument_a_line(app):
    dialog = _dialog()
    dialog.name_edit.setText("  files  ")
    dialog.command_edit.setPlainText("npx\n-y\n@example/server files\n\n C:/My Work\n")
    dialog.folder_edit.setText("C:/work")
    dialog.timeout_spin.setValue(90)
    dialog._add_variable("API_TOKEN", TOKEN)
    dialog._add_variable("", "a value without a name")

    profile = dialog.profile()

    assert profile == McpServerProfile(
        "files", ("npx", "-y", "@example/server files", " C:/My Work"), {"API_TOKEN": TOKEN}, "C:/work", 90.0)
    dialog.deleteLater()


def test_a_server_being_changed_starts_with_what_it_has_and_keeps_its_trusted_tools(app):
    before = _profile(trusted_tools=frozenset({"echo"}))
    dialog = _dialog(before)

    assert dialog.name_edit.text() == "fake"
    assert dialog.command() == before.command
    assert dialog.environment() == {"FAKE_TOKEN": TOKEN}
    assert dialog.profile() == before
    dialog.deleteLater()


def test_the_values_of_the_variables_are_dots_until_they_are_asked_for(app):
    dialog = _dialog(_profile())
    table = dialog.environment_table
    delegate = table.itemDelegateForColumn(1)

    assert delegate.displayText(TOKEN, table.locale()) == "\u2022" * 8
    assert delegate.displayText("", table.locale()) == ""
    table.editItem(table.item(0, 1))
    assert table.findChild(QLineEdit).echoMode() == QLineEdit.EchoMode.Password

    dialog.show_values_box.setChecked(True)
    assert delegate.displayText(TOKEN, table.locale()) == TOKEN
    dialog.deleteLater()


def test_a_variable_is_added_and_removed(app):
    dialog = _dialog(_profile())

    dialog.add_variable_button.click()
    assert dialog.environment_table.rowCount() == 2
    dialog.environment_table.setCurrentCell(0, 0)
    dialog.remove_variable_button.click()

    assert dialog.environment() == {}
    dialog.deleteLater()


@pytest.mark.parametrize(("name", "command", "problem"), [
    ("", "server", "mcp_profile_needs_name"),
    ("taken", "server", "mcp_profile_name_taken"),
    ("new", "  \n\n", "mcp_profile_needs_command"),
])
def test_a_server_that_cannot_be_saved_is_told_what_it_needs(app, answers, name, command, problem):
    dialog = _dialog(taken={"taken"})
    dialog.name_edit.setText(name)
    dialog.command_edit.setPlainText(command)

    dialog.accept()

    assert [asked["text"] for asked in answers.asked] == [_word(problem)]
    assert dialog.result() != McpProfileDialog.DialogCode.Accepted
    dialog.deleteLater()


def test_a_server_with_a_name_and_a_command_is_saved(app, answers):
    dialog = _dialog(taken={"taken"})
    dialog.name_edit.setText("new")
    dialog.command_edit.setPlainText("server")

    dialog.accept()

    assert answers.asked == []
    assert dialog.result() == McpProfileDialog.DialogCode.Accepted
    dialog.deleteLater()


def _panel(home: Path, monkeypatch, set_up) -> McpServerPanel:
    panel = McpServerPanel(home / "project")
    monkeypatch.setattr(panel, "_set_up", set_up)
    return panel


def test_a_server_added_is_kept_and_selected(app, home, monkeypatch):
    save_profiles([_profile("first")])
    panel = _panel(home, monkeypatch, lambda profile, taken: _profile("second") if taken == {"first"} else None)

    assert panel.add_server() is True

    assert [profile.name for profile in load_profiles()] == ["first", "second"]
    assert panel.selected() == (_profile("second"), True)
    panel.deleteLater()


def test_a_set_up_that_was_cancelled_changes_nothing(app, home, monkeypatch):
    save_profiles([_profile("first")])
    panel = _panel(home, monkeypatch, lambda profile, taken: None)

    assert panel.add_server() is False
    assert panel.edit_server() is False
    assert load_profiles() == [_profile("first")]
    panel.deleteLater()


def test_a_server_changed_keeps_its_place_and_may_keep_its_name(app, home, monkeypatch):
    save_profiles([_profile("first"), _profile("second")])
    seen: list = []

    def set_up(profile, taken):
        seen.append((profile.name, taken))
        return _profile("first", timeout_seconds=5.0)

    panel = _panel(home, monkeypatch, set_up)
    panel.server_list.setCurrentRow(0)

    assert panel.edit_server() is True

    assert seen == [("first", {"second"})]
    assert [(profile.name, profile.timeout_seconds) for profile in load_profiles()] == [("first", 5.0), ("second", 20.0)]
    panel.deleteLater()


def test_editing_a_projects_server_makes_it_the_users_own(app, home, monkeypatch):
    (home / "project" / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"theirs": {"command": "node"}}}), encoding="utf-8")
    panel = _panel(home, monkeypatch, lambda profile, taken: profile)

    assert panel.edit_server() is True

    assert [profile.name for profile in load_profiles()] == ["theirs"]
    assert panel.selected()[1] is True
    assert panel.server_list.count() == 1
    panel.deleteLater()


def test_a_server_is_removed_only_after_a_yes(app, home, monkeypatch):
    save_profiles([_profile("first")])
    panel = McpServerPanel(home / "project")
    asked: list = []

    def question(_parent, _title, text, _buttons, default):
        asked.append((text, default))
        return QMessageBox.StandardButton.No if len(asked) == 1 else QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", question)

    assert panel.remove_server() is False
    assert load_profiles() == [_profile("first")]
    assert panel.remove_server() is True

    assert load_profiles() == []
    assert asked[0] == (_asked("mcp_servers_remove_question", name="first"), QMessageBox.StandardButton.No)
    panel.deleteLater()


def test_servers_that_cannot_be_saved_are_said_and_the_list_stays(app, home, monkeypatch):
    save_profiles([_profile("first")])
    panel = _panel(home, monkeypatch, lambda profile, taken: _profile("second"))
    warned: list = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, title, text: warned.append(text))

    def refuse(_profiles):
        raise PermissionError(13, "Permission denied", str(home / "secret-place"))

    monkeypatch.setattr("pybreeze.pybreeze_ui.mcp_gui.mcp_server_panel.save_profiles", refuse)

    assert panel.add_server() is False

    assert len(warned) == 1 and str(home) not in warned[0]
    assert panel.server_list.count() == 1
    panel.deleteLater()


# ----------------------------------------------------------------------
# The tab
# ----------------------------------------------------------------------

def test_closing_the_tab_ends_the_server(app, home, answers):
    save_profiles([_profile()])
    gui = McpClientGUI()
    _connected(gui)
    client = gui._session.client

    gui.close()
    gui.deleteLater()

    deadline = time.monotonic() + 20
    while not client.closed and time.monotonic() < deadline:
        time.sleep(0.02)
    assert client.closed


def test_the_tab_is_a_tool_of_the_mcp_category(app, home):
    from pybreeze.pybreeze_ui.menu.tools import tools_menu

    assert tools_menu.TOOLS["McpClient"].category == "mcp"
    widget = tools_menu.build_tool_widget(None, "McpClient")
    try:
        assert isinstance(widget, McpClientGUI)
    finally:
        widget.deleteLater()
