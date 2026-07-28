"""
prthinker 的設定視窗
The settings window for prthinker.

一張表填完就能開始審查：要用哪個推論後端、模型或伺服器在哪、以及要對哪個儲存庫發表
審查意見。金鑰欄位以圓點顯示，寫進使用者目錄下的設定檔，不會出現在命令列上。
One form is all a review needs: which inference backend to use, where the model
or the server is, and which repository the review is posted to. A key is shown
as dots, is written to the settings file under the user's own directory, and
never reaches a command line.
"""
from __future__ import annotations

from typing import Dict

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit,
    QVBoxLayout
)
from je_editor import language_wrapper

from pybreeze.extend.prthinker_extend.prthinker_setting import (
    BACKENDS, PLATFORMS, load_setting, save_setting, setting_path
)

# 以圓點顯示的欄位 / The fields shown as dots
SECRET_FIELDS = (
    "remote_api_key", "openai_api_key", "anthropic_api_key", "platform_token")

# 表格上的欄位順序，以及每一欄的說明用哪個語言鍵
# The fields in the order they are shown, and the language key labelling each
FIELDS = (
    ("backend", "prthinker_setting_backend_label"),
    ("model_name", "prthinker_setting_model_name_label"),
    ("remote_url", "prthinker_setting_remote_url_label"),
    ("remote_api_key", "prthinker_setting_remote_api_key_label"),
    ("openai_base_url", "prthinker_setting_openai_base_url_label"),
    ("openai_api_key", "prthinker_setting_openai_api_key_label"),
    ("anthropic_api_key", "prthinker_setting_anthropic_api_key_label"),
    ("platform", "prthinker_setting_platform_label"),
    ("platform_base_url", "prthinker_setting_platform_base_url_label"),
    ("repository", "prthinker_setting_repository_label"),
    ("platform_token", "prthinker_setting_platform_token_label"),
    ("extra_arguments", "prthinker_setting_extra_arguments_label"),
    ("source_path", "prthinker_setting_source_path_label"),
)


class PRThinkerSettingDialog(QDialog):
    """填 prthinker 設定的視窗 / The window prthinker's settings are filled in on."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.word_dict = language_wrapper.language_word_dict
        self.setWindowTitle(self.word_dict.get("prthinker_setting_dialog_title"))
        self.setting: Dict[str, str] = load_setting()
        self.editors: Dict[str, QLineEdit | QComboBox] = {}

        layout = QVBoxLayout()
        form = QFormLayout()
        for key, label_key in FIELDS:
            form.addRow(self.word_dict.get(label_key), self._editor_for(key))
        layout.addLayout(form)

        # 設定寫在哪裡，使用者才知道要備份或刪掉哪個檔案
        # Where the settings live, so it is clear what to back up or remove
        where = QLabel(
            f"{self.word_dict.get('prthinker_setting_stored_at_label')} {setting_path()}")
        where.setWordWrap(True)
        layout.addWidget(where)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _editor_for(self, key: str):
        """依欄位種類給對應的輸入元件 / The right kind of editor for a field."""
        if key == "backend":
            editor = self._chooser(BACKENDS, self.setting.get(key, ""))
        elif key == "platform":
            editor = self._chooser(PLATFORMS, self.setting.get(key, ""))
        else:
            editor = QLineEdit(self.setting.get(key, ""))
            if key in SECRET_FIELDS:
                editor.setEchoMode(QLineEdit.EchoMode.Password)
        self.editors[key] = editor
        return editor

    @staticmethod
    def _chooser(choices, chosen: str) -> QComboBox:
        """做一個下拉選單，選到目前的值 / A combo box, on the value in use."""
        box = QComboBox()
        box.addItems(list(choices))
        if chosen in choices:
            box.setCurrentText(chosen)
        return box

    def values(self) -> Dict[str, str]:
        """
        表格上目前填的內容
        What the form currently holds.

        :return: 設定 / the settings
        """
        return {
            key: editor.currentText() if isinstance(editor, QComboBox) else editor.text()
            for key, editor in self.editors.items()
        }

    def save(self) -> None:
        """存檔並關閉；存不起來就留在視窗上 / Store and close, or stay open if it cannot be stored."""
        self.setting.update(self.values())
        if save_setting(self.setting):
            self.accept()
