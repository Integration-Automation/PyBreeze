from __future__ import annotations

import re
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass

from pybreeze.pybreeze_ui.diagram_editor.diagram_items import (
    ConnectionStyle,
    NodeShape,
)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class _NodeInfo:
    id: str
    text: str
    shape: NodeShape
    x: float = 0.0
    y: float = 0.0


@dataclass
class _EdgeInfo:
    source: str
    target: str
    label: str = ""
    style: ConnectionStyle = ConnectionStyle.SOLID
    line_width: float = 2.0


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_DIRECTION_RE = re.compile(
    r"^\s*(?:graph|flowchart)\s+(TD|TB|LR|RL|BT)", re.IGNORECASE
)
_COMMENT_RE = re.compile(r"%%.*$")
_SKIP_RE = re.compile(
    r"^\s*(?:subgraph|end\b|style\b|classDef\b|class\s|click\b|linkStyle\b)",
    re.IGNORECASE,
)

# Arrow / link operator with optional pipe-label. Handles every common mermaid
# link: normal/thick/dotted bodies, optional right head (arrow ``>``, circle
# ``o`` or cross ``x``) and an optional ``<`` left head for bidirectional links.
# The left head is restricted to ``<`` on purpose: allowing ``o``/``x`` as a left
# head would wrongly split node names ending in those letters (e.g. ``Box-->B``).
_ARROW_SPLIT_RE = re.compile(
    r"\s*"
    r"("
    r"<?"                       # optional left head (bidirectional)
    r"(?:={2,}|-\.+-|-{2,})"    # body: thick (==), dotted (-.-) or normal (--)
    r"[>ox]?"                   # optional right head: arrow / circle / cross
    r"(?:\|[^|]*\|)?"           # optional |label|
    r")"
    r"\s*"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_LABEL_MAX = 200  # bound non-greedy match to prevent polynomial backtracking on pathological input


def _normalize_inline_labels(line: str) -> str:
    """Convert ``-- label -->`` style to ``-->|label|`` pipe style."""
    line = re.sub(rf"--\s+(\S[^|]{{0,{_LABEL_MAX}}}?)\s+-->", r"-->|\1|", line)
    line = re.sub(rf"-\.\s+(\S[^|]{{0,{_LABEL_MAX}}}?)\s+\.->", r"-.->|\1|", line)
    line = re.sub(rf"==\s+(\S[^|]{{0,{_LABEL_MAX}}}?)\s+==>", r"==>|\1|", line)
    return line


# Ordered longest-first so multi-char shapes match before their single-char
# prefixes (e.g. ``(((`` before ``((`` before ``(``). The editor has four node
# shapes, so mermaid shapes without an exact counterpart map to the nearest one
# (cylinder/subroutine/parallelogram/trapezoid/asymmetric -> rectangle,
# double-circle -> ellipse, hexagon -> diamond).
_SHAPE_DELIMS: tuple[tuple[str, str, NodeShape], ...] = (
    ("(((", ")))", NodeShape.ELLIPSE),      # double circle
    ("((", "))", NodeShape.ELLIPSE),        # circle
    ("([", "])", NodeShape.ROUNDED_RECT),   # stadium / pill
    ("[[", "]]", NodeShape.RECTANGLE),      # subroutine
    ("[(", ")]", NodeShape.RECTANGLE),      # cylinder / database
    ("[/", "/]", NodeShape.RECTANGLE),      # parallelogram
    ("[\\", "\\]", NodeShape.RECTANGLE),    # trapezoid
    ("{{", "}}", NodeShape.DIAMOND),        # hexagon
    (">", "]", NodeShape.RECTANGLE),        # asymmetric / flag
    ("(",  ")",  NodeShape.ROUNDED_RECT),   # round edges
    ("{",  "}",  NodeShape.DIAMOND),        # rhombus / decision
    ("[",  "]",  NodeShape.RECTANGLE),      # rectangle
)


def _unquote(text: str) -> str:
    """Drop the surrounding double quotes mermaid uses to allow special chars."""
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return text


def _extract_shape(rest: str, default_text: str) -> tuple[str, NodeShape]:
    """Strip matching delimiters from ``rest`` and return ``(text, shape)``."""
    for open_tok, close_tok, shape in _SHAPE_DELIMS:
        if rest.startswith(open_tok) and rest.endswith(close_tok):
            inner = rest[len(open_tok):-len(close_tok)].strip()
            return _unquote(inner), shape
    return default_text, NodeShape.RECTANGLE


def _parse_node_ref(raw: str, nodes: dict[str, _NodeInfo]) -> str | None:
    """Parse ``ID[text]`` / ``ID(text)`` / ``ID{text}`` / ``ID((text))`` and
    register in *nodes*.  Returns the node ID or ``None``."""
    raw = raw.strip()
    if not raw:
        return None
    m = re.match(r"(\w+)(.*)", raw, re.DOTALL)
    if not m:
        return None
    node_id = m.group(1)
    rest = m.group(2).strip()
    text, shape = _extract_shape(rest, default_text=node_id)
    existing = nodes.get(node_id)
    if existing is None:
        nodes[node_id] = _NodeInfo(id=node_id, text=text, shape=shape)
    elif rest:
        # An explicit label/shape declaration updates a node that was first
        # seen as a bare reference (mermaid commonly declares edges before
        # labelling the nodes). A bare reference never clobbers a label.
        existing.text = text
        existing.shape = shape
    return node_id


def _split_node_group(raw: str) -> list[str]:
    """Split a node group on top-level ``&`` (mermaid fan-in/out).

    ``&`` inside brackets or quotes is part of a label, not a separator, so the
    split tracks bracket depth and quote state (e.g. ``A["Tom & Jerry"] & B``
    yields two members, not three).
    """
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    in_quote = False
    for char in raw:
        if char == '"':
            in_quote = not in_quote
        elif not in_quote and char in "([{":
            depth += 1
        elif not in_quote and char in ")]}":
            depth = max(0, depth - 1)
        if char == "&" and depth == 0 and not in_quote:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return parts


def _parse_node_group(raw: str, nodes: dict[str, _NodeInfo]) -> list[str]:
    """Parse one ``&``-joined node group, returning the registered node IDs."""
    ids: list[str] = []
    for member in _split_node_group(raw):
        node_id = _parse_node_ref(member, nodes)
        if node_id is not None:
            ids.append(node_id)
    return ids


def _parse_arrow(token: str) -> tuple[str, ConnectionStyle, float]:
    """Return ``(label, style, line_width)`` from an arrow token."""
    label = ""
    lm = re.search(r"\|([^|]*)\|", token)
    if lm:
        label = lm.group(1).strip()

    if "==" in token:
        return label, ConnectionStyle.SOLID, 3.5  # thick link
    if "-." in token:
        return label, ConnectionStyle.DOTTED, 2.0  # dotted link
    return label, ConnectionStyle.SOLID, 2.0


# ---------------------------------------------------------------------------
# Auto-layout (layered BFS)
# ---------------------------------------------------------------------------


def _build_adjacency(
    nodes: dict[str, _NodeInfo],
    edges: list[_EdgeInfo],
) -> tuple[dict[str, list[str]], dict[str, int]]:
    adj: dict[str, list[str]] = defaultdict(list)
    in_deg: dict[str, int] = dict.fromkeys(nodes, 0)
    for e in edges:
        if e.source in nodes and e.target in nodes:
            adj[e.source].append(e.target)
            in_deg[e.target] = in_deg.get(e.target, 0) + 1
    return adj, in_deg


def _assign_layers(
    nodes: dict[str, _NodeInfo],
    adj: dict[str, list[str]],
    in_deg: dict[str, int],
) -> dict[str, int]:
    roots = [nid for nid, deg in in_deg.items() if deg == 0] or [next(iter(nodes))]
    layers: dict[str, int] = dict.fromkeys(roots, 0)
    queue: deque[str] = deque(roots)
    # Longest simple path in a graph of N nodes spans at most N-1 edges. A
    # back-edge (cycle or self-loop) would otherwise relax layers upward
    # forever and hang the parser, so we never push a layer to N or beyond.
    max_layer_bound = len(nodes)
    while queue:
        nid = queue.popleft()
        for child in adj.get(nid, []):
            new_layer = layers[nid] + 1
            if new_layer >= max_layer_bound:
                continue
            if child not in layers or layers[child] < new_layer:
                layers[child] = new_layer
                queue.append(child)
    max_layer = max(layers.values(), default=0)
    for nid in nodes:
        if nid not in layers:
            max_layer += 1
            layers[nid] = max_layer
    return layers


# Alternating top-down/bottom-up barycenter sweeps. Four passes is the usual
# sweet spot — most crossing reduction lands in the first couple of sweeps.
_LAYOUT_SWEEPS = 4


def _sweep_layers(
    layer_groups: dict[int, list[str]],
    adj: dict[str, list[str]],
    rev_adj: dict[str, list[str]],
    apply_layer: Callable[[list[str], int, dict[str, list[str]]], None],
) -> None:
    """Run alternating top-down / bottom-up Sugiyama sweeps.

    For each layer (in sweep order) calls ``apply_layer(group, fixed_layer,
    neighbours)`` where *neighbours* is the adjacency toward the adjacent,
    already-positioned *fixed_layer*. Centralises the sweep skeleton so the
    ordering and coordinate passes stay flat and low-complexity.
    """
    layer_indices = sorted(layer_groups.keys())
    for sweep in range(_LAYOUT_SWEEPS):
        going_down = sweep % 2 == 0
        order = layer_indices if going_down else layer_indices[::-1]
        neighbours = rev_adj if going_down else adj
        for layer in order:
            fixed_layer = layer - 1 if going_down else layer + 1
            apply_layer(layer_groups[layer], fixed_layer, neighbours)


def _order_layers(
    layer_groups: dict[int, list[str]],
    layers: dict[str, int],
    adj: dict[str, list[str]],
    rev_adj: dict[str, list[str]],
) -> None:
    """Reorder nodes within each layer to reduce edge crossings, in place.

    Standard Sugiyama crossing-reduction barycenter heuristic: sweep layer by
    layer (alternating direction) moving every node to the mean position of its
    neighbours in the adjacent, already-fixed layer.
    """
    pos: dict[str, int] = {}
    for group in layer_groups.values():
        for index, nid in enumerate(group):
            pos[nid] = index

    def barycenter(nid: str, neighbours: dict[str, list[str]], fixed_layer: int) -> float:
        coords = [pos[n] for n in neighbours.get(nid, []) if layers.get(n) == fixed_layer]
        return sum(coords) / len(coords) if coords else float(pos[nid])

    def reorder(group: list[str], fixed_layer: int, neighbours: dict[str, list[str]]) -> None:
        group.sort(key=lambda nid: barycenter(nid, neighbours, fixed_layer))
        for index, nid in enumerate(group):
            pos[nid] = index

    _sweep_layers(layer_groups, adj, rev_adj, reorder)


def _resolve_offsets(group: list[str], desired: list[float], offset: dict[str, float]) -> None:
    """Place *group* near *desired* offsets, preserving order, in place.

    Nodes keep their within-layer order (so no new crossings) and stay at least
    one slot apart (so no overlaps); the layer is then re-centred on zero.
    """
    placed: list[float] = []
    prev: float | None = None
    for want in desired:
        value = want if prev is None else max(want, prev + 1.0)
        placed.append(value)
        prev = value
    if not placed:
        return
    # Shift the whole run so its centre matches the centre of the desired
    # positions: this preserves alignment (a lone child stays under its parent)
    # while cancelling the left-to-right spacing push.
    shift = sum(desired) / len(desired) - sum(placed) / len(placed)
    for nid, value in zip(group, placed, strict=True):
        offset[nid] = value + shift


def _assign_cross_offsets(
    layer_groups: dict[int, list[str]],
    layers: dict[str, int],
    adj: dict[str, list[str]],
    rev_adj: dict[str, list[str]],
) -> dict[str, float]:
    """Assign a cross-axis offset to each node, aligning it with its neighbours.

    The Sugiyama coordinate-assignment phase: alternating sweeps pull each node
    toward the mean offset of its neighbours in the adjacent fixed layer, which
    straightens edges. ``_resolve_offsets`` keeps the result legal (ordered,
    non-overlapping, centred).
    """
    offset: dict[str, float] = {}
    for group in layer_groups.values():
        count = len(group)
        for i, nid in enumerate(group):
            offset[nid] = float(i) - (count - 1) / 2

    def realign(group: list[str], fixed_layer: int, neighbours: dict[str, list[str]]) -> None:
        desired = []
        for nid in group:
            coords = [offset[n] for n in neighbours.get(nid, []) if layers.get(n) == fixed_layer]
            desired.append(sum(coords) / len(coords) if coords else offset[nid])
        _resolve_offsets(group, desired, offset)

    _sweep_layers(layer_groups, adj, rev_adj, realign)
    return offset


_NODE_H = 60.0
_GAP_MAIN = 120.0
_GAP_CROSS = 80.0


def _position_node(node: _NodeInfo, layer_idx: int, cross_offset: float,
                   horizontal: bool, flip: bool) -> None:
    if horizontal:
        main_pos = layer_idx * (200 + _GAP_MAIN)
        cross_pos = cross_offset * (_NODE_H + _GAP_CROSS)
        if flip:
            main_pos = -main_pos
        node.x = main_pos
        node.y = cross_pos
    else:
        main_pos = layer_idx * (_NODE_H + _GAP_MAIN)
        cross_pos = cross_offset * (200 + _GAP_CROSS)
        if flip:
            main_pos = -main_pos
        node.x = cross_pos
        node.y = main_pos


def _auto_layout(
    nodes: dict[str, _NodeInfo],
    edges: list[_EdgeInfo],
    direction: str,
) -> None:
    if not nodes:
        return
    adj, in_deg = _build_adjacency(nodes, edges)
    layers = _assign_layers(nodes, adj, in_deg)

    rev_adj: dict[str, list[str]] = defaultdict(list)
    for source, targets in adj.items():
        for target in targets:
            rev_adj[target].append(source)

    layer_groups: dict[int, list[str]] = defaultdict(list)
    for nid, layer in layers.items():
        layer_groups[layer].append(nid)

    _order_layers(layer_groups, layers, adj, rev_adj)
    offsets = _assign_cross_offsets(layer_groups, layers, adj, rev_adj)

    horizontal = direction in ("LR", "RL")
    flip = direction in ("RL", "BT")

    for layer_idx in sorted(layer_groups.keys()):
        for nid in layer_groups[layer_idx]:
            _position_node(nodes[nid], layer_idx, offsets[nid], horizontal, flip)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _parse_statement(
    stmt: str,
    nodes: dict[str, _NodeInfo],
    edges: list[_EdgeInfo],
) -> None:
    """Parse one ``;``-delimited mermaid statement, updating *nodes* and *edges*."""
    stmt = _normalize_inline_labels(stmt.strip())
    if not stmt:
        return
    parts = [p for p in _ARROW_SPLIT_RE.split(stmt) if p.strip()]
    if len(parts) < 3:
        if parts:
            _parse_node_group(parts[0], nodes)
        return
    idx = 0
    while idx + 2 < len(parts):
        src_ids = _parse_node_group(parts[idx], nodes)
        label, style, width = _parse_arrow(parts[idx + 1])
        tgt_ids = _parse_node_group(parts[idx + 2], nodes)
        # mermaid joins every source to every target ("A & B --> C & D").
        for src_id in src_ids:
            for tgt_id in tgt_ids:
                edges.append(_EdgeInfo(
                    source=src_id, target=tgt_id,
                    label=label, style=style, line_width=width,
                ))
        idx += 2


def _parse_direction(line: str) -> tuple[str, str] | None:
    """Return ``(direction, remainder)`` when *line* opens with a graph/flowchart
    direction keyword, else ``None``.

    *remainder* is any ``;``-separated statement text that followed the keyword
    on the same line (valid mermaid), so the caller can still parse it instead
    of discarding the rest of the line.
    """
    match = _DIRECTION_RE.match(line)
    if match is None:
        return None
    direction = match.group(1).upper()
    direction = "TD" if direction == "TB" else direction
    remainder = line[match.end():].lstrip(" ;").strip()
    return direction, remainder


def parse_mermaid(text: str) -> dict:
    """Parse Mermaid flowchart syntax and return a diagram dict with
    auto-layout positions.

    Supported subset::

        graph TD
            A[Rectangle] --> B(Rounded Rect)
            B --> C{Diamond}
            C -->|Yes| D((Ellipse))
            C -->|No| E[End]
            A -- label --> B
            X -.-> Y
            P ==> Q
    """
    nodes: dict[str, _NodeInfo] = {}
    edges: list[_EdgeInfo] = []
    direction = "TD"

    for raw_line in text.splitlines():
        line = _COMMENT_RE.sub("", raw_line).strip()
        if not line:
            continue
        parsed_dir = _parse_direction(line)
        if parsed_dir is not None:
            direction, remainder = parsed_dir
            if not remainder:
                continue
            line = remainder
        if _SKIP_RE.match(line):
            continue
        for stmt in line.split(";"):
            _parse_statement(stmt, nodes, edges)

    _auto_layout(nodes, edges, direction)

    node_list = list(nodes.values())
    id_to_idx: dict[str, int] = {n.id: i for i, n in enumerate(node_list)}

    def _node_w(n: _NodeInfo) -> float:
        return max(100.0, min(len(n.text) * 11 + 40, 300.0))

    return {
        "nodes": [
            {
                "id": i,
                "x": n.x,
                "y": n.y,
                "w": _node_w(n),
                "h": 60.0,
                "text": n.text,
                "shape": n.shape.name,
            }
            for i, n in enumerate(node_list)
        ],
        "connections": [
            {
                "source": id_to_idx[e.source],
                "target": id_to_idx[e.target],
                "label": e.label,
                "style": e.style.name,
                "line_width": e.line_width,
            }
            for e in edges
            if e.source in id_to_idx and e.target in id_to_idx
        ],
    }
