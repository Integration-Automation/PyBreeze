from __future__ import annotations

from contextlib import contextmanager
from enum import Enum, auto

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPen, QPixmap, QTransform, QUndoStack
from PySide6.QtWidgets import QGraphicsItem, QGraphicsLineItem, QGraphicsScene, QMenu

from pybreeze.pybreeze_ui.diagram_editor.diagram_commands import DiagramSnapshotCommand
from pybreeze.pybreeze_ui.diagram_editor.diagram_items import (
    ConnectionStyle,
    DiagramConnection,
    DiagramImage,
    DiagramNode,
    NodeShape,
    ResizeHandle,
)


class ToolMode(Enum):
    """State pattern: each mode defines how mouse events behave on the canvas."""
    SELECT = auto()
    ADD_RECT = auto()
    ADD_ROUNDED_RECT = auto()
    ADD_ELLIPSE = auto()
    ADD_DIAMOND = auto()
    ADD_CONNECTION = auto()
    ADD_TEXT = auto()


_MODE_SHAPE_MAP: dict[ToolMode, NodeShape] = {
    ToolMode.ADD_RECT: NodeShape.RECTANGLE,
    ToolMode.ADD_ROUNDED_RECT: NodeShape.ROUNDED_RECT,
    ToolMode.ADD_ELLIPSE: NodeShape.ELLIPSE,
    ToolMode.ADD_DIAMOND: NodeShape.DIAMOND,
}


class DiagramScene(QGraphicsScene):
    """QGraphicsScene with tool-mode state, undo/redo, grid, copy/paste, and align."""

    mode_changed = Signal(ToolMode)
    item_count_changed = Signal()
    zoom_requested = Signal(float)  # emitted when scene wants to change zoom

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode: ToolMode = ToolMode.SELECT
        self._connection_source: DiagramNode | None = None
        self._temp_line: QGraphicsLineItem | None = None
        self.setSceneRect(-4000, -4000, 8000, 8000)

        # BSP tree for fast spatial queries on large diagrams
        self.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.BspTreeIndex)
        self.setBspTreeDepth(14)

        # Undo/Redo
        self.undo_stack = QUndoStack(self)
        self._pending_undo_snapshot: dict | None = None
        self._pending_undo_desc: str | None = None

        # Grid
        self._grid_enabled = False
        self._grid_size = 20

        # Clipboard
        self._clipboard: dict | None = None

    # ------------------------------------------------------------------
    # Grid
    # ------------------------------------------------------------------

    @property
    def grid_enabled(self) -> bool:
        return self._grid_enabled

    @grid_enabled.setter
    def grid_enabled(self, value: bool) -> None:
        self._grid_enabled = value
        DiagramNode.grid_enabled = value

    @property
    def grid_size(self) -> int:
        return self._grid_size

    @grid_size.setter
    def grid_size(self, value: int) -> None:
        self._grid_size = max(5, value)
        DiagramNode.grid_size = self._grid_size

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    @property
    def mode(self) -> ToolMode:
        return self._mode

    @mode.setter
    def mode(self, value: ToolMode) -> None:
        self._cancel_connection()
        focus = self.focusItem()
        if focus is not None:
            focus.clearFocus()
        self._mode = value
        self.mode_changed.emit(value)

    # ------------------------------------------------------------------
    # Undo helpers
    # ------------------------------------------------------------------

    def _snapshot(self) -> dict:
        return self.to_dict()

    def begin_undo(self, description: str) -> None:
        self._pending_undo_desc = description
        self._pending_undo_snapshot = self._snapshot()

    def end_undo(self) -> None:
        if self._pending_undo_snapshot is None:
            return
        new = self._snapshot()
        if new != self._pending_undo_snapshot:
            cmd = DiagramSnapshotCommand(
                self, self._pending_undo_desc or "Edit",
                self._pending_undo_snapshot, new,
            )
            self.undo_stack.push(cmd)
        self._pending_undo_snapshot = None
        self._pending_undo_desc = None

    @contextmanager
    def undo_scope(self, description: str):
        self.begin_undo(description)
        yield
        self.end_undo()

    def _restore_from_dict(self, data: dict) -> None:
        """Rebuild scene from serialised data (used by undo/redo)."""
        self.blockSignals(True)
        self._clear_items()
        self._load_items(data)
        self.blockSignals(False)
        self.item_count_changed.emit()
        # Trigger selection change so property panel updates
        self.selectionChanged.emit()

    # ------------------------------------------------------------------
    # Mouse handlers
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        pos = event.scenePos()

        # Node creation modes
        shape = _MODE_SHAPE_MAP.get(self._mode)
        if shape is not None:
            with self.undo_scope("Add Node"):
                node = DiagramNode(x=pos.x() - 70, y=pos.y() - 30, shape=shape)
                self.addItem(node)
            self.item_count_changed.emit()
            self.mode = ToolMode.SELECT
            return

        # Text-only node
        if self._mode == ToolMode.ADD_TEXT:
            with self.undo_scope("Add Text"):
                node = DiagramNode(
                    x=pos.x() - 70, y=pos.y() - 20,
                    w=140, h=40, text="Text",
                    shape=NodeShape.RECTANGLE,
                )
                self.addItem(node)
            self.item_count_changed.emit()
            self.mode = ToolMode.SELECT
            return

        # Connection mode
        if self._mode == ToolMode.ADD_CONNECTION:
            target_node = self._node_at(pos)
            if target_node is not None:
                if self._connection_source is None:
                    # First click — pick source
                    self._connection_source = target_node
                    self._temp_line = QGraphicsLineItem()
                    self._temp_line.setPen(QPen(QColor("#90a4ae"), 1.5, Qt.PenStyle.DashLine))
                    self._temp_line.setZValue(-100)
                    self._temp_line.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
                    center = target_node.center_pos()
                    self._temp_line.setLine(center.x(), center.y(), pos.x(), pos.y())
                    self.addItem(self._temp_line)
                else:
                    # Second click — create connection
                    if target_node is not self._connection_source:
                        with self.undo_scope("Add Connection"):
                            conn = DiagramConnection(self._connection_source, target_node)
                            self.addItem(conn)
                        self.item_count_changed.emit()
                    self._cancel_connection()
                    self.mode = ToolMode.SELECT
                return
            # Clicked empty area — cancel current connection attempt
            if self._connection_source is not None:
                self._cancel_connection()
                return
            return

        # SELECT mode — track for move undo
        if self._mode == ToolMode.SELECT:
            super().mousePressEvent(event)
            selected_nodes = [i for i in self.selectedItems() if isinstance(i, DiagramNode)]
            if selected_nodes:
                self.begin_undo("Move")
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._temp_line is not None and self._connection_source is not None:
            center = self._connection_source.center_pos()
            self._temp_line.setLine(
                center.x(), center.y(),
                event.scenePos().x(), event.scenePos().y(),
            )
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        self.end_undo()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            focus = self.focusItem()
            if focus is not None and focus.textInteractionFlags() & Qt.TextInteractionFlag.TextEditorInteraction:
                super().keyPressEvent(event)
                return
            self.delete_selected()
            return
        if event.key() == Qt.Key.Key_Escape:
            self._cancel_connection()
            self.mode = ToolMode.SELECT
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event) -> None:
        from je_editor import language_wrapper
        menu = QMenu()
        item = self._node_at(event.scenePos())
        conn = self._connection_at(event.scenePos())

        if item is not None or conn is not None:
            menu.addAction(
                language_wrapper.language_word_dict.get("diagram_editor_ctx_delete", "Delete"),
                self.delete_selected,
            )
            if item is not None:
                menu.addAction(
                    language_wrapper.language_word_dict.get("diagram_editor_ctx_duplicate", "Duplicate"),
                    self.duplicate_selected,
                )
                menu.addSeparator()
                menu.addAction(
                    language_wrapper.language_word_dict.get("diagram_editor_ctx_bring_front", "Bring to Front"),
                    lambda: self._change_z(1),
                )
                menu.addAction(
                    language_wrapper.language_word_dict.get("diagram_editor_ctx_send_back", "Send to Back"),
                    lambda: self._change_z(-1),
                )
        else:
            if self._clipboard:
                menu.addAction(
                    language_wrapper.language_word_dict.get("diagram_editor_ctx_paste", "Paste"),
                    self.paste_clipboard,
                )
            menu.addAction(
                language_wrapper.language_word_dict.get("diagram_editor_ctx_select_all", "Select All"),
                self.select_all,
            )

        if menu.actions():
            menu.exec(event.screenPos())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _node_at(self, pos: QPointF) -> DiagramNode | None:
        """Find the topmost DiagramNode at pos, skipping temp_line and resize handles."""
        for item in self.items(pos):
            if item is self._temp_line:
                continue
            if isinstance(item, ResizeHandle):
                continue
            node = self._find_parent_node(item)
            if node is not None:
                return node
        return None

    def _connection_at(self, pos: QPointF) -> DiagramConnection | None:
        for item in self.items(pos):
            if isinstance(item, DiagramConnection):
                return item
        return None

    @staticmethod
    def _find_parent_node(item) -> DiagramNode | None:
        while item is not None:
            if isinstance(item, DiagramNode):
                return item
            item = item.parentItem()
        return None

    def _cancel_connection(self) -> None:
        self._connection_source = None
        if self._temp_line is not None:
            self.removeItem(self._temp_line)
            self._temp_line = None

    def _change_z(self, direction: int) -> None:
        for item in self.selectedItems():
            if isinstance(item, DiagramNode):
                item.setZValue(item.zValue() + direction)

    # ------------------------------------------------------------------
    # Operations (all undoable)
    # ------------------------------------------------------------------

    def delete_selected(self) -> None:
        selected = self.selectedItems()
        if not selected:
            return
        with self.undo_scope("Delete"):
            for item in list(selected):
                if isinstance(item, DiagramConnection):
                    item.detach()
                    self.removeItem(item)
            for item in list(selected):
                if isinstance(item, DiagramNode):
                    for conn in list(item.connections):
                        conn.detach()
                        self.removeItem(conn)
                    self.removeItem(item)
                elif isinstance(item, DiagramImage):
                    self.removeItem(item)
        self.item_count_changed.emit()

    def select_all(self) -> None:
        for item in self.items():
            if isinstance(item, (DiagramNode, DiagramConnection, DiagramImage)):
                item.setSelected(True)

    def copy_selected(self) -> None:
        nodes = [i for i in self.selectedItems() if isinstance(i, DiagramNode)]
        if not nodes:
            return
        node_set = set(nodes)
        connections = [
            i for i in self.selectedItems()
            if isinstance(i, DiagramConnection)
            and i.source in node_set and i.target in node_set
        ]
        node_map = {n: idx for idx, n in enumerate(nodes)}
        self._clipboard = {
            "nodes": [n.to_dict(node_map[n]) for n in nodes],
            "connections": [c.to_dict(node_map) for c in connections],
        }

    def paste_clipboard(self) -> None:
        if not self._clipboard:
            return
        with self.undo_scope("Paste"):
            self.clearSelection()
            id_to_node: dict[int, DiagramNode] = {}
            for nd in self._clipboard["nodes"]:
                data = dict(nd)
                data["x"] += 30
                data["y"] += 30
                node = DiagramNode.from_dict(data)
                self.addItem(node)
                node.setSelected(True)
                id_to_node[nd["id"]] = node
            for cd in self._clipboard["connections"]:
                src = id_to_node.get(cd["source"])
                tgt = id_to_node.get(cd["target"])
                if src is not None and tgt is not None:
                    conn = DiagramConnection(
                        src, tgt,
                        label=cd.get("label", ""),
                        line_color=cd.get("line_color"),
                        line_width=cd.get("line_width", 2.0),
                        style=ConnectionStyle[cd.get("style", "SOLID")],
                    )
                    self.addItem(conn)
        self.item_count_changed.emit()

    def duplicate_selected(self) -> None:
        self.copy_selected()
        self.paste_clipboard()

    # ------------------------------------------------------------------
    # Align tools (all undoable)
    # ------------------------------------------------------------------

    def _selected_nodes(self) -> list[DiagramNode]:
        return [i for i in self.selectedItems() if isinstance(i, DiagramNode)]

    def align_left(self) -> None:
        nodes = self._selected_nodes()
        if len(nodes) < 2:
            return
        target = min(n.pos().x() for n in nodes)
        with self.undo_scope("Align Left"):
            for n in nodes:
                n.setPos(target, n.pos().y())

    def align_right(self) -> None:
        nodes = self._selected_nodes()
        if len(nodes) < 2:
            return
        target = max(n.pos().x() + n.node_w for n in nodes)
        with self.undo_scope("Align Right"):
            for n in nodes:
                n.setPos(target - n.node_w, n.pos().y())

    def align_top(self) -> None:
        nodes = self._selected_nodes()
        if len(nodes) < 2:
            return
        target = min(n.pos().y() for n in nodes)
        with self.undo_scope("Align Top"):
            for n in nodes:
                n.setPos(n.pos().x(), target)

    def align_bottom(self) -> None:
        nodes = self._selected_nodes()
        if len(nodes) < 2:
            return
        target = max(n.pos().y() + n.node_h for n in nodes)
        with self.undo_scope("Align Bottom"):
            for n in nodes:
                n.setPos(n.pos().x(), target - n.node_h)

    def align_center_h(self) -> None:
        nodes = self._selected_nodes()
        if len(nodes) < 2:
            return
        centers = [n.pos().x() + n.node_w / 2 for n in nodes]
        target = sum(centers) / len(centers)
        with self.undo_scope("Center Horizontal"):
            for n in nodes:
                n.setPos(target - n.node_w / 2, n.pos().y())

    def align_center_v(self) -> None:
        nodes = self._selected_nodes()
        if len(nodes) < 2:
            return
        centers = [n.pos().y() + n.node_h / 2 for n in nodes]
        target = sum(centers) / len(centers)
        with self.undo_scope("Center Vertical"):
            for n in nodes:
                n.setPos(n.pos().x(), target - n.node_h / 2)

    def distribute_h(self) -> None:
        nodes = self._selected_nodes()
        if len(nodes) < 3:
            return
        nodes.sort(key=lambda n: n.pos().x())
        left = nodes[0].pos().x()
        right = nodes[-1].pos().x() + nodes[-1].node_w
        total_w = sum(n.node_w for n in nodes)
        gap = (right - left - total_w) / (len(nodes) - 1) if len(nodes) > 1 else 0
        with self.undo_scope("Distribute Horizontal"):
            x = left
            for n in nodes:
                n.setPos(x, n.pos().y())
                x += n.node_w + gap

    def distribute_v(self) -> None:
        nodes = self._selected_nodes()
        if len(nodes) < 3:
            return
        nodes.sort(key=lambda n: n.pos().y())
        top = nodes[0].pos().y()
        bottom = nodes[-1].pos().y() + nodes[-1].node_h
        total_h = sum(n.node_h for n in nodes)
        gap = (bottom - top - total_h) / (len(nodes) - 1) if len(nodes) > 1 else 0
        with self.undo_scope("Distribute Vertical"):
            y = top
            for n in nodes:
                n.setPos(n.pos().x(), y)
                y += n.node_h + gap

    # ------------------------------------------------------------------
    # Image operations
    # ------------------------------------------------------------------

    def add_image(self, pixmap: QPixmap, source: str, pos: QPointF | None = None) -> DiagramImage:
        """Add an image to the scene at *pos* (default: centre of view)."""
        w = min(pixmap.width(), 400)
        h = int(pixmap.height() * w / max(pixmap.width(), 1))
        if pos is None:
            views = self.views()
            if views:
                pos = views[0].mapToScene(views[0].viewport().rect().center())
            else:
                pos = QPointF(0, 0)
        with self.undo_scope("Add Image"):
            img = DiagramImage(x=pos.x() - w / 2, y=pos.y() - h / 2, w=w, h=h, source=source, pixmap=pixmap)
            self.addItem(img)
        self.item_count_changed.emit()
        return img

    def get_all_images(self) -> list[DiagramImage]:
        return [item for item in self.items() if isinstance(item, DiagramImage)]

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def get_all_nodes(self) -> list[DiagramNode]:
        return [item for item in self.items() if isinstance(item, DiagramNode)]

    def get_all_connections(self) -> list[DiagramConnection]:
        return [item for item in self.items() if isinstance(item, DiagramConnection)]

    def to_dict(self) -> dict:
        nodes = self.get_all_nodes()
        node_map: dict[DiagramNode, int] = {n: i for i, n in enumerate(nodes)}
        return {
            "nodes": [n.to_dict(node_map[n]) for n in nodes],
            "connections": [c.to_dict(node_map) for c in self.get_all_connections()],
            "images": [img.to_dict(i) for i, img in enumerate(self.get_all_images())],
        }

    def _clear_items(self) -> None:
        """Remove all diagram items without clearing the scene entirely."""
        for item in list(self.items()):
            if isinstance(item, (DiagramNode, DiagramConnection, DiagramImage)):
                if isinstance(item, DiagramConnection):
                    item.detach()
                self.removeItem(item)

    def _load_items(self, data: dict) -> None:
        """Add items from serialised data."""
        id_to_node: dict[int, DiagramNode] = {}
        for nd in data.get("nodes", []):
            node = DiagramNode.from_dict(nd)
            self.addItem(node)
            id_to_node[nd["id"]] = node
        for cd in data.get("connections", []):
            src = id_to_node.get(cd["source"])
            tgt = id_to_node.get(cd["target"])
            if src is not None and tgt is not None:
                conn = DiagramConnection(
                    src, tgt,
                    label=cd.get("label", ""),
                    line_color=cd.get("line_color"),
                    line_width=cd.get("line_width", 2.0),
                    style=ConnectionStyle[cd.get("style", "SOLID")],
                )
                self.addItem(conn)
        for img_d in data.get("images", []):
            img = DiagramImage.from_dict(img_d)
            self.addItem(img)
            # Try to reload pixmap from source
            source = img_d.get("source", "")
            if source:
                self._try_load_image_source(img, source)

    def _try_load_image_source(self, img: DiagramImage, source: str) -> None:
        """Load pixmap from local path or URL into a DiagramImage."""
        from pathlib import Path
        path = Path(source)
        if path.is_file():
            pix = QPixmap(str(path))
            if not pix.isNull():
                img.set_pixmap(pix, source)
                return
        # Try as URL (non-blocking would be better, but keep it simple)
        if source.startswith(("http://", "https://")):
            try:
                from urllib.request import urlopen
                data = urlopen(source, timeout=10).read()
                pix = QPixmap()
                pix.loadFromData(data)
                if not pix.isNull():
                    img.set_pixmap(pix, source)
            except Exception:
                pass

    def load_from_dict(self, data: dict) -> None:
        self._clear_items()
        self._load_items(data)
        self.undo_stack.clear()
        self.item_count_changed.emit()
