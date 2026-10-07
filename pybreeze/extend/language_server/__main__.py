"""Start the action language server on this process's standard input and output."""
from __future__ import annotations

import sys
from pathlib import Path

# The editor starts this file by its path, not with -m: the folder the IDE is
# in (a project someone opened) is then not on the import path, and a package
# there called pybreeze is not what gets imported. Started that way the path
# begins with this folder, and the folder PyBreeze is in takes its place.
if not __package__:
    sys.path[0] = str(Path(__file__).resolve().parents[3])

from pybreeze.extend.language_server.server_main import main  # noqa: E402 — the import path is set first

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
