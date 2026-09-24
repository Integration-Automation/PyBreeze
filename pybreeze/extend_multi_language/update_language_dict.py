from __future__ import annotations

from je_editor import language_wrapper

from pybreeze.extend_multi_language.extend_english import (
    pybreeze_english_word_dict, update_english_word_dict
)
from pybreeze.extend_multi_language.extend_traditional_chinese import \
    update_traditional_chinese_word_dict

# The one JEditor string PyBreeze replaces rather than adds. The product's name is
# the same in every language, but JEditor's other languages (Japanese, Simplified
# Chinese, any a plugin registers) carry their own "JEditor", which would win over
# the English fallback PyBreeze's other strings rely on.
_APPLICATION_NAME_KEY = "application_name"


def update_language_dict():
    """Add PyBreeze's strings to JEditor's word dicts.

    Call it before JEditor picks the startup language (``PyBreezeMainWindow``
    does, ahead of ``EditorMain.__init__``): JEditor serves every language but
    English from a merged copy built at that moment.
    """
    update_traditional_chinese_word_dict()
    update_english_word_dict()
    application_name = pybreeze_english_word_dict[_APPLICATION_NAME_KEY]
    for word_dict in language_wrapper.choose_language_dict.values():
        word_dict[_APPLICATION_NAME_KEY] = application_name
