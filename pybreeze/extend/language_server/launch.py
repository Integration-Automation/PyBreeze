"""Have JEditor's editors start the action language server for JSON files.

JEditor's editor asks a language server about the file it holds, chosen by the
file's suffix from ``je_editor.utils.lsp.language_servers.DEFAULT_SERVERS``.
PyBreeze puts its own server there for ``.json``: the automation scripts are
JSON, and for any other JSON file the server says only whether it is JSON.
"""
from __future__ import annotations

import sys
from pathlib import Path

from je_editor.utils.lsp.language_servers import DEFAULT_SERVERS

# The files the server answers for
ACTION_SCRIPT_SUFFIX = ".json"
_ENTRY = Path(__file__).with_name("__main__.py")


def can_serve() -> bool:
    """Whether there is an interpreter to run the server with: not in a packaged build, where ``sys.executable`` is the app."""
    return not getattr(sys, "frozen", False)


def server_command(interpreter: str | None, language: str) -> list[str]:
    """The command that starts the server.

    The entry is named by its path rather than with ``-m``, which would put
    the folder the IDE is in first on the server's import path.

    :param interpreter: the Python that runs the scripts; the IDE's own when ``None``
    :param language: the IDE's language, by JEditor's name for it
    """
    command = [sys.executable, str(_ENTRY), "--language", language]
    if interpreter:
        command += ["--interpreter", interpreter]
    return command


def offer_to_jeditor(interpreter: str | None, language: str) -> None:
    """Make the action language server the one JEditor's editors start for a JSON file."""
    DEFAULT_SERVERS[ACTION_SCRIPT_SUFFIX] = server_command(interpreter, language)
