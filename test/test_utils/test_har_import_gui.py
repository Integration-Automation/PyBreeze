"""Tests for the HAR import tool widget."""
from __future__ import annotations

import json
import os
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.extend_english import pybreeze_english_word_dict as EN
from pybreeze.extend_multi_language.update_language_dict import update_language_dict

_HAR = json.dumps({"log": {"version": "1.2", "entries": [
    {
        "startedDateTime": "2026-07-25T00:00:00.000Z",
        "request": {
            "method": "GET", "url": "https://api.example.com/v1/items?page=1",
            "headers": [{"name": "Accept", "value": "application/json"}],
        },
        "response": {"status": 200, "content": {"mimeType": "application/json"}},
    },
    {
        "startedDateTime": "2026-07-25T00:00:01.000Z",
        "request": {
            "method": "POST", "url": "https://api.example.com/v1/items",
            "headers": [{"name": "Content-Type", "value": "application/json"}],
            "postData": {"mimeType": "application/json", "text": "{\"name\": \"x\"}"},
        },
        "response": {"status": 201, "content": {"mimeType": "application/json"}},
    },
    {
        "startedDateTime": "2026-07-25T00:00:02.000Z",
        "request": {"method": "GET", "url": "https://cdn.example.com/app.css", "headers": []},
        "response": {"status": 200, "content": {"mimeType": "text/css"}},
    },
]}})


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture()
def widget(app):
    from pybreeze.pybreeze_ui.tools_gui.har_import_gui import HarImportGUI
    gui = HarImportGUI()
    yield gui
    gui.close()
    gui.deleteLater()


@pytest.fixture()
def loaded(widget):
    widget.load_text(_HAR)
    return widget


class TestHarImportLoading:
    def test_load_lists_api_requests_only_by_default(self, loaded):
        assert loaded.entry_list.count() == 2

    def test_unchecking_the_filter_lists_every_request(self, loaded):
        loaded.api_only_check.setChecked(False)
        assert loaded.entry_list.count() == 3

    def test_entry_rows_describe_the_request(self, loaded):
        first = loaded.entry_list.item(0).text()
        assert "GET" in first and "/v1/items?page=1" in first and "200" in first

    def test_summary_reports_counts_and_hosts(self, loaded):
        summary = loaded.summary_label.text()
        assert "3" in summary and "2" in summary
        assert "api.example.com" in summary

    def test_invalid_har_reports_an_error(self, widget):
        assert widget.load_text("not a har") is False
        assert widget.entry_list.count() == 0
        assert widget.output_edit.toPlainText() != ""

    def test_error_then_valid_load_recovers(self, widget):
        widget.load_text("not a har")
        assert widget.load_text(_HAR) is True
        assert widget.entry_list.count() == 2


class TestHarImportGeneration:
    def _select_target(self, widget, target_key):
        widget.target_select.setCurrentIndex(widget.target_select.findData(target_key))

    def test_generate_all_covers_every_listed_request(self, loaded):
        loaded.generate_all()
        code = loaded.output_edit.toPlainText()
        assert "/v1/items" in code
        assert "app.css" not in code  # filtered out, so it must not be generated

    def test_generate_all_includes_assets_when_the_filter_is_off(self, loaded):
        loaded.api_only_check.setChecked(False)
        loaded.generate_all()
        assert "app.css" in loaded.output_edit.toPlainText()

    def test_generate_selected_covers_only_the_selection(self, loaded):
        loaded.entry_list.setCurrentRow(1)
        loaded.generate_selected()
        code = loaded.output_edit.toPlainText()
        assert "POST" in code
        assert "page" not in code

    def test_generate_without_selection_shows_the_hint(self, loaded):
        loaded.entry_list.clearSelection()
        loaded.generate_selected()
        assert loaded.output_edit.toPlainText() == EN["har_import_no_selection"]

    def test_pytest_target_writes_one_test_per_request(self, loaded):
        self._select_target(loaded, "pytest")
        loaded.generate_all()
        code = loaded.output_edit.toPlainText()
        assert code.count("def test_") == 2

    def test_action_target_writes_one_action_list(self, loaded):
        self._select_target(loaded, "apitestka_action")
        loaded.generate_all()
        actions = json.loads(loaded.output_edit.toPlainText())
        assert len(actions) == 2

    def test_suggested_filename_follows_the_target(self, loaded):
        self._select_target(loaded, "apitestka_action")
        assert loaded.actions.suggested_filename() == "actions.json"
        self._select_target(loaded, "pytest")
        assert loaded.actions.suggested_filename() == "session.py"

    def test_copy_output(self, app, loaded):
        loaded.generate_all()
        loaded.actions.copy()
        assert "/v1/items" in QApplication.clipboard().text()

    def test_save_before_generating_is_noop(self, loaded):
        assert loaded.actions.save_to_file() is None


class TestHarImportFileDialog:
    def test_open_file_loads_the_chosen_export(self, widget, tmp_path):
        path = tmp_path / "session.har"
        path.write_text(_HAR, encoding="utf-8")
        with patch(
            "pybreeze.pybreeze_ui.tools_gui.har_import_gui.QFileDialog.getOpenFileName",
            return_value=(str(path), "HAR export (*.har *.json)"),
        ):
            result = widget.open_file()
        assert result == str(path)
        assert widget.entry_list.count() == 2

    def test_cancelled_dialog_changes_nothing(self, widget):
        with patch(
            "pybreeze.pybreeze_ui.tools_gui.har_import_gui.QFileDialog.getOpenFileName",
            return_value=("", ""),
        ):
            assert widget.open_file() is None
        assert widget.entry_list.count() == 0

    def test_unreadable_file_reports_an_error(self, widget, tmp_path):
        missing = tmp_path / "gone.har"
        with patch(
            "pybreeze.pybreeze_ui.tools_gui.har_import_gui.QFileDialog.getOpenFileName",
            return_value=(str(missing), ""),
        ):
            assert widget.open_file() is None
        assert widget.output_edit.toPlainText() != ""
