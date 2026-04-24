from __future__ import annotations

import re
from collections import defaultdict, deque
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

# Arrow operators with optional pipe-label.
# Order matters: longer patterns first to avoid partial matches.
_ARROW_SPLIT_RE = re.compile(
    r"\s*"
    r"("
    r"={2,}>(?:\|[^|]*\|)?"    # ==>  or  ==>|label|
    r"|-\.+->(?:\|[^|]*\|)?"   # -.-> or  -.->|label|
    r"|--+>(?:\|[^|]*\|)?"     # -->  or  -->|label|
    r"|={2,}"                   # ===
    r"|-\.+-"                   # -.-
    r"|---+"                    # ---
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


# Ordered longest-first so the double-bracket shapes match before single-bracket ones.
_SHAPE_DELIMS: tuple[tuple[str, str, NodeShape], ...] = (
    ("((", "))", NodeShape.ELLIPSE),
    ("([", "])", NodeShape.ROUNDED_RECT),
    ("{{", "}}", NodeShape.DIAMOND),
    ("[[", "]]", NodeShape.RECTANGLE),
    ("(",  ")",  NodeShape.ROUNDED_RECT),
    ("{",  "}",  NodeShape.DIAMOND),
    ("[",  "]",  NodeShape.RECTANGLE),
)


def _extract_shape(rest: str, default_text: str) -> tuple[str, NodeShape]:
    """Strip matching delimiters from ``rest`` and return ``(text, shape)``."""
    for open_tok, close_tok, shape in _SHAPE_DELIMS:
        if rest.startswith(open_tok) and rest.endswith(close_tok):
            return rest[len(open_tok):-len(close_tok)].strip(), shape
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
    if node_id not in nodes:
        nodes[node_id] = _NodeInfo(id=node_id, text=text, shape=shape)
    return node_id


def _parse_arrow(token: str) -> tuple[str, ConnectionStyle, float]:
    """Return ``(label, style, line_width)`` from an arrow token."""
    label = ""
    lm = re.search(r"\|([^|]*)\|", token)
    if lm:
        label = lm.group(1).strip()

    if "==" in token:
        return label, ConnectionStyle.SOLID, 3.5
    if "-." in token:
        return label, ConnectionStyle.DASHED, 2.0
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
    layers: dict[str, int] = {r: 0 for r in roots}
    queue: deque[str] = deque(roots)
    while queue:
        nid = queue.popleft()
        for child in adj.get(nid, []):
            new_layer = layers[nid] + 1
            if child not in layers or layers[child] < new_layer:
                layers[child] = new_layer
                queue.append(child)
    max_layer = max(layers.values(), default=0)
    for nid in nodes:
        if nid not in layers:
            max_layer += 1
            layers[nid] = max_layer
    return layers


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

    layer_groups: dict[int, list[str]] = defaultdict(list)
    for nid, layer in layers.items():
        layer_groups[layer].append(nid)

    horizontal = direction in ("LR", "RL")
    flip = direction in ("RL", "BT")

    for layer_idx in sorted(layer_groups.keys()):
        group = layer_groups[layer_idx]
        count = len(group)
        for i, nid in enumerate(group):
            cross_offset = i - (count - 1) / 2
            _position_node(nodes[nid], layer_idx, cross_offset, horizontal, flip)


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
            _parse_node_ref(parts[0], nodes)
        return
    idx = 0
    while idx + 2 < len(parts):
        src_id = _parse_node_ref(parts[idx], nodes)
        label, style, width = _parse_arrow(parts[idx + 1])
        tgt_id = _parse_node_ref(parts[idx + 2], nodes)
        if src_id and tgt_id:
            edges.append(_EdgeInfo(
                source=src_id, target=tgt_id,
                label=label, style=style, line_width=width,
            ))
        idx += 2


def _parse_direction(line: str) -> str | None:
    match = _DIRECTION_RE.match(line)
    if match is None:
        return None
    direction = match.group(1).upper()
    return "TD" if direction == "TB" else direction


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
        new_dir = _parse_direction(line)
        if new_dir is not None:
            direction = new_dir
            continue
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
