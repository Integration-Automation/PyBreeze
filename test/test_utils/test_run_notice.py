"""A run window's own notices ([Error], [Run], [Mail] ...) in the IDE language."""
from __future__ import annotations

import pathlib
import re

import pybreeze
from pybreeze.extend.process_executor import run_notice as run_notice_mod
from pybreeze.extend.process_executor.run_notice import RUN_NOTICE_KEY_PREFIX, run_notice
from pybreeze.extend_multi_language.extend_english import pybreeze_english_word_dict as ENGLISH
from pybreeze.extend_multi_language.extend_traditional_chinese import (
    pybreeze_traditional_chinese_word_dict as CHINESE,
)


def test_a_notice_in_chinese(monkeypatch):
    # "[Error] Command not found: gcc" whatever the IDE spoke
    monkeypatch.setattr(run_notice_mod.language_wrapper, "language_word_dict", CHINESE)

    assert run_notice("command_not_found", command="gcc") == "[錯誤] 找不到指令：gcc\n"
    assert run_notice("run", name="build/main.exe") == "[執行] build/main.exe\n"


def test_english_when_the_ide_dictionary_lacks_the_notice(monkeypatch):
    # An executor started before update_language_dict() (a script, a test)
    monkeypatch.setattr(run_notice_mod.language_wrapper, "language_word_dict", {})

    assert run_notice("compile_failed", code=3) == "[Compile failed] exit code 3\n"


def test_every_notice_the_executors_use_is_in_both_dictionaries():
    executors = pathlib.Path(pybreeze.__file__).parent / "extend" / "process_executor"
    used = {name for path in executors.rglob("*.py")
            for name in re.findall(r'run_notice\(\s*"(\w+)"', path.read_text(encoding="utf-8"))}

    assert used
    assert not {RUN_NOTICE_KEY_PREFIX + name for name in used} - set(ENGLISH)
    assert not {RUN_NOTICE_KEY_PREFIX + name for name in used} - set(CHINESE)


def test_no_executor_writes_an_english_notice_of_its_own():
    # They were f"[Error] ..." literals in append_output and the mail notice
    executors = pathlib.Path(pybreeze.__file__).parent / "extend" / "process_executor"
    literal = re.compile(r'f?"\[(?:Error|Run|Compile|Compile failed|Stopped|Mail)\]')
    offenders = [path.name for path in executors.rglob("*.py") if literal.search(path.read_text(encoding="utf-8"))]
    assert not offenders


def test_why_a_report_mail_was_not_sent_in_chinese(monkeypatch):
    # "[郵件] 沒有寄出測試報告：no mail user is set"
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from pybreeze.extend.process_executor.process_executor_utils import _MailNotice
    from pybreeze.utils.exception.exception_tags import mail_no_user_error

    QApplication.instance() or QApplication([])
    monkeypatch.setattr(run_notice_mod.language_wrapper, "language_word_dict", CHINESE)
    notice = _MailNotice()
    told: list = []
    notice.told.connect(lambda text, is_error: told.append((text, is_error)))

    notice.tell(mail_no_user_error)

    assert told == [("[郵件] 沒有寄出測試報告：沒有設定郵件使用者\n", True)]


def test_the_exit_code_and_held_output_lines_in_chinese(monkeypatch):
    monkeypatch.setattr(run_notice_mod.language_wrapper, "language_word_dict", CHINESE)

    assert run_notice("exit_code", code=0) == "執行結束，結束代碼 0\n"
    assert run_notice("output_still_held").startswith("[這次執行啟動的某個行程仍握著輸出")
