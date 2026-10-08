"""The action language server's process: its arguments, the frameworks it asks, the language it answers in."""
from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from functools import partial
from importlib import metadata as installed

from pybreeze.extend_multi_language.supported_languages import MAINTAINED
from pybreeze.utils.exception.exceptions import LanguageServiceException
from pybreeze.utils.language_service.framework_profiles import PROFILES, FrameworkProfile
from pybreeze.utils.language_service.lsp_server import ActionLanguageServer, serve
from pybreeze.utils.language_service.metadata_probe import read_metadata


def words_of(language: str) -> dict[str, str]:
    """PyBreeze's strings in *language*; in English for a language PyBreeze does not maintain."""
    return next((each.words for each in MAINTAINED if each.key == language), MAINTAINED[0].words)


def server_version() -> str:
    """The installed PyBreeze's version; empty when it runs from a source tree."""
    try:
        return installed.version("pybreeze")
    except installed.PackageNotFoundError:
        return ""


def ask_framework(
        server: ActionLanguageServer, profile: FrameworkProfile, interpreter: str | None) -> Callable[[], list[dict]]:
    """Ask *profile*'s framework for its keywords, and return what gives *server* the answer.

    The asking imports the framework in a process of its own and takes
    seconds: the server runs this on a thread and goes on answering.
    """
    try:
        metadata = read_metadata(profile, interpreter)
    except LanguageServiceException as error:
        return partial(server.decline, profile.framework, str(error))
    return partial(server.offer, metadata)


def main(arguments: list[str]) -> int:
    """Serve the protocol on standard input and output until the editor says ``exit`` or goes away."""
    parser = argparse.ArgumentParser(
        prog="python -m pybreeze.extend.language_server",
        description="Language server for WebRunner, AutoControl and LoadDensity action scripts (JSON), "
                    "speaking the Language Server Protocol on standard input and output.")
    parser.add_argument("--interpreter", default=None,
                        help="the Python that runs the scripts, whose installed frameworks are asked for their "
                             "keywords (default: the one running this server)")
    parser.add_argument("--language", default=MAINTAINED[0].key,
                        help="the language of the diagnostics, as the IDE names it (default: %(default)s)")
    options = parser.parse_args(arguments)
    server = ActionLanguageServer(words_of(options.language), server_version())
    serve(server, sys.stdin.buffer, sys.stdout.buffer,
          [partial(ask_framework, server, profile, options.interpreter) for profile in PROFILES])
    return 0
