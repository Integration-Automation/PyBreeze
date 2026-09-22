from __future__ import annotations

from contextlib import contextmanager
from http.client import HTTPException
from enum import Enum, auto
from pathlib import Path, PureWindowsPath

from PySide6.QtCore import QPointF, Qt, QThread, Signal
from PySide6.QtGui import QColor, QPen, QPixmap, QUndoStack
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsScene, QMenu
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.diagram_editor.diagram_commands import DiagramSnapshotCommand
from pybreeze.pybreeze_ui.diagram_editor.diagram_items import (
    ConnectionStyle,
    DiagramConnection,
    DiagramImage,
    DiagramNode,
    NodeShape,
    ResizeHandle,
)
from pybreeze.pybreeze_ui.diagram_editor.diagram_net_utils import (
    ImageDownloadError,
    safe_download_image,
)
from pybreeze.utils.logging.logger import pybreeze_logger

# Allowlist of image extensions that a saved diagram may reference on disk.
# Defined once at module scope because it is a security boundary (only these
# local files are read back when reloading a ``.diagram.json``).
# How far a pasted copy sits from the original, so it is visible as a copy
_PASTE_OFFSET = 30

_VALID_IMAGE_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".svg", ".webp", ".ico"}
)


def _is_on_this_machine(source: str) -> bool:
    """Whether *source* names a path on this machine rather than another host.

    UNC paths (``\\\\host\\share\\x.png``, or ``//host/share/x.png``, which
    Windows treats the same) are refused: see ``_try_load_image_source``.
    """
    if source.startswith(("\\\\", "//")):
        return False
    return not PureWindowsPath(source).drive.startswith("\\\\")


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


class ImageDownloadThread(QThread):
    """Fetch one image for the canvas, off the UI thread.

    A download is bounded by ``safe_download_image``'s own 15 s timeout, which is
    15 s the IDE would otherwise spend frozen -- once per image, and again on
    every undo, because an undo rebuilds every item from the saved dictionary.
    Only the two signals reach the UI.
    """

    fetched = Signal(str, bytes)
    failed = Signal(str, str)

    def __init__(self, source: str) -> None:
        super().__init__()
        self._source = source

    def run(self) -> None:
        try:
            data = safe_download_image(self._source)
        except (ImageDownloadError, OSError, HTTPException) as err:
            self.failed.emit(self._source, str(err))
        else:
            self.fetched.emit(self._source, data)


class DiagramScene(QGraphicsScene):
    """QGraphicsScene with tool-mode state, undo/redo, grid, copy/paste, and align."""

    mode_changed = Signal(ToolMode)
    item_count_changed = Signal()

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

        # Images already loaded, and the fetches still going, by source
        self._pixmap_cache: dict[str, QPixmap] = {}
        self._image_downloads: dict[str, ImageDownloadThread] = {}

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
        # Both item types snap independently, so keep their class flags in sync —
        # otherwise images ignore the grid while nodes honour it.
        DiagramNode.grid_enabled = value
        DiagramImage.grid_enabled = value

    @property
    def grid_size(self) -> int:
        return self._grid_size

    @grid_size.setter
    def grid_size(self, value: int) -> None:
        self._grid_size = max(5, value)
        DiagramNode.grid_size = self._grid_size
        DiagramImage.grid_size = self._grid_size

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
        """Take a snapshot, run the body, and record what it changed.

        The closing snapshot is taken even when the body raises: a scope left
        open would be closed by the next mouse release instead, turning an
        unrelated click into an undo entry that reverts everything since.
        """
        self.begin_undo(description)
        try:
            yield
        finally:
            self.end_undo()

    @staticmethod
    def _check_is_a_diagram(data: dict) -> None:
        """Raise ``ValueError`` unless *data* has the shape of a diagram."""
        if not isinstance(data, dict):
            raise ValueError("a diagram file holds an object, not a %s" % type(data).__name__)
        for section in ("nodes", "connections", "images"):
            value = data.get(section, [])
            if not isinstance(value, list):
                raise ValueError(f"a diagram's '{section}' is a list, not a {type(value).__name__}")

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

        shape = _MODE_SHAPE_MAP.get(self._mode)
        if shape is not None:
            self._add_shape_node(pos, shape)
            return

        if self._mode == ToolMode.ADD_TEXT:
            self._add_text_node(pos)
            return

        if self._mode == ToolMode.ADD_CONNECTION:
            self._handle_connection_click(pos)
            return

        if self._mode == ToolMode.SELECT:
            super().mousePressEvent(event)
            if any(isinstance(i, DiagramNode) for i in self.selectedItems()):
                self.begin_undo("Move")
            return

        super().mousePressEvent(event)

    def _add_shape_node(self, pos: QPointF, shape: NodeShape) -> None:
        with self.undo_scope("Add Node"):
            self.addItem(DiagramNode(x=pos.x() - 70, y=pos.y() - 30, shape=shape))
        self.item_count_changed.emit()
        self.mode = ToolMode.SELECT

    def _add_text_node(self, pos: QPointF) -> None:
        with self.undo_scope("Add Text"):
            self.addItem(DiagramNode(
                x=pos.x() - 70, y=pos.y() - 20,
                w=140, h=40, text="Text",
                shape=NodeShape.RECTANGLE,
            ))
        self.item_count_changed.emit()
        self.mode = ToolMode.SELECT

    def _handle_connection_click(self, pos: QPointF) -> None:
        target_node = self._node_at(pos)
        if target_node is None:
            if self._connection_source is not None:
                self._cancel_connection()
            return
        if self._connection_source is None:
            self._start_connection_drag(target_node, pos)
            return
        if target_node is not self._connection_source:
            with self.undo_scope("Add Connection"):
                self.addItem(DiagramConnection(self._connection_source, target_node))
            self.item_count_changed.emit()
        self._cancel_connection()
        self.mode = ToolMode.SELECT

    def _start_connection_drag(self, source: DiagramNode, pos: QPointF) -> None:
        self._connection_source = source
        self._temp_line = QGraphicsLineItem()
        self._temp_line.setPen(QPen(QColor("#90a4ae"), 1.5, Qt.PenStyle.DashLine))
        self._temp_line.setZValue(-100)
        self._temp_line.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        center = source.center_pos()
        self._temp_line.setLine(center.x(), center.y(), pos.x(), pos.y())
        self.addItem(self._temp_line)

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
        """Raise or lower the selected nodes. Undoable, and kept in the file."""
        with self.undo_scope("Change Z"):
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
            for item in selected:
                if isinstance(item, DiagramConnection):
                    item.detach()
                    self.removeItem(item)
            for item in selected:
                if isinstance(item, DiagramNode):
                    # snapshot: detach() mutates item.connections during iteration
                    for conn in tuple(item.connections):
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
        """Put the selected items on the clipboard, in the diagram's own format.

        A connection comes along only when both of its ends do; an image comes
        along on its own, which is also what ``Ctrl+D`` on one needs.
        """
        nodes = [i for i in self.selectedItems() if isinstance(i, DiagramNode)]
        images = [i for i in self.selectedItems() if isinstance(i, DiagramImage)]
        if not nodes and not images:
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
            "images": [image.to_dict(index) for index, image in enumerate(images)],
        }

    def paste_clipboard(self) -> None:
        if not self._clipboard:
            return
        with self.undo_scope("Paste"):
            self.clearSelection()
            id_to_node: dict[int, DiagramNode] = {}
            for nd in self._clipboard["nodes"]:
                data = dict(nd)
                data["x"] += _PASTE_OFFSET
                data["y"] += _PASTE_OFFSET
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
                        style=ConnectionStyle.__members__.get(cd.get("style", "SOLID"), ConnectionStyle.SOLID),
                    )
                    self.addItem(conn)
            self._paste_images()
        self.item_count_changed.emit()

    def _paste_images(self) -> None:
        """Add the clipboard's images, offset like its nodes and selected with them."""
        for image_dict in self._clipboard.get("images", ()):
            data = dict(image_dict)
            data["x"] += _PASTE_OFFSET
            data["y"] += _PASTE_OFFSET
            image = DiagramImage.from_dict(data)
            self.addItem(image)
            image.setSelected(True)
            source = data.get("source", "")
            if source:
                self._try_load_image_source(image, source)

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
        # snapshot: removeItem() mutates scene items during iteration
        for item in tuple(self.items()):
            if isinstance(item, (DiagramNode, DiagramConnection, DiagramImage)):
                if isinstance(item, DiagramConnection):
                    item.detach()
                self.removeItem(item)

    def _load_items(self, data: dict) -> None:
        """Add items from serialised data, skipping any malformed entry.

        A single corrupt node/connection/image must not abort the whole load
        and lose the valid items alongside it (saved diagrams can be hand-edited
        or partially written), so each entry is loaded defensively.
        """
        id_to_node = self._load_nodes(data.get("nodes", []))
        self._load_connections(data.get("connections", []), id_to_node)
        self._load_images(data.get("images", []))

    def _load_nodes(self, node_dicts: list) -> dict[int, DiagramNode]:
        id_to_node: dict[int, DiagramNode] = {}
        for nd in node_dicts:
            try:
                node = DiagramNode.from_dict(nd)
            except (KeyError, ValueError, TypeError) as err:
                pybreeze_logger.debug("Skipping malformed diagram node %r: %s", nd, err)
                continue
            self.addItem(node)
            try:
                node_id = nd.get("id")
                if node_id is not None:
                    if node_id in id_to_node:
                        # Later wins, as before; connections to that id now
                        # point at this node, which is worth a line in the log.
                        pybreeze_logger.debug(
                            "Diagram has more than one node with id %r", node_id)
                    id_to_node[node_id] = node
            except TypeError as err:
                # An id that cannot be a key (a list, say): the node is on the
                # canvas, only its connections cannot find it.
                pybreeze_logger.debug("Diagram node with an unusable id %r: %s", nd, err)
        return id_to_node

    def _load_connections(self, conn_dicts: list, id_to_node: dict[int, DiagramNode]) -> None:
        for cd in conn_dicts:
            try:
                conn = self._connection_from_dict(cd, id_to_node)
            except (AttributeError, KeyError, TypeError, ValueError) as err:
                pybreeze_logger.debug("Skipping malformed diagram connection %r: %s", cd, err)
                continue
            if conn is not None:
                self.addItem(conn)

    @staticmethod
    def _connection_from_dict(
            cd: dict, id_to_node: dict[int, DiagramNode]) -> DiagramConnection | None:
        """Build one connection, or ``None`` when either end is not on the canvas."""
        src = id_to_node.get(cd.get("source"))
        tgt = id_to_node.get(cd.get("target"))
        if src is None or tgt is None:
            return None
        style = ConnectionStyle.__members__.get(cd.get("style", "SOLID"), ConnectionStyle.SOLID)
        return DiagramConnection(
            src, tgt,
            label=cd.get("label", ""),
            line_color=cd.get("line_color"),
            line_width=cd.get("line_width", 2.0),
            style=style,
        )

    def _load_images(self, image_dicts: list) -> None:
        for img_d in image_dicts:
            try:
                img = DiagramImage.from_dict(img_d)
            except (KeyError, ValueError, TypeError) as err:
                pybreeze_logger.debug("Skipping malformed diagram image %r: %s", img_d, err)
                continue
            self.addItem(img)
            # Try to reload pixmap from source
            source = img_d.get("source", "")
            if source:
                self._try_load_image_source(img, source)

    def _try_load_image_source(self, img: DiagramImage, source: str) -> None:
        """Put the image *source* names into *img*, fetching it if it is a URL.

        Local paths are restricted to existing image files on this machine. A URL
        is validated and size-limited by ``safe_download_image``, on its own
        thread, and what comes back is kept for the rest of the session: an undo
        rebuilds every item, and re-fetching each time froze the IDE for as long
        as the host took to answer.
        """
        cached = self._pixmap_cache.get(source)
        if cached is not None:
            img.set_pixmap(cached, source)
            return
        path = Path(source)
        # The extension is checked before the filesystem is touched, and a path
        # on another machine is refused outright: on Windows, merely asking
        # whether \\host\share\x.png is a file makes the SMB client authenticate
        # to that host, so a diagram from someone else could collect the user's
        # credentials, and an unreachable host would block the UI thread until
        # SMB gives up.
        if (path.suffix.lower() in _VALID_IMAGE_SUFFIXES
                and _is_on_this_machine(source) and path.is_file()):
            pix = QPixmap(str(path))
            if not pix.isNull():
                self._pixmap_cache[source] = pix
                img.set_pixmap(pix, source)
                return
        if source.startswith(("http://", "https://")):  # NOSONAR S5332 — scheme detection; actual fetch goes through safe_download_image with SSRF validation
            self._start_image_download(source)

    def _start_image_download(self, source: str) -> None:
        """Fetch *source* in the background, unless a fetch for it is already going."""
        if source in self._image_downloads:
            return
        thread = ImageDownloadThread(source)
        thread.fetched.connect(self._on_image_fetched)
        thread.failed.connect(self._on_image_download_failed)
        thread.finished.connect(lambda: self._image_downloads.pop(source, None))
        self._image_downloads[source] = thread
        thread.start()

    def _on_image_fetched(self, source: str, data: bytes) -> None:
        """Hand a fetched image to every item still waiting for it. UI thread."""
        pix = QPixmap()
        pix.loadFromData(data)
        if pix.isNull():
            pybreeze_logger.debug("Fetched image is not an image: %s", source)
            return
        self._pixmap_cache[source] = pix
        for image in self.get_all_images():
            if image.source() == source:
                image.set_pixmap(pix, source)

    @staticmethod
    def _on_image_download_failed(source: str, message: str) -> None:
        pybreeze_logger.debug("safe_download_image failed for %s: %s", source, message)

    def stop_image_downloads(self) -> None:
        """Wait for every fetch still going, with its signals blocked.

        Called when the editor closes: a running QThread destroyed with the
        scene aborts the process, and a late signal would reach a dead scene.
        """
        for thread in tuple(self._image_downloads.values()):
            thread.blockSignals(True)
            thread.wait()
        self._image_downloads.clear()

    def load_from_dict(self, data: dict) -> None:
        """Replace what is on the canvas with *data*.

        The canvas is cleared only once *data* is known to be a diagram: the
        editor saves back to the file it opened last, so a load that emptied the
        canvas half-way would be written over the user's own file by the next
        save.

        :param data: a diagram, as :meth:`to_dict` writes it
        :raises ValueError: when *data* is not a diagram; nothing is cleared then
        """
        self._check_is_a_diagram(data)
        self._clear_items()
        self._load_items(data)
        self.undo_stack.clear()
        self.item_count_changed.emit()
