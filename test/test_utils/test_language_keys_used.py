"""Every word the language dictionaries define is still asked for somewhere."""
from __future__ import annotations

import re
from pathlib import Path

from pybreeze.extend_multi_language.extend_english import pybreeze_english_word_dict

PACKAGE = Path(__file__).resolve().parents[2] / "pybreeze"

# Keys whose name is put together at run time, and JEditor's own widgets'
# (its plugin browser reads plugin_browser_*, which PyBreeze translates)
BUILT_OR_READ_ELSEWHERE = (
    "error_text_",                           # error_text: ERROR_TEXT_KEY_PREFIX + an exception tag
    "run_window_",                           # run_notice.RUN_NOTICE_KEY_PREFIX
    "ssh_file_viewer_context_menu_action_",  # ssh_file_viewer_widget: f"...{name}"
    "ssh_file_viewer_tree_header_",
    "ssh_file_viewer_type_",
    "header_analyzer_level_",                # header_analyzer_gui: f"...{finding.level}"
    "header_finding_",
    "plugin_browser_",
)


def _source_outside_the_dictionaries() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in PACKAGE.rglob("*.py")
        if "extend_multi_language" not in path.parts
    )


def test_no_word_is_left_unused():
    source = _source_outside_the_dictionaries()
    unused = [
        key for key in pybreeze_english_word_dict
        if not key.startswith(BUILT_OR_READ_ELSEWHERE)
        and not re.search(rf"[\"']{re.escape(key)}[\"']", source)
    ]
    assert unused == []
