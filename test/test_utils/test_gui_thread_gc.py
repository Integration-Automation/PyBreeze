"""Cyclic garbage is collected on the GUI thread, never on a worker."""
from __future__ import annotations

import gc
import os
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QObject

from pybreeze.pybreeze_ui import gui_thread_gc
from pybreeze.pybreeze_ui.gui_thread_gc import GuiThreadGarbageCollector


@pytest.fixture()
def collector():
    was_enabled = gc.isenabled()
    made = GuiThreadGarbageCollector()
    yield made
    made.stop()
    if not was_enabled:
        gc.disable()


class _Cyclic(QObject):
    """A Python-owned QObject that only the cycle collector can free."""

    def __init__(self) -> None:
        super().__init__()
        self.me = self


def test_automatic_collection_is_off_until_stopped(collector):
    assert gc.isenabled() is False

    collector.stop()

    assert gc.isenabled() is True


def test_a_worker_that_allocates_frees_no_qt_object(collector):
    # A worker allocating past the threshold used to collect a Qt object made
    # on the GUI thread, and run its destructor there
    import weakref

    freed_in: list = []
    cyclic = _Cyclic()
    # A connection to its destroyed signal would keep it alive; a weak
    # reference's callback runs in whichever thread frees it
    watch = weakref.ref(cyclic, lambda _ref: freed_in.append(threading.current_thread().name))
    del cyclic

    worker = threading.Thread(target=lambda: [{} for _ in range(200_000)], name="worker")
    worker.start()
    worker.join()
    assert freed_in == []

    gc.collect()
    assert freed_in == [threading.main_thread().name]
    assert watch() is None


@pytest.mark.parametrize(("counts", "collected"), [
    ((700, 0, 0), []),
    ((701, 0, 0), [0]),
    ((701, 11, 3), [0, 1]),
    ((701, 11, 11), [0, 1, 2]),
])
def test_a_generation_is_collected_past_the_interpreters_threshold(collector, monkeypatch, counts, collected):
    done: list = []
    monkeypatch.setattr(collector, "_thresholds", (700, 10, 10))
    monkeypatch.setattr(gui_thread_gc.gc, "get_count", lambda: counts)
    monkeypatch.setattr(gui_thread_gc.gc, "collect", done.append)

    collector.check()

    assert done == collected


def test_a_threshold_of_zero_is_never_reached(collector, monkeypatch):
    # Python 3.14 leaves the third threshold at 0
    done: list = []
    monkeypatch.setattr(collector, "_thresholds", (2000, 10, 0))
    monkeypatch.setattr(gui_thread_gc.gc, "get_count", lambda: (2001, 11, 5))
    monkeypatch.setattr(gui_thread_gc.gc, "collect", done.append)

    collector.check()

    assert done == [0, 1]


def test_the_ide_switches_collection_to_its_gui_thread():
    import inspect

    from pybreeze.pybreeze_ui.editor_main import main_ui

    assert "collect_garbage_on_gui_thread(new_ide)" in inspect.getsource(main_ui.start_editor)
