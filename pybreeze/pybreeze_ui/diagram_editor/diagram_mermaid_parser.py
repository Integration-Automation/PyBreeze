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


def _normalize_inline_labels(line: str) -> str:
    """Convert ``-- label -->`` style to ``-->|label|`` pipe style."""
    line = re.sub(r"--\s+(\S[^|]*?)\s+-->", r"-->|\1|", line)
    line = re.sub(r"-\.\s+(\S[^|]*?)\s+\.->", r"-.->|\1|", line)
    line = re.sub(r"==\s+(\S[^|]*?)\s+==>", r"==>|\1|", line)
    return line


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

    text = node_id
    shape = NodeShape.RECTANGLE

    if rest.startswith("((") and rest.endswith("))"):
        text, shape = rest[2:-2].strip(), NodeShape.ELLIPSE
    elif rest.startswith("([") and rest.endswith("])"):
        text, shape = rest[2:-2].strip(), NodeShape.ROUNDED_RECT
    elif rest.startswith("(") and rest.endswith(")"):
        text, shape = rest[1:-1].strip(), NodeShape.ROUNDED_RECT
    elif rest.startswith("{{") and rest.endswith("}}"):
        text, shape = rest[2:-2].strip(), NodeShape.DIAMOND
    elif rest.startswith("{") and rest.endswith("}"):
        text, shape = rest[1:-1].strip(), NodeShape.DIAMOND
    elif rest.startswith("[[") and rest.endswith("]]"):
        text, shape = rest[2:-2].strip(), NodeShape.RECTANGLE
    elif rest.startswith("[") and rest.endswith("]"):
        text, shape = rest[1:-1].strip(), NodeShape.RECTANGLE

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


def _auto_layout(
    nodes: dict[str, _NodeInfo],
    edges: list[_EdgeInfo],
    direction: str,
) -> None:
    if not nodes:
        return

    adj: dict[str, list[str]] = defaultdict(list)
    in_deg: dict[str, int] = {nid: 0 for nid in nodes}

    for e in edges:
        if e.source in nodes and e.target in nodes:
            adj[e.source].append(e.target)
            in_deg[e.target] = in_deg.get(e.target, 0) + 1

    # BFS from roots
    roots = [nid for nid, deg in in_deg.items() if deg == 0]
    if not roots:
        roots = [next(iter(nodes))]

    layers: dict[str, int] = {}
    queue: deque[str] = deque()
    for r in roots:
        layers[r] = 0
        queue.append(r)

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

    # Group by layer
    layer_groups: dict[int, list[str]] = defaultdict(list)
    for nid, layer in layers.items():
        layer_groups[layer].append(nid)

    # Estimate node width from text length
    def _node_w(nid: str) -> float:
        return max(100.0, min(len(nodes[nid].text) * 11 + 40, 300.0))

    node_h = 60.0
    gap_main = 120.0   # between layers
    gap_cross = 80.0    # between siblings

    horizontal = direction in ("LR", "RL")
    flip = direction in ("RL", "BT")

    for layer_idx in sorted(layer_groups.keys()):
        group = layer_groups[layer_idx]
        count = len(group)

        for i, nid in enumerate(group):
            nw = _node_w(nid)
            cross_offset = (i - (count - 1) / 2)

            if horizontal:
                main_pos = layer_idx * (200 + gap_main)
                cross_pos = cross_offset * (node_h + gap_cross)
                if flip:
                    main_pos = -main_pos
                nodes[nid].x = main_pos
                nodes[nid].y = cross_pos
            else:
                main_pos = layer_idx * (node_h + gap_main)
                cross_pos = cross_offset * (200 + gap_cross)
                if flip:
                    main_pos = -main_pos
                nodes[nid].x = cross_pos
                nodes[nid].y = main_pos


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


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

        # Direction header
        dm = _DIRECTION_RE.match(line)
        if dm:
            direction = dm.group(1).upper()
            if direction == "TB":
                direction = "TD"
            continue

        # Skip unsupported directives
        if _SKIP_RE.match(line):
            continue

        # Handle semicolon-separated statements on one line
        for stmt in line.split(";"):
            stmt = stmt.strip()
            if not stmt:
                continue

            stmt = _normalize_inline_labels(stmt)

            parts = _ARROW_SPLIT_RE.split(stmt)
            parts = [p for p in parts if p.strip()]

            if len(parts) < 3:
                # Standalone node definition
                if parts:
                    _parse_node_ref(parts[0], nodes)
                continue

            # Chained edges: N0 arrow N1 arrow N2 ...
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

    # Auto-layout
    _auto_layout(nodes, edges, direction)

    # Build output dict (same format as DiagramScene.to_dict)
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
