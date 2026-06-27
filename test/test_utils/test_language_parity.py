from __future__ import annotations

import re

from pybreeze.extend_multi_language.extend_english import (
    pybreeze_english_word_dict as EN,
)
from pybreeze.extend_multi_language.extend_traditional_chinese import (
    pybreeze_traditional_chinese_word_dict as ZH,
)


def _placeholders(text: str) -> set[str]:
    return set(re.findall(r"{(\w+)}", str(text)))


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
