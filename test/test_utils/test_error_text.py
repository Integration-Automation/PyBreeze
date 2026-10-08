"""Why a tool refused its input, shown in the IDE language rather than always in English."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.extend_traditional_chinese import (
    pybreeze_traditional_chinese_word_dict as CHINESE,
)
from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui import error_text as error_text_mod
from pybreeze.pybreeze_ui.error_text import error_text
from pybreeze.utils.exception import exception_tags
from pybreeze.utils.exception.error_templates import ERROR_TEXT_KEY_PREFIX, TEMPLATE_FIELD, error_templates


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture
def chinese(monkeypatch):
    monkeypatch.setattr(error_text_mod.language_wrapper, "language_word_dict", CHINESE)


def _sample(template: str) -> dict[str, str]:
    return {field.group(1): f"<{field.group(1)}>" for field in TEMPLATE_FIELD.finditer(template)}


class TestEveryConstant:
    def test_has_a_chinese_translation(self):
        missing = [name for name in error_templates() if ERROR_TEXT_KEY_PREFIX + name not in CHINESE]
        assert not missing

    @pytest.mark.parametrize("name", sorted(error_templates()))
    def test_is_found_again_from_the_message(self, chinese, name):
        constant = getattr(exception_tags, name)
        fields = _sample(error_templates()[name])
        message = constant.format(**fields)
        # A field written {key!r} is in the message as its repr
        shown = {field: repr(value) if "{" + field + "!r}" in constant else value
                 for field, value in fields.items()}

        assert error_text(message) == CHINESE[ERROR_TEXT_KEY_PREFIX + name].format(**shown)


class TestWhatIsKept:
    def test_a_value_repr_d_into_the_message(self, chinese):
        message = exception_tags.json_duplicate_key_error.format(key="a")

        assert error_text(message) == "這份 JSON 在同一個物件裡給了兩次 'a' 鍵"

    def test_a_detail_after_the_constant(self, chinese):
        message = f"{exception_tags.cant_reformat_json_error} (Expecting value)"

        assert error_text(message) == "無法重新格式化 JSON：型別正確嗎？ (Expecting value)"

    def test_braces_in_a_value_are_not_read_as_fields(self, chinese):
        message = exception_tags.invalid_regex_pattern_error.format(detail="bad {0} here")

        assert error_text(message) == "無效的正規表示式：bad {0} here"

    def test_a_message_from_elsewhere(self, chinese):
        assert error_text("[Errno 2] No such file") == "[Errno 2] No such file"

    def test_english_is_the_constant_itself(self, app):
        message = exception_tags.json_duplicate_key_error.format(key="'a'")

        assert error_text(message) == message


class TestATab:
    def test_shows_the_reason_in_chinese(self, app, chinese, monkeypatch):
        # "轉換失敗：not a recognized epoch number or ISO-8601 date-time"
        from pybreeze.pybreeze_ui.tools_gui import timestamp_gui
        from pybreeze.pybreeze_ui.tools_gui.timestamp_gui import TimestampGUI

        monkeypatch.setattr(timestamp_gui.language_wrapper, "language_word_dict", CHINESE)
        tab = TimestampGUI()
        tab.input_edit.setText("not a time")

        tab.convert()

        shown = tab.output_edit.toPlainText()
        assert "無法辨識為 epoch 數值或 ISO-8601 日期時間" in shown
        assert "recognized" not in shown
        tab.deleteLater()

    def test_a_har_file_that_is_not_one(self, app, chinese, monkeypatch):
        from pybreeze.pybreeze_ui.tools_gui import har_import_gui
        from pybreeze.pybreeze_ui.tools_gui.har_import_gui import HarImportGUI

        monkeypatch.setattr(har_import_gui.language_wrapper, "language_word_dict", CHINESE)
        tab = HarImportGUI()

        assert not tab.load_text('{"log": {}}')

        shown = tab.output_edit.toPlainText()
        assert "這份 JSON 沒有 log.entries 清單，不是 HAR 匯出檔" in shown
        assert "entries list" not in shown
        tab.deleteLater()


class TestTheNetworkReasons:
    """URL checks, request failures, image downloads, host keys and Skills' status texts."""

    @pytest.mark.parametrize(("status", "headers", "body", "expected"), [
        (302, {"Location": "https://elsewhere.example/x?key=1"}, "", "重新導向（未跟隨）至 https://elsewhere.example"),
        (302, {"Location": "/next"}, "", "重新導向（未跟隨）至這台伺服器上的另一個路徑"),
        (401, {}, "", "驗證或授權失敗"),
        (503, {}, "overloaded", "伺服器錯誤：overloaded"),
    ])
    def test_a_skills_answer_that_is_not_2xx(self, chinese, status, headers, body, expected):
        from types import SimpleNamespace

        from pybreeze.pybreeze_ui.extend_ai_gui.skills.skills_send_gui import describe_failed_status

        response = SimpleNamespace(status_code=status, headers=headers, is_redirect=status == 302)

        assert describe_failed_status(response, body)[1] == expected

    def test_an_image_that_did_not_download(self, app, chinese, monkeypatch):
        from pybreeze.pybreeze_ui.diagram_editor import diagram_scene
        from pybreeze.pybreeze_ui.diagram_editor.diagram_net_utils import ImageDownloadError

        def refuse(_source):
            raise ImageDownloadError(exception_tags.image_too_large_error.format(megabytes=20))

        monkeypatch.setattr(diagram_scene, "safe_download_image", refuse)
        thread = diagram_scene.ImageDownloadThread("https://example.org/a.png")
        failed: list = []
        thread.failed.connect(lambda _source, message: failed.append(message))

        thread.run()  # on this thread: a direct connection

        assert failed == ["圖片超過 20 MB 的上限。"]

    def test_a_url_the_ssrf_check_refuses(self, chinese):
        from pybreeze.utils.network.url_validation import UnsafeURLError, validate_url

        with pytest.raises(UnsafeURLError) as refused:
            validate_url("ftp://example.org/")

        assert error_text(str(refused.value)) == "不允許 'ftp' 協定，請使用 http 或 https。"

    def test_a_request_that_timed_out(self, chinese):
        import requests

        from pybreeze.utils.network.http_client import describe_request_error

        assert error_text(describe_request_error(requests.ReadTimeout())) == "請求逾時 (ReadTimeout)"

    def test_a_host_key_the_user_declined(self, app, chinese):
        from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_command_widget import SSHCommandWidget

        widget = SSHCommandWidget()
        client = object()
        widget.ssh_client = client
        widget._cleanup = lambda: None

        widget._on_connect_failed(client, exception_tags.host_key_rejected_error.format(hostname="example.org"))

        assert "已拒絕 example.org 的主機金鑰。" in widget.terminal.toPlainText()
        widget.ssh_client = None
        widget.close()

    def test_a_host_key_the_user_declined_in_the_file_tree(self, app, chinese, monkeypatch):
        from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_file_viewer_widget as tree_mod

        shown: list = []
        monkeypatch.setattr(tree_mod.QMessageBox, "critical", lambda *args: shown.append(args[2]))
        tree = tree_mod.SSHFileTreeManager()

        tree._on_connect_failed(exception_tags.host_key_rejected_error.format(hostname="example.org"))

        assert len(shown) == 1
        assert "已拒絕 example.org 的主機金鑰。" in shown[0]
        tree.close()
        tree.deleteLater()


def test_no_tool_tab_shows_a_reason_as_raised():
    # The HAR tab's load error was missed once: its format( call ran over two lines
    import pathlib
    import re

    import pybreeze

    tabs = pathlib.Path(pybreeze.__file__).parent / "pybreeze_ui" / "tools_gui"
    raw = re.compile(r"error\s*=\s*str\(\s*(?:error|err|exc|e)\s*\)")
    offenders = [path.name for path in tabs.glob("*.py") if raw.search(path.read_text(encoding="utf-8"))]
    assert not offenders


class TestADiagramFile:
    def test_that_is_not_a_diagram(self, app, chinese, monkeypatch, tmp_path):
        from pybreeze.pybreeze_ui.diagram_editor import diagram_editor_widget
        from pybreeze.pybreeze_ui.diagram_editor.diagram_editor_widget import DiagramEditorWidget

        target = tmp_path / "list.diagram.json"
        target.write_text("[]", encoding="utf-8")
        shown: list = []
        monkeypatch.setattr(diagram_editor_widget.QMessageBox, "warning", lambda *args: shown.append(args[2]))
        monkeypatch.setattr(diagram_editor_widget.QFileDialog, "getOpenFileName",
                            staticmethod(lambda *args, **kwargs: (str(target), "")))
        editor = DiagramEditorWidget()

        editor._open_diagram()

        assert len(shown) == 1
        assert "架構圖檔案應該是一個物件，而不是 list" in shown[0]
        editor.deleteLater()


def test_a_constant_with_no_translation_stays_as_it_is(app, monkeypatch):
    # A language without the entry: the English the tool wrote is still shown
    monkeypatch.setattr(error_text_mod.language_wrapper, "language_word_dict", {})
    message = exception_tags.wrong_json_data_error

    assert error_text(message) == message
