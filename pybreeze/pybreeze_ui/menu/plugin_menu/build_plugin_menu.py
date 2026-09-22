from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMessageBox

from je_editor import get_all_plugin_metadata, language_wrapper
from je_editor.pyside_ui.main_ui.plugin_browser.plugin_browser_widget import PluginBrowserWidget

from pybreeze.pybreeze_ui.menu.plugin_menu.build_run_with_menu import run_current_file_with

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
        _add_plugin_entry(ui_we_want_to_set, meta)


def _add_plugin_entry(ui_we_want_to_set: PyBreezeMainWindow, meta: dict) -> None:
    """Add one plugin's menu entries (submenu with run actions, or a bare About action)."""
    plugin_name = meta.get("name", "Unknown")
    plugin_author = meta.get("author", "")
    plugin_version = meta.get("version", "")
    run_config = meta.get("run_config")

    if run_config is None:
        # 沒有執行設定的插件（如翻譯插件），只顯示關於
        # Plugins without run config (e.g. translation), show about only
        about_action = QAction(plugin_name, ui_we_want_to_set.plugin_menu)
        about_action.triggered.connect(
            _make_about_callback(plugin_name, plugin_version, plugin_author)
        )
        ui_we_want_to_set.plugin_menu.addAction(about_action)
        return

    suffixes = run_config.get("suffixes", ())
    config_name = run_config.get("name", plugin_name)
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

    if len(suffixes) > 1:
        # 多種副檔名：每個副檔名一個執行動作
        # Multiple suffixes: one run action per suffix
        for suffix in suffixes:
            _add_run_action(ui_we_want_to_set, sub_menu, run_config,
                            label_name=f"{config_name} ({suffix})")
    else:
        # 單一副檔名：一個執行動作
        # Single suffix: one run action
        _add_run_action(ui_we_want_to_set, sub_menu, run_config, label_name=config_name)


def _add_run_action(ui_we_want_to_set: PyBreezeMainWindow, parent_menu,
                    run_config: dict, label_name: str) -> None:
    run_action = QAction(
        language_wrapper.language_word_dict.get(
            "plugin_menu_run_with", "Run with {name}"
        ).format(name=label_name),
        parent_menu,
    )
    run_action.triggered.connect(
        _make_run_callback(ui_we_want_to_set, run_config)
    )
    parent_menu.addAction(run_action)


def _open_plugin_browser(ui_we_want_to_set: PyBreezeMainWindow) -> None:
    """
    開啟插件瀏覽器分頁。
    Open plugin browser tab.
    """
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


def _make_run_callback(ui_we_want_to_set: PyBreezeMainWindow, run_config: dict):
    """
    建立使用插件執行設定來執行程式的回呼函式，與「Run with...」選單同一套流程。
    Create a callback that runs the current file with a plugin run config, the
    same way the "Run with..." menu does.
    """
    def callback():
        run_current_file_with(ui_we_want_to_set, run_config)
    return callback
