"""Plain CFG DOT visualization (no energy annotations)."""

# Colorblind-safe palette (Okabe-Ito inspired)
NTYPE_COLORS = {
    "ENTRY": "#009E73", "EXIT": "#CC79A7",
    "LOOP": "#E69F00", "COND": "#F0E442",
    "STMT": "#E0E0E0", "RETURN": "#CC79A7",
    "BREAK": "#56B4E9", "CONTINUE": "#56B4E9",
    "SWITCH": "#F0E442", "CASE": "#E69F00",
}
NTYPE_SHAPES = {
    "ENTRY": "box", "EXIT": "box",
    "LOOP": "diamond", "COND": "diamond",
    "SWITCH": "diamond", "CASE": "box",
}


def _dot_escape(text: str) -> str:
    return text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ').replace('\r', '')


def cfg_to_dot(nodes, edges, method_name: str = "method") -> str:
    """Render a CFG as Graphviz DOT format.

    nodes: list of CNode-like objects with .id, .ntype, .text
    edges: list of (src_id, dst_id, label) tuples
    """
    lines = [f'digraph "{_dot_escape(method_name)}" {{',
             '  rankdir=TB;',
             f'  fontname="Courier"; fontsize=12;',
             f'  node [fontname="Courier" fontsize=10];',
             f'  edge [fontname="Courier" fontsize=9];',
             f'  label="{_dot_escape(method_name)}";',
             '  labelloc=t;']
    for node in nodes:
        ntype = getattr(node, 'ntype', None)
        ntype_name = ntype.name if hasattr(ntype, 'name') else str(ntype)
        text = _dot_escape(getattr(node, 'text', '')[:60])
        color = NTYPE_COLORS.get(ntype_name, "#E0E0E0")
        shape = NTYPE_SHAPES.get(ntype_name, "ellipse")
        lines.append(f'  {node.id} [label="{ntype_name}: {text}" shape={shape} '
                     f'style=filled fillcolor="{color}"];')
    for src, dst, label in edges:
        attrs = f' [label="{_dot_escape(label)}"]' if label else ""
        lines.append(f'  {src} -> {dst}{attrs};')
    lines.append('}')
    return '\n'.join(lines)
