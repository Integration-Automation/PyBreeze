"""What the executors write into a run window about the run itself, in the IDE language.

A compile, a run starting, a stop, a command that is not there: each is a line
of its own in the window, ``[Error] ...`` or ``[Run] ...``, and they were all
English whatever the IDE spoke.
"""
from __future__ import annotations

from je_editor import language_wrapper

from pybreeze.extend_multi_language.extend_english import pybreeze_english_word_dict

# The language-dictionary key of a notice is this followed by its name
RUN_NOTICE_KEY_PREFIX = "run_window_"


def run_notice(notice: str, /, **fields: object) -> str:
    """The notice ``run_window_<notice>`` with *fields* filled in, as one line (newline included).

    *notice* is positional-only, so a field may be called anything (``[Run] {name}``).
    PyBreeze's English is used when the IDE's dictionary lacks the notice:
    an executor started before ``update_language_dict()`` (a script, a test)
    still says what happened.
    """
    key = RUN_NOTICE_KEY_PREFIX + notice
    template = language_wrapper.language_word_dict.get(key) or pybreeze_english_word_dict[key]
    return template.format(**fields) + "\n"
