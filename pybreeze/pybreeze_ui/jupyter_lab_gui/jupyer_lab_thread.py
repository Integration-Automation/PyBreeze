import socket
import subprocess
import sys
from PySide6.QtCore import QThread, Signal
import time


def find_free_port():
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class JupyterServerThread(QThread):
    server_ready = Signal(str)

    def __init__(self):
        super().__init__()
        self.process = None

    def run(self):
        port = find_free_port()

        cmd = [
            sys.executable,
            "-m",
            "jupyterlab",
            "--no-browser",
            f"--ServerApp.port={port}",
            "--ServerApp.token=",
            "--ServerApp.password=",
            "--ServerApp.allow_origin=*",
            "--ServerApp.disable_check_xsrf=True",
        ]

        self.process = subprocess.Popen(cmd)

        # 輪詢 port，直到可連
        while True:
            try:
                s = socket.create_connection(("localhost", port), timeout=0.5)
                s.close()
                break
            except OSError:
                time.sleep(0.1)

        # Server ready，發射 signal
        self.server_ready.emit(f"http://localhost:{port}/lab")

    def stop(self):
        if self.process:
            self.process.terminate()