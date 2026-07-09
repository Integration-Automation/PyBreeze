from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import traceback

from PySide6.QtCore import QThread, Signal
from je_editor import language_wrapper

from pybreeze.utils.logging.logger import pybreeze_logger
from pybreeze.utils.subprocess_util import no_window_creationflags

JUPYTER_STARTUP_TIMEOUT = 60


def find_free_port() -> int:
    # Bind to loopback only: this socket exists purely to have the kernel pick an
    # unused port, which the JupyterLab server (also localhost-only) will reuse.
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get_venv_python() -> str:
    # If already in a venv
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        return sys.executable

    # Try common venv locations
    if sys.platform in ["win32", "cygwin", "msys"]:
        possible_paths = [
            os.path.join(os.getcwd(), "venv", "Scripts", "python.exe"),
            os.path.join(os.getcwd(), ".venv", "Scripts", "python.exe"),
        ]
    else:
        possible_paths = [
            os.path.join(os.getcwd(), "venv", "bin", "python"),
            os.path.join(os.getcwd(), ".venv", "bin", "python"),
        ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    raise RuntimeError("Cannot find venv python executable")


def is_jupyter_installed(python_exe: str) -> bool:
    # Query local venv for jupyterlab. python_exe is resolved via get_venv_python()
    # from a fixed allowlist of venv paths; shell=False. nosec B603.
    result = subprocess.run(  # nosec B603  # nosemgrep  # noqa: S603
        [python_exe, "-m", "pip", "show", "jupyterlab"],
        capture_output=True,
        timeout=30,
        creationflags=no_window_creationflags(),
    )
    return result.returncode == 0


class JupyterLauncherThread(QThread):
    server_ready = Signal(str)
    status_update = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, parent=None, startup_timeout: int = JUPYTER_STARTUP_TIMEOUT):
        super().__init__(parent)
        self.process = None
        self.startup_timeout = startup_timeout

    def run(self):
        try:
            python_exe = get_venv_python()

            if not is_jupyter_installed(python_exe):
                self.status_update.emit(language_wrapper.language_word_dict.get("jupyterlab_downloading"))

                # Install jupyterlab into the local venv. python_exe comes from
                # get_venv_python(); shell=False. nosec B603.
                result = subprocess.run([  # nosec B603  # nosemgrep  # noqa: S603
                    python_exe,
                    "-m",
                    "pip",
                    "install",
                    "jupyterlab",
                    "-U"
                ], capture_output=True, text=True, timeout=300,
                    creationflags=no_window_creationflags())

                if result.returncode != 0:
                    raise RuntimeError(result.stderr)

            self.status_update.emit(language_wrapper.language_word_dict.get("jupyterlab_loading"))

            port = find_free_port()

            # Launch embedded JupyterLab. Server binds to localhost only (see
            # CLAUDE.md JupyterLab integration notes); shell=False. nosec B603.
            # The bind address is pinned explicitly: with token/password empty,
            # XSRF disabled and a wildcard origin, the loopback-only binding is
            # the sole barrier, so we never rely on the jupyter default staying
            # localhost.
            self.process = subprocess.Popen([  # nosec B603  # nosemgrep  # noqa: S603
                python_exe,
                "-m",
                "jupyterlab",
                "--no-browser",
                "--ServerApp.ip=localhost",
                f"--ServerApp.port={port}",
                "--ServerApp.token=",
                "--ServerApp.password=",
                "--ServerApp.allow_origin=*",
                "--ServerApp.disable_check_xsrf=True",
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                creationflags=no_window_creationflags())

            self._wait_until_ready(port)
            self.server_ready.emit(f"http://localhost:{port}/lab")

        except Exception:
            err = traceback.format_exc()
            # Tear down a half-started server so a startup timeout doesn't leave an
            # orphaned JupyterLab process running and holding the port.
            self.stop()
            self.error_occurred.emit(err)
            pybreeze_logger.error(f"JupyterLab launch failed: {err}")

    @staticmethod
    def _port_open(port: int) -> bool:
        try:
            with socket.create_connection(("localhost", port), timeout=0.5):
                return True
        except OSError:
            return False

    def _wait_until_ready(self, port: int) -> None:
        """Block until the server accepts connections, or raise on failure."""
        process = self.process
        if process is None:
            raise RuntimeError("JupyterLab process was not started")
        start_time = time.time()
        while True:
            elapsed = time.time() - start_time
            if elapsed > self.startup_timeout:
                raise TimeoutError(
                    f"JupyterLab startup timeout ({self.startup_timeout}s)")

            # Fail fast if the server died (port conflict, bad install, ...)
            # instead of polling a dead port until the full timeout elapses.
            if process.poll() is not None:
                stderr_tail = ""
                if process.stderr is not None:
                    # Bounded read: the process has exited so the pipe holds at
                    # most its buffer; cap explicitly and keep the tail message.
                    stderr_tail = process.stderr.read(65536)[-500:]
                raise RuntimeError(
                    f"JupyterLab exited early (code {process.returncode}): {stderr_tail}")

            self.status_update.emit(
                f"{language_wrapper.language_word_dict.get('jupyterlab_loading')} "
                f"({int(elapsed)}s / {self.startup_timeout}s)")

            if self._port_open(port):
                return
            time.sleep(0.2)

    def stop(self):
        if self.process is not None:
            try:
                self.process.terminate()
            except OSError as error:
                pybreeze_logger.debug("JupyterLab terminate failed: %r", error)
