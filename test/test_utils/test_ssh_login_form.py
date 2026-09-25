"""The SSH login form: Enter connects, and the key file can be picked instead of typed."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.connect_gui.ssh import ssh_login_widget as login_mod


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture
def form(app):
    widget = login_mod.LoginWidget()
    yield widget
    widget.deleteLater()


class TestEnter:
    @pytest.mark.parametrize("field", ["host_edit", "user_edit", "pass_edit", "key_edit"])
    def test_in_any_field_connects(self, form, field):
        # Connecting needed the mouse
        clicks: list = []
        form.connect_btn.clicked.connect(lambda: clicks.append(True))

        getattr(form, field).returnPressed.emit()

        assert clicks == [True]


class TestChoosingTheKey:
    def test_a_chosen_file_fills_the_path_and_ticks_key_authentication(self, form, monkeypatch, tmp_path):
        key = tmp_path / "id_ed25519"
        asked: list = []
        monkeypatch.setattr(login_mod.QFileDialog, "getOpenFileName",
                            staticmethod(lambda *args: asked.append(args) or (str(key), "")))

        form.browse_key_btn.click()

        assert form.key_edit.text() == str(key)
        assert form.use_key_check.isChecked()
        assert asked[0][1] == login_mod.language_wrapper.language_word_dict.get(
            "ssh_login_widget_dialog_title_choose_key")

    def test_starts_in_the_ssh_folder(self, form, monkeypatch, tmp_path):
        (tmp_path / ".ssh").mkdir()
        monkeypatch.setattr(login_mod.Path, "home", staticmethod(lambda: tmp_path))
        asked: list = []
        monkeypatch.setattr(login_mod.QFileDialog, "getOpenFileName",
                            staticmethod(lambda *args: asked.append(args) or ("", "")))

        form.choose_key_file()

        assert asked[0][2] == str(tmp_path / ".ssh")

    def test_cancelling_changes_nothing(self, form, monkeypatch):
        form.key_edit.setText("typed")
        monkeypatch.setattr(login_mod.QFileDialog, "getOpenFileName", staticmethod(lambda *args: ("", "")))

        form.choose_key_file()

        assert form.key_edit.text() == "typed"
        assert not form.use_key_check.isChecked()


class TestTheSecretField:
    """With key authentication the password field holds the key's passphrase, and says so."""

    def _words(self):
        from je_editor import language_wrapper
        return language_wrapper.language_word_dict

    def test_it_asks_for_the_password_at_first(self, form):
        assert form.pass_label.text() == self._words().get("ssh_login_widget_label_password")

    def test_key_authentication_makes_it_the_passphrase(self, form):
        form.use_key_check.setChecked(True)
        assert form.pass_label.text() == self._words().get("ssh_login_widget_label_passphrase")
        assert form.pass_edit.placeholderText() == self._words().get("ssh_login_widget_placeholder_passphrase")

    def test_unticking_it_gives_the_password_back(self, form):
        form.use_key_check.setChecked(True)
        form.use_key_check.setChecked(False)
        assert form.pass_label.text() == self._words().get("ssh_login_widget_label_password")
        assert form.pass_edit.placeholderText() == self._words().get("ssh_login_widget_placeholder_password")
