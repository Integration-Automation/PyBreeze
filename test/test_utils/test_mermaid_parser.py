from __future__ import annotations

import pytest

from pybreeze.pybreeze_ui.diagram_editor.diagram_mermaid_parser import (
    _order_layers,
    parse_mermaid,
)


def _count_crossings(result):
    """Count edge crossings between adjacent layers in a TD layout."""
    nodes = {n["id"]: n for n in result["nodes"]}
    conns = result["connections"]
    crossings = 0
    for i in range(len(conns)):
        for j in range(i + 1, len(conns)):
            a, b = conns[i], conns[j]
            ay = (round(nodes[a["source"]]["y"]), round(nodes[a["target"]]["y"]))
            by = (round(nodes[b["source"]]["y"]), round(nodes[b["target"]]["y"]))
            if set(ay) == set(by) and ay[0] != ay[1]:
                ax = (nodes[a["source"]]["x"], nodes[a["target"]]["x"])
                bx = (nodes[b["source"]]["x"], nodes[b["target"]]["x"])
                if (ax[0] - bx[0]) * (ax[1] - bx[1]) < 0:
                    crossings += 1
    return crossings


def _texts(result):
    return {n["text"] for n in result["nodes"]}


def _shapes(result):
    return {n["text"]: n["shape"] for n in result["nodes"]}


class TestBasicParsing:
    def test_simple_edge(self):
        r = parse_mermaid("graph TD\nA-->B")
        assert len(r["nodes"]) == 2
        assert len(r["connections"]) == 1
        assert _texts(r) == {"A", "B"}

    def test_chained_arrows(self):
        r = parse_mermaid("graph TD\nA-->B-->C")
        assert len(r["nodes"]) == 3
        assert len(r["connections"]) == 2

    def test_node_text_overrides_id(self):
        r = parse_mermaid("graph TD\nA[Start]-->B[End]")
        assert _texts(r) == {"Start", "End"}

    def test_label_after_bare_reference_is_applied(self):
        # Edges declared first, labels later — labels must still take effect.
        r = parse_mermaid("graph TD\nA-->B\nA[Hello]\nB[World]")
        assert _texts(r) == {"Hello", "World"}

    def test_bare_reference_does_not_clobber_label(self):
        r = parse_mermaid("graph TD\nA[Hello]-->B\nA-->C")
        shapes = _shapes(r)
        assert "Hello" in shapes
        assert shapes["Hello"] == "RECTANGLE"

    def test_empty_input(self):
        r = parse_mermaid("")
        assert r["nodes"] == []
        assert r["connections"] == []

    def test_whitespace_and_comments_ignored(self):
        r = parse_mermaid("graph TD\n%% a comment\n\n   \nA-->B %% trailing")
        assert len(r["nodes"]) == 2


class TestShapes:
    def test_all_shapes(self):
        r = parse_mermaid(
            "graph LR\n"
            "A[Rect]-->B(Round)\n"
            "B-->C{Diamond}\n"
            "C-->D((Ellipse))"
        )
        shapes = _shapes(r)
        assert shapes["Rect"] == "RECTANGLE"
        assert shapes["Round"] == "ROUNDED_RECT"
        assert shapes["Diamond"] == "DIAMOND"
        assert shapes["Ellipse"] == "ELLIPSE"


class TestArrowsAndLabels:
    def test_pipe_label(self):
        r = parse_mermaid("graph TD\nA-->|yes|B")
        assert r["connections"][0]["label"] == "yes"

    def test_inline_label(self):
        r = parse_mermaid("graph TD\nA -- maybe --> B")
        assert r["connections"][0]["label"] == "maybe"

    def test_dotted_and_thick_styles(self):
        r = parse_mermaid("graph TD\nA-.->B\nB==>C")
        styles = {c["style"] for c in r["connections"]}
        assert "DOTTED" in styles   # -.-> dotted link
        assert "SOLID" in styles    # ==> thick link (solid, wider)


class TestExtendedShapes:
    @pytest.mark.parametrize("text,label,shape", [
        ("graph TD\nA[(Database)]-->B", "Database", "RECTANGLE"),   # cylinder
        ("graph TD\nA(((Core)))-->B", "Core", "ELLIPSE"),           # double circle
        ("graph TD\nA[/Input/]-->B", "Input", "RECTANGLE"),         # parallelogram
        ("graph TD\nA[\\Trap\\]-->B", "Trap", "RECTANGLE"),         # trapezoid
        ("graph TD\nA>Flag]-->B", "Flag", "RECTANGLE"),             # asymmetric/flag
        ("graph TD\nA([Pill])-->B", "Pill", "ROUNDED_RECT"),        # stadium
        ("graph TD\nA[[Sub]]-->B", "Sub", "RECTANGLE"),             # subroutine
        ("graph TD\nA{{Hex}}-->B", "Hex", "DIAMOND"),               # hexagon
    ])
    def test_shape_text_is_clean(self, text, label, shape):
        r = parse_mermaid(text)
        match = next(n for n in r["nodes"] if n["text"] == label)
        assert match["shape"] == shape

    @pytest.mark.parametrize("text,label", [
        ('graph TD\nA["Hello World"]-->B', "Hello World"),
        ('graph TD\nA["a (b) [c]"]-->B', "a (b) [c]"),
        ('graph TD\nA("quoted round")-->B', "quoted round"),
        ('graph TD\nA{"decision?"}-->B', "decision?"),
    ])
    def test_quoted_labels_are_unquoted(self, text, label):
        r = parse_mermaid(text)
        assert label in {n["text"] for n in r["nodes"]}


class TestExtendedArrows:
    @pytest.mark.parametrize("text", [
        "graph TD\nA --o B",   # circle edge
        "graph TD\nA --x B",   # cross edge
        "graph TD\nA <--> B",  # bidirectional
        "graph TD\nA ==o B",   # thick circle
        "graph TD\nA o--o B",  # bidirectional circle
    ])
    def test_connection_not_lost(self, text):
        # Regression: --o / --x / <--> used to fail the arrow split and drop the edge.
        r = parse_mermaid(text)
        assert len(r["nodes"]) == 2
        assert len(r["connections"]) == 1

    @pytest.mark.parametrize("text,first_node", [
        ("graph TD\nBox-->B", "Box"),     # node ending in 'x' must not be split
        ("graph TD\nFox--xB", "Fox"),     # 'x' cross head must not eat the 'x' in Fox
        ("graph TD\nHippo-->B", "Hippo"),  # node ending in 'o'
    ])
    def test_node_names_ending_in_o_or_x_not_split(self, text, first_node):
        r = parse_mermaid(text)
        assert first_node in {n["text"] for n in r["nodes"]}
        assert len(r["connections"]) == 1


class TestDirections:
    @pytest.mark.parametrize("direction", ["TD", "TB", "LR", "RL", "BT"])
    def test_direction_keywords_accepted(self, direction):
        r = parse_mermaid(f"graph {direction}\nA-->B")
        assert len(r["nodes"]) == 2

    def test_direction_on_same_line_as_statements(self):
        # Regression: a direction keyword followed by ';'-separated statements
        # used to swallow the whole line and yield zero nodes.
        r = parse_mermaid("graph TD; A-->B; B-->C")
        assert len(r["nodes"]) == 3
        assert len(r["connections"]) == 2


class TestAmpersandMultiNode:
    def _edges(self, result):
        return sorted((c["source"], c["target"]) for c in result["connections"])

    def test_fan_out(self):
        r = parse_mermaid("graph TD\nA --> B & C")
        assert len(r["nodes"]) == 3
        assert self._edges(r) == [(0, 1), (0, 2)]  # A->B, A->C

    def test_fan_in(self):
        r = parse_mermaid("graph TD\nA & B --> C")
        assert len(r["nodes"]) == 3
        assert self._edges(r) == [(0, 2), (1, 2)]  # A->C, B->C

    def test_cartesian_product(self):
        r = parse_mermaid("graph TD\nA & B --> C & D")
        assert len(r["nodes"]) == 4
        assert len(r["connections"]) == 4

    def test_chain_after_group(self):
        r = parse_mermaid("graph TD\nA & B --> C --> D")
        assert len(r["nodes"]) == 4
        assert self._edges(r) == [(0, 2), (1, 2), (2, 3)]

    def test_ampersand_inside_label_not_split(self):
        # The '&' inside a quoted label must not act as a node separator.
        r = parse_mermaid('graph TD\nA["Tom & Jerry"] & B --> C')
        assert len(r["nodes"]) == 3
        assert "Tom & Jerry" in {n["text"] for n in r["nodes"]}


class TestCyclesTerminate:
    """Regression: cyclic graphs used to hang the layout pass forever."""

    def test_self_loop(self):
        r = parse_mermaid("graph TD\nA-->A")
        assert len(r["nodes"]) == 1

    def test_two_cycle(self):
        r = parse_mermaid("graph TD\nA-->B\nB-->A")
        assert len(r["nodes"]) == 2
        assert len(r["connections"]) == 2

    def test_three_cycle(self):
        r = parse_mermaid("graph LR\nA-->B\nB-->C\nC-->A")
        assert len(r["nodes"]) == 3

    def test_cycle_with_tail(self):
        r = parse_mermaid("graph TD\nA-->B\nB-->C\nC-->B\nC-->D")
        assert len(r["nodes"]) == 4


class TestLayout:
    def test_layers_separate_chain_nodes(self):
        r = parse_mermaid("graph TD\nA-->B-->C")
        ys = {n["text"]: n["y"] for n in r["nodes"]}
        # TD layout stacks successive layers along Y.
        assert ys["A"] < ys["B"] < ys["C"]


def _layer_overlap(result):
    """True if any two nodes sharing a layer (same y) sit within one slot."""
    from collections import defaultdict
    layer = defaultdict(list)
    for n in result["nodes"]:
        layer[round(n["y"])].append(n["x"])
    for xs in layer.values():
        xs.sort()
        if any(abs(b - a) < 1.0 for a, b in zip(xs, xs[1:])):
            return True
    return False


class TestCoordinateAlignment:
    def _x(self, result):
        return {n["text"]: n["x"] for n in result["nodes"]}

    def test_lone_child_aligns_under_parent(self):
        # C has a single child D; the C->D edge should be straight (same x).
        x = self._x(parse_mermaid("graph TD\nA-->B\nA-->C\nC-->D"))
        assert abs(x["C"] - x["D"]) < 0.5

    def test_chain_is_a_straight_line(self):
        x = self._x(parse_mermaid("graph TD\nA-->B-->C-->D"))
        assert len({round(v, 1) for v in x.values()}) == 1

    def test_alignment_keeps_nodes_from_overlapping(self):
        r = parse_mermaid("graph TD\nR-->A\nR-->B\nR-->C\nA-->X\nB-->X\nC-->Y")
        assert _layer_overlap(r) is False

    def test_alignment_does_not_add_crossings(self):
        r = parse_mermaid("graph TD\nA-->Y\nB-->X\nC-->Z\nA2-->X\nB2-->Y\nC2-->Z")
        assert _count_crossings(r) == 0


class TestCrossingReduction:
    def test_order_layers_uncrosses(self):
        # Initial order makes A->D and B->C cross; barycenter must swap C/D.
        layer_groups = {0: ["A", "B"], 1: ["C", "D"]}
        layers = {"A": 0, "B": 0, "C": 1, "D": 1}
        adj = {"A": ["D"], "B": ["C"]}
        rev_adj = {"D": ["A"], "C": ["B"]}
        _order_layers(layer_groups, layers, adj, rev_adj)
        assert layer_groups[1] == ["D", "C"]

    def test_complex_graph_has_no_crossings(self):
        # This bipartite-ish graph can be drawn crossing-free; the layout must
        # find such an ordering rather than leaving avoidable crossings.
        r = parse_mermaid(
            "graph TD\nA-->Y\nB-->X\nC-->Z\nA2-->X\nB2-->Y\nC2-->Z"
        )
        assert _count_crossings(r) == 0

    def test_tree_has_no_crossings(self):
        r = parse_mermaid("graph TD\nR-->A\nR-->B\nA-->X\nA-->Y\nB-->Z")
        assert _count_crossings(r) == 0
