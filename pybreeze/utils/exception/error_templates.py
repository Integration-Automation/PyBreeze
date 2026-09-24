"""The tool error constants as translatable templates.

``exception_tags`` holds the English reasons the pure tools raise. Each one whose
name ends in ``_error`` is also a language-dictionary entry, ``error_text_<name>``:
the English dictionary takes them from here, and ``pybreeze_ui/error_text.py``
turns a raised message back into its entry in the IDE language.
"""
from __future__ import annotations

import re

from pybreeze.utils.exception import exception_tags

# The language-dictionary key of a constant is this followed by its name
ERROR_TEXT_KEY_PREFIX = "error_text_"
# A replacement field in a constant: {detail}, {key!r}
TEMPLATE_FIELD = re.compile(r"\{(\w+)(?:![rsa])?\}")


def error_templates() -> dict[str, str]:
    """Every tool error constant by name, its fields without a conversion (``{key!r}`` as ``{key}``)."""
    return {
        name: TEMPLATE_FIELD.sub(r"{\1}", value)
        for name, value in vars(exception_tags).items()
        if name.endswith("_error") and isinstance(value, str)
    }
