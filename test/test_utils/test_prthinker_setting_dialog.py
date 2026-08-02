"""The prthinker settings form: what it builds, what it reads back, what it stores."""
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QLineEdit

from pybreeze.extend.prthinker_extend import prthinker_setting
from pybreeze.extend.prthinker_extend.prthinker_setting import (
    BACKENDS, DEFAULT_SETTING, PLATFORMS, SETTING_FILE_NAME, save_setting
)
from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.dialog import prthinker_setting_dialog
from pybreeze.pybreeze_ui.dialog.prthinker_setting_dialog import (
    FIELDS, SECRET_FIELDS, PRThinkerSettingDialog
)


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    """Point the settings file at a temporary directory, never the real home."""
    monkeypatch.setattr(prthinker_setting, "pybreeze_data_dir", lambda: tmp_path)
    return tmp_path


@pytest.fixture()
def dialog(app, data_dir):
    made = PRThinkerSettingDialog()
    yield made
    made.deleteLater()


def stored(data_dir) -> dict:
    return json.loads((data_dir / SETTING_FILE_NAME).read_text(encoding="utf-8"))


class TestTheFormItBuilds:
    def test_every_field_gets_an_editor(self, dialog):
        assert set(dialog.editors) == {key for key, _label in FIELDS}

    def test_a_key_is_shown_as_dots(self, dialog):
        for key in SECRET_FIELDS:
            assert dialog.editors[key].echoMode() == QLineEdit.EchoMode.Password, key

    def test_an_ordinary_field_is_shown_as_text(self, dialog):
        assert dialog.editors["repository"].echoMode() == QLineEdit.EchoMode.Normal

    def test_the_backend_is_chosen_from_the_supported_list(self, dialog):
        editor = dialog.editors["backend"]
        assert isinstance(editor, QComboBox)
        assert [editor.itemText(i) for i in range(editor.count())] == list(BACKENDS)

    def test_the_platform_is_chosen_from_the_supported_list(self, dialog):
        editor = dialog.editors["platform"]
        assert [editor.itemText(i) for i in range(editor.count())] == list(PLATFORMS)

    def test_a_stored_choice_comes_back_selected(self, app, data_dir):
        save_setting({**DEFAULT_SETTING, "backend": "anthropic", "platform": "gitea"})
        made = PRThinkerSettingDialog()
        assert made.editors["backend"].currentText() == "anthropic"
        assert made.editors["platform"].currentText() == "gitea"
        made.deleteLater()

    def test_a_stored_value_that_is_not_on_offer_leaves_the_first_choice(self, app, data_dir):
        (data_dir / SETTING_FILE_NAME).write_text(
            json.dumps({**DEFAULT_SETTING, "backend": "nonsense"}), encoding="utf-8")
        made = PRThinkerSettingDialog()
        assert made.editors["backend"].currentText() == BACKENDS[0]
        made.deleteLater()

    def test_stored_text_is_filled_in(self, app, data_dir):
        save_setting({**DEFAULT_SETTING, "repository": "owner/name"})
        made = PRThinkerSettingDialog()
        assert made.editors["repository"].text() == "owner/name"
        made.deleteLater()


class TestReadingTheFormBack:
    def test_values_reads_both_kinds_of_editor(self, dialog):
        dialog.editors["repository"].setText("owner/name")
        dialog.editors["backend"].setCurrentText("openai")
        values = dialog.values()
        assert values["repository"] == "owner/name"
        assert values["backend"] == "openai"

    def test_values_covers_every_field(self, dialog):
        assert set(dialog.values()) == {key for key, _label in FIELDS}


class TestSaving:
    def test_what_was_typed_reaches_the_file(self, dialog, data_dir):
        dialog.editors["repository"].setText("owner/name")
        dialog.editors["platform_token"].setText("secret-token")
        dialog.save()
        assert stored(data_dir)["repository"] == "owner/name"
        assert stored(data_dir)["platform_token"] == "secret-token"

    def test_saving_closes_the_window(self, dialog):
        dialog.save()
        assert dialog.result() == QDialog.DialogCode.Accepted

    def test_a_failed_save_leaves_the_window_open(self, dialog, monkeypatch):
        # A settings file that cannot be written must not look like a success:
        # the user needs the form still in front of them to retry or copy from.
        monkeypatch.setattr(
            prthinker_setting_dialog, "save_setting", lambda _setting: False)
        dialog.save()
        assert dialog.result() != QDialog.DialogCode.Accepted

    def test_a_field_left_untouched_keeps_its_stored_value(self, app, data_dir):
        save_setting({**DEFAULT_SETTING, "model_name": "kept"})
        made = PRThinkerSettingDialog()
        made.editors["repository"].setText("owner/name")
        made.save()
        assert stored(data_dir)["model_name"] == "kept"
        made.deleteLater()
