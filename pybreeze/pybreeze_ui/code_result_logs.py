"""Only warnings and errors from loggers in the editor's Code Result panel.

JEditor shows log records in the panel, in red, through a handler it hooks onto
every logger that exists when its window is built. The automation packages set
the root logger to DEBUG as they are imported, so every library's debug records
went there: opening a file filled it with gitpython's ``Popen([...])`` lines,
and PyBreeze's own debug and info records went there too.
"""
from __future__ import annotations

import logging

from je_editor.utils.redirect_manager.redirect_manager_class import RedirectStdErr


def show_only_warnings_in_code_result() -> None:
    """Let JEditor's Code Result handler take only warnings and worse, on every logger it is on.

    Call it once the editor window is built: JEditor hooks the handler then. It
    changes the handler's level only; loggers keep theirs, so their files and
    other handlers still get every record.
    """
    loggers = [logging.root, *(
        logger for logger in list(logging.root.manager.loggerDict.values())
        if isinstance(logger, logging.Logger))]
    for logger in loggers:
        for handler in logger.handlers:
            if isinstance(handler, RedirectStdErr):
                handler.setLevel(logging.WARNING)
