"""Align and distribute in the diagram editor: where the selected nodes end up, and one undo step back."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from pybreeze.extend_multi_language.update_language_dict import update_language_dict
from pybreeze.pybreeze_ui.diagram_editor.diagram_items import DiagramNode
from pybreeze.pybreeze_ui.diagram_editor.diagram_scene import DiagramScene


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    update_language_dict()
    return instance


@pytest.fixture()
def scene(app):
    diagram = DiagramScene()
    yield diagram
    diagram.deleteLater()


def _nodes(scene: DiagramScene, *boxes: tuple[float, float, float, float]) -> list[DiagramNode]:
    """Selected nodes at (x, y, w, h)."""
    nodes = []
    for x, y, w, h in boxes:
        node = DiagramNode(x=x, y=y, w=w, h=h, text="n")
        scene.addItem(node)
        node.setSelected(True)
        nodes.append(node)
    return nodes


def _positions(nodes: list[DiagramNode]) -> list[tuple[float, float]]:
    return [(node.pos().x(), node.pos().y()) for node in nodes]


_THREE = ((10, 100, 100, 60), (200, 40, 50, 30), (400, 0, 80, 120))


@pytest.mark.parametrize(("operation", "expected"), [
    ("align_left", [(10, 100), (10, 40), (10, 0)]),
    ("align_right", [(380, 100), (430, 40), (400, 0)]),
    ("align_top", [(10, 0), (200, 0), (400, 0)]),
    ("align_bottom", [(10, 100), (200, 130), (400, 40)]),
])
def test_each_edge_lines_up(scene, operation, expected):
    nodes = _nodes(scene, *_THREE)

    getattr(scene, operation)()

    assert _positions(nodes) == expected


def test_centres_line_up_on_their_average(scene):
    nodes = _nodes(scene, (0, 0, 100, 40), (300, 100, 50, 20))

    scene.align_center_h()
    scene.align_center_v()

    centres = {(node.pos().x() + node.node_w / 2, node.pos().y() + node.node_h / 2) for node in nodes}
    assert centres == {(187.5, 65.0)}


def test_distributing_leaves_equal_gaps_between_the_outer_two(scene):
    nodes = _nodes(scene, (0, 0, 100, 40), (130, 10, 60, 40), (400, 20, 100, 40))

    scene.distribute_h()

    lefts = [node.pos().x() for node in nodes]
    gaps = [lefts[1] - (lefts[0] + 100), lefts[2] - (lefts[1] + 60)]
    assert lefts[0] == 0 and lefts[2] == 400
    assert gaps[0] == pytest.approx(gaps[1])


def test_one_undo_takes_the_whole_alignment_back(scene):
    nodes = _nodes(scene, *_THREE)
    before = _positions(nodes)

    scene.align_left()
    scene.undo_stack.undo()

    # Undo rebuilds the items from a snapshot: compare what is on the canvas now
    now = sorted((item.pos().x(), item.pos().y()) for item in scene.items() if isinstance(item, DiagramNode))
    assert now == sorted(before)
    assert not scene.undo_stack.canUndo()


@pytest.mark.parametrize("operation", ["align_left", "align_center_v", "distribute_h", "distribute_v"])
def test_too_few_nodes_changes_nothing_and_leaves_no_undo_step(scene, operation):
    nodes = _nodes(scene, (0, 0, 100, 40), (300, 100, 50, 20))[: 1 if operation.startswith("align") else 2]
    for extra in scene.selectedItems():
        if extra not in nodes:
            extra.setSelected(False)
    before = _positions(nodes)

    getattr(scene, operation)()

    assert _positions(nodes) == before
    assert not scene.undo_stack.canUndo()
