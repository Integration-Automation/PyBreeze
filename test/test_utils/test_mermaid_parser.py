from __future__ import annotations

import re

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

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

    @pytest.mark.parametrize("line", ['A-->|"a|b"|B', 'A-->| "a|b" |B'])
    def test_a_quoted_pipe_label_keeps_its_bar(self, line):
        # The label stopped at the "|" inside the quotes: '"a'
        r = parse_mermaid(f"graph TD\n{line}")
        assert [c["label"] for c in r["connections"]] == ["a|b"]
        assert len(r["nodes"]) == 2

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

    def test_a_cycle_no_root_reaches_gets_layers_of_its_own(self):
        # C and D point only at each other: nothing leads to them from A, so the
        # layering never reaches them. They go below, each on a layer of its own,
        # rather than all landing on the first layer on top of A
        r = parse_mermaid("graph TD\nA-->B\nC-->D\nD-->C")
        ys = {n["text"]: n["y"] for n in r["nodes"]}
        assert ys["A"] < ys["B"] < ys["C"] < ys["D"]


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


def _node_texts(result) -> list:
    return [node["text"] for node in result["nodes"]]


def _edges(result):
    texts = [node["text"] for node in result["nodes"]]
    return [(texts[c["source"]], texts[c["target"]], c["label"]) for c in result["connections"]]


class TestTextThatLooksLikeSyntax:
    @pytest.mark.parametrize("label", ["a --> b", "a;b", "x -- y --> z", "p ~~~ q"])
    def test_an_arrow_or_semicolon_inside_a_quoted_label_is_label(self, label):
        result = parse_mermaid(f'graph TD\nA["{label}"]-->B')

        assert _node_texts(result) == [label, "B"]
        assert _edges(result) == [(label, "B", "")]

    def test_a_bracket_inside_quotes_does_not_end_the_label(self):
        result = parse_mermaid('graph TD\nA["list[0]; done"] --> B')

        assert _node_texts(result) == ["list[0]; done", "B"]


class TestHeadersAndDirectives:
    @pytest.mark.parametrize("header", ["graph", "flowchart", "Flowchart"])
    def test_a_header_without_a_direction_is_not_a_node(self, header):
        result = parse_mermaid(f"{header}\nA-->B")

        assert _node_texts(result) == ["A", "B"]

    def test_direction_inside_a_subgraph_is_not_a_node(self):
        result = parse_mermaid("graph LR\nsubgraph S\ndirection TB\nA-->B\nend")

        assert _node_texts(result) == ["A", "B"]

    def test_a_node_whose_name_starts_like_a_keyword_is_still_a_node(self):
        assert "graphics" in _node_texts(parse_mermaid("graph TD\ngraphics-->directions"))


class TestMoreLinks:
    @pytest.mark.parametrize("link", ["-- text ---", "-- text --o", "-- text --x", "-- text -->"])
    def test_text_on_any_normal_link_is_its_label(self, link):
        result = parse_mermaid(f"graph TD\nA {link} B")

        assert _node_texts(result) == ["A", "B"]
        assert _edges(result) == [("A", "B", "text")]

    def test_an_invisible_link_keeps_both_nodes_and_draws_nothing(self):
        result = parse_mermaid("graph TD\nA ~~~ B")

        assert _node_texts(result) == ["A", "B"]
        assert result["connections"] == []


class TestWhatTheReviewFound:
    def test_capitalised_keywords_are_nodes(self):
        # "End", "Click", "Style" were taken for keywords and their lines skipped
        result = parse_mermaid("graph TD\nStart --> End\nEnd((Finish))\nEnd --> C\nStyle[Style guide] --> Click")

        assert _node_texts(result) == ["Start", "Finish", "C", "Style guide", "Click"]
        assert ("Start", "Finish", "") in _edges(result)
        assert ("Finish", "C", "") in _edges(result)

    def test_lower_case_keywords_are_still_skipped(self):
        result = parse_mermaid("graph TD\nsubgraph one\nA --> B\nend\nstyle A fill:#f9f\nclick A callback")

        assert _node_texts(result) == ["A", "B"]

    def test_a_class_suffix_keeps_the_label(self):
        # "A[Label]:::hot" became a node labelled "A"
        assert _node_texts(parse_mermaid("graph TD\nA[Label]:::hot --> B")) == ["Label", "B"]
        assert _node_texts(parse_mermaid("graph TD\nA[Label] --> B\nA:::hot")) == ["Label", "B"]

    def test_a_chain_of_open_links_keeps_its_middle_node(self):
        # The last two dashes of "---" were read as the start of an edge label
        result = parse_mermaid("graph TD\nA --- B --- C")

        assert _node_texts(result) == ["A", "B", "C"]
        assert _edges(result) == [("A", "B", ""), ("B", "C", "")]

    def test_percent_signs_in_a_label_are_not_a_comment(self):
        result = parse_mermaid('graph TD\nA["100%% done"] --> B %% a real comment\n%% a whole-line comment')

        assert _node_texts(result) == ["100%% done", "B"]
        assert _edges(result) == [("100%% done", "B", "")]

    def test_a_quoted_edge_label_loses_its_quotes(self):
        assert _edges(parse_mermaid('graph TD\nA -->|"quoted label"| B')) == [("A", "B", "quoted label")]


class TestArrowLabels:
    @pytest.mark.parametrize("token,label", [
        ("-->", ""),
        ("-->|yes|", "yes"),
        ("-->| yes |", "yes"),
        ('-->|"a|b"|', "a|b"),
        ('-->| "a|b" |', "a|b"),
        ('-->|"a" b|', '"a" b'),
        ('-->|"a|', '"a'),
        ("-->||", ""),
        ("-->| |", ""),
        ("==>|thick|", "thick"),
        ('-->|""|', ""),
        ("-->|x|y|", "x"),
        ("--> |yes|", "yes"),
    ])
    def test_the_label_of_an_arrow(self, token, label):
        from pybreeze.pybreeze_ui.diagram_editor.diagram_mermaid_parser import _parse_arrow

        assert _parse_arrow(token)[0] == label

    @given(st.text(alphabet='|" a\t', max_size=14))
    @settings(max_examples=400, deadline=None)
    def test_the_label_is_the_one_the_old_pattern_found(self, tail):
        # The pattern the two replaced, as the oracle: cubic, but not on 14 characters
        from pybreeze.pybreeze_ui.diagram_editor.diagram_mermaid_parser import _arrow_label

        old = re.search(r'\|\s*("[^"]*"|[^|]*)\s*\|', "-->" + tail)

        assert _arrow_label("-->" + tail).strip() == (old.group(1).strip() if old else "")

    def test_a_long_unclosed_label_is_read_in_linear_time(self):
        # The label pattern backtracked in cubic time: 800 spaces took half a
        # second, 3,000 about half a minute, on the UI thread
        import time

        from pybreeze.pybreeze_ui.diagram_editor.diagram_mermaid_parser import _parse_arrow

        started = time.perf_counter()
        _parse_arrow("-->|" + " " * 3000 + "x")
        _parse_arrow('-->| "' + " " * 3000 + "x")

        assert time.perf_counter() - started < 1


def _connections(result):
    return [(c["label"], c["style"], c["line_width"]) for c in result["connections"]]


class TestTheLabelIsNotTheLink:
    """A link's style is its body's: text in its label that looks like a link is text."""

    @pytest.mark.parametrize("source", [
        "A -->|a==b| B",
        "A -->|x -. y| B",
        "A -- a==b --> B",
        'A -->|"c -.- d"| B',
    ])
    def test_a_label_does_not_make_a_normal_link_thick_or_dotted(self, source):
        # "==" anywhere in the token drew a thick line, "-." a dotted one
        result = parse_mermaid(f"graph TD\n{source}")

        assert [style for _, style, _ in _connections(result)] == ["SOLID"]
        assert [width for _, _, width in _connections(result)] == [2.0]

    def test_a_link_labelled_with_tildes_is_drawn(self):
        # "~~~" in the label took the link for an invisible one
        assert _edges(parse_mermaid("graph TD\nA -->|~~~| B")) == [("A", "B", "~~~")]

    @pytest.mark.parametrize(("source", "style", "width"), [
        ("A ==>|a| B", "SOLID", 3.5),
        ("A -.->|a| B", "DOTTED", 2.0),
    ])
    def test_the_body_still_decides(self, source, style, width):
        assert _connections(parse_mermaid(f"graph TD\n{source}")) == [("a", style, width)]


class TestLineBreaksAndEntityCodes:
    """Text as mermaid shows it: ``<br>`` starts a line, ``#quot;`` and ``#9829;`` are characters."""

    @pytest.mark.parametrize("br", ["<br>", "<br/>", "<br />", "<BR>", "<br  />"])
    def test_a_br_tag_in_a_node_starts_a_new_line(self, br):
        result = parse_mermaid(f"graph TD\nA[one{br}two] --> B")

        assert _node_texts(result) == ["one\ntwo", "B"]

    def test_a_br_tag_in_a_link_label_starts_a_new_line(self):
        assert _edges(parse_mermaid("graph TD\nA -->|one<br>two| B")) == [("A", "B", "one\ntwo")]

    @pytest.mark.parametrize(("written", "shown"), [
        ('"say #quot;hi#quot;"', 'say "hi"'),
        ("love #9829;", "love ♥"),
        ("#35;1", "#1"),
        ("a #amp; b", "a & b"),
        ("#nosuch; stays", "#nosuch; stays"),
        ("#60;br#62;", "<br>"),  # an encoded tag is text, not a line break
    ])
    def test_an_entity_code_is_its_character(self, written, shown):
        result = parse_mermaid(f"graph TD\nA[{written}] -->|{written}| B")

        assert _node_texts(result) == [shown, "B"]
        assert _edges(result) == [(shown, "B", shown)]

    def test_a_node_is_as_wide_as_its_longest_line_and_taller_past_two_lines(self):
        result = parse_mermaid("graph TD\nA[short<br>a much longer line<br>x<br>y] --> B[one<br>two]")
        tall, two_lines = result["nodes"]
        one_line = parse_mermaid("graph TD\nC[a much longer line]")["nodes"][0]

        assert tall["w"] == one_line["w"]
        assert two_lines["h"] == one_line["h"]
        assert tall["h"] > one_line["h"]


class TestKeywordsAfterASemicolon:
    """``;`` separates statements as a new line does: a keyword is one wherever its statement starts."""

    @pytest.mark.parametrize("statement", [
        "style A fill:#f9f",
        "classDef hot fill:#f00",
        "class A hot",
        "click A callback",
        "linkStyle 0 stroke:#f00",
        "direction LR",
    ])
    def test_a_styling_statement_after_a_semicolon_is_not_a_node(self, statement):
        # Each made a node named after its keyword
        result = parse_mermaid(f"graph TD\nA-->B; {statement}")

        assert _node_texts(result) == ["A", "B"]
        assert _edges(result) == [("A", "B", "")]

    def test_a_subgraph_on_one_line_keeps_its_links(self):
        # The line began with "subgraph" and was skipped whole
        result = parse_mermaid("graph TD\nsubgraph one; A-->B; end\nB-->C")

        assert _node_texts(result) == ["A", "B", "C"]
        assert _edges(result) == [("A", "B", ""), ("B", "C", "")]
