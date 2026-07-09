from __future__ import annotations

import os

import pytest

# Use Qt's offscreen platform so the widgets never need a real display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qt_app():
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:  # pragma: no cover - PySide6 is a hard dependency
        pytest.skip("PySide6 not available")
    app = QApplication.instance()
    if app is None:
        try:
            app = QApplication([])
        except Exception as exc:  # pragma: no cover - no usable Qt platform
            pytest.skip(f"Cannot start QApplication: {exc}")
    return app


class TestNodeRoundTrip:
    def test_node_preserves_fields(self, qt_app):
        from pybreeze.pybreeze_ui.diagram_editor.diagram_items import DiagramNode, NodeShape

        node = DiagramNode(x=12, y=34, w=140, h=70, text="Hello", shape=NodeShape.DIAMOND)
        restored = DiagramNode.from_dict(node.to_dict(0))

        assert restored.text() == "Hello"
        assert restored.shape_type is NodeShape.DIAMOND
        assert restored.node_w == 140
        assert restored.node_h == 70

    def test_to_dict_and_from_dict_field_symmetry(self, qt_app):
        from pybreeze.pybreeze_ui.diagram_editor.diagram_items import DiagramNode, NodeShape

        # Every persisted field (except the positional id) must be consumable by
        # from_dict — guards against adding a to_dict field without restoring it.
        node = DiagramNode(x=0, y=0, w=100, h=60, text="N", shape=NodeShape.RECTANGLE)
        data = node.to_dict(0)
        clone = DiagramNode.from_dict(data)
        clone_data = clone.to_dict(0)
        for key in ("x", "y", "w", "h", "text", "shape", "font_size"):
            assert clone_data[key] == data[key], f"field {key} not round-tripped"


class TestImageRoundTrip:
    def test_image_preserves_source_and_geometry(self, qt_app):
        from pybreeze.pybreeze_ui.diagram_editor.diagram_items import DiagramImage

        img = DiagramImage(x=5, y=6, w=210, h=120, source="C:/pics/logo.png")
        restored = DiagramImage.from_dict(img.to_dict(0))

        assert restored._source == "C:/pics/logo.png"
        assert restored.img_w == 210
        assert restored.img_h == 120


class TestSceneLoadRobustness:
    def test_valid_items_load_despite_malformed_entries(self, qt_app):
        from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import DiagramScene

        scene = DiagramScene()
        data = {
            "nodes": [
                {"id": 0, "x": 0, "y": 0, "text": "Good", "shape": "RECTANGLE"},
                {"id": 1},                       # malformed: missing x/y
                {"x": 5, "y": 5, "text": "NoId"},  # missing id -> loads, not mappable
            ],
            "connections": [
                {"source": 0, "target": 0, "style": "SOLID"},
                {"source": 0, "target": 99},     # dangling target -> skipped
                {"target": 0},                   # missing source -> skipped
            ],
            "images": [
                {"id": 0},                       # malformed: missing x/y
            ],
        }
        # Must not raise even though several entries are malformed.
        scene.load_from_dict(data)
        nodes = scene.get_all_nodes()
        # "Good" and "NoId" load; the {"id": 1} node is skipped.
        assert {n.text() for n in nodes} == {"Good", "NoId"}
        # Only the valid self-connection survives.
        assert len(scene.get_all_connections()) == 1

    def test_invalid_connection_style_falls_back_to_solid(self, qt_app):
        from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import DiagramScene
        from pybreeze.pybreeze_ui.diagram_editor.diagram_items import ConnectionStyle

        scene = DiagramScene()
        scene.load_from_dict({
            "nodes": [
                {"id": 0, "x": 0, "y": 0, "text": "A"},
                {"id": 1, "x": 0, "y": 80, "text": "B"},
            ],
            "connections": [{"source": 0, "target": 1, "style": "NOT_A_STYLE"}],
        })
        conns = scene.get_all_connections()
        assert len(conns) == 1
        assert conns[0]._style is ConnectionStyle.SOLID


class TestUndoRedo:
    def test_add_node_undo_redo_cycle(self, qt_app):
        from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import DiagramScene
        from pybreeze.pybreeze_ui.diagram_editor.diagram_items import DiagramNode, NodeShape

        scene = DiagramScene()
        with scene.undo_scope("Add"):
            scene.addItem(DiagramNode(x=0, y=0, w=100, h=60, text="X", shape=NodeShape.RECTANGLE))
        assert len(scene.get_all_nodes()) == 1

        scene.undo_stack.undo()
        assert len(scene.get_all_nodes()) == 0

        scene.undo_stack.redo()
        assert len(scene.get_all_nodes()) == 1

    def test_no_op_scope_pushes_no_command(self, qt_app):
        from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import DiagramScene

        scene = DiagramScene()
        with scene.undo_scope("Nothing"):
            pass
        # A scope that changes nothing must not create an undo entry.
        assert scene.undo_stack.count() == 0


class TestCopyPaste:
    def _two_connected_nodes(self):
        from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import DiagramScene
        from pybreeze.pybreeze_ui.diagram_editor.diagram_items import (
            DiagramConnection, DiagramNode, NodeShape,
        )
        scene = DiagramScene()
        n1 = DiagramNode(x=0, y=0, w=100, h=60, text="A", shape=NodeShape.RECTANGLE)
        n2 = DiagramNode(x=200, y=0, w=100, h=60, text="B", shape=NodeShape.RECTANGLE)
        scene.addItem(n1)
        scene.addItem(n2)
        conn = DiagramConnection(n1, n2)
        scene.addItem(conn)
        return scene, n1, n2, conn

    def test_copy_paste_duplicates_nodes_and_internal_connection(self, qt_app):
        scene, n1, n2, conn = self._two_connected_nodes()
        for item in (n1, n2, conn):
            item.setSelected(True)
        scene.copy_selected()
        scene.paste_clipboard()
        assert len(scene.get_all_nodes()) == 4
        assert len(scene.get_all_connections()) == 2

    def test_paste_offsets_copies(self, qt_app):
        scene, n1, n2, conn = self._two_connected_nodes()
        n1.setSelected(True)
        scene.copy_selected()
        scene.paste_clipboard()
        # The pasted copy of A sits at the original +30,+30.
        offsets = {(round(n.pos().x()), round(n.pos().y())) for n in scene.get_all_nodes() if n.text() == "A"}
        assert (0, 0) in offsets
        assert (30, 30) in offsets

    def test_connection_with_external_endpoint_not_copied(self, qt_app):
        # Only n1 selected; the connection touches n2 (unselected) so it must
        # not be copied (avoids a dangling reference).
        scene, n1, n2, conn = self._two_connected_nodes()
        n1.setSelected(True)
        scene.copy_selected()
        scene.paste_clipboard()
        assert len(scene.get_all_connections()) == 1  # only the original remains


class TestCorruptedNodeData:
    def test_zero_size_node_is_clamped_and_edge_point_survives(self, qt_app):
        from PySide6.QtCore import QPointF
        from pybreeze.pybreeze_ui.diagram_editor.diagram_items import DiagramNode, NodeShape

        node = DiagramNode(x=0, y=0, w=0, h=0, text="X", shape=NodeShape.DIAMOND)
        assert node.node_w >= 40
        assert node.node_h >= 20
        # Previously a zero-size diamond divided by zero here.
        point = node.edge_point(QPointF(100, 100))
        assert point is not None

    def test_invalid_colour_falls_back(self, qt_app):
        from pybreeze.pybreeze_ui.diagram_editor.diagram_items import DiagramNode

        node = DiagramNode.from_dict({
            "x": 0, "y": 0, "text": "N", "shape": "RECTANGLE",
            "fill_color": "not-a-real-color",
        })
        assert node._fill_color.isValid()

    def test_valid_colour_preserved(self, qt_app):
        from pybreeze.pybreeze_ui.diagram_editor.diagram_items import DiagramNode

        node = DiagramNode(fill_color="#ff0000")
        assert node._fill_color.name() == "#ff0000"


class TestGridSettings:
    def test_grid_settings_sync_to_nodes_and_images(self, qt_app):
        from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import DiagramScene
        from pybreeze.pybreeze_ui.diagram_editor.diagram_items import DiagramImage, DiagramNode

        scene = DiagramScene()
        try:
            scene.grid_enabled = True
            scene.grid_size = 25
            # Both item types snap independently; the scene must update both,
            # otherwise images ignore the grid that nodes honour.
            assert DiagramNode.grid_enabled is True
            assert DiagramImage.grid_enabled is True
            assert DiagramNode.grid_size == 25
            assert DiagramImage.grid_size == 25
        finally:
            # These are class-level flags; reset so other tests see defaults.
            scene.grid_enabled = False
            scene.grid_size = 20


class TestMermaidImportEndToEnd:
    def test_parse_then_load_preserves_shapes_arrows_styles(self, qt_app):
        from pybreeze.pybreeze_ui.diagram_editor.diagram_mermaid_parser import parse_mermaid
        from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import DiagramScene

        data = parse_mermaid("graph LR\nA[(DB)] -.-> B & C\nB ==> D{{Decision}}")
        scene = DiagramScene()
        scene.load_from_dict(data)

        assert len(scene.get_all_nodes()) == 4
        assert len(scene.get_all_connections()) == 3
        texts = {n.text() for n in scene.get_all_nodes()}
        assert {"DB", "B", "C", "Decision"} == texts
        styles = sorted(c._style.name for c in scene.get_all_connections())
        assert styles == ["DOTTED", "DOTTED", "SOLID"]  # two dotted fan-out, one thick
