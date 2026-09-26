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


from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QMessageBox,
    QVBoxLayout
)
from je_editor import language_wrapper

from pybreeze.extend.prthinker_extend.prthinker_setting import (
    BACKENDS, KEY_FROM_ENVIRONMENT, PLATFORMS, RAG_MODES, load_setting, read_extra_arguments, save_setting,
    setting_path
)
from pybreeze.pybreeze_ui.plain_text import as_text

# 以圓點顯示的欄位 / The fields shown as dots
SECRET_FIELDS = (
    "remote_api_key", "openai_api_key", "anthropic_api_key", "platform_token")

# 從清單裡選的欄位，以及各自的選項 / The fields picked from a list, and each one's choices
CHOICE_FIELDS = {"backend": BACKENDS, "rag": RAG_MODES, "platform": PLATFORMS}

# 表格上的欄位順序，以及每一欄的說明用哪個語言鍵
# The fields in the order they are shown, and the language key labelling each
FIELDS = (
    ("backend", "prthinker_setting_backend_label"),
    ("model_name", "prthinker_setting_model_name_label"),
    ("remote_url", "prthinker_setting_remote_url_label"),
    ("remote_api_key", "prthinker_setting_remote_api_key_label"),
    ("rag", "prthinker_setting_rag_label"),
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
        self.setting: dict[str, str] = load_setting()
        self.editors: dict[str, QLineEdit | QComboBox] = {}

        layout = QVBoxLayout()
        form = QFormLayout()
        for key, label_key in FIELDS:
            form.addRow(self.word_dict.get(label_key), self._editor_for(key))
        layout.addLayout(form)

        # 沒有金鑰欄位的後端，說出金鑰從哪個環境變數來；以前選了它只會因為沒有金鑰而失敗
        # For a backend with no key field, the variable its key comes from: chosen
        # here alone, it used to fail for want of a key with nothing said
        self.key_note = QLabel()
        self.key_note.setWordWrap(True)
        layout.addWidget(self.key_note)
        backend = self.editors["backend"]
        backend.currentTextChanged.connect(self._show_key_note)
        self._show_key_note(backend.currentText())

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
        if key in CHOICE_FIELDS:
            editor = self._chooser(CHOICE_FIELDS[key], self.setting.get(key, ""))
        else:
            editor = QLineEdit(self.setting.get(key, ""))
            if key in SECRET_FIELDS:
                editor.setEchoMode(QLineEdit.EchoMode.Password)
        self.editors[key] = editor
        return editor

    def _show_key_note(self, backend: str) -> None:
        """說出 *backend* 的金鑰從哪個環境變數來；有金鑰欄位的後端就不顯示 / Say where *backend*'s key comes from, if not from this form."""
        variable = KEY_FROM_ENVIRONMENT.get(backend)
        self.key_note.setText(
            self.word_dict.get("prthinker_setting_key_from_environment").format(variable=variable)
            if variable else "")
        self.key_note.setHidden(variable is None)

    @staticmethod
    def _chooser(choices, chosen: str) -> QComboBox:
        """做一個下拉選單，選到目前的值 / A combo box, on the value in use."""
        box = QComboBox()
        box.addItems(list(choices))
        if chosen in choices:
            box.setCurrentText(chosen)
        return box

    def values(self) -> dict[str, str]:
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
        values = self.values()
        try:
            read_extra_arguments(values.get("extra_arguments", ""))
        except ValueError:
            # 以前照存，執行時整串被丟掉，審查少了使用者以為有加上的參數
            # It used to be stored, then dropped whole at run time: a review ran
            # without the arguments the user thought it had
            QMessageBox.warning(
                self, self.word_dict.get("prthinker_setting_dialog_title"),
                self.word_dict.get("prthinker_setting_bad_extra_arguments"))
            return
        self.setting.update(values)
        if save_setting(self.setting):
            self.accept()
            return
        # 以前只寫進 log，視窗不關也不說原因
        # It used to go to the log only: the window stayed open with no reason given
        QMessageBox.warning(
            self, self.word_dict.get("prthinker_setting_dialog_title"),
            as_text(self.word_dict.get("prthinker_setting_save_failed").format(path=setting_path())))
