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
from pybreeze.utils.exception.error_templates import ERROR_TEXT_KEY_PREFIX, error_templates


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture()
def chinese(monkeypatch):
    monkeypatch.setattr(error_text_mod.language_wrapper, "language_word_dict", CHINESE)


def _sample(template: str) -> dict[str, str]:
    return {name: f"<{name}>" for name in ("key", "detail", "seconds") if "{" + name + "}" in template}


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
