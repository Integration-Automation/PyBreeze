from __future__ import annotations

import socket
import subprocess
import tempfile
import threading
import time
import traceback

from PySide6.QtCore import QThread, Signal
from je_editor import JEditorExecException, language_wrapper

from pybreeze.extend.process_executor.python_task_process_manager import default_interpreter
from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.subprocess_util import child_environment, no_window_creationflags, utf8_subprocess_env

JUPYTER_STARTUP_TIMEOUT = 60
# How much of a failure's reason the tab shows: pip's stderr can run long
_SHOWN_REASON_CHARACTERS = 2000
# Run by the chosen interpreter: exits 0 when it can import jupyterlab
_HAS_JUPYTERLAB = "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('jupyterlab') else 1)"
# The server listens on localhost; the port is checked, and polled, on IPv4 loopback
_LOOPBACK = "127.0.0.1"


def find_free_port() -> int:
    # Bind to loopback only: this socket exists purely to have the kernel pick an
    # unused port, which the JupyterLab server (also localhost-only) will reuse.
    with socket.socket() as s:
        s.bind((_LOOPBACK, 0))
        return s.getsockname()[1]


def choose_python(chosen: str | None) -> str:
    """The interpreter the lab runs in: the one chosen in the IDE, else the one a run uses.

    It took the IDE's own or a ``venv``/``.venv`` in the working directory and
    never the one chosen in the IDE, so kernels ran in the wrong environment,
    and an IDE installed outside a venv could not start the lab at all. Then an
    IDE started from a venv of its own ran the lab there, while a run of the
    project used the project's ``.venv``: now both go through
    ``default_interpreter`` (a ``venv``/``.venv`` in the working directory,
    else the IDE's own; a packaged build looks on ``PATH``).

    :raises JEditorExecException: when a packaged build finds no Python
    """
    return chosen or default_interpreter()


def is_jupyter_installed(python_exe: str) -> bool:
    """Whether *python_exe* can import jupyterlab.

    Asked of the interpreter, not of pip: a venv made without pip (``uv venv``)
    failed ``pip show`` with jupyterlab installed, and the install that
    followed failed with "No module named pip". shell=False. nosec B603.
    """
    result = subprocess.run(  # nosec B603  # nosemgrep  # noqa: S603
        [python_exe, "-c", _HAS_JUPYTERLAB],
        capture_output=True,
        timeout=30,
        check=False,
        env=child_environment(),
        creationflags=no_window_creationflags(),
    )
    return result.returncode == 0


class JupyterLauncherThread(QThread):
    server_ready = Signal(str)
    status_update = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, parent=None, startup_timeout: int = JUPYTER_STARTUP_TIMEOUT,
                 python_exe: str | None = None):
        super().__init__(parent)
        # The interpreter chosen in the IDE, if any (choose_python)
        self._chosen_python = python_exe
        self.process = None
        # Set by stop(). Checked, under the lock, before the server is started:
        # a tab closed during the install would otherwise get a server started
        # after it had gone, with nothing left to stop it.
        self._stopped = threading.Event()
        self._process_lock = threading.Lock()
        # The server's output, kept in a file rather than a pipe
        self._output = None
        self.startup_timeout = startup_timeout

    def run(self):
        try:
            python_exe = choose_python(self._chosen_python)

            if not is_jupyter_installed(python_exe):
                self.status_update.emit(language_wrapper.language_word_dict.get("jupyterlab_downloading"))

                # Install jupyterlab into the interpreter the lab runs in
                # (choose_python); shell=False. nosec B603.
                result = subprocess.run([  # nosec B603  # nosemgrep  # noqa: S603
                    python_exe,
                    "-m",
                    "pip",
                    "install",
                    "jupyterlab",
                    "-U"
                ], capture_output=True, timeout=300, check=False,
                    # pip told to write UTF-8 and read as such: an interpreter in UTF-8
                    # mode (the default from Python 3.15) writes it whatever the code
                    # page, and read in the code page its reason was lost
                    env=utf8_subprocess_env(), encoding="utf-8", errors="replace",
                    creationflags=no_window_creationflags())

                if result.returncode != 0:
                    raise RuntimeError(result.stderr)

            self.status_update.emit(language_wrapper.language_word_dict.get("jupyterlab_loading"))

            port = find_free_port()

            with self._process_lock:
                if self._stopped.is_set():
                    return
                self._output = tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace")
                self.process = self._start_server(python_exe, port)

            self._wait_until_ready(port)
            self.server_ready.emit(f"http://localhost:{port}/lab")

        # OSError includes the TimeoutError of a server that never came up;
        # JEditorExecException, a packaged build that found no Python
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, JEditorExecException) as error:
            if self._stopped.is_set():
                # The tab closed: stop() ended the server, and the wait saw it
                # exit. Not a failure, and it used to be logged as one.
                pybreeze_logger.debug("JupyterLab launch stopped with its tab: %r", error)
                return
            # Tear down a half-started server so a startup timeout doesn't leave an
            # orphaned JupyterLab process running and holding the port.
            self.stop()
            pybreeze_logger.error("JupyterLab launch failed: %s", traceback.format_exc())
            # The reason, not the traceback: the tab shows it.
            self.error_occurred.emit(str(error)[-_SHOWN_REASON_CHARACTERS:])

    def _start_server(self, python_exe: str, port: int) -> subprocess.Popen:
        """Start the server on *port*, its output going to ``self._output``.

        It binds to localhost only (CLAUDE.md, Security > JupyterLab); shell=False.
        The bind address is pinned explicitly: with token and password empty,
        the loopback-only binding is the sole barrier, so this never relies on
        jupyter's default staying localhost. No wildcard origin: a loopback bind
        does not stop a browser, and with the origin open any page the user
        visits could drive this server's API and kernel sockets. The view this
        serves loads from the same origin, so it needs nothing relaxed.
        """
        return subprocess.Popen([  # nosec B603  # nosemgrep  # noqa: S603
            python_exe,
            "-m",
            "jupyterlab",
            "--no-browser",
            "--ServerApp.ip=localhost",
            f"--ServerApp.port={port}",
            # A port taken since it was found fails at once: the server moved
            # to the next free one, and the tab waited on (or loaded) this one
            "--ServerApp.port_retries=0",
            # No token and no password: jupyter_server 2's names, and 1.x's,
            # which 2 still reads with a deprecation warning. Only the old ones
            # left a server that drops them making a token of its own.
            "--IdentityProvider.token=",
            "--PasswordIdentityProvider.hashed_password=",
            "--ServerApp.token=",
            "--ServerApp.password=",
            "--ServerApp.disable_check_xsrf=True",
        ], stdout=self._output, stderr=subprocess.STDOUT, text=True,
            env=child_environment(), creationflags=no_window_creationflags())

    @staticmethod
    def _port_open(port: int) -> bool:
        try:
            with socket.create_connection((_LOOPBACK, port), timeout=0.5):
                return True
        except OSError:
            return False

    def _wait_until_ready(self, port: int) -> None:
        """Block until the server accepts connections, or raise on failure."""
        process = self.process
        if process is None:
            raise RuntimeError("JupyterLab process was not started")
        word = language_wrapper.language_word_dict
        start_time = time.time()
        while True:
            elapsed = time.time() - start_time
            if elapsed > self.startup_timeout:
                raise TimeoutError(f"{word.get('jupyterlab_timeout')} ({self.startup_timeout}s)")

            # Fail fast if the server died (port conflict, bad install, ...)
            # instead of polling a dead port until the full timeout elapses.
            if process.poll() is not None:
                raise RuntimeError(word.get("jupyterlab_exited_early").format(
                    code=process.returncode, output=self._output_tail()))

            self.status_update.emit(
                f"{language_wrapper.language_word_dict.get('jupyterlab_loading')} "
                f"({int(elapsed)}s / {self.startup_timeout}s)")

            if self._port_open(port):
                return
            time.sleep(0.2)

    def _output_tail(self, characters: int = 500) -> str:
        """The end of what the server wrote, for an error message.

        Its output goes to a temporary file rather than a pipe: nothing reads a
        pipe once the server is up, and a server that keeps logging would block
        in ``write()`` when the pipe buffer filled, freezing the lab with
        nothing to show for it.
        """
        if self._output is None:
            return ""
        try:
            self._output.seek(0)
            return self._output.read()[-characters:]
        except (OSError, ValueError) as error:
            pybreeze_logger.debug("JupyterLab output could not be read: %r", error)
            return ""

    def stop(self):
        """Stop the server, and any server not started yet, and let go of its output.

        Safe to call twice, and from any thread. Once it has been called the
        launcher starts no server, even one it is still installing.
        """
        with self._process_lock:
            self._stopped.set()
            process, self.process = self.process, None
            output, self._output = self._output, None
        if process is not None:
            try:
                process.terminate()
            except OSError as error:
                pybreeze_logger.debug("JupyterLab terminate failed: %r", error)
        if output is not None:
            output.close()
