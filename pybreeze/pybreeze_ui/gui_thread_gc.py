"""Run Python's cyclic garbage collection on the GUI thread only.

CPython collects in whichever thread happens to allocate past the threshold,
and a worker allocates plenty (the Diff tab matching lines, a run's output
readers, an AI request). When that collection frees a Qt object the GUI thread
made, its destructor runs on the worker: its timers cannot be stopped from
there ("QBasicTimer::stop: Failed"), and the GUI thread later delivers a timer
event to the freed object and the IDE dies with an access violation.

Automatic collection is switched off and a timer on the GUI thread collects
instead, by the same thresholds the interpreter would use.
"""
from __future__ import annotations

import gc

from PySide6.QtCore import QObject, QTimer

#: How often the GUI thread looks at the allocation counts.
COLLECT_INTERVAL_MS = 1000


class GuiThreadGarbageCollector(QObject):
    """Collect on a timer of the thread that makes it, with automatic collection off.

    Constructing it calls ``gc.disable()`` for the whole process; :meth:`stop`
    turns automatic collection back on.
    """

    def __init__(self, parent: QObject | None = None, interval_ms: int = COLLECT_INTERVAL_MS) -> None:
        super().__init__(parent)
        self._thresholds = gc.get_threshold()
        gc.disable()
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.check)
        self._timer.start()

    def check(self) -> None:
        """Collect each generation whose count is past the interpreter's threshold.

        A threshold of 0 means the interpreter never collects that generation
        on its own (Python 3.14 leaves the third at 0), so neither does this.
        """
        for count, threshold, generation in zip(gc.get_count(), self._thresholds, range(3)):
            if threshold == 0 or count <= threshold:
                return
            gc.collect(generation)

    def stop(self) -> None:
        """Stop the timer and give collection back to the interpreter."""
        self._timer.stop()
        gc.enable()


def collect_garbage_on_gui_thread(app: QObject) -> GuiThreadGarbageCollector:
    """Switch collection to *app*'s thread; the collector lives as long as *app*."""
    return GuiThreadGarbageCollector(app)
