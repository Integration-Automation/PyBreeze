"""Every key in PyBreeze's dictionaries is one something asks for.

``diagram_editor_confirm_title`` stayed in both dictionaries after the only code
asking for it was gone. A key is used when the package names it, or when it
belongs to a family whose names are built as the IDE runs.
"""
from __future__ import annotations

import re
from pathlib import Path

from pybreeze.extend_multi_language.extend_english import pybreeze_english_word_dict

_PACKAGE = Path(__file__).resolve().parents[2] / "pybreeze"

# Families of keys whose names are built at run time, and where
_BUILT_AT_RUN_TIME = (
    "error_text_",                            # error_text.py: ERROR_TEXT_KEY_PREFIX + a tag
    "run_window_",                            # run_notice.py: a run window's own notices
    "header_finding_", "header_analyzer_level_",  # header_analyzer_gui.py: a finding's code and level
    "http_status_category_",                  # http_status_gui.py: CATEGORY_KEY_PREFIX + the class
    "ssh_file_viewer_context_menu_action_",   # ssh_file_viewer_widget.py: the menu's table
    "ssh_file_viewer_tree_header_", "ssh_file_viewer_type_",
    "plugin_browser_",                        # JEditor's Plugin Browser asks for these
)


def test_every_key_is_asked_for():
    code = "\n".join(path.read_text(encoding="utf-8") for path in _PACKAGE.rglob("*.py")
                     if "extend_multi_language" not in path.parts and "__pycache__" not in path.parts)
    named = set(re.findall(r"['\"]([a-z][a-z0-9_]*)['\"]", code))
    unused = [key for key in pybreeze_english_word_dict
              if not key.startswith(_BUILT_AT_RUN_TIME) and key not in named]
    assert unused == []
