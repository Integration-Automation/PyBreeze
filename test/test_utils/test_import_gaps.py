"""The line under an importer's output that names what the chosen target leaves out."""
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from je_editor import language_wrapper
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.extend_traditional_chinese import (
    pybreeze_traditional_chinese_word_dict as CHINESE,
)
from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.design.tokens import State
from pybreeze.pybreeze_ui.tools_gui import import_gaps
from pybreeze.pybreeze_ui.tools_gui.curl_import_gui import CurlImportGUI
from pybreeze.pybreeze_ui.tools_gui.har_import_gui import HarImportGUI
from pybreeze.pybreeze_ui.tools_gui.import_gaps import gaps_text
from pybreeze.utils.curl_import.curl_parser import parse_curl
from pybreeze.utils.import_targets.builtin_targets import IMPORT_TARGETS
from pybreeze.utils.import_targets.target_registry import RequestPart

_URL = "https://x.example/api"
_POST = f"curl {_URL} -H 'X-A: 1' -d 'a=1' -b 'c=1' -m 3"


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


def _target(key: str):
    return IMPORT_TARGETS.target(key)


class TestTheLine:
    def test_a_target_that_sends_everything_has_nothing_to_say(self, app):
        assert gaps_text(_target("requests"), [parse_curl(_POST)]) == ""

    def test_nothing_to_send_leaves_nothing_out(self, app):
        assert gaps_text(_target("webrunner_action"), []) == ""

    def test_what_is_left_out_is_named_in_the_order_of_the_parts(self, app):
        assert gaps_text(_target("webrunner_action"), [parse_curl(_POST)]) == (
            "Not sent by this target: the method (this target makes a GET) · headers · the body")

    def test_a_part_is_named_once_however_many_requests_have_it(self, app):
        requests = [parse_curl(f"curl {_URL}/1 -H 'X-A: 1'"), parse_curl(f"curl {_URL}/2 -H 'X-A: 2' -u a:b")]

        assert gaps_text(_target("loaddensity_python"), requests) == (
            "Not sent by this target: headers · the user name and password")

    def test_every_part_has_a_name_in_both_dictionaries(self, app):
        assert set(import_gaps._PART_WORDS) == set(RequestPart)
        for key in import_gaps._PART_WORDS.values():
            assert language_wrapper.language_word_dict.get(key), key
            assert CHINESE.get(key), key

    def test_in_chinese_the_line_and_its_parts_are_chinese(self, app, monkeypatch):
        monkeypatch.setattr(import_gaps.language_wrapper, "language_word_dict", CHINESE)

        assert gaps_text(_target("loaddensity_python"), [parse_curl(f"curl {_URL} -H 'X-A: 1' -u a:b")]) == (
            "這個目標不會送出：標頭 · 使用者名稱與密碼")


def _choose(widget, key: str) -> None:
    widget.target_select.setCurrentIndex(widget.target_select.findData(key))


class TestTheCurlTab:
    @pytest.fixture
    def tab(self, app):
        made = CurlImportGUI()
        yield made
        made.deleteLater()

    def test_nothing_is_shown_before_anything_is_generated(self, tab):
        assert tab.gaps_line.isHidden()

    def test_a_target_that_sends_everything_shows_no_line(self, tab):
        tab.input_edit.setPlainText(_POST)

        tab.convert()

        assert tab.gaps_line.isHidden()

    def test_a_target_that_leaves_something_out_says_so_as_a_warning(self, tab):
        tab.input_edit.setPlainText(_POST)

        _choose(tab, "webrunner_action")

        assert not tab.gaps_line.isHidden()
        assert tab.gaps_line.text() == (
            "Not sent by this target: the method (this target makes a GET) · headers · the body")
        assert tab.gaps_line.state is State.WARNING
        assert json.loads(tab.output_edit.toPlainText())[-1] == ["WR_quit"]

    def test_going_back_to_a_target_that_sends_everything_takes_the_line_away(self, tab):
        tab.input_edit.setPlainText(_POST)
        _choose(tab, "webrunner_action")

        _choose(tab, "requests")

        assert tab.gaps_line.isHidden()

    def test_a_command_that_cannot_be_read_shows_no_line(self, tab):
        tab.input_edit.setPlainText(_POST)
        _choose(tab, "loaddensity_python")
        assert not tab.gaps_line.isHidden()

        tab.input_edit.setPlainText("not a curl command")
        tab.convert()

        assert tab.gaps_line.isHidden()

    def test_the_new_target_saves_as_a_json_file_of_its_own_name(self, tab):
        _choose(tab, "webrunner_action")

        assert tab.output_actions.suggested_filename() == "web_action.json"


def _har(*requests: dict) -> str:
    return json.dumps({"log": {"entries": [{"request": request, "response": {"status": 200}} for request in requests]}})


_GET = {"method": "GET", "url": f"{_URL}/1", "headers": [{"name": "Accept", "value": "application/json"}]}
_POSTED = {"method": "POST", "url": f"{_URL}/2", "headers": [{"name": "Content-Type", "value": "application/json"}],
           "postData": {"mimeType": "application/json", "text": "{}"}}


class TestTheHarTab:
    @pytest.fixture
    def tab(self, app):
        made = HarImportGUI()
        made.api_only_check.setChecked(False)
        made.load_text(_har(_GET, _POSTED))
        yield made
        made.deleteLater()

    def test_nothing_is_shown_before_anything_is_generated(self, tab):
        assert tab.gaps_line.isHidden()

    def test_what_any_of_the_requests_loses_is_named(self, tab):
        _choose(tab, "webrunner_action")

        tab.generate_all()

        assert tab.gaps_line.text() == (
            "Not sent by this target: the method (this target makes a GET) · headers · the body")
        assert tab.output_actions.suggested_filename() == "web_actions.json"

    def test_a_target_that_sends_everything_shows_no_line(self, tab):
        tab.generate_all()

        assert tab.gaps_line.isHidden()

    def test_changing_the_target_changes_the_line_with_the_output(self, tab):
        tab.generate_all()

        _choose(tab, "loaddensity_python")

        assert tab.gaps_line.text() == "Not sent by this target: headers · the body"

    def test_nothing_selected_shows_no_line(self, tab):
        _choose(tab, "webrunner_action")
        tab.generate_all()

        tab.generate_selected()

        assert tab.gaps_line.isHidden()

    def test_another_file_takes_the_line_away(self, tab):
        _choose(tab, "webrunner_action")
        tab.generate_all()

        tab.load_text(_har(_GET))

        assert tab.gaps_line.isHidden()

    def test_a_file_that_is_not_a_har_export_takes_the_line_away(self, tab):
        _choose(tab, "webrunner_action")
        tab.generate_all()

        tab.load_text("not json")

        assert tab.gaps_line.isHidden()
