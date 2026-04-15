from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QMarginsF, QRectF, QSizeF, Qt
from PySide6.QtGui import QImage, QKeySequence, QPainter, QShortcut
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from je_editor import language_wrapper

from pybreeze.pybreeze_ui.diagram_editor.diagram_mermaid_parser import parse_mermaid
from pybreeze.pybreeze_ui.diagram_editor.diagram_property_panel import DiagramPropertyPanel
from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import DiagramScene, ToolMode
from pybreeze.pybreeze_ui.diagram_editor.diagram_view import DiagramView
from pybreeze.utils.logging.logger import pybreeze_logger


def _lang(key: str, fallback: str = "") -> str:
    return language_wrapper.language_word_dict.get(key, fallback or key)


_STATUS_HINTS: dict[ToolMode, str] = {
    ToolMode.SELECT: "diagram_editor_status_select",
    ToolMode.ADD_RECT: "diagram_editor_status_add_node",
    ToolMode.ADD_ROUNDED_RECT: "diagram_editor_status_add_node",
    ToolMode.ADD_ELLIPSE: "diagram_editor_status_add_node",
    ToolMode.ADD_DIAMOND: "diagram_editor_status_add_node",
    ToolMode.ADD_CONNECTION: "diagram_editor_status_connection",
    ToolMode.ADD_TEXT: "diagram_editor_status_text",
}


def _make_tool_btn(text: str, checkable: bool = False) -> QToolButton:
    """Create a QToolButton that always shows text (qt_material compatible)."""
    btn = QToolButton()
    btn.setText(text)
    btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
    btn.setCheckable(checkable)
    btn.setMinimumWidth(60)
    btn.setMinimumHeight(28)
    return btn


def _make_action_btn(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setMinimumHeight(28)
    return btn


def _make_hsep() -> QFrame:
    """Vertical separator line for toolbar groups."""
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.VLine)
    sep.setFrameShadow(QFrame.Shadow.Sunken)
    sep.setFixedWidth(2)
    return sep


_MERMAID_PLACEHOLDER = """\
graph TD
    A[Start] --> B{Decision}
    B -->|Yes| C(Process)
    B -->|No| D((End))
    C --> D
"""


class MermaidImportDialog(QDialog):
    """Dialog for pasting Mermaid flowchart code."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_lang("diagram_editor_import_title", "Import Mermaid Diagram"))
        self.setMinimumSize(560, 420)
        self.resize(600, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        hint = QLabel(_lang("diagram_editor_import_hint", "Paste Mermaid flowchart code below:"))
        layout.addWidget(hint)

        self._editor = QPlainTextEdit()
        self._editor.setPlaceholderText(_MERMAID_PLACEHOLDER)
        self._editor.setTabStopDistance(32)
        layout.addWidget(self._editor, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        convert_btn = QPushButton(_lang("diagram_editor_import_convert", "Convert"))
        convert_btn.setDefault(True)
        convert_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton(_lang("diagram_editor_import_cancel", "Cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(convert_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def get_text(self) -> str:
        return self._editor.toPlainText()


class DiagramEditorWidget(QWidget):
    """Full-featured WYSIWYG architecture-diagram editor."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_path: Path | None = None

        # --- MVC core ---
        self._scene = DiagramScene(self)
        self._view = DiagramView(self._scene, self)
        self._prop_panel = DiagramPropertyPanel(self._scene, self)

        # ===================================================================
        # Row 1: Drawing tool modes
        # ===================================================================
        row1 = QHBoxLayout()
        row1.setContentsMargins(8, 6, 8, 2)
        row1.setSpacing(6)

        self._tool_buttons: dict[ToolMode, QToolButton] = {}
        tool_defs: list[tuple[str, ToolMode]] = [
            ("diagram_editor_tool_select", ToolMode.SELECT),
            ("diagram_editor_tool_rect", ToolMode.ADD_RECT),
            ("diagram_editor_tool_rounded_rect", ToolMode.ADD_ROUNDED_RECT),
            ("diagram_editor_tool_ellipse", ToolMode.ADD_ELLIPSE),
            ("diagram_editor_tool_diamond", ToolMode.ADD_DIAMOND),
            ("diagram_editor_tool_connection", ToolMode.ADD_CONNECTION),
            ("diagram_editor_tool_text", ToolMode.ADD_TEXT),
        ]
        for lang_key, mode in tool_defs:
            btn = _make_tool_btn(_lang(lang_key), checkable=True)
            btn.clicked.connect(lambda checked, m=mode: self._set_mode(m))
            row1.addWidget(btn)
            self._tool_buttons[mode] = btn

        row1.addWidget(_make_hsep())

        # --- Image buttons ---
        img_file_btn = _make_tool_btn(_lang("diagram_editor_tool_image_file", "Image"))
        img_file_btn.clicked.connect(self._add_image_from_file)
        row1.addWidget(img_file_btn)

        img_url_btn = _make_tool_btn(_lang("diagram_editor_tool_image_url", "URL Image"))
        img_url_btn.clicked.connect(self._add_image_from_url)
        row1.addWidget(img_url_btn)

        row1.addStretch()

        # ===================================================================
        # Row 2: Actions, undo, align, grid, export, zoom
        # ===================================================================
        row2 = QHBoxLayout()
        row2.setContentsMargins(8, 2, 8, 6)
        row2.setSpacing(6)

        # --- File ---
        for lang_key, handler in [
            ("diagram_editor_action_new", self._new_diagram),
            ("diagram_editor_action_open", self._open_diagram),
            ("diagram_editor_action_save", self._save_diagram),
            ("diagram_editor_action_import", self._import_mermaid),
        ]:
            btn = _make_action_btn(_lang(lang_key))
            btn.clicked.connect(handler)
            row2.addWidget(btn)

        row2.addWidget(_make_hsep())

        # --- Undo / Redo ---
        self._undo_btn = _make_action_btn(_lang("diagram_editor_action_undo", "Undo"))
        self._undo_btn.clicked.connect(self._scene.undo_stack.undo)
        self._undo_btn.setEnabled(False)
        row2.addWidget(self._undo_btn)

        self._redo_btn = _make_action_btn(_lang("diagram_editor_action_redo", "Redo"))
        self._redo_btn.clicked.connect(self._scene.undo_stack.redo)
        self._redo_btn.setEnabled(False)
        row2.addWidget(self._redo_btn)

        self._scene.undo_stack.canUndoChanged.connect(self._undo_btn.setEnabled)
        self._scene.undo_stack.canRedoChanged.connect(self._redo_btn.setEnabled)

        row2.addWidget(_make_hsep())

        # --- Align menu ---
        align_btn = _make_tool_btn(_lang("diagram_editor_align_menu", "Align"))
        align_menu = QMenu(self)
        for lang_key, method in [
            ("diagram_editor_align_left", self._scene.align_left),
            ("diagram_editor_align_right", self._scene.align_right),
            ("diagram_editor_align_top", self._scene.align_top),
            ("diagram_editor_align_bottom", self._scene.align_bottom),
            ("diagram_editor_align_center_h", self._scene.align_center_h),
            ("diagram_editor_align_center_v", self._scene.align_center_v),
        ]:
            align_menu.addAction(_lang(lang_key), method)
        align_menu.addSeparator()
        align_menu.addAction(_lang("diagram_editor_distribute_h", "Distribute H"), self._scene.distribute_h)
        align_menu.addAction(_lang("diagram_editor_distribute_v", "Distribute V"), self._scene.distribute_v)
        align_btn.setMenu(align_menu)
        align_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        row2.addWidget(align_btn)

        row2.addWidget(_make_hsep())

        # --- Grid / Snap ---
        self._grid_cb = QCheckBox(_lang("diagram_editor_action_grid", "Grid"))
        self._grid_cb.toggled.connect(self._toggle_grid)
        row2.addWidget(self._grid_cb)

        self._snap_cb = QCheckBox(_lang("diagram_editor_action_snap", "Snap"))
        self._snap_cb.toggled.connect(self._toggle_snap)
        row2.addWidget(self._snap_cb)

        row2.addWidget(_make_hsep())

        # --- Export ---
        for lang_key, handler in [
            ("diagram_editor_action_export_png", self._export_png),
            ("diagram_editor_action_export_svg", self._export_svg),
        ]:
            btn = _make_action_btn(_lang(lang_key))
            btn.clicked.connect(handler)
            row2.addWidget(btn)

        row2.addWidget(_make_hsep())

        # --- Zoom ---
        zoom_out_btn = _make_action_btn(" - ")
        zoom_out_btn.clicked.connect(self._view.zoom_out)
        row2.addWidget(zoom_out_btn)

        self._zoom_label = QLabel("100%")
        self._zoom_label.setMinimumWidth(48)
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row2.addWidget(self._zoom_label)

        zoom_in_btn = _make_action_btn(" + ")
        zoom_in_btn.clicked.connect(self._view.zoom_in)
        row2.addWidget(zoom_in_btn)

        fit_btn = _make_action_btn(_lang("diagram_editor_action_zoom_fit", "Fit"))
        fit_btn.clicked.connect(self._zoom_fit)
        row2.addWidget(fit_btn)

        row2.addStretch()

        # ===================================================================
        # Status bar
        # ===================================================================
        self._status_label = QLabel()
        self._status_label.setContentsMargins(8, 4, 8, 4)

        # ===================================================================
        # Main layout
        # ===================================================================
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar container
        toolbar_widget = QWidget()
        toolbar_layout = QVBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(0)
        toolbar_layout.addLayout(row1)
        toolbar_layout.addLayout(row2)
        layout.addWidget(toolbar_widget)

        # Canvas + property panel
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._view)
        splitter.addWidget(self._prop_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([800, 240])
        splitter.setCollapsible(1, True)
        splitter.setHandleWidth(6)
        layout.addWidget(splitter, 1)

        layout.addWidget(self._status_label)

        # ===================================================================
        # Signals
        # ===================================================================
        self._scene.mode_changed.connect(self._on_mode_changed)
        self._view.zoom_changed.connect(lambda p: self._zoom_label.setText(f"{p}%"))
        self._set_mode(ToolMode.SELECT)

        # ===================================================================
        # Keyboard shortcuts
        # ===================================================================
        self._bind_shortcuts()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _bind_shortcuts(self) -> None:
        shortcuts = [
            (QKeySequence.StandardKey.Undo, self._scene.undo_stack.undo),
            (QKeySequence.StandardKey.Redo, self._scene.undo_stack.redo),
            (QKeySequence.StandardKey.Copy, self._scene.copy_selected),
            (QKeySequence.StandardKey.Paste, self._scene.paste_clipboard),
            (QKeySequence.StandardKey.SelectAll, self._scene.select_all),
            (QKeySequence.StandardKey.Save, self._save_diagram),
            (QKeySequence("Ctrl+Shift+S"), self._save_as_diagram),
            (QKeySequence("Ctrl+D"), self._scene.duplicate_selected),
            (QKeySequence("Ctrl+="), self._view.zoom_in),
            (QKeySequence("Ctrl+-"), self._view.zoom_out),
            (QKeySequence("Ctrl+0"), lambda: self._view.set_zoom(100)),
        ]
        for key, slot in shortcuts:
            sc = QShortcut(key, self)
            sc.activated.connect(slot)

    # ------------------------------------------------------------------
    # Tool mode
    # ------------------------------------------------------------------

    def _set_mode(self, mode: ToolMode) -> None:
        self._scene.mode = mode

    def _on_mode_changed(self, mode: ToolMode) -> None:
        for m, btn in self._tool_buttons.items():
            btn.setChecked(m == mode)
        hint_key = _STATUS_HINTS.get(mode, "")
        self._status_label.setText(_lang(hint_key, ""))

    # ------------------------------------------------------------------
    # Grid / Snap
    # ------------------------------------------------------------------

    def _toggle_grid(self, checked: bool) -> None:
        self._view.draw_grid = checked

    def _toggle_snap(self, checked: bool) -> None:
        self._scene.grid_enabled = checked

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _new_diagram(self) -> None:
        if self._scene.items():
            reply = QMessageBox.question(
                self,
                _lang("diagram_editor_confirm_title", "Confirm"),
                _lang("diagram_editor_confirm_new", "Discard current diagram?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._scene._clear_items()
        self._scene.undo_stack.clear()
        self._scene.item_count_changed.emit()
        self._current_path = None

    def _open_diagram(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            _lang("diagram_editor_dialog_open", "Open Diagram"),
            "",
            "Diagram JSON (*.diagram.json);;All Files (*)",
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            self._scene.load_from_dict(data)
            self._current_path = Path(path)
        except Exception as e:
            pybreeze_logger.error(f"Open diagram failed: {e}")
            QMessageBox.warning(self, _lang("diagram_editor_error_title", "Error"), str(e))

    def _save_diagram(self) -> None:
        if self._current_path is None:
            self._save_as_diagram()
            return
        self._write_json(self._current_path)

    def _save_as_diagram(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            _lang("diagram_editor_dialog_save", "Save Diagram"),
            "untitled.diagram.json",
            "Diagram JSON (*.diagram.json);;All Files (*)",
        )
        if not path:
            return
        self._current_path = Path(path)
        self._write_json(self._current_path)

    def _import_mermaid(self) -> None:
        dialog = MermaidImportDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        text = dialog.get_text().strip()
        if not text:
            return
        try:
            data = parse_mermaid(text)
            if not data.get("nodes"):
                QMessageBox.information(
                    self,
                    _lang("diagram_editor_import_title", "Import"),
                    _lang("diagram_editor_import_empty", "No nodes found in the input."),
                )
                return
            with self._scene.undo_scope("Import Mermaid"):
                self._scene._clear_items()
                self._scene._load_items(data)
            self._scene.item_count_changed.emit()
            self._zoom_fit()
        except Exception as e:
            pybreeze_logger.error(f"Mermaid import failed: {e}")
            QMessageBox.warning(
                self,
                _lang("diagram_editor_import_error", "Parse Error"),
                str(e),
            )

    def _write_json(self, path: Path) -> None:
        try:
            data = self._scene.to_dict()
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            pybreeze_logger.error(f"Save diagram failed: {e}")
            QMessageBox.warning(self, _lang("diagram_editor_error_title", "Error"), str(e))

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _get_content_rect(self) -> QRectF:
        rect = self._scene.itemsBoundingRect()
        return rect.marginsAdded(QMarginsF(40, 40, 40, 40))

    def _export_png(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, _lang("diagram_editor_dialog_export_png", "Export PNG"),
            "diagram.png", "PNG Image (*.png)",
        )
        if not path:
            return
        try:
            rect = self._get_content_rect()
            scale = 2.0
            image = QImage(
                int(rect.width() * scale), int(rect.height() * scale),
                QImage.Format.Format_ARGB32_Premultiplied,
            )
            image.fill(Qt.GlobalColor.white)
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.scale(scale, scale)
            painter.translate(-rect.topLeft())
            self._scene.clearSelection()
            self._scene.render(painter, QRectF(), rect)
            painter.end()
            image.save(path)
        except Exception as e:
            pybreeze_logger.error(f"Export PNG failed: {e}")

    def _export_svg(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, _lang("diagram_editor_dialog_export_svg", "Export SVG"),
            "diagram.svg", "SVG Image (*.svg)",
        )
        if not path:
            return
        try:
            rect = self._get_content_rect()
            gen = QSvgGenerator()
            gen.setFileName(path)
            gen.setSize(QSizeF(rect.width(), rect.height()).toSize())
            gen.setViewBox(QRectF(0, 0, rect.width(), rect.height()))
            painter = QPainter(gen)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.translate(-rect.topLeft())
            self._scene.clearSelection()
            self._scene.render(painter, QRectF(), rect)
            painter.end()
        except Exception as e:
            pybreeze_logger.error(f"Export SVG failed: {e}")

    # ------------------------------------------------------------------
    # Image operations
    # ------------------------------------------------------------------

    def _add_image_from_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            _lang("diagram_editor_dialog_image_file", "Open Image"),
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.svg *.webp);;All Files (*)",
        )
        if not path:
            return
        from PySide6.QtGui import QPixmap
        pix = QPixmap(path)
        if pix.isNull():
            QMessageBox.warning(self, _lang("diagram_editor_error_title", "Error"),
                                _lang("diagram_editor_image_load_failed", "Failed to load image."))
            return
        self._scene.add_image(pix, path)

    def _add_image_from_url(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        url, ok = QInputDialog.getText(
            self,
            _lang("diagram_editor_dialog_image_url", "Image URL"),
            _lang("diagram_editor_dialog_image_url_hint", "Enter image URL:"),
        )
        if not ok or not url.strip():
            return
        url = url.strip()
        try:
            from pybreeze.pybreeze_ui.diagram_editor.diagram_net_utils import safe_download_image
            data = safe_download_image(url)
            from PySide6.QtGui import QPixmap
            pix = QPixmap()
            pix.loadFromData(data)
            if pix.isNull():
                raise ValueError("Invalid image data")
            self._scene.add_image(pix, url)
        except Exception as e:
            pybreeze_logger.error(f"URL image load failed: {e}")
            QMessageBox.warning(self, _lang("diagram_editor_error_title", "Error"), str(e))

    # ------------------------------------------------------------------
    # View helpers
    # ------------------------------------------------------------------

    def _zoom_fit(self) -> None:
        rect = self._scene.itemsBoundingRect()
        if rect.isNull():
            return
        self._view.fitInView(rect.marginsAdded(QMarginsF(20, 20, 20, 20)), Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom_label.setText(f"{int(self._view.transform().m11() * 100)}%")
