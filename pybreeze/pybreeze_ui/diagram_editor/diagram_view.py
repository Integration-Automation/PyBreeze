from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsView

from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import DiagramScene

_ZOOM_FACTOR = 1.15
_MIN_SCALE = 0.1
_MAX_SCALE = 5.0
_GRID_COLOR = QColor("#e0e0e0")
_GRID_COLOR_MAJOR = QColor("#bdbdbd")
_BG_COLOR = QColor("#ffffff")


class DiagramView(QGraphicsView):
    """Pannable, zoomable view with performance optimisations.

    - MinimalViewportUpdate: only repaint dirty regions
    - CacheBackground: grid painted once, blitted on scroll
    - DontAdjustForAntialiasing: skip bounding-rect inflation
    - Item-level DeviceCoordinateCache (set on each item)
    - BSP tree index on the scene for O(log n) spatial queries
    """

    zoom_changed = Signal(int)  # percentage

    def __init__(self, scene: DiagramScene, parent=None):
        super().__init__(scene, parent)

        # --- Background ---
        self.setBackgroundBrush(QBrush(_BG_COLOR))

        # --- Render hints ---
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
            | QPainter.RenderHint.TextAntialiasing
        )

        # --- Performance ---
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)
        self.setOptimizationFlags(
            QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing
        )
        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)

        # --- Interaction ---
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self._panning = False
        self._pan_start = None
        self._draw_grid = False
        self._grid_size = 20

    # --- grid ---

    @property
    def draw_grid(self) -> bool:
        return self._draw_grid

    @draw_grid.setter
    def draw_grid(self, value: bool) -> None:
        self._draw_grid = value
        self.resetCachedContent()
        self.viewport().update()

    @property
    def grid_size(self) -> int:
        return self._grid_size

    @grid_size.setter
    def grid_size(self, value: int) -> None:
        self._grid_size = max(5, value)
        if self._draw_grid:
            self.resetCachedContent()
            self.viewport().update()

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        # Fill background explicitly (required for OpenGL viewport)
        painter.fillRect(rect, _BG_COLOR)

        if not self._draw_grid:
            return

        gs = self._grid_size
        left = int(rect.left()) - (int(rect.left()) % gs)
        top = int(rect.top()) - (int(rect.top()) % gs)

        # Minor grid
        painter.setPen(QPen(_GRID_COLOR, 0.5))
        x = left
        while x <= rect.right():
            painter.drawLine(int(x), int(rect.top()), int(x), int(rect.bottom()))
            x += gs
        y = top
        while y <= rect.bottom():
            painter.drawLine(int(rect.left()), int(y), int(rect.right()), int(y))
            y += gs

        # Major grid (every 5 cells)
        major = gs * 5
        painter.setPen(QPen(_GRID_COLOR_MAJOR, 1))
        left_major = int(rect.left()) - (int(rect.left()) % major)
        top_major = int(rect.top()) - (int(rect.top()) % major)
        x = left_major
        while x <= rect.right():
            painter.drawLine(int(x), int(rect.top()), int(x), int(rect.bottom()))
            x += major
        y = top_major
        while y <= rect.bottom():
            painter.drawLine(int(rect.left()), int(y), int(rect.right()), int(y))
            y += major

    # --- zoom ---

    def wheelEvent(self, event) -> None:
        factor = _ZOOM_FACTOR if event.angleDelta().y() > 0 else 1.0 / _ZOOM_FACTOR
        current = self.transform().m11()
        if current * factor < _MIN_SCALE or current * factor > _MAX_SCALE:
            return
        self.scale(factor, factor)
        self.zoom_changed.emit(int(self.transform().m11() * 100))

    def set_zoom(self, percent: int) -> None:
        factor = percent / 100.0
        factor = max(_MIN_SCALE, min(factor, _MAX_SCALE))
        self.resetTransform()
        self.scale(factor, factor)
        self.zoom_changed.emit(int(factor * 100))

    def zoom_in(self) -> None:
        current = self.transform().m11()
        if current * _ZOOM_FACTOR <= _MAX_SCALE:
            self.scale(_ZOOM_FACTOR, _ZOOM_FACTOR)
            self.zoom_changed.emit(int(self.transform().m11() * 100))

    def zoom_out(self) -> None:
        current = self.transform().m11()
        if current / _ZOOM_FACTOR >= _MIN_SCALE:
            self.scale(1.0 / _ZOOM_FACTOR, 1.0 / _ZOOM_FACTOR)
            self.zoom_changed.emit(int(self.transform().m11() * 100))

    # --- middle-button / right-button pan ---

    def mousePressEvent(self, event) -> None:
        if event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            self._panning = True
            self._pan_start = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._panning and self._pan_start is not None:
            delta = event.position().toPoint() - self._pan_start
            self._pan_start = event.position().toPoint()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton) and self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)
