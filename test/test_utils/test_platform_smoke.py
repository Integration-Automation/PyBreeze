"""What PyBreeze needs from the system it runs on: a start, a child process, its files, and Qt with no display.

Each of these is tested in depth elsewhere, on the system the whole suite runs
on. This is the short form, the one CI runs on every system (the
``platform-smoke`` job): a failure here says the IDE cannot work on that system
at all, before any one tool is looked at. Nothing in it may depend on which
system it is.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from test_utils.started_window import run_started_window

from pybreeze.utils.app_dirs import DATA_DIR_MODE, pybreeze_data_dir
from pybreeze.utils.file_process.replace_file import replace_text
from pybreeze.utils.subprocess_util import IDE_ONLY, child_environment, no_window_creationflags, utf8_subprocess_env

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
# A child interpreter on a busy CI runner can take a while to start
_CHILD_TIMEOUT_SECONDS = 60
# Text that is not ASCII, not in any one legacy code page, and partly outside the Basic Multilingual Plane
_ANY_LANGUAGE = "測試 naïve \U0001f600"
# A folder name with a space and letters of several scripts: where a user's project may well be.
# None of the letters has a decomposed form, which a file system may hand back instead (macOS)
_AWKWARD_FOLDER = "專案 with space ж"


@pytest.fixture(scope="module")
def qt_app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _run_python(*arguments: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a child Python the way the IDE starts one, from the repository unless *cwd* is given."""
    return subprocess.run(
        [sys.executable, *arguments], capture_output=True, timeout=_CHILD_TIMEOUT_SECONDS, check=False,
        shell=False, cwd=cwd or _REPOSITORY_ROOT, env=utf8_subprocess_env(),
        creationflags=no_window_creationflags())


def _process_events_until(qt_app, finished) -> None:
    deadline = time.monotonic() + _CHILD_TIMEOUT_SECONDS
    while not finished():
        if time.monotonic() > deadline:
            pytest.fail("what was waited for did not happen in time")
        qt_app.processEvents()
        time.sleep(0.01)


class TestStartup:
    def test_the_package_is_imported_without_qt(self):
        # The pure tools must be usable where Qt cannot load
        child = _run_python("-c", "import sys, pybreeze, pybreeze.utils.app_dirs; print('PySide6' in sys.modules)")

        assert child.returncode == 0, child.stderr.decode("utf-8", "replace")
        assert child.stdout.decode("utf-8").strip() == "False"

    def test_the_main_window_is_built_and_closed(self, tmp_path):
        title = run_started_window(tmp_path, "result = window.windowTitle()")

        assert title == "PyBreeze"


class TestChildProcesses:
    def test_a_childs_output_comes_back_as_it_was_written(self):
        child = _run_python("-c", f"print({_ANY_LANGUAGE!a})")

        assert child.returncode == 0, child.stderr.decode("utf-8", "replace")
        assert child.stdout.decode("utf-8").strip() == _ANY_LANGUAGE

    def test_a_variable_the_ide_keeps_for_itself_stays_out_of_a_child(self, monkeypatch):
        monkeypatch.setenv("PYBREEZE_SMOKE_KEPT", IDE_ONLY)
        monkeypatch.setenv("PYBREEZE_SMOKE_GIVEN", "given")

        child = _run_python(
            "-c", "import os; print(os.environ.get('PYBREEZE_SMOKE_KEPT'), os.environ.get('PYBREEZE_SMOKE_GIVEN'))")

        assert child.stdout.decode("utf-8").split() == ["None", "given"]
        assert "PYBREEZE_SMOKE_KEPT" not in child_environment()

    def test_a_script_in_a_folder_with_spaces_and_other_scripts_runs(self, tmp_path):
        folder = tmp_path / _AWKWARD_FOLDER
        folder.mkdir()
        script = folder / "腳本.py"
        script.write_text("from pathlib import Path\nprint(Path(__file__).parent.name)\n", encoding="utf-8")

        child = _run_python(str(script), cwd=folder)

        assert child.returncode == 0, child.stderr.decode("utf-8", "replace")
        assert child.stdout.decode("utf-8").strip() == _AWKWARD_FOLDER

    def test_a_run_shows_in_its_window_what_the_child_wrote(self, qt_app, tmp_path):
        # The whole path of a run: process, pipe, reader thread, queue, timer, run window
        from pybreeze.extend.process_executor.process_executor_utils import build_task_process

        class MainWindow:
            """The little of the IDE's main window that opening a run window touches."""

            python_compiler = sys.executable
            encoding = "utf-8"

            def __init__(self) -> None:
                self.current_run_code_window: list = []

            def clear_code_result(self) -> None:
                """Nothing to clear in a stand-in."""

        data = tmp_path / "data.json"
        data.write_text(json.dumps({"said": _ANY_LANGUAGE}), encoding="utf-8")
        run = build_task_process(MainWindow())

        run.start_module_process("json.tool", ["--no-ensure-ascii", str(data)])
        _process_events_until(qt_app, lambda: run.process is None)

        assert _ANY_LANGUAGE in run.main_window.code_result.toPlainText()


class TestFiles:
    def test_the_data_folder_is_made_in_the_home_folder_for_its_owner(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

        folder = pybreeze_data_dir()

        assert folder == tmp_path / ".pybreeze"
        assert folder.is_dir()
        if os.name == "posix":
            # Windows keeps the profile's own access rules; POSIX is given the mode
            assert folder.stat().st_mode & 0o777 == DATA_DIR_MODE

    def test_a_file_is_replaced_whole_whatever_its_name(self, tmp_path):
        folder = tmp_path / _AWKWARD_FOLDER
        folder.mkdir()
        target = folder / "設定 ж.json"

        replace_text(target, "first")
        replace_text(target, _ANY_LANGUAGE)

        assert target.read_text(encoding="utf-8") == _ANY_LANGUAGE
        assert [entry.name for entry in folder.iterdir()] == [target.name]


class TestQtWithoutADisplay:
    def test_the_application_runs_on_the_offscreen_platform(self, qt_app):
        if os.environ["QT_QPA_PLATFORM"] != "offscreen":
            pytest.skip("another Qt platform was chosen for this run")

        assert qt_app.platformName() == "offscreen"

    def test_a_widget_is_shown_and_drawn(self, qt_app):
        from PySide6.QtWidgets import QLabel

        label = QLabel(_ANY_LANGUAGE)
        label.resize(200, 40)
        label.show()
        qt_app.processEvents()

        try:
            assert label.isVisible()
            assert not label.grab().isNull()
        finally:
            label.close()
            label.deleteLater()

    def test_a_timer_fires_on_the_gui_thread(self, qt_app):
        from PySide6.QtCore import QTimer

        fired_on: list = []
        QTimer.singleShot(0, lambda: fired_on.append(threading.current_thread()))

        _process_events_until(qt_app, lambda: bool(fired_on))

        assert fired_on == [threading.main_thread()]

    def test_the_web_engine_the_editor_needs_is_importable(self):
        # JEditor imports it as the IDE starts. In a child: a missing system
        # library is then a readable error here, not a crash of the test run
        child = _run_python("-c", "from PySide6.QtWebEngineWidgets import QWebEngineView; print(QWebEngineView.__name__)")

        assert child.returncode == 0, child.stderr.decode("utf-8", "replace")
        assert child.stdout.decode("utf-8").strip() == "QWebEngineView"
