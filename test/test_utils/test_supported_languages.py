"""Which languages PyBreeze translates and which it only passes on from JEditor: said in one place, and checked."""
from __future__ import annotations

import logging
import pathlib
import re

import pytest
from je_editor import language_wrapper

import pybreeze
from pybreeze.extend_multi_language import update_language_dict as merger
from pybreeze.extend_multi_language.supported_languages import (
    EDITOR_ONLY,
    MAINTAINED,
    REWORDED_JEDITOR_KEYS,
    MaintainedLanguage,
    Owner,
    rewords_jeditor,
    who_translates,
)
from pybreeze.extend_multi_language.update_language_dict import update_language_dict

_ROOT = pathlib.Path(pybreeze.__file__).parent.parent
_READMES = ("README.md", "README/README_zh-TW.md", "README/README_zh-CN.md")
# A key someone could have typed into a settings file: letters, digits and underscores
_KEY = re.compile(r"[A-Za-z][A-Za-z0-9_]*")


class TestTheList:
    def test_pybreeze_maintains_english_and_traditional_chinese(self):
        assert [(language.key, language.display_name) for language in MAINTAINED] == [
            ("English", "English"), ("Traditional_Chinese", "繁體中文")]

    def test_the_first_is_the_one_the_others_fall_back_to(self):
        assert MAINTAINED[0].key == "English"

    def test_japanese_and_simplified_chinese_are_jeditors_alone(self):
        assert EDITOR_ONLY == {"Japanese": "日本語", "Simplified_Chinese": "简体中文"}

    def test_no_language_is_in_both_lists(self):
        assert not {language.key for language in MAINTAINED} & set(EDITOR_ONLY)

    def test_a_key_is_one_a_saved_setting_can_hold(self):
        for key in [language.key for language in MAINTAINED] + list(EDITOR_ONLY):
            assert _KEY.fullmatch(key), key

    def test_every_maintained_language_has_the_same_strings(self):
        # Parity, for however many languages there are: one string added to one only is found here
        reference = set(MAINTAINED[0].words)
        different = {language.key: sorted(set(language.words) ^ reference)
                     for language in MAINTAINED if set(language.words) != reference}

        assert different == {}

    def test_no_maintained_language_leaves_a_string_empty(self):
        empty = [(language.key, key) for language in MAINTAINED for key, value in language.words.items()
                 if not isinstance(value, str) or not value.strip()]

        assert empty == []

    @pytest.mark.parametrize(("language", "owner"), [
        ("English", Owner.PYBREEZE), ("Traditional_Chinese", Owner.PYBREEZE),
        ("Japanese", Owner.NOBODY), ("Simplified_Chinese", Owner.NOBODY),
        ("French", Owner.PLUGIN), ("", Owner.PLUGIN),
    ])
    def test_who_translates_pybreezes_strings_in_a_language(self, language, owner):
        assert who_translates(language) is owner


class TestAgainstJEditor:
    def test_every_language_jeditor_offers_is_placed(self):
        # A language JEditor adds has to be put in one list or the other before it ships
        built_in = {"English", "Traditional_Chinese", "Simplified_Chinese", "Japanese"}
        offered = set(language_wrapper.display_names)

        assert offered == {language.key for language in MAINTAINED} | set(EDITOR_ONLY)
        assert offered == built_in

    def test_a_maintained_language_is_one_jeditor_serves(self):
        for language in MAINTAINED:
            assert language.key in language_wrapper.choose_language_dict, language.key

    def test_the_names_are_the_ones_the_language_menu_shows(self):
        named = {language.key: language.display_name for language in MAINTAINED} | EDITOR_ONLY

        assert {key: language_wrapper.display_name(key) for key in named} == named

    def test_merging_puts_every_string_into_jeditors_own_dictionaries(self):
        update_language_dict()

        for language in MAINTAINED:
            served = language_wrapper.choose_language_dict[language.key]
            assert all(served[key] == value for key, value in language.words.items()), language.key

    def test_pybreeze_and_jeditor_meet_only_in_the_keys_pybreeze_rewords(self):
        # An editor-only language holds JEditor's keys and none of PyBreeze's own. The
        # keys both define are the product's name and the plugin browser and menu;
        # another one would be a PyBreeze string silently replacing an editor's
        update_language_dict()

        for language in EDITOR_ONLY:
            shared = set(MAINTAINED[0].words) & set(language_wrapper.choose_language_dict[language])
            assert shared, language
            assert [key for key in sorted(shared) if not rewords_jeditor(key)] == [], language

    def test_each_reworded_key_is_one_jeditor_has(self):
        jeditors = set(language_wrapper.choose_language_dict[next(iter(EDITOR_ONLY))])

        for start in REWORDED_JEDITOR_KEYS:
            assert any(key.startswith(start) for key in jeditors), start
            assert any(key.startswith(start) for key in MAINTAINED[0].words), start

    def test_every_language_calls_the_window_pybreeze(self):
        update_language_dict()

        names = {key: words["application_name"] for key, words in language_wrapper.choose_language_dict.items()}
        assert set(names.values()) == {"PyBreeze"}

    def test_a_language_jeditor_no_longer_has_is_logged_and_the_rest_are_merged(self, monkeypatch, caplog):
        gone = MaintainedLanguage("Klingon", "tlhIngan Hol", {"application_name": "PyBreeze", "only_here": "nuqneH"})
        monkeypatch.setattr(merger, "MAINTAINED", (*MAINTAINED, gone))

        with caplog.at_level(logging.ERROR):
            update_language_dict()

        assert "Klingon" in caplog.text
        assert "Klingon" not in language_wrapper.choose_language_dict
        assert language_wrapper.choose_language_dict["English"]["application_name"] == "PyBreeze"


class TestTheDictionariesArePlainData:
    @pytest.mark.parametrize("module", ["extend_english", "extend_traditional_chinese", "supported_languages"])
    def test_a_dictionary_module_imports_no_editor(self, module):
        # The list of languages can be read without JEditor or Qt: a test, a script, the docs
        source = (_ROOT / "pybreeze" / "extend_multi_language" / f"{module}.py").read_text(encoding="utf-8")

        assert not re.search(r"^\s*(from|import)\s+(je_editor|PySide6)\b", source, re.MULTILINE)


class TestTheReadmes:
    @pytest.mark.parametrize("readme", _READMES)
    def test_each_names_every_language_as_the_menu_shows_it(self, readme):
        # The supported set is said in three files; a language added to the list is added to them
        text = (_ROOT / readme).read_text(encoding="utf-8")
        missing = [name for name in [language.display_name for language in MAINTAINED] + list(EDITOR_ONLY.values())
                   if name not in text]

        assert missing == []
