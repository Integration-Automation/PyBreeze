"""
"Run with..." menu — lets users run the current file with a plugin-registered runner.

Uses je_editor's plugin run config registry instead of scanning sys.modules. The
Plugins menu's run entries go through ``run_current_file_with`` here as well.
"""
from __future__ import annotations

import codecs
import locale
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMessageBox

from je_editor import (
    EditorWidget, JEditorSaveFileException, get_all_plugin_run_configs, language_wrapper
)
from je_editor.pyside_ui.dialog.file_dialog.save_file_dialog import choose_file_get_save_file_path
from je_editor.utils.encodings.text_codec import DEFAULT_ENCODING, LINE_ENDING_LF
from je_editor.utils.file.save.save_file import write_file_with_encoding

from pybreeze.extend.process_executor.file_runner_process import FileRunnerProcess
from pybreeze.extend.process_executor.process_executor_utils import open_run_window
from pybreeze.utils.logging.logger import pybreeze_logger

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import PyBreezeMainWindow


def plugin_text(value: object, fallback: str) -> str:
    """A plugin-supplied name or label as text, *fallback* when there is none.

    A plugin is anyone's code: a ``None`` name reached ``QMenu.addMenu(None)``,
    which is an access violation, not a Python error, and a mix of ``None``
    and text names made sorting the configs raise, both while the IDE started.
    """
    text = "" if value is None else str(value).strip()
    return text or fallback


def plugin_run_configs() -> list[dict]:
    """The registered run configs that are dicts, named, in name order; others are logged and skipped."""
    configs = []
    for config in get_all_plugin_run_configs():
        if isinstance(config, dict):
            configs.append(config)
        else:
            pybreeze_logger.error("Plugin run config ignored: not a dict (%s)", type(config).__name__)
    return sorted(configs, key=lambda config: plugin_text(config.get("name"), "Unknown").lower())


def run_config_suffixes(run_config: dict) -> tuple[str, ...]:
    """The suffixes a plugin's run config accepts, as ``Path.suffix`` gives them: lower case, with the dot.

    JEditor keeps what the plugin registered as it was, so ``".R"`` or ``"r"``
    never matched a file's suffix and the run was always refused.
    """
    suffixes = run_config.get("suffixes", ())
    if isinstance(suffixes, str):
        suffixes = (suffixes,)
    normalized: list[str] = []
    for suffix in suffixes:
        if not isinstance(suffix, str) or not suffix.strip(". "):
            continue
        one = "." + suffix.strip().lstrip(".").lower()
        if one not in normalized:
            normalized.append(one)
    return tuple(normalized)


def save_current_file_for_run(main_window: PyBreezeMainWindow) -> str | None:
    """Save the current editor tab and return its path, or None when there is nothing to run.

    A tab that already has a file is written in place the way JEditor's own saves
    write it: in the tab's encoding and line ending (a Big5 or CRLF file stays
    one), with the tab's file watcher told to expect the write (otherwise it asks
    whether to reload the file PyBreeze just wrote), and with the tab's unsaved
    marker cleared. A tab without a file goes through JEditor's Save As dialog.

    A save that fails -- a character the tab's encoding cannot hold, a read-only
    or locked file -- is reported and runs nothing: the run would otherwise use
    what is on disk, not what is in the tab.
    """
    widget = main_window.tab_widget.currentWidget()
    if not isinstance(widget, EditorWidget):
        return None
    try:
        return _save(main_window, widget)
    except JEditorSaveFileException as error:
        pybreeze_logger.error("Save before run failed: %r", error.__cause__ or error)
        QMessageBox.warning(
            main_window, language_wrapper.language_word_dict.get("run_with_menu_label"),
            language_wrapper.language_word_dict.get("run_with_save_failed").format(
                file=Path(str(widget.current_file or "")).name,
                error=error.__cause__ or error))
        return None


def _save(main_window: PyBreezeMainWindow, widget: EditorWidget) -> str | None:
    """Write *widget* to its file, or through Save As; the path, or None if cancelled."""
    if not widget.current_file:
        if not choose_file_get_save_file_path(main_window):
            return None
        # The save dialog can be accepted without a path being set.
        return widget.current_file or None
    write_file_with_encoding(
        str(widget.current_file), widget.code_edit.toPlainText(),
        getattr(widget, "file_encoding", DEFAULT_ENCODING),
        getattr(widget, "line_ending", LINE_ENDING_LF))
    # Only after a write that happened: set before one that failed, the flag
    # stayed on and swallowed the next real change made outside the editor.
    # The watcher's signal is queued, so it still arrives after this.
    widget.mark_ignore_next_file_change()
    widget.mark_saved()
    return widget.current_file


def run_current_file_with(main_window: PyBreezeMainWindow, run_config: dict) -> None:
    """Save the current file, then run it with *run_config* in a new run window."""
    file_path = save_current_file_for_run(main_window)
    if not file_path:
        return

    # Check suffix match
    suffix = Path(file_path).suffix.lower()
    supported = run_config_suffixes(run_config)
    if supported and suffix not in supported:
        msg = QMessageBox(main_window)
        msg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        msg.setWindowTitle(language_wrapper.language_word_dict.get("run_with_menu_label"))
        msg.setText(
            language_wrapper.language_word_dict.get("run_with_suffix_mismatch").format(
                suffix=suffix,
                expected=", ".join(supported),
            )
        )
        msg.exec()
        return

    # JEditor does not check what a plugin registers: a config without a
    # name raised KeyError here, after the file had been saved.
    code_window = open_run_window(
        main_window, f"{plugin_text(run_config.get('name'), 'Run')} - {Path(file_path).name}")

    code_window.runner = FileRunnerProcess(
        main_window=code_window,
        program_encoding=output_encoding(run_config, main_window.encoding),
    )
    code_window.runner.run_file(run_config, file_path)


def output_encoding(run_config: dict, default: str) -> str:
    """The encoding the program run by *run_config* writes: its ``encoding``, else *default*.

    Go, Rust and C programs write the bytes they were given, usually UTF-8, but
    Java and localized compilers write the console's code page (MS950 on a
    Traditional Chinese Windows): decoded as UTF-8 their text was garbled. A
    plugin says so with ``"encoding": "cp950"``, or ``"locale"`` for the
    machine's own. A name Python does not know is logged and ignored.
    """
    named = run_config.get("encoding")
    if not isinstance(named, str) or not named.strip():
        return default
    if named.strip().lower() == "locale":
        return locale.getpreferredencoding(False)
    try:
        return codecs.lookup(named.strip()).name
    except LookupError:
        pybreeze_logger.error("Run config %s names an unknown encoding %r; using %s",
                              plugin_text(run_config.get("name"), "Run"), named, default)
        return default


def set_run_with_menu(ui_we_want_to_set: PyBreezeMainWindow) -> None:
    """Build the 'Run with...' submenu. Only creates if configs exist."""
    configs = plugin_run_configs()
    if not configs:
        return

    ui_we_want_to_set.run_with_menu = ui_we_want_to_set.run_menu.addMenu(
        language_wrapper.language_word_dict.get("run_with_menu_label")
    )

    for config in configs:
        name = plugin_text(config.get("name"), "Unknown")
        suffixes = ", ".join(run_config_suffixes(config))
        label = f"{name}  ({suffixes})" if suffixes else name

        action = QAction(label, ui_we_want_to_set.run_with_menu)
        action.triggered.connect(
            lambda checked=False, cfg=config: run_current_file_with(ui_we_want_to_set, cfg)
        )
        ui_we_want_to_set.run_with_menu.addAction(action)
