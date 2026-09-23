from __future__ import annotations

import multiprocessing

from pybreeze import start_editor

# Guarded: in the packaged executable the regex tester runs its worker as a
# spawned process, which re-runs the main script in the child, and an unguarded
# start_editor() there would open a second IDE; freeze_support() lets the child
# start as a worker. (From source, the worker is a plain script and needs neither.)
if __name__ == "__main__":
    multiprocessing.freeze_support()
    start_editor()
