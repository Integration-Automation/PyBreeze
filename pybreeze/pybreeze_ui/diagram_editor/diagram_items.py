from __future__ import annotations

import math
from enum import Enum, auto

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsTextItem,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class NodeShape(Enum):
    RECTANGLE = auto()
    ROUNDED_RECT = auto()
    ELLIPSE = auto()
    DIAMOND = auto()


class ConnectionStyle(Enum):
    SOLID = auto()
    DASHED = auto()
    DOTTED = auto()


_STYLE_TO_PEN_STYLE: dict[ConnectionStyle, Qt.PenStyle] = {
    ConnectionStyle.SOLID: Qt.PenStyle.SolidLine,
    ConnectionStyle.DASHED: Qt.PenStyle.DashLine,
    ConnectionStyle.DOTTED: Qt.PenStyle.DotLine,
}

# ---------------------------------------------------------------------------
# Strategy: shape rendering delegated to QGraphicsItem subclasses
# ---------------------------------------------------------------------------


class _RectBody(QGraphicsRectItem):
    def __init__(self, w: float, h: float):
        super().__init__(0, 0, w, h)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)


class _RoundedRectBody(QGraphicsRectItem):
    RADIUS = 10.0

    def __init__(self, w: float, h: float):
        super().__init__(0, 0, w, h)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawRoundedRect(self.rect(), self.RADIUS, self.RADIUS)


class _EllipseBody(QGraphicsEllipseItem):
    def __init__(self, w: float, h: float):
        super().__init__(0, 0, w, h)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)


class _DiamondBody(QGraphicsPolygonItem):
    def __init__(self, w: float, h: float):
        poly = QPolygonF([
            QPointF(w / 2, 0),
            QPointF(w, h / 2),
            QPointF(w / 2, h),
            QPointF(0, h / 2),
        ])
        super().__init__(poly)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)


_SHAPE_FACTORY: dict[NodeShape, type] = {
    NodeShape.RECTANGLE: _RectBody,
    NodeShape.ROUNDED_RECT: _RoundedRectBody,
    NodeShape.ELLIPSE: _EllipseBody,
    NodeShape.DIAMOND: _DiamondBody,
}

# ---------------------------------------------------------------------------
# Visual constants
# ---------------------------------------------------------------------------

_DEFAULT_NODE_W = 140.0
_DEFAULT_NODE_H = 60.0
_NODE_PEN_COLOR = "#455a64"
_NODE_BRUSH_COLOR = "#e3f2fd"
_NODE_SELECTED_COLOR = "#1565c0"
_LABEL_FONT_FAMILY = "Segoe UI"
_LABEL_FONT_SIZE = 10
_CONNECTION_COLOR = "#37474f"
_CONNECTION_WIDTH = 2.0
_ARROW_SIZE = 10.0
_HANDLE_SIZE = 8.0


# ---------------------------------------------------------------------------
# Editable label — only enters edit mode on double-click
# ---------------------------------------------------------------------------

class _EditableLabel(QGraphicsTextItem):
    """Label that is read-only by default; double-click to edit, focus-out to commit."""

    def focusOutEvent(self, event) -> None:
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        tc = self.textCursor()
        tc.clearSelection()
        self.setTextCursor(tc)
        parent = self.parentItem()
        if parent is not None and hasattr(parent, "_center_label"):
            parent._center_label()
        super().focusOutEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mouseDoubleClickEvent(event)


# ---------------------------------------------------------------------------
# Resize handles
# ---------------------------------------------------------------------------

_HANDLE_CURSORS: dict[str, Qt.CursorShape] = {
    "tl": Qt.CursorShape.SizeFDiagCursor,
    "tr": Qt.CursorShape.SizeBDiagCursor,
    "bl": Qt.CursorShape.SizeBDiagCursor,
    "br": Qt.CursorShape.SizeFDiagCursor,
}


class ResizeHandle(QGraphicsRectItem):
    """Draggable corner handle for node resizing."""

    def __init__(self, role: str, parent_node: DiagramNode):
        hs = _HANDLE_SIZE
        super().__init__(-hs / 2, -hs / 2, hs, hs, parent_node)
        self.role = role
        self._parent_node = parent_node
        self.setBrush(QBrush(QColor(_NODE_SELECTED_COLOR)))
        self.setPen(QPen(QColor("#0d47a1"), 1))
        self.setCursor(_HANDLE_CURSORS.get(role, Qt.CursorShape.SizeAllCursor))
        self.setAcceptHoverEvents(True)
        self.setVisible(False)
        self.setZValue(100)
        self._drag_start: QPointF | None = None
        self._orig_rect: QRectF | None = None
        self._orig_pos: QPointF | None = None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.scenePos()
            self._orig_rect = QRectF(0, 0, self._parent_node.node_w, self._parent_node.node_h)
            self._orig_pos = QPointF(self._parent_node.pos())
            self._parent_node._resizing = True
            scene = self.scene()
            if scene and hasattr(scene, "begin_undo"):
                scene.begin_undo("Resize")
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is None:
            return
        delta = event.scenePos() - self._drag_start
        self._parent_node._apply_resize(self.role, delta, self._orig_rect, self._orig_pos)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._drag_start is not None:
            self._drag_start = None
            self._parent_node._resizing = False
            scene = self.scene()
            if scene and hasattr(scene, "end_undo"):
                scene.end_undo()
            event.accept()
        else:
            super().mouseReleaseEvent(event)


# ---------------------------------------------------------------------------
# DiagramNode
# ---------------------------------------------------------------------------

class DiagramNode(QGraphicsRectItem):
    """Composite node: invisible bounding rect holds a shape body + centred label + resize handles."""

    # Class-level grid config (set by DiagramScene)
    grid_enabled: bool = False
    grid_size: int = 20

    def __init__(
        self,
        x: float = 0,
        y: float = 0,
        w: float = _DEFAULT_NODE_W,
        h: float = _DEFAULT_NODE_H,
        text: str = "Node",
        shape: NodeShape = NodeShape.RECTANGLE,
        fill_color: str | None = None,
        border_color: str | None = None,
        font_size: int = _LABEL_FONT_SIZE,
    ):
        super().__init__(0, 0, w, h)
        self.setPen(QPen(Qt.PenStyle.NoPen))
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.setPos(x, y)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.node_w = w
        self.node_h = h
        self.shape_type = shape
        self.connections: list[DiagramConnection] = []
        self._resizing = False

        # Colors
        self._fill_color = QColor(fill_color) if fill_color else QColor(_NODE_BRUSH_COLOR)
        self._border_color = QColor(border_color) if border_color else QColor(_NODE_PEN_COLOR)
        self._font_size = font_size

        # Shape body (child)
        self.body: QGraphicsItem = self._make_body(w, h)

        # Label (child) — read-only by default; double-click to edit
        self.label = _EditableLabel(text, self)
        self.label.setFont(QFont(_LABEL_FONT_FAMILY, self._font_size))
        self.label.setDefaultTextColor(QColor("#212121"))
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self._center_label()

        # Resize handles (children)
        self._handles: dict[str, ResizeHandle] = {}
        for role in ("tl", "tr", "bl", "br"):
            self._handles[role] = ResizeHandle(role, self)
        self._update_handles()

    # --- body factory ---

    def _make_body(self, w: float, h: float) -> QGraphicsItem:
        body_cls = _SHAPE_FACTORY[self.shape_type]
        body = body_cls(w, h)
        body.setParentItem(self)
        body.setPen(QPen(self._border_color, 2))
        body.setBrush(QBrush(self._fill_color))
        return body

    def _rebuild_body(self) -> None:
        if self.body.scene():
            self.body.scene().removeItem(self.body)
        else:
            self.body.setParentItem(None)
        self.body = self._make_body(self.node_w, self.node_h)

    # --- size / geometry ---

    def set_size(self, w: float, h: float) -> None:
        w = max(40.0, w)
        h = max(20.0, h)
        self.prepareGeometryChange()
        self.node_w = w
        self.node_h = h
        self.setRect(0, 0, w, h)
        self._rebuild_body()
        self._center_label()
        self._update_handles()
        for conn in self.connections:
            conn.update_path()

    def _apply_resize(self, role: str, delta: QPointF, orig_rect: QRectF, orig_pos: QPointF) -> None:
        new_w = orig_rect.width()
        new_h = orig_rect.height()
        new_x = orig_pos.x()
        new_y = orig_pos.y()

        if "r" in role:
            new_w = orig_rect.width() + delta.x()
        if "l" in role:
            new_w = orig_rect.width() - delta.x()
            new_x = orig_pos.x() + delta.x()
        if "b" in role:
            new_h = orig_rect.height() + delta.y()
        if "t" in role:
            new_h = orig_rect.height() - delta.y()
            new_y = orig_pos.y() + delta.y()

        # Clamp minimum
        if new_w < 40:
            if "l" in role:
                new_x = orig_pos.x() + orig_rect.width() - 40
            new_w = 40
        if new_h < 20:
            if "t" in role:
                new_y = orig_pos.y() + orig_rect.height() - 20
            new_h = 20

        self.setPos(new_x, new_y)
        self.prepareGeometryChange()
        self.node_w = new_w
        self.node_h = new_h
        self.setRect(0, 0, new_w, new_h)
        self._rebuild_body()
        self._center_label()
        self._update_handles()
        for conn in self.connections:
            conn.update_path()

    def _center_label(self) -> None:
        br = self.label.boundingRect()
        self.label.setPos(
            (self.node_w - br.width()) / 2,
            (self.node_h - br.height()) / 2,
        )

    def _update_handles(self) -> None:
        positions = {
            "tl": QPointF(0, 0),
            "tr": QPointF(self.node_w, 0),
            "bl": QPointF(0, self.node_h),
            "br": QPointF(self.node_w, self.node_h),
        }
        for role, handle in self._handles.items():
            handle.setPos(positions[role])

    def _show_handles(self, visible: bool) -> None:
        for h in self._handles.values():
            h.setVisible(visible)

    # --- geometry helpers ---

    def center_pos(self) -> QPointF:
        return self.pos() + QPointF(self.node_w / 2, self.node_h / 2)

    def edge_point(self, target: QPointF) -> QPointF:
        """Return the intersection of the line from center→target with the node boundary."""
        center = self.center_pos()
        dx = target.x() - center.x()
        dy = target.y() - center.y()
        if dx == 0 and dy == 0:
            return center

        hw, hh = self.node_w / 2, self.node_h / 2

        if self.shape_type == NodeShape.ELLIPSE:
            angle = math.atan2(dy, dx)
            return center + QPointF(hw * math.cos(angle), hh * math.sin(angle))

        if self.shape_type == NodeShape.DIAMOND:
            denom = abs(dx) / hw + abs(dy) / hh
            if denom < 1e-9:
                return center
            scale = 1.0 / denom
            return center + QPointF(dx * scale, dy * scale)

        # Rectangle / Rounded Rect
        adx, ady = abs(dx), abs(dy)
        if adx < 1e-9:
            return center + QPointF(0, hh if dy > 0 else -hh)
        if ady < 1e-9:
            return center + QPointF(hw if dx > 0 else -hw, 0)
        if adx * hh > ady * hw:
            scale = hw / adx
        else:
            scale = hh / ady
        return center + QPointF(dx * scale, dy * scale)

    # --- text ---

    def text(self) -> str:
        return self.label.toPlainText()

    def set_text(self, text: str) -> None:
        self.label.setPlainText(text)
        self._center_label()

    # --- style setters ---

    def set_fill_color(self, color: QColor) -> None:
        self._fill_color = color
        self.body.setBrush(QBrush(color))

    def set_border_color(self, color: QColor) -> None:
        self._border_color = color
        self.body.setPen(QPen(color, 2))

    def set_font_size(self, size: int) -> None:
        self._font_size = max(6, min(size, 48))
        self.label.setFont(QFont(_LABEL_FONT_FAMILY, self._font_size))
        self._center_label()

    def set_shape(self, shape: NodeShape) -> None:
        if shape == self.shape_type:
            return
        self.shape_type = shape
        self._rebuild_body()
        self._center_label()

    # --- overrides ---

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            if DiagramNode.grid_enabled and not self._resizing:
                gs = DiagramNode.grid_size
                if gs > 0:
                    x = round(value.x() / gs) * gs
                    y = round(value.y() / gs) * gs
                    return QPointF(x, y)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for conn in self.connections:
                conn.update_path()
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            selected = self.isSelected()
            pen = QPen(QColor(_NODE_SELECTED_COLOR), 2.5) if selected else QPen(self._border_color, 2)
            self.body.setPen(pen)
            self._show_handles(selected)
        return super().itemChange(change, value)

    # --- serialisation ---

    def to_dict(self, node_id: int) -> dict:
        return {
            "id": node_id,
            "x": self.pos().x(),
            "y": self.pos().y(),
            "w": self.node_w,
            "h": self.node_h,
            "text": self.text(),
            "shape": self.shape_type.name,
            "fill_color": self._fill_color.name(),
            "border_color": self._border_color.name(),
            "font_size": self._font_size,
        }

    @classmethod
    def from_dict(cls, data: dict) -> DiagramNode:
        return cls(
            x=data["x"],
            y=data["y"],
            w=data.get("w", _DEFAULT_NODE_W),
            h=data.get("h", _DEFAULT_NODE_H),
            text=data.get("text", "Node"),
            shape=NodeShape[data.get("shape", "RECTANGLE")],
            fill_color=data.get("fill_color", data.get("color")),
            border_color=data.get("border_color"),
            font_size=data.get("font_size", _LABEL_FONT_SIZE),
        )


# ---------------------------------------------------------------------------
# DiagramConnection
# ---------------------------------------------------------------------------

class DiagramConnection(QGraphicsPathItem):
    """Directed edge drawn as a cubic bezier with arrowhead, connecting node borders."""

    def __init__(
        self,
        source: DiagramNode,
        target: DiagramNode,
        label: str = "",
        line_color: str | None = None,
        line_width: float = _CONNECTION_WIDTH,
        style: ConnectionStyle = ConnectionStyle.SOLID,
    ):
        super().__init__()
        self.source = source
        self.target = target
        self._line_color = QColor(line_color) if line_color else QColor(_CONNECTION_COLOR)
        self._line_width = line_width
        self._style = style
        self._apply_pen()
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        self.setZValue(-1)

        source.connections.append(self)
        target.connections.append(self)

        self._label_item: QGraphicsTextItem | None = None
        if label:
            self._create_label(label)

        self.update_path()

    def _apply_pen(self) -> None:
        pen = QPen(self._line_color, self._line_width)
        pen.setStyle(_STYLE_TO_PEN_STYLE.get(self._style, Qt.PenStyle.SolidLine))
        self.setPen(pen)

    def _create_label(self, text: str) -> None:
        self._label_item = _EditableLabel(text, self)
        self._label_item.setFont(QFont(_LABEL_FONT_FAMILY, 8))
        self._label_item.setDefaultTextColor(QColor("#616161"))
        self._label_item.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

    # --- style setters ---

    def set_line_color(self, color: QColor) -> None:
        self._line_color = color
        self._apply_pen()

    def set_line_width(self, width: float) -> None:
        self._line_width = max(0.5, min(width, 10.0))
        self._apply_pen()

    def set_style(self, style: ConnectionStyle) -> None:
        self._style = style
        self._apply_pen()

    def edge_label(self) -> str:
        return self._label_item.toPlainText() if self._label_item else ""

    def set_edge_label(self, text: str) -> None:
        if text and self._label_item is None:
            self._create_label(text)
        elif self._label_item is not None:
            self._label_item.setPlainText(text)
        self.update_path()

    # --- path calculation with edge intersection ---

    def update_path(self) -> None:
        sc = self.source.center_pos()
        tc = self.target.center_pos()
        sp = self.source.edge_point(tc)
        tp = self.target.edge_point(sc)

        dx = tp.x() - sp.x()
        dy = tp.y() - sp.y()
        dist = math.hypot(dx, dy)
        offset = min(dist * 0.3, 60.0) if dist > 1e-3 else 0

        # Control points: orient along dominant axis
        if abs(dx) >= abs(dy):
            sign = 1 if dx >= 0 else -1
            c1 = QPointF(sp.x() + offset * sign, sp.y())
            c2 = QPointF(tp.x() - offset * sign, tp.y())
        else:
            sign = 1 if dy >= 0 else -1
            c1 = QPointF(sp.x(), sp.y() + offset * sign)
            c2 = QPointF(tp.x(), tp.y() - offset * sign)

        path = QPainterPath(sp)
        path.cubicTo(c1, c2, tp)

        # Arrowhead
        arrow_ref = c2 if dist > 1e-3 else sc
        angle = math.atan2(tp.y() - arrow_ref.y(), tp.x() - arrow_ref.x())
        p1 = tp - QPointF(
            math.cos(angle - math.pi / 6) * _ARROW_SIZE,
            math.sin(angle - math.pi / 6) * _ARROW_SIZE,
        )
        p2 = tp - QPointF(
            math.cos(angle + math.pi / 6) * _ARROW_SIZE,
            math.sin(angle + math.pi / 6) * _ARROW_SIZE,
        )
        path.moveTo(tp)
        path.lineTo(p1)
        path.moveTo(tp)
        path.lineTo(p2)

        self.setPath(path)

        # Edge label at midpoint
        if self._label_item is not None:
            mid = QPointF((sp.x() + tp.x()) / 2, (sp.y() + tp.y()) / 2)
            br = self._label_item.boundingRect()
            self._label_item.setPos(mid.x() - br.width() / 2, mid.y() - br.height() - 4)

    # --- overrides ---

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            color = QColor(_NODE_SELECTED_COLOR) if self.isSelected() else self._line_color
            pen = QPen(color, self._line_width + (0.5 if self.isSelected() else 0))
            pen.setStyle(_STYLE_TO_PEN_STYLE.get(self._style, Qt.PenStyle.SolidLine))
            self.setPen(pen)
        return super().itemChange(change, value)

    def detach(self) -> None:
        if self in self.source.connections:
            self.source.connections.remove(self)
        if self in self.target.connections:
            self.target.connections.remove(self)

    # --- serialisation ---

    def to_dict(self, node_map: dict[DiagramNode, int]) -> dict:
        return {
            "source": node_map[self.source],
            "target": node_map[self.target],
            "label": self.edge_label(),
            "line_color": self._line_color.name(),
            "line_width": self._line_width,
            "style": self._style.name,
        }


# ---------------------------------------------------------------------------
# DiagramImage — draggable image on the canvas
# ---------------------------------------------------------------------------

_IMG_BORDER_PEN = QPen(QColor("#90a4ae"), 1)
_IMG_SELECTED_PEN = QPen(QColor(_NODE_SELECTED_COLOR), 2)


class DiagramImage(QGraphicsRectItem):
    """A movable, resizable image item.

    Stores the *source* (local path or URL string) so the diagram can be
    saved and reloaded.  The actual pixel data is held in a child
    ``QGraphicsPixmapItem``.
    """

    grid_enabled: bool = False
    grid_size: int = 20

    def __init__(
        self,
        x: float = 0,
        y: float = 0,
        w: float = 200,
        h: float = 200,
        source: str = "",
        pixmap: QPixmap | None = None,
    ):
        super().__init__(0, 0, w, h)
        self.setPen(_IMG_BORDER_PEN)
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.setPos(x, y)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.img_w = w
        self.img_h = h
        self._source = source
        self._resizing = False

        # Optional caption
        self.label = _EditableLabel("", self)
        self.label.setFont(QFont(_LABEL_FONT_FAMILY, 9))
        self.label.setDefaultTextColor(QColor("#424242"))
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

        # Pixmap child — cached for GPU compositing
        self._pix_item = QGraphicsPixmapItem(self)
        self._pix_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self._pix_item.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        if pixmap and not pixmap.isNull():
            self._apply_pixmap(pixmap)

        # Resize handles
        self._handles: dict[str, ResizeHandle] = {}
        for role in ("tl", "tr", "bl", "br"):
            self._handles[role] = ResizeHandle(role, self)
        self._update_handles()
        self.connections: list[DiagramConnection] = []

    # --- pixmap ---

    def _apply_pixmap(self, pixmap: QPixmap) -> None:
        scaled = pixmap.scaled(
            int(self.img_w), int(self.img_h),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._pix_item.setPixmap(scaled)
        # Centre pixmap inside bounding rect
        self._pix_item.setPos(
            (self.img_w - scaled.width()) / 2,
            (self.img_h - scaled.height()) / 2,
        )

    def set_pixmap(self, pixmap: QPixmap, source: str = "") -> None:
        if source:
            self._source = source
        if pixmap.isNull():
            return
        self._apply_pixmap(pixmap)

    def source(self) -> str:
        return self._source

    # --- geometry ---

    def center_pos(self) -> QPointF:
        return self.pos() + QPointF(self.img_w / 2, self.img_h / 2)

    def set_size(self, w: float, h: float) -> None:
        w, h = max(40.0, w), max(40.0, h)
        self.prepareGeometryChange()
        self.img_w, self.img_h = w, h
        self.setRect(0, 0, w, h)
        pix = self._pix_item.pixmap()
        if pix and not pix.isNull():
            self._apply_pixmap(QPixmap(pix))
        self._center_label()
        self._update_handles()

    def _apply_resize(self, role, delta, orig_rect, orig_pos):
        new_w, new_h = orig_rect.width(), orig_rect.height()
        new_x, new_y = orig_pos.x(), orig_pos.y()
        if "r" in role:
            new_w = orig_rect.width() + delta.x()
        if "l" in role:
            new_w = orig_rect.width() - delta.x()
            new_x = orig_pos.x() + delta.x()
        if "b" in role:
            new_h = orig_rect.height() + delta.y()
        if "t" in role:
            new_h = orig_rect.height() - delta.y()
            new_y = orig_pos.y() + delta.y()
        if new_w < 40:
            if "l" in role:
                new_x = orig_pos.x() + orig_rect.width() - 40
            new_w = 40
        if new_h < 40:
            if "t" in role:
                new_y = orig_pos.y() + orig_rect.height() - 40
            new_h = 40
        self.setPos(new_x, new_y)
        self.set_size(new_w, new_h)

    def _center_label(self) -> None:
        br = self.label.boundingRect()
        self.label.setPos(
            (self.img_w - br.width()) / 2,
            self.img_h + 2,
        )

    def _update_handles(self) -> None:
        positions = {
            "tl": QPointF(0, 0), "tr": QPointF(self.img_w, 0),
            "bl": QPointF(0, self.img_h), "br": QPointF(self.img_w, self.img_h),
        }
        for role, h in self._handles.items():
            h.setPos(positions[role])

    def _show_handles(self, visible: bool) -> None:
        for h in self._handles.values():
            h.setVisible(visible)

    def text(self) -> str:
        return self.label.toPlainText()

    def set_text(self, text: str) -> None:
        self.label.setPlainText(text)
        self._center_label()

    # --- overrides ---

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            if DiagramImage.grid_enabled and not self._resizing:
                gs = DiagramImage.grid_size
                if gs > 0:
                    return QPointF(round(value.x() / gs) * gs, round(value.y() / gs) * gs)
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.setPen(_IMG_SELECTED_PEN if self.isSelected() else _IMG_BORDER_PEN)
            self._show_handles(self.isSelected())
        return super().itemChange(change, value)

    # --- serialisation ---

    def to_dict(self, img_id: int) -> dict:
        return {
            "id": img_id,
            "x": self.pos().x(),
            "y": self.pos().y(),
            "w": self.img_w,
            "h": self.img_h,
            "source": self._source,
            "caption": self.text(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> DiagramImage:
        img = cls(
            x=data["x"], y=data["y"],
            w=data.get("w", 200), h=data.get("h", 200),
            source=data.get("source", ""),
        )
        caption = data.get("caption", "")
        if caption:
            img.set_text(caption)
        return img
