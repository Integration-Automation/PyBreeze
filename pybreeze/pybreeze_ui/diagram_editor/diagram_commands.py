from __future__ import annotations

import zlib
from typing import TYPE_CHECKING

from PySide6.QtGui import QUndoCommand

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import DiagramScene


class DiagramSnapshotCommand(QUndoCommand):
    """Snapshot-based undo/redo: stores full scene state before and after a change."""

    def __init__(self, scene: DiagramScene, description: str, old_data: dict, new_data: dict,
                 merge_key: str | None = None):
        """
        :param merge_key: steps with the same key, one after another, are one
            undo step (every arrow click on a spin box was its own)
        """
        super().__init__(description)
        self._scene = scene
        self._old_data = old_data
        self._new_data = new_data
        self._first_redo = True
        self._merge_key = merge_key

    def id(self) -> int:
        """The same for commands that may merge; -1 (never merged) without a key."""
        if self._merge_key is None:
            return -1
        return zlib.crc32(self._merge_key.encode("utf-8")) & 0x7FFFFFFF

    def mergeWith(self, other: QUndoCommand) -> bool:
        """Take in *other*, the next step on the same property: its result is this one's."""
        if not isinstance(other, DiagramSnapshotCommand) or other._merge_key != self._merge_key:
            return False
        self._new_data = other._new_data
        return True

    def redo(self) -> None:
        if self._first_redo:
            self._first_redo = False
            return
        self._scene._restore_from_dict(self._new_data)

    def undo(self) -> None:
        self._scene._restore_from_dict(self._old_data)
