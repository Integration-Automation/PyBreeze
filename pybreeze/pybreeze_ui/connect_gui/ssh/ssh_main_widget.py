import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSplitter, QApplication, QSizePolicy

from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_command_widget import SSHCommandWidget
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_file_viewer_widget import SSHFileTreeManager
from pybreeze.pybreeze_ui.connect_gui.ssh.ssh_login_widget import LoginWidget


class SSHMainWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # 已經實作好的元件
        self.login_widget = LoginWidget()
        self.login_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.file_tree = SSHFileTreeManager(external_login_widget=self.login_widget, add_login_widget=False)
        self.command_widget = SSHCommandWidget(external_login_widget=self.login_widget, add_login_widget=False)

        # 整體垂直布局
        main_layout = QVBoxLayout(self)

        # 上方放登入區
        main_layout.addWidget(self.login_widget)

        # Splitter 左右分割
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.file_tree)  # 左邊檔案瀏覽器
        splitter.addWidget(self.command_widget)  # 右邊命令區
        # 設定初始比例：左邊 30%，右邊 70%
        splitter.setSizes([300, 700])  # 數值會依視窗大小縮放
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        # 讓拖曳更平滑：加寬 handle 並避免完全收合
        splitter.setHandleWidth(8)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        main_layout.addWidget(splitter)
        self.setLayout(main_layout)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = SSHMainWidget()
    win.showMaximized()
    sys.exit(app.exec())
