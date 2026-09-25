"""The Sphinx pages' inline markup renders, in Chinese as in English.

reStructuredText ends ``**strong**`` or ````literal```` only before whitespace or
certain punctuation, and starts one only after them. Chinese runs on without
spaces, so ``**程式碼輸入區**（左面板）`` was published with its asterisks showing.
An escaped space (backslash, space) between them renders as nothing.
"""
from __future__ import annotations

from pathlib import Path

import pytest

docutils_core = pytest.importorskip("docutils.core")
from docutils import nodes  # noqa: E402 — docutils may be missing: skipped then

_SOURCE = Path(__file__).resolve().parents[2] / "docs" / "source"


def _inline_markup_problems(path: Path) -> list[str]:
    document = docutils_core.publish_doctree(
        path.read_text(encoding="utf-8"), source_path=str(path),
        settings_overrides={"report_level": 5, "halt_level": 5, "warning_stream": False})
    # Only the inline markup: the Sphinx directives (toctree) are unknown to plain docutils
    return [message.astext() for message in document.findall(nodes.system_message)
            if ") Inline " in message.astext()]


def test_there_are_pages_to_check():
    assert len(list(_SOURCE.rglob("*.rst"))) > 20


@pytest.mark.parametrize("page", sorted(_SOURCE.rglob("*.rst")), ids=lambda page: str(page.relative_to(_SOURCE)))
def test_the_inline_markup_of_each_page_closes(page):
    assert _inline_markup_problems(page) == []
