"""Running a prthinker review: what the child is actually asked to do."""
from __future__ import annotations

import pytest

from pybreeze.extend.process_executor.prthinker import prthinker_process
from pybreeze.extend.prthinker_extend.prthinker_setting import DEFAULT_SETTING


class Editor:
    """Stands in for an editor tab, which is known by its open file."""

    def __init__(self, current_file=None) -> None:
        self.current_file = current_file


class Window:
    """The little of a main window that starting a review touches."""

    def __init__(self, current_widget=None) -> None:
        self.tab_widget = self
        self._current_widget = current_widget
        self.current_run_code_window: list = []
        self.encoding = "utf-8"
        self.cleared = False

    def currentWidget(self):  # noqa: N802 — the Qt name this stands in for
        return self._current_widget

    def clear_code_result(self) -> None:
        self.cleared = True


class RecordingProcess:
    """Stands in for the task process manager and remembers the call."""

    calls: list = []

    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def start_module_process(self, package, arguments, environment=None):
        RecordingProcess.calls.append((package, list(arguments), dict(environment or {})))


@pytest.fixture()
def recorded(monkeypatch):
    """Catch the review before it reaches a real process or a real window."""
    RecordingProcess.calls = []
    monkeypatch.setattr(prthinker_process, "TaskProcessManager", RecordingProcess)
    monkeypatch.setattr(prthinker_process, "CodeWindow", lambda: object())
    # The editor tab is recognised by its type, so the stand-in becomes that type.
    monkeypatch.setattr(prthinker_process, "EditorWidget", Editor)
    return RecordingProcess.calls


@pytest.fixture()
def settings(monkeypatch):
    """Let each test decide what the settings hold."""
    stored = dict(DEFAULT_SETTING)
    monkeypatch.setattr(prthinker_process, "load_setting", lambda: stored)
    return stored


class TestReviewingTheCurrentFile:
    def test_a_saved_file_is_reviewed(self, tmp_path, recorded, settings):
        source = tmp_path / "main.py"
        source.write_text("print(1)\n", encoding="utf-8")
        window = Window(Editor(str(source)))

        assert prthinker_process.review_current_file(window) is True
        package, arguments, _environment = recorded[0]
        assert package == "prthinker"
        assert arguments == ["review-file", str(source)]
        assert window.cleared

    def test_the_settings_reach_the_child_as_environment(self, tmp_path, recorded, settings):
        source = tmp_path / "main.py"
        source.write_text("print(1)\n", encoding="utf-8")
        settings["remote_url"] = "http://review-server"

        prthinker_process.review_current_file(Window(Editor(str(source))))
        _package, _arguments, environment = recorded[0]
        assert environment["PRTHINKER_REMOTE_URL"] == "http://review-server"

    def test_an_unsaved_tab_is_refused(self, recorded, settings):
        assert prthinker_process.review_current_file(Window(Editor(None))) is False
        assert recorded == []

    def test_a_file_that_is_gone_is_refused(self, tmp_path, recorded, settings):
        editor = Editor(str(tmp_path / "missing.py"))
        assert prthinker_process.review_current_file(Window(editor)) is False
        assert recorded == []

    def test_a_tab_that_is_not_an_editor_is_refused(self, recorded, settings):
        assert prthinker_process.review_current_file(Window(object())) is False
        assert recorded == []


class TestReviewingAPullRequest:
    def test_the_number_reaches_the_command(self, recorded, settings):
        settings["repository"] = "owner/name"
        assert prthinker_process.review_pull_request(Window(), 12) is True
        _package, arguments, _environment = recorded[0]
        assert arguments == ["review-pr", "--pr-number", "12"]

    def test_the_repository_and_token_travel_as_environment(self, recorded, settings):
        settings["repository"] = "owner/name"
        settings["platform_token"] = "s3cr3t"
        prthinker_process.review_pull_request(Window(), 12)
        _package, arguments, environment = recorded[0]
        assert environment["GITHUB_REPOSITORY"] == "owner/name"
        assert environment["GITHUB_TOKEN"] == "s3cr3t"
        assert "s3cr3t" not in " ".join(arguments)

    def test_without_a_repository_nothing_is_started(self, recorded, settings):
        assert prthinker_process.review_pull_request(Window(), 12) is False
        assert recorded == []
