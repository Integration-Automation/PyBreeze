from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMessageBox

from je_editor import language_wrapper
from je_editor.plugins import get_all_plugin_metadata

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow


def set_plugin_menu(ui_we_want_to_set: PyBreezeMainWindow) -> None:
    """
    建立插件選單，顯示所有已載入插件的名稱、版本、作者。
    Build Plugin menu showing all loaded plugins with name, version, author.
    同一語言若支援多種副檔名，以子選單呈現。
    If a language plugin supports multiple suffixes, show them in a submenu.
    """
    metadata_list = get_all_plugin_metadata()
    if not metadata_list:
        return

    ui_we_want_to_set.plugin_menu = ui_we_want_to_set.menu.addMenu(
        language_wrapper.language_word_dict.get("plugin_menu_label", "Plugins")
    )

    # 插件瀏覽器入口 / Plugin browser entry
    browse_action = QAction(
        language_wrapper.language_word_dict.get("plugin_browser_tab_name", "Plugin Browser"),
        ui_we_want_to_set.plugin_menu,
    )
    browse_action.triggered.connect(lambda: _open_plugin_browser(ui_we_want_to_set))
    ui_we_want_to_set.plugin_menu.addAction(browse_action)
    ui_we_want_to_set.plugin_menu.addSeparator()

    for meta in metadata_list:
        plugin_name = meta.get("name", "Unknown")
        plugin_author = meta.get("author", "")
        plugin_version = meta.get("version", "")
        run_config = meta.get("run_config")

        if run_config is not None:
            suffixes = run_config.get("suffixes", ())
            config_name = run_config.get("name", plugin_name)

            if len(suffixes) > 1:
                # 多種副檔名：建立子選單
                # Multiple suffixes: create a submenu
                sub_menu = ui_we_want_to_set.plugin_menu.addMenu(config_name)

                # 「關於」動作
                # "About" action
                about_action = QAction(
                    language_wrapper.language_word_dict.get("plugin_menu_about", "About"),
                    sub_menu,
                )
                about_action.triggered.connect(
                    _make_about_callback(plugin_name, plugin_version, plugin_author)
                )
                sub_menu.addAction(about_action)
                sub_menu.addSeparator()

                # 每個副檔名一個執行動作
                # One run action per suffix
                for suffix in suffixes:
                    run_action = QAction(
                        language_wrapper.language_word_dict.get(
                            "plugin_menu_run_with", "Run with {name}"
                        ).format(name=f"{config_name} ({suffix})"),
                        sub_menu,
                    )
                    run_action.triggered.connect(
                        _make_run_callback(ui_we_want_to_set, run_config, suffix)
                    )
                    sub_menu.addAction(run_action)
            else:
                # 單一副檔名：建立子選單含關於與執行
                # Single suffix: submenu with about and run
                sub_menu = ui_we_want_to_set.plugin_menu.addMenu(config_name)

                about_action = QAction(
                    language_wrapper.language_word_dict.get("plugin_menu_about", "About"),
                    sub_menu,
                )
                about_action.triggered.connect(
                    _make_about_callback(plugin_name, plugin_version, plugin_author)
                )
                sub_menu.addAction(about_action)
                sub_menu.addSeparator()

                suffix = suffixes[0] if suffixes else ""
                run_action = QAction(
                    language_wrapper.language_word_dict.get(
                        "plugin_menu_run_with", "Run with {name}"
                    ).format(name=config_name),
                    sub_menu,
                )
                run_action.triggered.connect(
                    _make_run_callback(ui_we_want_to_set, run_config, suffix)
                )
                sub_menu.addAction(run_action)
        else:
            # 沒有執行設定的插件（如翻譯插件），只顯示關於
            # Plugins without run config (e.g. translation), show about only
            about_action = QAction(plugin_name, ui_we_want_to_set.plugin_menu)
            about_action.triggered.connect(
                _make_about_callback(plugin_name, plugin_version, plugin_author)
            )
            ui_we_want_to_set.plugin_menu.addAction(about_action)


def _open_plugin_browser(ui_we_want_to_set: PyBreezeMainWindow) -> None:
    """
    開啟插件瀏覽器分頁。
    Open plugin browser tab.
    """
    from je_editor.pyside_ui.main_ui.plugin_browser.plugin_browser_widget import PluginBrowserWidget

    tab_name = language_wrapper.language_word_dict.get("plugin_browser_tab_name", "Plugin Browser")
    ui_we_want_to_set.tab_widget.addTab(
        PluginBrowserWidget(),
        f"{tab_name} {ui_we_want_to_set.tab_widget.count()}"
    )


def _make_about_callback(name: str, version: str, author: str):
    """
    建立顯示插件資訊的回呼函式。
    Create a callback to show plugin info dialog.
    """
    def callback():
        message_box = QMessageBox()
        message_box.setWindowTitle(name)
        message_box.setText(
            f"{name}\n"
            f"Version: {version}\n"
            f"Author: {author}"
        )
        message_box.exec()
    return callback


def _make_run_callback(ui_we_want_to_set: PyBreezeMainWindow, run_config: dict, suffix: str):
    """
    建立使用插件執行設定來執行程式的回呼函式。
    Create a callback to run a program using plugin run config.
    使用 PyBreeze 的 FileRunnerProcess 與 CodeWindow。
    Uses PyBreeze's FileRunnerProcess and CodeWindow.
    """
    def callback():
        from pathlib import Path
        from PySide6.QtWidgets import QMessageBox

        from je_editor.pyside_ui.main_ui.editor.editor_widget import EditorWidget
        from je_editor.utils.file.save.save_file import write_file

        from pybreeze.extend.process_executor.file_runner_process import FileRunnerProcess
        from pybreeze.pybreeze_ui.show_code_window.code_window import CodeWindow

        widget = ui_we_want_to_set.tab_widget.currentWidget()
        if not isinstance(widget, EditorWidget):
            return

        # 取得並儲存檔案 / Get and save file
        if widget.current_file:
            write_file(widget.current_file, widget.code_edit.toPlainText())
            file_path = widget.current_file
        else:
            from je_editor.pyside_ui.dialog.file_dialog.save_file_dialog import choose_file_get_save_file_path
            if not choose_file_get_save_file_path(ui_we_want_to_set):
                return
            file_path = widget.current_file

        # 檢查副檔名是否匹配 / Check suffix match
        file_suffix = Path(file_path).suffix.lower()
        supported = run_config.get("suffixes", ())
        if supported and file_suffix not in supported:
            msg = QMessageBox(ui_we_want_to_set)
            msg.setWindowTitle(language_wrapper.language_word_dict.get("run_with_menu_label", "Run with..."))
            msg.setText(
                language_wrapper.language_word_dict.get(
                    "run_with_suffix_mismatch",
                    "Current file ({suffix}) does not match expected suffixes: {expected}",
                ).format(suffix=file_suffix, expected=", ".join(supported))
            )
            msg.exec()
            return

        # 建立 CodeWindow 並執行 / Create CodeWindow and run
        code_window = CodeWindow()
        code_window.setWindowTitle(f"{run_config['name']} - {Path(file_path).name}")
        ui_we_want_to_set.current_run_code_window.append(code_window)

        runner = FileRunnerProcess(
            main_window=code_window,
            program_encoding=ui_we_want_to_set.encoding,
        )
        runner.run_file(run_config, file_path)

    return callback
