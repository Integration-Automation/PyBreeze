"""Collect cyclic garbage on the main thread only, as the IDE does.

Left automatic, a collection started by a worker (a Diff comparison, a run's
output readers) freed Qt objects an earlier test had left, on that worker, and a
later ``processEvents`` crashed on their timers.
"""
from __future__ import annotations

import functools
import sys
import threading

import pytest
from PySide6.QtCore import QThread

from pybreeze.pybreeze_ui.gui_thread_gc import GuiThreadGarbageCollector


def _traced_run(run):
    """*run*, handing its thread the tracer ``threading`` gives the threads Python starts."""
    @functools.wraps(run)
    def traced(self, *args, **kwargs):
        tracer = threading.gettrace()
        if tracer is not None:
            sys.settrace(tracer)
        return run(self, *args, **kwargs)
    return traced


def _measure_qthreads(cls, **kwargs) -> None:
    """Let coverage see a ``QThread``'s ``run``: it traces the threads Python starts, not Qt's.

    Every QThread subclass defined after this (the package's are imported by the
    tests) gets a ``run`` that installs coverage's tracer on its own thread. It
    does nothing when coverage is not running: there is no tracer to install.
    """
    super(QThread, cls).__init_subclass__(**kwargs)
    if "run" in cls.__dict__:
        cls.run = _traced_run(cls.__dict__["run"])


QThread.__init_subclass__ = classmethod(_measure_qthreads)


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
