from __future__ import annotations

from typing import TYPE_CHECKING

from je_editor import MainBrowserWidget

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.editor_main.main_ui import AutomationEditor


def open_web_browser(
        automation_editor_instance: AutomationEditor, url: str, tab_name: str) -> None:
    automation_editor_instance.tab_widget.addTab(
        MainBrowserWidget(start_url=url),
        f"{tab_name}{automation_editor_instance.tab_widget.count()}"
    )
