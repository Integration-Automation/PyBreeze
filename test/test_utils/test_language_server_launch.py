"""The action language server is the one JEditor's editors start for a JSON file."""
from __future__ import annotations

import sys
from pathlib import Path

from je_editor.utils.lsp import language_servers

from pybreeze.extend.language_server import launch
from test_utils.started_window import run_started_window


def test_the_command_starts_the_servers_entry_with_the_ides_own_interpreter():
    command = launch.server_command(None, "English")

    assert command[0] == sys.executable
    assert Path(command[1]).is_file() and Path(command[1]).name == "__main__.py"
    assert Path(command[1]).parent.name == "language_server"
    assert command[2:] == ["--language", "English"]


def test_the_entry_is_named_by_its_path_so_the_working_folder_is_not_on_the_servers_import_path():
    command = launch.server_command(None, "English")

    assert "-m" not in command
    assert Path(command[1]).is_absolute()


def test_the_interpreter_that_runs_the_scripts_is_passed_on_when_there_is_one():
    assert launch.server_command("C:/project/.venv/python", "Traditional_Chinese")[2:] == [
        "--language", "Traditional_Chinese", "--interpreter", "C:/project/.venv/python"]


def test_a_packaged_build_has_no_interpreter_to_run_the_server_with(monkeypatch):
    assert launch.can_serve()

    monkeypatch.setattr(sys, "frozen", True, raising=False)

    assert not launch.can_serve()


def test_once_offered_the_server_is_what_jeditor_starts_for_a_json_file(monkeypatch):
    monkeypatch.setitem(language_servers.DEFAULT_SERVERS, launch.ACTION_SCRIPT_SUFFIX, ["some-other-server"])

    launch.offer_to_jeditor(None, "English")

    # JEditor's own lookup, which also checks that the command exists
    assert language_servers.server_command(".json") == launch.server_command(None, "English")
    assert language_servers.server_command(".JSON") == launch.server_command(None, "English")


def test_other_files_keep_the_server_jeditor_names_for_them(monkeypatch):
    before = {suffix: list(command) for suffix, command in language_servers.DEFAULT_SERVERS.items()}
    monkeypatch.setitem(language_servers.DEFAULT_SERVERS, launch.ACTION_SCRIPT_SUFFIX, ["some-other-server"])

    launch.offer_to_jeditor(None, "English")

    after = dict(language_servers.DEFAULT_SERVERS)
    assert {suffix: command for suffix, command in after.items() if suffix != ".json"} == {
        suffix: command for suffix, command in before.items() if suffix != ".json"}


_AN_EDITOR_ASKS_THE_SERVER = """
from pathlib import Path
from PySide6.QtCore import QEventLoop, QTimer
from je_editor import EditorWidget
from je_editor.utils.lsp.language_servers import DEFAULT_SERVERS

script = Path("script.json").resolve()
script.write_text('[["WR_quit"] ["WR_quit"]]', encoding="utf-8")
editors = [window.tab_widget.widget(index) for index in range(window.tab_widget.count())
           if isinstance(window.tab_widget.widget(index), EditorWidget)]
result = {"command": DEFAULT_SERVERS.get(".json"), "language": language_wrapper.language,
          "editors": len(editors), "started": False, "diagnostics": []}
if editors:
    code_edit = editors[0].code_edit
    received = []
    waiting = QEventLoop()
    code_edit.lsp_client.diagnostics_ready.connect(received.append)
    code_edit.lsp_client.diagnostics_ready.connect(waiting.quit)
    code_edit.current_file = str(script)
    code_edit.setPlainText(script.read_text(encoding="utf-8"))
    result["started"] = code_edit.start_language_server()
    if result["started"] and not received:
        QTimer.singleShot(30000, waiting.quit)
        waiting.exec()
    result["diagnostics"] = received[0] if received else []
    code_edit.lsp_client.stop()
"""


def test_the_started_ide_offers_the_server_and_an_editor_gets_diagnostics_from_it(tmp_path):
    seen = run_started_window(tmp_path, _AN_EDITOR_ASKS_THE_SERVER)

    assert seen["command"][1].endswith("__main__.py")
    assert seen["command"][2:4] == ["--language", seen["language"]]
    assert "--interpreter" in seen["command"]
    assert seen["editors"] >= 1
    assert seen["started"], "the editor did not start the language server for a .json file"
    assert len(seen["diagnostics"]) == 1, seen["diagnostics"]
    assert "JSON" in str(seen["diagnostics"][0])
