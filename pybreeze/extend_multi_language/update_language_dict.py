from __future__ import annotations

from je_editor import language_wrapper

from pybreeze.extend_multi_language.supported_languages import MAINTAINED
from pybreeze.utils.logging.logger import pybreeze_logger

# The one JEditor string PyBreeze replaces rather than adds. The product's name is
# the same in every language, but JEditor's other languages (Japanese, Simplified
# Chinese, any a plugin registers) carry their own "JEditor", which would win over
# the English fallback PyBreeze's other strings rely on.
_APPLICATION_NAME_KEY = "application_name"


def update_language_dict():
    """Add PyBreeze's strings to JEditor's word dicts, for each language PyBreeze maintains.

    Call it before JEditor picks the startup language (``PyBreezeMainWindow``
    does, ahead of ``EditorMain.__init__``): JEditor serves every language but
    English from a merged copy built at that moment.

    Each of JEditor's own dictionaries is added to in place. It is the object
    ``choose_language_dict`` serves, so the strings are there for whoever holds
    it; registering the language again (``register_natural_language``) would
    replace that object and leave the editor's own strings behind.
    """
    for language in MAINTAINED:
        words = language_wrapper.choose_language_dict.get(language.key)
        if words is None:
            # JEditor no longer has the language: nothing to add PyBreeze's strings to
            pybreeze_logger.error("update_language_dict.py JEditor has no %s to translate into", language.key)
            continue
        words.update(language.words)
    application_name = MAINTAINED[0].words[_APPLICATION_NAME_KEY]
    for word_dict in language_wrapper.choose_language_dict.values():
        word_dict[_APPLICATION_NAME_KEY] = application_name
