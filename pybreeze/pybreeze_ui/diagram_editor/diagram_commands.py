from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QUndoCommand

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import DiagramScene


class DiagramSnapshotCommand(QUndoCommand):
    """Snapshot-based undo/redo: stores full scene state before and after a change."""

    def __init__(self, scene: DiagramScene, description: str, old_data: dict, new_data: dict):
        super().__init__(description)
        self._scene = scene
        self._old_data = old_data
        self._new_data = new_data
        self._first_redo = True

    def redo(self) -> None:
        if self._first_redo:
            self._first_redo = False
            return
        self._scene._restore_from_dict(self._new_data)

    def undo(self) -> None:
        self._scene._restore_from_dict(self._old_data)
