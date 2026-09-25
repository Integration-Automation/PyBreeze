"""What starting the IDE leaves alone: the DPI awareness Qt sets, and packages nobody has used yet."""
from __future__ import annotations

import sys

import pytest

from test_utils.started_window import run_started_window

_WHAT_THE_START_LOADED = """
import ctypes
awareness = None
if sys.platform == "win32":
    user32 = ctypes.windll.user32
    user32.GetThreadDpiAwarenessContext.restype = ctypes.c_void_p
    user32.GetAwarenessFromDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    awareness = user32.GetAwarenessFromDpiAwarenessContext(user32.GetThreadDpiAwarenessContext())
result = {
    "awareness": awareness,
    "loaded": sorted(name for name in ("je_auto_control",) if name in sys.modules),
}
"""


@pytest.fixture(scope="module")
def started(tmp_path_factory) -> dict:
    return run_started_window(tmp_path_factory.mktemp("started"), _WHAT_THE_START_LOADED)


@pytest.mark.skipif(sys.platform != "win32", reason="DPI awareness is a Windows process setting")
def test_the_dpi_awareness_is_left_to_qt(started):
    # je_auto_control makes the process system DPI aware as it imports. Imported
    # with the menus, before the application existed, it left Qt unable to set
    # per-monitor awareness ("SetProcessDpiAwarenessContext() failed" at every
    # start): Windows stretched the IDE as a bitmap on a screen scaled
    # differently from the main one. The offscreen platform sets none, so the
    # process is still unaware (0) here.
    assert started["awareness"] == 0


def test_the_autocontrol_package_is_loaded_when_used(started):
    assert started["loaded"] == []
