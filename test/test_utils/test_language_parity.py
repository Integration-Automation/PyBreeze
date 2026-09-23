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

# language_word_dict.get("key"), the same through a local alias
# (word = language_wrapper.language_word_dict; word.get("key")), and the
# diagram editor's _lang("key", fallback), whose English fallback hid a key
# missing from both dicts
_GET_KEY_RE = re.compile(
    r'(?:\b(?:language_word_dict|word_dict|word)\.get|\b_lang)\(\s*["\']([A-Za-z0-9_]+)["\']')


def _placeholders(text: str) -> set[str]:
    return set(re.findall(r"{(\w+)}", str(text)))


def _code_used_keys() -> dict[str, str]:
    """Map every literal key the code looks up (see ``_GET_KEY_RE``) to a source file."""
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

    def test_every_prompt_editor_label_key_exists(self):
        # The prompt editors pass their keys through a dataclass, so the regex
        # above cannot see them. Check the declared keys directly instead, or a
        # renamed key would show up as a blank button with nothing to catch it.
        import dataclasses

        from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.cot_prompt_editor_widget import (
            COT_LABELS
        )
        from pybreeze.pybreeze_ui.extend_ai_gui.prompt_edit_gui.skills_prompt_editor_widget import (
            SKILL_LABELS
        )

        missing = [
            key
            for labels in (COT_LABELS, SKILL_LABELS)
            for key in dataclasses.astuple(labels)
            if key not in EN
        ]
        assert not missing, f"Prompt editor label keys missing from the dict: {missing}"

    def test_every_header_finding_and_level_has_a_message(self):
        # The header analyzer's GUI builds these keys with an f-string, which
        # the regex above cannot see; a missing one shows the bare code
        from pybreeze.utils.header_tools import header_analyzer

        source = pathlib.Path(header_analyzer.__file__).read_text(encoding="utf-8")
        codes = set(re.findall(r'HeaderFinding\(\s*"([a-z0-9_]+)"', source))
        codes |= {code for _name, _canonical, code in header_analyzer._RESPONSE_SECURITY_HEADERS}
        levels = {header_analyzer.LEVEL_WARNING, header_analyzer.LEVEL_INFO}

        assert len(codes) > 10
        missing = sorted(f"header_finding_{code}" for code in codes if f"header_finding_{code}" not in EN)
        missing += sorted(f"header_analyzer_level_{level}" for level in levels
                          if f"header_analyzer_level_{level}" not in EN)
        assert not missing, f"Header analyzer keys missing from the dict: {missing}"


class TestEveryLanguageServesPyBreezeStrings:
    def test_each_registered_language_resolves_every_key(self):
        # JEditor serves each language but English from a merged copy of its dict
        # and English's. Once PyBreeze's strings are in, every language, even one
        # PyBreeze does not translate, must resolve every key the code asks for.
        from je_editor import language_wrapper

        from pybreeze.extend_multi_language.update_language_dict import update_language_dict

        update_language_dict()
        used = _code_used_keys()
        original = language_wrapper.language
        missing = {}
        try:
            for language in language_wrapper.available_languages():
                language_wrapper.reset_language(language)
                blank = sorted(
                    key for key in used if not language_wrapper.language_word_dict.get(key))
                if blank:
                    missing[language] = blank
        finally:
            language_wrapper.reset_language(original)
        assert not missing, f"Keys a language cannot resolve: {missing}"

    def test_the_window_is_called_pybreeze_in_every_language(self):
        from je_editor import language_wrapper

        from pybreeze.extend_multi_language.update_language_dict import update_language_dict

        update_language_dict()
        original = language_wrapper.language
        names = {}
        try:
            for language in language_wrapper.available_languages():
                language_wrapper.reset_language(language)
                names[language] = language_wrapper.language_word_dict["application_name"]
        finally:
            language_wrapper.reset_language(original)
        assert set(names.values()) == {"PyBreeze"}, names
