from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.diagram_editor.diagram_items import (
    ConnectionStyle,
    DiagramConnection,
    DiagramImage,
    DiagramNode,
    NodeShape,
)

if TYPE_CHECKING:
    from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import DiagramScene


def _lang(key: str, fallback: str = "") -> str:
    return language_wrapper.language_word_dict.get(key, fallback or key)


# ---------------------------------------------------------------------------
# Color picker button
# ---------------------------------------------------------------------------

class ColorButton(QPushButton):
    color_changed = Signal(QColor)

    def __init__(self, color: QColor = QColor("#e3f2fd"), parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedHeight(24)
        self.setMinimumWidth(60)
        self._update_style()
        self.clicked.connect(self._pick)

    def _update_style(self) -> None:
        # Choose text color based on background brightness
        luma = self._color.red() * 0.299 + self._color.green() * 0.587 + self._color.blue() * 0.114
        text_color = "#000000" if luma > 128 else "#ffffff"
        self.setStyleSheet(
            f"background-color: {self._color.name()}; color: {text_color};"
            f" border: 1px solid #888; border-radius: 3px;"
        )
        self.setText(self._color.name())

    def _pick(self) -> None:
        color = QColorDialog.getColor(self._color, self.window())
        if color.isValid():
            self._color = color
            self._update_style()
            self.color_changed.emit(color)

    def color(self) -> QColor:
        return self._color

    def set_color(self, color: QColor) -> None:
        self._color = color
        self._update_style()


# ---------------------------------------------------------------------------
# Property panel
# ---------------------------------------------------------------------------

_SHAPE_ITEMS: list[tuple[str, NodeShape]] = [
    ("diagram_editor_shape_rectangle", NodeShape.RECTANGLE),
    ("diagram_editor_shape_rounded_rect", NodeShape.ROUNDED_RECT),
    ("diagram_editor_shape_ellipse", NodeShape.ELLIPSE),
    ("diagram_editor_shape_diamond", NodeShape.DIAMOND),
]

_STYLE_ITEMS: list[tuple[str, ConnectionStyle]] = [
    ("diagram_editor_style_solid", ConnectionStyle.SOLID),
    ("diagram_editor_style_dashed", ConnectionStyle.DASHED),
    ("diagram_editor_style_dotted", ConnectionStyle.DOTTED),
]


class DiagramPropertyPanel(QWidget):
    """Sidebar panel showing properties of the selected diagram item."""

    def __init__(self, scene: DiagramScene, parent=None):
        super().__init__(parent)
        self._scene = scene
        self._updating = False  # guard against feedback loops
        self._current_node: DiagramNode | None = None
        self._current_conn: DiagramConnection | None = None
        self._current_img: DiagramImage | None = None
        self.setMinimumWidth(240)
        self.setMaximumWidth(320)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(8)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- Title ---
        self._title = QLabel(_lang("diagram_editor_prop_title", "Properties"))
        self._title.setStyleSheet("font-weight: bold; font-size: 13px; padding: 4px 0px;")
        self._layout.addWidget(self._title)

        # --- No selection label ---
        self._no_sel_label = QLabel(_lang("diagram_editor_prop_no_selection", "No selection"))
        self._no_sel_label.setContentsMargins(0, 8, 0, 0)
        self._layout.addWidget(self._no_sel_label)

        # --- Node group ---
        self._node_group = QGroupBox(_lang("diagram_editor_prop_node_group", "Node"))
        nf = QFormLayout()
        nf.setContentsMargins(8, 12, 8, 8)
        nf.setVerticalSpacing(8)
        nf.setHorizontalSpacing(10)
        self._node_text = QLineEdit()
        self._node_text.editingFinished.connect(self._on_node_text)
        nf.addRow(_lang("diagram_editor_prop_text", "Text"), self._node_text)

        self._node_w = QSpinBox()
        self._node_w.setRange(40, 800)
        self._node_w.valueChanged.connect(self._on_node_size)
        nf.addRow(_lang("diagram_editor_prop_width", "Width"), self._node_w)

        self._node_h = QSpinBox()
        self._node_h.setRange(20, 600)
        self._node_h.valueChanged.connect(self._on_node_size)
        nf.addRow(_lang("diagram_editor_prop_height", "Height"), self._node_h)

        self._node_shape = QComboBox()
        for lang_key, _ in _SHAPE_ITEMS:
            self._node_shape.addItem(_lang(lang_key, lang_key))
        self._node_shape.currentIndexChanged.connect(self._on_node_shape)
        nf.addRow(_lang("diagram_editor_prop_shape", "Shape"), self._node_shape)

        self._node_fill = ColorButton()
        self._node_fill.color_changed.connect(self._on_node_fill)
        nf.addRow(_lang("diagram_editor_prop_fill_color", "Fill"), self._node_fill)

        self._node_border = ColorButton(QColor("#455a64"))
        self._node_border.color_changed.connect(self._on_node_border)
        nf.addRow(_lang("diagram_editor_prop_border_color", "Border"), self._node_border)

        self._node_font = QSpinBox()
        self._node_font.setRange(6, 48)
        self._node_font.valueChanged.connect(self._on_node_font)
        nf.addRow(_lang("diagram_editor_prop_font_size", "Font"), self._node_font)

        self._node_group.setLayout(nf)
        self._layout.addWidget(self._node_group)
        self._node_group.hide()

        # --- Connection group ---
        self._conn_group = QGroupBox(_lang("diagram_editor_prop_conn_group", "Connection"))
        cf = QFormLayout()
        cf.setContentsMargins(8, 12, 8, 8)
        cf.setVerticalSpacing(8)
        cf.setHorizontalSpacing(10)
        self._conn_label = QLineEdit()
        self._conn_label.editingFinished.connect(self._on_conn_label)
        cf.addRow(_lang("diagram_editor_prop_label", "Label"), self._conn_label)

        self._conn_style = QComboBox()
        for lang_key, _ in _STYLE_ITEMS:
            self._conn_style.addItem(_lang(lang_key, lang_key))
        self._conn_style.currentIndexChanged.connect(self._on_conn_style)
        cf.addRow(_lang("diagram_editor_prop_line_style", "Style"), self._conn_style)

        self._conn_color = ColorButton(QColor("#37474f"))
        self._conn_color.color_changed.connect(self._on_conn_color)
        cf.addRow(_lang("diagram_editor_prop_line_color", "Color"), self._conn_color)

        self._conn_width = QDoubleSpinBox()
        self._conn_width.setRange(0.5, 10.0)
        self._conn_width.setSingleStep(0.5)
        self._conn_width.valueChanged.connect(self._on_conn_width)
        cf.addRow(_lang("diagram_editor_prop_line_width", "Width"), self._conn_width)

        self._conn_group.setLayout(cf)
        self._layout.addWidget(self._conn_group)
        self._conn_group.hide()

        # --- Image group ---
        self._img_group = QGroupBox(_lang("diagram_editor_prop_img_group", "Image"))
        imf = QFormLayout()
        imf.setContentsMargins(8, 12, 8, 8)
        imf.setVerticalSpacing(8)
        imf.setHorizontalSpacing(10)

        self._img_caption = QLineEdit()
        self._img_caption.editingFinished.connect(self._on_img_caption)
        imf.addRow(_lang("diagram_editor_prop_caption", "Caption"), self._img_caption)

        self._img_source = QLineEdit()
        self._img_source.setReadOnly(True)
        imf.addRow(_lang("diagram_editor_prop_source", "Source"), self._img_source)

        self._img_w = QSpinBox()
        self._img_w.setRange(40, 2000)
        self._img_w.valueChanged.connect(self._on_img_size)
        imf.addRow(_lang("diagram_editor_prop_width", "Width"), self._img_w)

        self._img_h = QSpinBox()
        self._img_h.setRange(40, 2000)
        self._img_h.valueChanged.connect(self._on_img_size)
        imf.addRow(_lang("diagram_editor_prop_height", "Height"), self._img_h)

        self._img_group.setLayout(imf)
        self._layout.addWidget(self._img_group)
        self._img_group.hide()

        self._layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll)

        # Connect to scene
        self._scene.selectionChanged.connect(self._on_selection_changed)

    # ------------------------------------------------------------------
    # Selection handling
    # ------------------------------------------------------------------

    def _on_selection_changed(self) -> None:
        self._updating = True
        self._current_node = None
        self._current_conn = None
        self._current_img = None
        selected = self._scene.selectedItems()

        nodes = [i for i in selected if isinstance(i, DiagramNode)]
        conns = [i for i in selected if isinstance(i, DiagramConnection)]
        imgs = [i for i in selected if isinstance(i, DiagramImage)]

        if len(nodes) == 1 and len(conns) == 0 and len(imgs) == 0:
            self._show_node(nodes[0])
        elif len(conns) == 1 and len(nodes) == 0 and len(imgs) == 0:
            self._show_connection(conns[0])
        elif len(imgs) == 1 and len(nodes) == 0 and len(conns) == 0:
            self._show_image(imgs[0])
        else:
            self._show_none()
        self._updating = False

    def _show_none(self) -> None:
        self._no_sel_label.show()
        self._node_group.hide()
        self._conn_group.hide()
        self._img_group.hide()

    def _show_node(self, node: DiagramNode) -> None:
        self._current_node = node
        self._no_sel_label.hide()
        self._node_group.show()
        self._conn_group.hide()
        self._img_group.hide()

        self._node_text.setText(node.text())
        self._node_w.setValue(int(node.node_w))
        self._node_h.setValue(int(node.node_h))
        # Find shape index
        for idx, (_, shape) in enumerate(_SHAPE_ITEMS):
            if shape == node.shape_type:
                self._node_shape.setCurrentIndex(idx)
                break
        self._node_fill.set_color(node._fill_color)
        self._node_border.set_color(node._border_color)
        self._node_font.setValue(node._font_size)

    def _show_connection(self, conn: DiagramConnection) -> None:
        self._current_conn = conn
        self._no_sel_label.hide()
        self._node_group.hide()
        self._conn_group.show()
        self._img_group.hide()

        self._conn_label.setText(conn.edge_label())
        for idx, (_, style) in enumerate(_STYLE_ITEMS):
            if style == conn._style:
                self._conn_style.setCurrentIndex(idx)
                break
        self._conn_color.set_color(conn._line_color)
        self._conn_width.setValue(conn._line_width)

    # ------------------------------------------------------------------
    # Node property handlers
    # ------------------------------------------------------------------

    def _on_node_text(self) -> None:
        if self._updating or self._current_node is None:
            return
        with self._scene.undo_scope("Edit Text"):
            self._current_node.set_text(self._node_text.text())

    def _on_node_size(self) -> None:
        if self._updating or self._current_node is None:
            return
        with self._scene.undo_scope("Resize"):
            self._current_node.set_size(self._node_w.value(), self._node_h.value())

    def _on_node_shape(self, index: int) -> None:
        if self._updating or self._current_node is None:
            return
        if 0 <= index < len(_SHAPE_ITEMS):
            with self._scene.undo_scope("Change Shape"):
                self._current_node.set_shape(_SHAPE_ITEMS[index][1])

    def _on_node_fill(self, color: QColor) -> None:
        if self._updating or self._current_node is None:
            return
        with self._scene.undo_scope("Change Fill"):
            self._current_node.set_fill_color(color)

    def _on_node_border(self, color: QColor) -> None:
        if self._updating or self._current_node is None:
            return
        with self._scene.undo_scope("Change Border"):
            self._current_node.set_border_color(color)

    def _on_node_font(self, size: int) -> None:
        if self._updating or self._current_node is None:
            return
        with self._scene.undo_scope("Change Font"):
            self._current_node.set_font_size(size)

    # ------------------------------------------------------------------
    # Connection property handlers
    # ------------------------------------------------------------------

    def _on_conn_label(self) -> None:
        if self._updating or self._current_conn is None:
            return
        with self._scene.undo_scope("Edit Label"):
            self._current_conn.set_edge_label(self._conn_label.text())

    def _on_conn_style(self, index: int) -> None:
        if self._updating or self._current_conn is None:
            return
        if 0 <= index < len(_STYLE_ITEMS):
            with self._scene.undo_scope("Change Style"):
                self._current_conn.set_style(_STYLE_ITEMS[index][1])

    def _on_conn_color(self, color: QColor) -> None:
        if self._updating or self._current_conn is None:
            return
        with self._scene.undo_scope("Change Color"):
            self._current_conn.set_line_color(color)

    def _on_conn_width(self, width: float) -> None:
        if self._updating or self._current_conn is None:
            return
        with self._scene.undo_scope("Change Width"):
            self._current_conn.set_line_width(width)

    # ------------------------------------------------------------------
    # Image property handlers
    # ------------------------------------------------------------------

    def _show_image(self, img: DiagramImage) -> None:
        self._current_img = img
        self._no_sel_label.hide()
        self._node_group.hide()
        self._conn_group.hide()
        self._img_group.show()

        self._img_caption.setText(img.text())
        src = img.source()
        self._img_source.setText(src if src else "")
        self._img_w.setValue(int(img.img_w))
        self._img_h.setValue(int(img.img_h))

    def _on_img_caption(self) -> None:
        if self._updating or self._current_img is None:
            return
        with self._scene.undo_scope("Edit Caption"):
            self._current_img.set_text(self._img_caption.text())

    def _on_img_size(self) -> None:
        if self._updating or self._current_img is None:
            return
        with self._scene.undo_scope("Resize Image"):
            self._current_img.set_size(self._img_w.value(), self._img_h.value())
