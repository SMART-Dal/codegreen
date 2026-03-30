"""Energy Flow Graph: CFG nodes annotated with energy data from CodeGreen.

Design principles:
- Method-level energy is MEASURED (from CodeGreen checkpoints).
- Statement-level energy is a RANKING HEURISTIC, not Joule values.
- Edge weights represent EXECUTION FREQUENCY (probability), not energy cost.
- Ball & Larus (1993) heuristics for branch probabilities when no data available.
- Call edge energy is PRO-RATED per call site.
- Hot path uses longest-path on SCC-collapsed DAG.
"""

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class Accuracy(Enum):
    MEASURED = auto()
    ESTIMATED = auto()
    HEURISTIC = auto()
    INFERRED = auto()
    UNKNOWN = auto()


class EnergyTier(Enum):
    HOT = auto()
    WARM = auto()
    COLD = auto()
    ZERO = auto()


# Ball & Larus (1993) static branch prediction heuristics (configurable)
BL_LOOP_BACK = 0.88
BL_ERROR = 0.01
BL_NULL = 0.95
BL_DEFAULT = 0.50

# Statement ranking weights (for ordering, NOT energy estimation)
RANK_WEIGHTS = {
    "LOOP": 3, "ALLOC": 5, "CALL": 3, "COND": 2, "STMT": 1,
    "ENTRY": 0, "EXIT": 0, "RETURN": 1, "BREAK": 1, "CONTINUE": 1,
    "SWITCH": 2, "CASE": 1,
}

BL_HEURISTICS = {
    "loop_back": BL_LOOP_BACK,
    "error": BL_ERROR,
    "null_check": BL_NULL,
    "default": BL_DEFAULT,
}

INSTRUMENTATION_MARKERS = ("CodeGreenStandaloneRuntime", "codegreen")

TIER_HOT_THRESHOLD = 0.3
TIER_WARM_THRESHOLD = 0.7
HOT_EDGE_FRACTION = 5
NODE_TEXT_MAX_LEN = 80
DOT_LABEL_MAX_LEN = 50
MIN_RANK_FOR_DISPLAY = 1

DOT_FONT_SIZE = 12
DOT_FONT_NAME = "Courier"
DOT_HOT_PENWIDTH = 3.0
DOT_NODE_SEP = 0.3
DOT_RANK_SEP = 0.5
DOT_SPLINES = "spline"

# Colorblind-safe palette (Okabe-Ito inspired, avoids red-green confusion)
TIER_COLORS = {
    EnergyTier.HOT: "#D55E00", EnergyTier.WARM: "#E69F00",
    EnergyTier.COLD: "#56B4E9", EnergyTier.ZERO: "#F0F0F0",
}
TIER_FONT_COLORS = {
    EnergyTier.HOT: "white", EnergyTier.WARM: "black",
    EnergyTier.COLD: "black", EnergyTier.ZERO: "gray",
}
NTYPE_SHAPES = {
    "LOOP": "diamond", "COND": "diamond", "ENTRY": "box",
    "EXIT": "box", "STMT": "ellipse", "SWITCH": "diamond", "CASE": "box",
    "RETURN": "ellipse", "BREAK": "ellipse", "CONTINUE": "ellipse",
}


@dataclass
class EFGConfig:
    tier_hot: float = TIER_HOT_THRESHOLD
    tier_warm: float = TIER_WARM_THRESHOLD
    hot_edge_fraction: int = HOT_EDGE_FRACTION
    node_text_max: int = NODE_TEXT_MAX_LEN
    dot_label_max: int = DOT_LABEL_MAX_LEN
    min_rank_display: float = MIN_RANK_FOR_DISPLAY
    instrumentation_markers: tuple[str, ...] = INSTRUMENTATION_MARKERS
    rank_weights: dict[str, int] = field(default_factory=lambda: dict(RANK_WEIGHTS))
    bl_heuristics: dict[str, float] = field(default_factory=lambda: dict(BL_HEURISTICS))
    dot_font_size: int = DOT_FONT_SIZE
    dot_font_name: str = DOT_FONT_NAME
    dot_hot_penwidth: float = DOT_HOT_PENWIDTH
    dot_node_sep: float = DOT_NODE_SEP
    dot_rank_sep: float = DOT_RANK_SEP
    dot_splines: str = DOT_SPLINES
    tier_colors: dict[EnergyTier, str] = field(default_factory=lambda: dict(TIER_COLORS))
    tier_font_colors: dict[EnergyTier, str] = field(default_factory=lambda: dict(TIER_FONT_COLORS))


DEFAULT_CONFIG = EFGConfig()


def configure_heuristics(overrides: dict[str, float]) -> None:
    global BL_LOOP_BACK, BL_ERROR, BL_NULL, BL_DEFAULT, BL_HEURISTICS
    if "loop_back" in overrides:
        BL_LOOP_BACK = overrides["loop_back"]
    if "error" in overrides:
        BL_ERROR = overrides["error"]
    if "null_check" in overrides:
        BL_NULL = overrides["null_check"]
    if "default" in overrides:
        BL_DEFAULT = overrides["default"]
    BL_HEURISTICS.update(overrides)


@dataclass
class EFGNode:
    id: int
    text: str
    ntype: str
    energy_j: float = 0.0
    exclusive_energy_j: float = 0.0
    self_ratio: float = 0.0
    rank_score: float = 0.0
    energy_pct: float = 0.0
    calls: int = 0
    energy_per_call_uj: float = 0.0
    estimated_iterations: Optional[float] = None
    tier: EnergyTier = EnergyTier.ZERO
    accuracy: Accuracy = Accuracy.UNKNOWN
    loop_depth: int = 0
    has_alloc: bool = False
    has_call: bool = False


@dataclass
class EFGEdge:
    src: int
    dst: int
    label: str = ""
    probability: float = 1.0
    energy_j: float = 0.0
    accuracy: Accuracy = Accuracy.UNKNOWN
    is_hot: bool = False


@dataclass
class EnergyFlowGraph:
    function: str
    file: str
    total_energy_j: float
    exclusive_energy_j: float
    calls: int
    verdict: str
    accuracy: Accuracy = Accuracy.MEASURED
    nodes: dict[int, EFGNode] = field(default_factory=dict)
    edges: list[EFGEdge] = field(default_factory=list)
    hot_path: list[int] = field(default_factory=list)

    def hot_nodes(self) -> list[EFGNode]:
        return [n for n in self.nodes.values() if n.tier == EnergyTier.HOT]


def _extract_callee_name(text: str) -> Optional[str]:
    idx = text.find('(')
    if idx < 0:
        return None
    prefix = text[:idx].strip()
    dot = prefix.rfind('.')
    eq = prefix.rfind('=')
    start = max(dot, eq, prefix.rfind(' ')) + 1
    name = prefix[start:].strip()
    return name if name else None


def _get_callee_calls(text: str, cg_functions: dict, fn_name: str) -> Optional[int]:
    callee = _extract_callee_name(text)
    if not callee or not cg_functions:
        return None
    cls_prefix = fn_name.rsplit('.', 1)[0] + '.' if '.' in fn_name else ''
    for key in [cls_prefix + callee, callee]:
        if key in cg_functions:
            return cg_functions[key].get("calls", 0)
    return None


def _compute_loop_depths(cfg_edges: list, node_ids: set) -> dict[int, int]:
    """Compute loop depth per node from CFG edges. Nodes inside a LOOP's
    true-branch body get depth incremented."""
    depths: dict[int, int] = {nid: 0 for nid in node_ids}
    # Find back-edges (dst <= src with a label indicating loop)
    # Use iterative BFS from each loop node's true branch
    loop_headers = set()
    for src, dst, label in cfg_edges:
        if label.lower() == "true" and src in node_ids:
            # Check if any edge from body goes back to src (back-edge)
            for s2, d2, _ in cfg_edges:
                if d2 == src and s2 != src and s2 in node_ids:
                    loop_headers.add(src)
                    break
    for lh in loop_headers:
        body = set()
        for src, dst, label in cfg_edges:
            if src == lh and label.lower() == "true":
                _collect_body(dst, lh, cfg_edges, body)
                body.add(dst)
        for nid in body:
            depths[nid] = depths.get(nid, 0) + 1
    return depths


def build_efg(cfg_nodes: list, cfg_edges: list, fn_name: str, fn_file: str,
              cg_entry: dict, cg_functions: Optional[dict] = None,
              config: Optional[EFGConfig] = None) -> EnergyFlowGraph:
    cfg = config or DEFAULT_CONFIG
    rw = cfg.rank_weights
    fn_inclusive = cg_entry.get("energy_j", 0)
    fn_exclusive = cg_entry.get("exclusive_energy_j", fn_inclusive)
    fn_calls = cg_entry.get("calls", 1) or 1
    verdict = cg_entry.get("verdict", "")

    # Compute loop depths from edges (CFG builder may not provide them)
    node_ids = {getattr(n, 'id', i) for i, n in enumerate(cfg_nodes)}
    computed_depths = _compute_loop_depths(cfg_edges, node_ids)

    efg_nodes: dict[int, EFGNode] = {}
    for node in cfg_nodes:
        ntype = getattr(node, 'ntype', None)
        ntype_name = ntype.name if hasattr(ntype, 'name') else str(ntype)
        text = getattr(node, 'text', '')
        # Use CFG-provided loop_depth if available, else computed
        loop_depth = getattr(node, 'loop_depth', 0) or computed_depths.get(node.id, 0)
        has_alloc = 'new ' in text or 'alloc' in text.lower()
        is_instrumentation = any(m in text for m in cfg.instrumentation_markers)
        has_call = ('(' in text and ntype_name not in ('ENTRY', 'EXIT', 'LOOP', 'COND')
                    and not is_instrumentation)

        callee_calls = _get_callee_calls(text, cg_functions, fn_name) if has_call else None
        if callee_calls is not None and callee_calls > 0:
            rank = float(callee_calls)
            acc = Accuracy.ESTIMATED
        elif has_alloc:
            rank = float(rw.get("ALLOC", 5))
            acc = Accuracy.HEURISTIC
        elif has_call:
            rank = float(rw.get("CALL", 3))
            acc = Accuracy.HEURISTIC
        else:
            rank = float(rw.get(ntype_name, 1))
            acc = Accuracy.HEURISTIC

        if ntype_name in ('ENTRY', 'EXIT') or is_instrumentation:
            acc = Accuracy.UNKNOWN
            rank = 0.0

        efg_nodes[node.id] = EFGNode(
            id=node.id, text=text[:cfg.node_text_max], ntype=ntype_name,
            rank_score=rank, calls=fn_calls,
            accuracy=acc, loop_depth=loop_depth,
            has_alloc=has_alloc, has_call=has_call)

    _estimate_loop_iterations(efg_nodes, cfg_edges, fn_calls, cg_functions, fn_name)
    _infer_uninstrumented_energy(efg_nodes, fn_inclusive, fn_exclusive, cg_functions, fn_name)
    _assign_tiers(efg_nodes, cfg.tier_hot, cfg.tier_warm)
    efg_edges = _build_edges(cfg_edges, efg_nodes, cg_functions, fn_name, fn_calls)
    _prorate_call_edges(efg_edges, efg_nodes, cg_functions, fn_name)
    _mark_hot_edges(efg_edges, efg_nodes, cfg.hot_edge_fraction)
    hot_path = _longest_path_dag(efg_nodes, efg_edges)

    return EnergyFlowGraph(
        function=fn_name, file=fn_file,
        total_energy_j=fn_inclusive, exclusive_energy_j=fn_exclusive,
        calls=fn_calls, verdict=verdict,
        nodes=efg_nodes, edges=efg_edges, hot_path=hot_path)


def _infer_uninstrumented_energy(
    nodes: dict[int, EFGNode], fn_inclusive: float, fn_exclusive: float,
    cg_functions: Optional[dict], fn_name: str
) -> None:
    """Level 3 INFERRED: distribute inclusive-exclusive gap across call nodes
    whose callees are NOT in CodeGreen data."""
    if not cg_functions or fn_inclusive <= 0:
        return
    callee_gap = fn_inclusive - fn_exclusive
    if callee_gap <= 0:
        return
    # Sum energy of instrumented callees
    instrumented_callee_energy = 0.0
    uninstrumented_call_nodes: list[EFGNode] = []
    for node in nodes.values():
        if not node.has_call:
            continue
        callee = _extract_callee_name(node.text)
        if not callee:
            continue
        cls_prefix = fn_name.rsplit('.', 1)[0] + '.' if '.' in fn_name else ''
        found = False
        for key in [cls_prefix + callee, callee]:
            if key in cg_functions:
                instrumented_callee_energy += cg_functions[key].get("energy_j", 0)
                found = True
                break
        if not found:
            uninstrumented_call_nodes.append(node)
    if not uninstrumented_call_nodes:
        return
    # Remaining gap after subtracting instrumented callees
    remaining = callee_gap - instrumented_callee_energy
    if remaining <= 0:
        return
    # Distribute evenly across uninstrumented call sites (best we can do)
    per_site = remaining / len(uninstrumented_call_nodes)
    for node in uninstrumented_call_nodes:
        node.energy_j = per_site
        node.accuracy = Accuracy.INFERRED


def _assign_tiers(nodes: dict[int, EFGNode], hot_t: float, warm_t: float) -> None:
    ranked = sorted([n for n in nodes.values() if n.rank_score > 0],
                    key=lambda n: n.rank_score, reverse=True)
    for i, node in enumerate(ranked):
        if i == 0:
            node.tier = EnergyTier.HOT
        elif len(ranked) > 1:
            pos = i / (len(ranked) - 1)
            node.tier = (EnergyTier.HOT if pos <= hot_t else
                         EnergyTier.WARM if pos <= warm_t else EnergyTier.COLD)
        else:
            node.tier = EnergyTier.HOT
    for node in nodes.values():
        if node.rank_score <= 0:
            node.tier = EnergyTier.ZERO


def _estimate_loop_iterations(
    nodes: dict[int, EFGNode], cfg_edges: list,
    fn_calls: int, cg_functions: Optional[dict], fn_name: str
) -> None:
    loop_ids = [nid for nid, n in nodes.items() if n.ntype == "LOOP"]
    for lid in loop_ids:
        body_ids = set()
        for src, dst, label in cfg_edges:
            if src == lid and label.lower() == "true":
                _collect_body(dst, lid, cfg_edges, body_ids)
                body_ids.add(dst)
        best_calls: Optional[int] = None
        for bid in body_ids:
            n = nodes.get(bid)
            if n and n.has_call and cg_functions:
                cc = _get_callee_calls(n.text, cg_functions, fn_name)
                if cc is not None and (best_calls is None or cc > best_calls):
                    best_calls = cc
        if best_calls is not None and fn_calls > 0:
            nodes[lid].estimated_iterations = best_calls / fn_calls
            nodes[lid].accuracy = Accuracy.ESTIMATED
        else:
            nodes[lid].estimated_iterations = None
            nodes[lid].accuracy = Accuracy.UNKNOWN


def _collect_body(start: int, loop_id: int, cfg_edges: list, visited: set) -> None:
    """Iterative BFS to collect loop body nodes (safe for deep nesting)."""
    worklist = [start]
    while worklist:
        node = worklist.pop()
        for src, dst, _ in cfg_edges:
            if src == node and dst != loop_id and dst not in visited:
                visited.add(dst)
                worklist.append(dst)


def _build_edges(
    cfg_edges: list, nodes: dict[int, EFGNode],
    cg_functions: Optional[dict], fn_name: str, fn_calls: int
) -> list[EFGEdge]:
    efg_edges = []
    for src, dst, label in cfg_edges:
        src_node = nodes.get(src)
        dst_node = nodes.get(dst)
        prob = _classify_edge_probability(label, src_node, dst_node)
        acc = Accuracy.HEURISTIC
        if not label:
            acc = Accuracy.MEASURED
        efg_edges.append(EFGEdge(
            src=src, dst=dst, label=label,
            probability=prob, accuracy=acc))
    return efg_edges


_NULL_PATTERN = re.compile(r'(==\s*null|!=\s*null|null\s*==|null\s*!=)', re.IGNORECASE)


def _is_null_check(text: str) -> bool:
    """Detect null comparisons from CFG node text. Post-migration (task #48),
    replace with CNode.is_null_check set via tree-sitter query at build time."""
    return bool(_NULL_PATTERN.search(text))


def _classify_edge_probability(label: str, src_node: Optional[EFGNode],
                                dst_node: Optional[EFGNode]) -> float:
    if not label:
        return 1.0
    label_lower = label.lower()
    if label_lower in ("exception", "catch"):
        return BL_ERROR
    if src_node and _is_null_check(src_node.text):
        if label_lower == "true":
            return 1.0 - BL_NULL
        if label_lower == "false":
            return BL_NULL
    if src_node and src_node.ntype == "LOOP" and label_lower == "true":
        return BL_LOOP_BACK
    if src_node and src_node.ntype == "LOOP" and label_lower == "false":
        return 1.0 - BL_LOOP_BACK
    if label_lower == "true":
        return BL_DEFAULT
    if label_lower == "false":
        return 1.0 - BL_DEFAULT
    return 1.0


def _prorate_call_edges(
    edges: list[EFGEdge], nodes: dict[int, EFGNode],
    cg_functions: Optional[dict], fn_name: str
) -> None:
    if not cg_functions:
        return
    for e in edges:
        src_node = nodes.get(e.src)
        if not src_node or not src_node.has_call:
            continue
        callee = _extract_callee_name(src_node.text)
        if not callee:
            continue
        cls_prefix = fn_name.rsplit('.', 1)[0] + '.' if '.' in fn_name else ''
        callee_data = None
        for key in [cls_prefix + callee, callee]:
            if key in cg_functions:
                callee_data = cg_functions[key]
                break
        if not callee_data:
            continue
        total_callee_calls = callee_data.get("calls", 0) or 1
        is_recursive = callee == fn_name.rsplit('.', 1)[-1]
        energy_src = "exclusive_energy_j" if is_recursive else "energy_j"
        callee_energy = callee_data.get(energy_src, 0)
        site_calls = src_node.calls
        e.energy_j = (callee_energy / total_callee_calls) * site_calls
        e.accuracy = Accuracy.MEASURED


def _mark_hot_edges(edges: list[EFGEdge], nodes: dict[int, EFGNode],
                    fraction: int = HOT_EDGE_FRACTION) -> None:
    if not edges:
        return
    scores = sorted(
        [e.probability * nodes.get(e.src, EFGNode(0, "", "STMT")).rank_score for e in edges],
        reverse=True)
    threshold = scores[max(0, len(scores) // fraction)]
    for e in edges:
        score = e.probability * nodes.get(e.src, EFGNode(0, "", "STMT")).rank_score
        e.is_hot = score >= threshold and score > 0


def _find_sccs(nodes: dict, edges: list) -> list[set[int]]:
    """Tarjan's SCC algorithm for loop-collapse in hot path computation."""
    adj: dict[int, list[int]] = {n: [] for n in nodes}
    for e in edges:
        if e.src in adj:
            adj[e.src].append(e.dst)
    index_counter = [0]
    stack: list[int] = []
    lowlink: dict[int, int] = {}
    index: dict[int, int] = {}
    on_stack: set[int] = set()
    sccs: list[set[int]] = []

    def strongconnect(v: int) -> None:
        index[v] = lowlink[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack.add(v)
        for w in adj.get(v, []):
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], index[w])
        if lowlink[v] == index[v]:
            scc: set[int] = set()
            while True:
                w = stack.pop()
                on_stack.discard(w)
                scc.add(w)
                if w == v:
                    break
            if len(scc) > 1:
                sccs.append(scc)

    for v in nodes:
        if v not in index:
            strongconnect(v)
    return sccs


def _longest_path_dag(nodes: dict, edges: list) -> list[int]:
    """F6: longest-path on SCC-collapsed DAG. SCCs (loops) collapsed to
    representative node with combined rank score."""
    if not nodes:
        return []
    sccs = _find_sccs(nodes, edges)
    # Map each node to its SCC representative (min id in SCC)
    node_to_rep: dict[int, int] = {}
    rep_score: dict[int, float] = {}
    scc_members: dict[int, set[int]] = {}
    for scc in sccs:
        rep = min(scc)
        scc_members[rep] = scc
        rep_score[rep] = sum(nodes[n].rank_score for n in scc if n in nodes)
        for n in scc:
            node_to_rep[n] = rep
    # Nodes not in any SCC map to themselves
    for n in nodes:
        if n not in node_to_rep:
            node_to_rep[n] = n
            rep_score[n] = nodes[n].rank_score

    # Build DAG on representatives
    dag_nodes = set(node_to_rep.values())
    dag_adj: dict[int, list[tuple[int, float]]] = {n: [] for n in dag_nodes}
    seen_edges: set[tuple[int, int]] = set()
    for e in edges:
        u, v = node_to_rep.get(e.src, e.src), node_to_rep.get(e.dst, e.dst)
        if u != v and (u, v) not in seen_edges:
            dag_adj[u].append((v, e.probability))
            seen_edges.add((u, v))

    # Topological sort via Kahn's algorithm
    in_degree = {n: 0 for n in dag_nodes}
    for u in dag_adj:
        for v, _ in dag_adj[u]:
            in_degree[v] = in_degree.get(v, 0) + 1
    queue = sorted([n for n in dag_nodes if in_degree.get(n, 0) == 0])
    topo: list[int] = []
    while queue:
        u = queue.pop(0)
        topo.append(u)
        for v, _ in dag_adj.get(u, []):
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)
                queue.sort()

    # Longest path DP on DAG
    dist = {n: 0.0 for n in dag_nodes}
    parent = {n: -1 for n in dag_nodes}
    for u in topo:
        for v, w in dag_adj.get(u, []):
            score = dist[u] + rep_score.get(v, 0) * w
            if score > dist[v]:
                dist[v] = score
                parent[v] = u
    if not dist:
        return list(nodes.keys())[:1]
    end = max(dist, key=dist.get)
    path_reps: list[int] = []
    current = end
    while current != -1:
        path_reps.append(current)
        current = parent[current]
    path_reps.reverse()

    # Expand SCC representatives back to original nodes
    path: list[int] = []
    for rep in path_reps:
        if rep in scc_members:
            path.extend(sorted(scc_members[rep]))
        else:
            path.append(rep)
    return path


# --- Serializers ---

def _dot_escape(text: str) -> str:
    return text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ').replace('\r', '')


def _truncate_label(text: str, max_len: int) -> str:
    """Truncate at syntax boundary (semicolon, paren, comma)."""
    if len(text) <= max_len:
        return text
    # Try to cut at a natural boundary
    for sep in (';', ',', ')', '(', ' '):
        idx = text.rfind(sep, 0, max_len)
        if idx > max_len // 2:
            return text[:idx + 1] + "..."
    return text[:max_len] + "..."


def efg_to_text(efg: EnergyFlowGraph, config: Optional[EFGConfig] = None) -> str:
    cfg = config or DEFAULT_CONFIG
    lines = [f"EFG: {efg.function} ({efg.exclusive_energy_j:.1f}J exclusive, "
             f"{efg.total_energy_j:.1f}J total, {efg.calls} calls, {efg.verdict})"]
    hot = [n.id for n in efg.nodes.values() if n.tier == EnergyTier.HOT]
    if efg.hot_path:
        lines.append(f"  Hot path: {' -> '.join(str(n) for n in efg.hot_path)}")
    for node in sorted(efg.nodes.values(), key=lambda n: n.rank_score, reverse=True):
        if node.rank_score < cfg.min_rank_display or node.ntype in ('ENTRY', 'EXIT'):
            continue
        indent = "  " + "  " * node.loop_depth
        tag = "CALL" if node.has_call else "ALLOC" if node.has_alloc else node.ntype
        iters = f" ~{node.estimated_iterations:.0f}x" if node.estimated_iterations else ""
        lines.append(f"{indent}{node.tier.name} [{node.accuracy.name}] "
                     f"rank={node.rank_score:.0f}{iters} {tag}: {node.text}")
    # Show branch probabilities
    branches = [(e.src, e.label, e.probability) for e in efg.edges if e.label]
    if branches:
        lines.append("  Branches:")
        for src, label, prob in branches:
            src_text = efg.nodes[src].text[:30] if src in efg.nodes else str(src)
            lines.append(f"    {src_text} --{label}--> p={prob:.2f}")
    return "\n".join(lines)


def efg_to_dot(efg: EnergyFlowGraph, config: Optional[EFGConfig] = None) -> str:
    cfg = config or DEFAULT_CONFIG
    lines = [
        f'digraph "{_dot_escape(efg.function)}" {{',
        f'  rankdir=TB;',
        f'  fontname="{cfg.dot_font_name}"; fontsize={cfg.dot_font_size};',
        f'  node [fontname="{cfg.dot_font_name}" fontsize=10 margin="0.1,0.05"];',
        f'  edge [fontname="{cfg.dot_font_name}" fontsize=9];',
        f'  nodesep={cfg.dot_node_sep}; ranksep={cfg.dot_rank_sep};',
        f'  splines={cfg.dot_splines};',
        f'  label="{_dot_escape(efg.function)}\\n'
        f'{efg.exclusive_energy_j:.1f}J | {efg.calls} calls | {efg.verdict}";',
        f'  labelloc=t;',
    ]
    # Group nodes by loop depth into subgraphs
    max_depth = max((n.loop_depth for n in efg.nodes.values()), default=0)
    if max_depth > 0:
        for depth in range(max_depth, 0, -1):
            depth_nodes = [n for n in efg.nodes.values() if n.loop_depth >= depth]
            if depth_nodes:
                lines.append(f'  subgraph cluster_loop{depth} {{')
                lines.append(f'    style=dashed; color=gray; label="loop depth {depth}";')
                for node in depth_nodes:
                    lines.append(f'    {node.id};')
                lines.append('  }')
    for node in efg.nodes.values():
        color = cfg.tier_colors.get(node.tier, '#F0F0F0')
        fc = cfg.tier_font_colors.get(node.tier, 'black')
        shape = NTYPE_SHAPES.get(node.ntype, 'ellipse')
        short = _truncate_label(_dot_escape(node.text), cfg.dot_label_max)
        iters = f"\\n~{node.estimated_iterations:.0f}x" if node.estimated_iterations else ""
        label = f"{short}\\nrank={node.rank_score:.0f} [{node.accuracy.name}]{iters}"
        lines.append(f'  {node.id} [label="{label}" shape={shape} style=filled '
                     f'fillcolor="{color}" fontcolor={fc}];')
    for edge in efg.edges:
        attrs = []
        if edge.label:
            attrs.append(f'label="{edge.label} p={edge.probability:.2f}"')
        if edge.energy_j > 0:
            attrs.append(f'taillabel="{edge.energy_j:.1f}J"')
        if edge.is_hot:
            attrs.append(f'color="#CC0000" penwidth={cfg.dot_hot_penwidth}')
        attr_str = f' [{", ".join(attrs)}]' if attrs else ''
        lines.append(f'  {edge.src} -> {edge.dst}{attr_str};')
    lines.append('}')
    return '\n'.join(lines)


def efg_to_mermaid(efg: EnergyFlowGraph, config: Optional[EFGConfig] = None) -> str:
    cfg = config or DEFAULT_CONFIG
    tier_class = {EnergyTier.HOT: 'hot', EnergyTier.WARM: 'warm',
                  EnergyTier.COLD: 'cold', EnergyTier.ZERO: 'zero'}
    lines = ['graph TD']
    for node in efg.nodes.values():
        cls = tier_class.get(node.tier, 'zero')
        safe = node.text.replace('"', "'").replace('\n', ' ').replace('<', '&lt;').replace('>', '&gt;')
        short = _truncate_label(safe, cfg.dot_label_max)
        label = f"{short}<br/>rank={node.rank_score:.0f}"
        lines.append(f'    N{node.id}["{label}"]:::{cls}')
    for edge in efg.edges:
        label = f"|{edge.label} p={edge.probability:.2f}|" if edge.label else ""
        style = " " if not edge.is_hot else " "
        lines.append(f'    N{edge.src} -->{label} N{edge.dst}')
    for tier_name, css_class in tier_class.items():
        color = cfg.tier_colors.get(tier_name, '#F0F0F0')
        fc = cfg.tier_font_colors.get(tier_name, 'black')
        lines.append(f'    classDef {css_class} fill:{color},color:{fc}')
    return '\n'.join(lines)


def efg_to_json(efg: EnergyFlowGraph) -> dict:
    return {
        "function": efg.function, "file": efg.file,
        "total_energy_j": efg.total_energy_j,
        "exclusive_energy_j": efg.exclusive_energy_j,
        "calls": efg.calls, "verdict": efg.verdict,
        "accuracy": efg.accuracy.name,
        "nodes": [{"id": n.id, "text": n.text, "ntype": n.ntype,
                    "rank_score": n.rank_score, "energy_j": n.energy_j,
                    "exclusive_energy_j": n.exclusive_energy_j,
                    "self_ratio": n.self_ratio, "energy_pct": n.energy_pct,
                    "energy_per_call_uj": n.energy_per_call_uj,
                    "estimated_iterations": n.estimated_iterations,
                    "tier": n.tier.name, "accuracy": n.accuracy.name,
                    "has_alloc": n.has_alloc, "has_call": n.has_call,
                    "loop_depth": n.loop_depth, "calls": n.calls}
                   for n in efg.nodes.values()],
        "edges": [{"src": e.src, "dst": e.dst, "label": e.label,
                    "probability": e.probability, "energy_j": e.energy_j,
                    "accuracy": e.accuracy.name, "is_hot": e.is_hot}
                   for e in efg.edges],
        "hot_path": efg.hot_path,
    }
