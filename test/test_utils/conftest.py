"""Collect cyclic garbage on the main thread only, as the IDE does.

Left automatic, a collection started by a worker (a Diff comparison, a run's
output readers) freed Qt objects an earlier test had left, on that worker, and a
later ``processEvents`` crashed on their timers.
"""
from __future__ import annotations

import pytest

from pybreeze.pybreeze_ui.gui_thread_gc import GuiThreadGarbageCollector


@pytest.fixture(scope="session", autouse=True)
def _gui_thread_collector():
    collector = GuiThreadGarbageCollector()
    yield collector
    collector.stop()


@pytest.fixture(autouse=True)
def _collect_after_each_test(_gui_thread_collector):
    yield
    # The timer only fires while a test processes events
    _gui_thread_collector.check()
