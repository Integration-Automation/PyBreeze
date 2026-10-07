"""Which interface languages PyBreeze answers for, and which it only passes on.

The Language menu is JEditor's, and it lists every language JEditor knows.
PyBreeze adds its own strings (its menus, its tools, its messages) for some of
them only. Picked, any other language changes the editor's own menus and
leaves PyBreeze's in English, and nothing said which was which: the answer was
in which dictionary files happened to exist.

This module is where it is said:

- :data:`MAINTAINED` are the languages PyBreeze owns its strings in. Every
  PyBreeze string is translated in each, the dictionaries hold the same keys,
  and these are the languages the documentation calls supported.
- :data:`EDITOR_ONLY` are the languages JEditor brings that PyBreeze adds
  nothing to. They work, in the sense above; a missing translation in one is
  not a bug in PyBreeze.
- A language neither list names came from a translation plugin
  (:func:`who_translates` calls it :attr:`Owner.PLUGIN`).

Who owns a string follows from where its key is defined: JEditor's keys are
JEditor's in every language, PyBreeze's keys are PyBreeze's. The two meet in a
few keys only (:data:`REWORDED_JEDITOR_KEYS`): JEditor's, with PyBreeze's own
wording in the languages it maintains.

A test reads JEditor's own list of languages and fails when one is in neither
list here, so a language JEditor adds has to be placed before it is shipped.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pybreeze.extend_multi_language.extend_english import pybreeze_english_word_dict
from pybreeze.extend_multi_language.extend_traditional_chinese import pybreeze_traditional_chinese_word_dict


class Owner(Enum):
    """Who translates PyBreeze's strings in a language."""

    PYBREEZE = "pybreeze"   # PyBreeze does: the language is supported
    NOBODY = "nobody"       # JEditor's language; PyBreeze's strings stay in English
    PLUGIN = "plugin"       # a translation plugin registered it, and translates what it chooses to


@dataclass(frozen=True)
class MaintainedLanguage:
    """A language PyBreeze translates its strings into.

    :param key: the language's name in JEditor's language wrapper, which a saved setting holds
    :param display_name: the name the Language menu shows, written as the language writes it
    :param words: PyBreeze's strings in it
    """

    key: str
    display_name: str
    words: dict[str, str]


# The first is the one the others fall back to
MAINTAINED: tuple[MaintainedLanguage, ...] = (
    MaintainedLanguage("English", "English", pybreeze_english_word_dict),
    MaintainedLanguage("Traditional_Chinese", "繁體中文", pybreeze_traditional_chinese_word_dict),
)

# JEditor's languages PyBreeze adds no strings to: key -> the name the Language menu shows
EDITOR_ONLY: dict[str, str] = {
    "Japanese": "日本語",
    "Simplified_Chinese": "简体中文",
}


# JEditor's keys that PyBreeze words its own way in the languages it maintains,
# each a key or the start of one: the product's name, and the plugin browser and
# the Plugins menu, which PyBreeze shows as its own. Every other key is defined
# on one side only.
REWORDED_JEDITOR_KEYS: tuple[str, ...] = ("application_name", "plugin_browser_", "plugin_menu_")


def rewords_jeditor(key: str) -> bool:
    """Whether *key* is one of JEditor's that PyBreeze gives its own wording."""
    return key.startswith(REWORDED_JEDITOR_KEYS)


def who_translates(language: str) -> Owner:
    """Who translates PyBreeze's strings in *language* (a key of JEditor's language wrapper)."""
    if any(language == maintained.key for maintained in MAINTAINED):
        return Owner.PYBREEZE
    return Owner.NOBODY if language in EDITOR_ONLY else Owner.PLUGIN
