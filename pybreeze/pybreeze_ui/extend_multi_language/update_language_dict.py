from pybreeze.pybreeze_ui.extend_multi_language.extend_english import update_english_word_dict
from pybreeze.pybreeze_ui.extend_multi_language.extend_traditional_chinese import \
    update_traditional_chinese_word_dict


def update_language_dict():
    update_traditional_chinese_word_dict()
    update_english_word_dict()
