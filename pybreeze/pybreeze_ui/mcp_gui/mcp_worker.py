"""One blocking call to an MCP server, made off the UI thread."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Signal

from pybreeze.pybreeze_ui.thread_keeper import KeptThread
from pybreeze.utils.exception.exception_tags import mcp_start_error
from pybreeze.utils.exception.exceptions import McpException
from pybreeze.utils.logging.logger import pybreeze_logger


class McpWorker(KeptThread):
    """Runs *work* on a thread of its own and says how it ended: ``done(result)`` or ``failed(error)``, never both.

    The client's calls block until the server answers, for as long as the
    profile's time limit. The panel that asked hears the end of every call:
    one that ended without a word would leave it waiting for good.

    :param work: the call to make; what it returns is the result
    """

    done = Signal(object)
    failed = Signal(object)  # the McpException

    def __init__(self, work: Callable[[], object]) -> None:
        super().__init__()
        self._work = work

    def run(self) -> None:
        try:
            result = self._work()
        except McpException as error:
            self.failed.emit(error)
            return
        except Exception as error:  # noqa: BLE001 — the panel must hear the end of every call
            pybreeze_logger.error("mcp_worker.py call failed unexpectedly: %r", error)
            self.failed.emit(McpException(mcp_start_error.format(reason=type(error).__name__)))
            return
        self.done.emit(result)
