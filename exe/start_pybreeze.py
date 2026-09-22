from __future__ import annotations

import multiprocessing

from pybreeze import start_editor

# Guarded: a tool that runs work in a spawned process (the regex tester) re-runs
# the main script in the child, and an unguarded start_editor() there would open
# a second IDE. freeze_support() does the same job for the packaged executable.
if __name__ == "__main__":
    multiprocessing.freeze_support()
    start_editor()
