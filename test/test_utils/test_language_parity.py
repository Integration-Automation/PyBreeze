from __future__ import annotations

import pathlib
import re

import pybreeze
from pybreeze.extend_multi_language.extend_english import (
    pybreeze_english_word_dict as EN,
)
from pybreeze.extend_multi_language.extend_traditional_chinese import (
    pybreeze_traditional_chinese_word_dict as ZH,
)

_GET_KEY_RE = re.compile(r'language_word_dict\.get\(\s*["\']([A-Za-z0-9_]+)["\']')


def _placeholders(text: str) -> set[str]:
    return set(re.findall(r"{(\w+)}", str(text)))


def _code_used_keys() -> dict[str, str]:
    """Map every literal ``language_word_dict.get("key")`` key to a source file."""
    root = pathlib.Path(pybreeze.__file__).parent
    used: dict[str, str] = {}
    for path in root.rglob("*.py"):
        for match in _GET_KEY_RE.finditer(path.read_text(encoding="utf-8")):
            used.setdefault(match.group(1), path.name)
    return used


class TestLanguageParity:
    def test_same_keys_in_both_languages(self):
        missing_in_zh = set(EN) - set(ZH)
        missing_in_en = set(ZH) - set(EN)
        assert not missing_in_zh, f"Keys present in English but missing in Chinese: {sorted(missing_in_zh)}"
        assert not missing_in_en, f"Keys present in Chinese but missing in English: {sorted(missing_in_en)}"

    def test_no_empty_english_values(self):
        empty = [k for k, v in EN.items() if not str(v).strip()]
        assert not empty, f"English keys with empty values: {empty}"

    def test_no_empty_chinese_values(self):
        empty = [k for k, v in ZH.items() if not str(v).strip()]
        assert not empty, f"Chinese keys with empty values: {empty}"

    def test_placeholders_match_across_languages(self):
        # A {placeholder} present in one language but not the other either crashes
        # .format() or leaks a literal "{x}" when the code concatenates instead.
        mismatched = {
            k: (_placeholders(EN[k]), _placeholders(ZH[k]))
            for k in EN
            if k in ZH and _placeholders(EN[k]) != _placeholders(ZH[k])
        }
        assert not mismatched, f"Placeholder mismatches between languages: {mismatched}"


class TestCodeKeysAreDefined:
    def test_every_get_key_exists_in_dict(self):
        # A typo'd key (e.g. the "cot_cot_..." double prefix) makes get() return
        # None, so the widget silently shows a blank title / message.
        used = _code_used_keys()
        missing = {k: src for k, src in used.items() if k not in EN}
        assert not missing, f"language_word_dict.get() keys missing from the dict: {missing}"
