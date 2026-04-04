import logging
import os
from logging.handlers import RotatingFileHandler

# 設定 root logger 等級 Set root logger level
logging.root.setLevel(logging.DEBUG)

# 建立 AutoControlGUI 專用 logger Create dedicated logger
pybreeze_logger = logging.getLogger("Pybreeze")

# 日誌格式 Formatter
formatter = logging.Formatter(
    "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)

# Configurable max log size via environment variable (default: 100MB)
DEFAULT_MAX_LOG_BYTES = 100 * 1024 * 1024  # 100MB


class PyBreezeLogger(RotatingFileHandler):
    """
    PyBreezeLoggingHandler
    Custom log handler extending RotatingFileHandler
    - Supports file size rotation
    - Default output to PyBreeze.log
    - Max size configurable via PYBREEZE_LOG_MAX_BYTES env var
    """

    def __init__(
        self,
        filename: str = "PyBreeze.log",
        mode: str = "w",
        max_bytes: int | None = None,
        backup_count: int = 1,
    ):
        if max_bytes is None:
            max_bytes = int(os.environ.get("PYBREEZE_LOG_MAX_BYTES", DEFAULT_MAX_LOG_BYTES))
        super().__init__(
            filename=filename,
            mode=mode,
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        self.setFormatter(formatter)
        self.setLevel(logging.DEBUG)

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)


# 建立並加入檔案處理器 Add file handler to logger
file_handler = PyBreezeLogger()
pybreeze_logger.addHandler(file_handler)
