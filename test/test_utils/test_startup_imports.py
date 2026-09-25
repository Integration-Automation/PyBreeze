"""What starting the IDE leaves alone: the DPI awareness Qt sets, and packages nobody has used yet."""
from __future__ import annotations

import sys

import pytest

from test_utils.started_window import run_started_window

# Imported by the entries that use them: together they took about a fifth of
# the IDE's start (the Load Density GUI brings locust and gevent; SSH brings
# paramiko and cryptography)
_UNUSED_YET = ("je_auto_control", "je_load_density", "locust", "je_api_testka", "paramiko")

_WHAT_THE_START_LOADED = f"UNUSED_YET = {_UNUSED_YET!r}\n" + """
import ctypes
import os
from pybreeze.utils.subprocess_util import utf8_subprocess_env
awareness = None
if sys.platform == "win32":
    user32 = ctypes.windll.user32
    user32.GetThreadDpiAwarenessContext.restype = ctypes.c_void_p
    user32.GetAwarenessFromDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    awareness = user32.GetAwarenessFromDpiAwarenessContext(user32.GetThreadDpiAwarenessContext())
result = {
    "awareness": awareness,
    "loaded": sorted(name for name in UNUSED_YET if name in sys.modules),
    "locust_patching": {
        "ide": os.environ.get("LOCUST_SKIP_MONKEY_PATCH"),
        "child": utf8_subprocess_env().get("LOCUST_SKIP_MONKEY_PATCH"),
    },
}
"""


@pytest.fixture(scope="module")
def started(tmp_path_factory) -> dict:
    with pytest.MonkeyPatch.context() as patch:
        # As a user starts it: an earlier test here may have imported the IDE,
        # which sets this in this process
        patch.delenv("LOCUST_SKIP_MONKEY_PATCH", raising=False)
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


def test_the_automation_packages_and_ssh_are_loaded_when_used(started):
    assert started["loaded"] == []


def test_locust_leaves_the_ide_unpatched_and_the_processes_it_starts_patched(started):
    # locust patches a process with gevent as it imports unless this is set. The
    # IDE sets it for itself (the Load Density GUI imports locust there), and it
    # went on to every process the IDE started: a load test of HttpUser users
    # then ran them one at a time, and a 3 s test took over three minutes.
    assert started["locust_patching"]["ide"]
    assert started["locust_patching"]["child"] is None
