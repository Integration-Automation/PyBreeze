"""Why a tool refused its input, in the IDE language.

The pure tools (``utils``) raise their reasons in English, from the constants in
``exception_tags``, and log them as they are. A tool tab shows the reason inside
a translated sentence, so in Traditional Chinese it read "轉換失敗：no value
provided". :func:`error_text` finds the constant a message was made from, the
values put into it and any detail after it, and gives the same message from the
language dictionary (``utils/exception/error_templates.py``).
"""
from __future__ import annotations

import re
from functools import cache

from je_editor import language_wrapper

from pybreeze.utils.exception.error_templates import (
    ERROR_TEXT_KEY_PREFIX,
    TEMPLATE_FIELD,
    error_templates,
)


@cache
def _patterns() -> tuple[tuple[str, re.Pattern], ...]:
    """(name, pattern) for each constant, the one with the most fixed text first."""
    patterns = []
    for name, template in error_templates().items():
        parts, position, fixed = [], 0, 0
        for field in TEMPLATE_FIELD.finditer(template):
            literal = template[position:field.start()]
            parts.extend((re.escape(literal), f"(?P<{field.group(1)}>.*?)"))
            fixed += len(literal)
            position = field.end()
        parts.append(re.escape(template[position:]))
        fixed += len(template) - position
        # A detail may follow the constant: "can't reformat JSON: ... (<reason>)"
        pattern = re.compile("".join(parts) + r"(?P<_rest>.*)\Z", re.DOTALL)
        patterns.append((fixed, name, pattern))
    patterns.sort(key=lambda item: -item[0])
    return tuple((name, pattern) for _fixed, name, pattern in patterns)


def error_text(message: str) -> str:
    """*message* in the IDE language when it was made from a tool error constant; as it is otherwise."""
    for name, pattern in _patterns():
        match = pattern.match(message)
        if match is None:
            continue
        translation = language_wrapper.language_word_dict.get(ERROR_TEXT_KEY_PREFIX + name)
        if not translation:
            return message
        fields = match.groupdict()
        rest = fields.pop("_rest")
        return translation.format(**fields) + rest
    return message
