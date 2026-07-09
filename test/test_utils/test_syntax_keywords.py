from __future__ import annotations

from collections import Counter

import pybreeze.pybreeze_ui.syntax.syntax_keyword as sk


def _keyword_lists():
    """Yield (name, list) for every module-level keyword sequence of strings."""
    for name in dir(sk):
        if name.startswith("_"):
            continue
        value = getattr(sk, name)
        if isinstance(value, (list, tuple)) and value and all(isinstance(x, str) for x in value):
            yield name, value


class TestSyntaxKeywords:
    def test_no_duplicate_keywords(self):
        offenders = {}
        for name, value in _keyword_lists():
            dups = {kw: n for kw, n in Counter(value).items() if n > 1}
            if dups:
                offenders[name] = dups
        assert not offenders, f"Duplicate keywords found: {offenders}"

    def test_no_blank_keywords(self):
        for name, value in _keyword_lists():
            blanks = [kw for kw in value if not kw.strip()]
            assert not blanks, f"{name} contains blank keywords"
