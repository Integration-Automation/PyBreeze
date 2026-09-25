from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMessageBox

from je_editor import get_all_plugin_metadata, language_wrapper
from je_editor.pyside_ui.main_ui.plugin_browser.plugin_browser_widget import PluginBrowserWidget

from pybreeze.pybreeze_ui.menu.plugin_menu.build_run_with_menu import (
    plugin_text, run_config_suffixes, run_current_file_with,
)
from pybreeze.pybreeze_ui.plain_text import as_text
from pybreeze.utils.logging.logger import pybreeze_logger

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow


def set_plugin_menu(ui_we_want_to_set: PyBreezeMainWindow) -> None:
    """
    建立插件選單，顯示所有已載入插件的名稱、版本、作者。
    Build Plugin menu showing all loaded plugins with name, version, author.
    有執行設定的插件是一個子選單：About 和一個「Run with」項目，支援多種副檔名時一併列出。
    A plugin with a run config gets a submenu: About, and one Run with entry
    that lists the suffixes when there are several.
    外掛瀏覽器一定在：沒有任何外掛時，第一個外掛就是從它安裝的。
    The Plugin Browser is always there, with no plugin loaded too: it is how
    the first one gets installed.
    """
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

    metadata_list = get_all_plugin_metadata()
    if metadata_list:
        ui_we_want_to_set.plugin_menu.addSeparator()
    for meta in metadata_list:
        # One plugin with bad metadata costs its own entry, not the IDE's start
        if not isinstance(meta, dict):
            pybreeze_logger.error("Plugin metadata ignored: not a dict (%s)", type(meta).__name__)
            continue
        try:
            _add_plugin_entry(ui_we_want_to_set, meta)
        except Exception as error:  # noqa: BLE001 — a plugin is third-party code; the menu must still build
            pybreeze_logger.error("Plugin %r left out of the menu: %r", meta.get("name"), error)


def _add_plugin_entry(ui_we_want_to_set: PyBreezeMainWindow, meta: dict) -> None:
    """Add one plugin's menu entries (submenu with run actions, or a bare About action)."""
    plugin_name = plugin_text(meta.get("name"), "Unknown")
    plugin_author = plugin_text(meta.get("author"), "")
    plugin_version = plugin_text(meta.get("version"), "")
    run_config = meta.get("run_config")
    if run_config is not None and not isinstance(run_config, dict):
        pybreeze_logger.error("Plugin %s run config ignored: not a dict", plugin_name)
        run_config = None

    if run_config is None:
        # 沒有執行設定的插件（如翻譯插件），只顯示關於
        # Plugins without run config (e.g. translation), show about only
        about_action = QAction(plugin_name, ui_we_want_to_set.plugin_menu)
        about_action.triggered.connect(
            _make_about_callback(ui_we_want_to_set, plugin_name, plugin_version, plugin_author)
        )
        ui_we_want_to_set.plugin_menu.addAction(about_action)
        return

    suffixes = run_config_suffixes(run_config)
    config_name = plugin_text(run_config.get("name"), plugin_name)
    sub_menu = ui_we_want_to_set.plugin_menu.addMenu(config_name)

    about_action = QAction(
        language_wrapper.language_word_dict.get("plugin_menu_about", "About"),
        sub_menu,
    )
    about_action.triggered.connect(
        _make_about_callback(ui_we_want_to_set, plugin_name, plugin_version, plugin_author)
    )
    sub_menu.addAction(about_action)
    sub_menu.addSeparator()

    # One entry: every one ran the same config, whatever suffix its label named
    label_name = f"{config_name} ({', '.join(suffixes)})" if len(suffixes) > 1 else config_name
    _add_run_action(ui_we_want_to_set, sub_menu, run_config, label_name=label_name)


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


def _make_about_callback(parent: PyBreezeMainWindow, name: str, version: str, author: str):
    """
    建立顯示插件資訊的回呼函式。
    Create a callback to show plugin info dialog.

    The plugin's own name, version and author are shown as text: Qt read
    markup in them. The box belongs to the main window; with no parent it
    could open behind it.
    """
    def callback():
        message_box = QMessageBox(parent)
        message_box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        message_box.setWindowTitle(name)
        message_box.setText(as_text(
            f"{name}\n"
            f"Version: {version}\n"
            f"Author: {author}"
        ))
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
