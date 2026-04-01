import os
import socket
import subprocess
import sys
import time
import traceback

from PySide6.QtCore import QThread, Signal
from je_editor import language_wrapper

from pybreeze.utils.logging.logger import pybreeze_logger


def find_free_port():
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def get_venv_python():
    # 如果在 venv 中
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        return sys.executable

    # 嘗試從常見位置找 venv
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


def is_jupyter_installed(python_exe):
    result = subprocess.run(
        [python_exe, "-m", "pip", "show", "jupyterlab"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return result.returncode == 0


class JupyterLauncherThread(QThread):
    server_ready = Signal(str)
    status_update = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None

    def run(self):
        try:
            python_exe = get_venv_python()

            if not is_jupyter_installed(python_exe):
                self.status_update.emit(language_wrapper.language_word_dict.get("jupyterlab_downloading"))

                result = subprocess.run([
                    python_exe,
                    "-m",
                    "pip",
                    "install",
                    "jupyterlab",
                    "-U"
                ], capture_output=True, text=True)

                if result.returncode != 0:
                    raise RuntimeError(result.stderr)

            self.status_update.emit(language_wrapper.language_word_dict.get("jupyterlab_loading"))

            port = find_free_port()

            self.process = subprocess.Popen([
                python_exe,
                "-m",
                "jupyterlab",
                "--no-browser",
                f"--ServerApp.port={port}",
                "--ServerApp.token=",
                "--ServerApp.password=",
                "--ServerApp.allow_origin=*",
                "--ServerApp.disable_check_xsrf=True",
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            start_time = time.time()

            while True:
                if time.time() - start_time > 30:
                    raise TimeoutError("JupyterLab 啟動超時")

                try:
                    s = socket.create_connection(("localhost", port), timeout=0.5)
                    s.close()
                    break
                except OSError:
                    time.sleep(0.2)

            self.server_ready.emit(f"http://localhost:{port}/lab")

        except Exception:
            err = traceback.format_exc()
            print(err)
            self.error_occurred.emit(err)
            pybreeze_logger.info(err)

    def stop(self):
        if self.process is not None:
            try:
                self.process.terminate()
            except OSError:
                pass