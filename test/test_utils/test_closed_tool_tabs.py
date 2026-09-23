"""A closed tool tab is deleted, not kept until the IDE exits.

JEditor's close_tab closes the page and removes the tab; ``removeTab`` keeps
the page, so every tool tab ever closed -- a diagram and its scene, an SSH
panel -- stayed in memory for the rest of the session.
"""
from __future__ import annotations

from test_utils.started_window import run_started_window

_CLOSE_TABS = """
from PySide6.QtCore import QCoreApplication, QEvent
from je_editor import EditorWidget
from pybreeze.pybreeze_ui.tools_gui.hash_gui import HashGUI
from pybreeze.pybreeze_ui.diagram_editor.diagram_editor_widget import DiagramEditorWidget

gone = []
tabs = {"hash": HashGUI(window), "diagram": DiagramEditorWidget()}
for name, tab in tabs.items():
    window.tab_widget.addTab(tab, name)
    tab.destroyed.connect(lambda *_, name=name: gone.append(name))
editor = next(window.tab_widget.widget(i) for i in range(window.tab_widget.count())
              if isinstance(window.tab_widget.widget(i), EditorWidget))
editor_gone = []
editor.destroyed.connect(lambda *_: editor_gone.append(True))

for tab in tabs.values():
    window.close_tab(window.tab_widget.indexOf(tab))
    # Only this page's delete: others posted by the window's start are not ours
    QCoreApplication.sendPostedEvents(tab, QEvent.Type.DeferredDelete)
app.processEvents()

result = {"gone": sorted(gone), "editor_gone": editor_gone}
"""


def test_a_closed_tool_tab_is_deleted_and_an_editor_tab_is_left_to_jeditor(tmp_path):
    seen = run_started_window(tmp_path, _CLOSE_TABS)

    assert seen["gone"] == ["diagram", "hash"]
    assert seen["editor_gone"] == []
