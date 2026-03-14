import logging
from logging.handlers import RotatingFileHandler

# 設定 root logger 等級 Set root logger level
logging.root.setLevel(logging.DEBUG)

# 建立 AutoControlGUI 專用 logger Create dedicated logger
automation_ide_logger = logging.getLogger("AutomationIDE")

# 日誌格式 Formatter
formatter = logging.Formatter(
    "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)


class AutomationIDELogger(RotatingFileHandler):
    """
    AutoControlGUILoggingHandler
    自訂日誌處理器，繼承 RotatingFileHandler
    - 支援檔案大小輪替
    - 預設輸出到 AutoControlGUI.log
    """

    def __init__(
        self,
        filename: str = "AutomationIDE.log",
        mode: str = "w",
        max_bytes: int = 1073741824,  # 1GB
        backup_count: int = 0,
    ):
        super().__init__(
            filename=filename,
            mode=mode,
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        self.setFormatter(formatter)  # 設定格式器
        self.setLevel(logging.DEBUG)  # 設定等級

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit log record.
        輸出日誌紀錄
        """
        super().emit(record)


# 建立並加入檔案處理器 Add file handler to logger
file_handler = AutomationIDELogger()
automation_ide_logger.addHandler(file_handler)
