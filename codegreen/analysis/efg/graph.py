"""EFG construction: annotate CFG nodes with CodeGreen energy data.

Design principles:
- Method-level energy is MEASURED (from CodeGreen checkpoints).
- Statement-level energy is a RANKING HEURISTIC, not Joule values.
- Edge weights represent EXECUTION FREQUENCY (probability), not energy cost.
- Ball & Larus (1993) heuristics for branch probabilities when no data available.
- Call edge energy is PRO-RATED per call site.
- Hot path uses longest-path on SCC-collapsed DAG.
"""

from typing import Optional

from codegreen.analysis.efg.heuristics import (
    DEFAULT_CONFIG, EFGConfig, HOT_EDGE_FRACTION, classify_edge_probability)
from codegreen.analysis.efg.paths import longest_path_dag
from codegreen.analysis.efg.types import (
    Accuracy, EFGEdge, EFGNode, EnergyFlowGraph, EnergyTier)


def extract_callee_name(text: str) -> Optional[str]:
    idx = text.find('(')
    if idx < 0:
        return None
    prefix = text[:idx].strip()
    dot = prefix.rfind('.')
    eq = prefix.rfind('=')
    start = max(dot, eq, prefix.rfind(' ')) + 1
    name = prefix[start:].strip()
    return name if name else None


def get_callee_calls(text: str, cg_functions: dict, fn_name: str) -> Optional[int]:
    callee = extract_callee_name(text)
    if not callee or not cg_functions:
        return None
    cls_prefix = fn_name.rsplit('.', 1)[0] + '.' if '.' in fn_name else ''
    for key in [cls_prefix + callee, callee]:
        if key in cg_functions:
            return cg_functions[key].get("calls", 0)
    return None


def compute_loop_depths(cfg_edges: list, node_ids: set) -> dict[int, int]:
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
                collect_body(dst, lh, cfg_edges, body)
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
    computed_depths = compute_loop_depths(cfg_edges, node_ids)

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

        callee_calls = get_callee_calls(text, cg_functions, fn_name) if has_call else None
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

    estimate_loop_iterations(efg_nodes, cfg_edges, fn_calls, cg_functions, fn_name)
    infer_uninstrumented_energy(efg_nodes, fn_inclusive, fn_exclusive, cg_functions, fn_name)
    assign_tiers(efg_nodes, cfg.tier_hot, cfg.tier_warm)
    efg_edges = build_edges(cfg_edges, efg_nodes, cg_functions, fn_name, fn_calls)
    prorate_call_edges(efg_edges, efg_nodes, cg_functions, fn_name)
    mark_hot_edges(efg_edges, efg_nodes, cfg.hot_edge_fraction)
    hot_path = longest_path_dag(efg_nodes, efg_edges)

    return EnergyFlowGraph(
        function=fn_name, file=fn_file,
        total_energy_j=fn_inclusive, exclusive_energy_j=fn_exclusive,
        calls=fn_calls, verdict=verdict,
        nodes=efg_nodes, edges=efg_edges, hot_path=hot_path)


def infer_uninstrumented_energy(
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
        callee = extract_callee_name(node.text)
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


def assign_tiers(nodes: dict[int, EFGNode], hot_t: float, warm_t: float) -> None:
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


def estimate_loop_iterations(
    nodes: dict[int, EFGNode], cfg_edges: list,
    fn_calls: int, cg_functions: Optional[dict], fn_name: str
) -> None:
    loop_ids = [nid for nid, n in nodes.items() if n.ntype == "LOOP"]
    for lid in loop_ids:
        body_ids = set()
        for src, dst, label in cfg_edges:
            if src == lid and label.lower() == "true":
                collect_body(dst, lid, cfg_edges, body_ids)
                body_ids.add(dst)
        best_calls: Optional[int] = None
        for bid in body_ids:
            n = nodes.get(bid)
            if n and n.has_call and cg_functions:
                cc = get_callee_calls(n.text, cg_functions, fn_name)
                if cc is not None and (best_calls is None or cc > best_calls):
                    best_calls = cc
        if best_calls is not None and fn_calls > 0:
            nodes[lid].estimated_iterations = best_calls / fn_calls
            nodes[lid].accuracy = Accuracy.ESTIMATED
        else:
            nodes[lid].estimated_iterations = None
            nodes[lid].accuracy = Accuracy.UNKNOWN


def collect_body(start: int, loop_id: int, cfg_edges: list, visited: set) -> None:
    """Iterative BFS to collect loop body nodes (safe for deep nesting)."""
    worklist = [start]
    while worklist:
        node = worklist.pop()
        for src, dst, _ in cfg_edges:
            if src == node and dst != loop_id and dst not in visited:
                visited.add(dst)
                worklist.append(dst)


def build_edges(
    cfg_edges: list, nodes: dict[int, EFGNode],
    cg_functions: Optional[dict], fn_name: str, fn_calls: int
) -> list[EFGEdge]:
    efg_edges = []
    for src, dst, label in cfg_edges:
        src_node = nodes.get(src)
        dst_node = nodes.get(dst)
        prob = classify_edge_probability(label, src_node, dst_node)
        acc = Accuracy.HEURISTIC
        if not label:
            acc = Accuracy.MEASURED
        efg_edges.append(EFGEdge(
            src=src, dst=dst, label=label,
            probability=prob, accuracy=acc))
    return efg_edges


def prorate_call_edges(
    edges: list[EFGEdge], nodes: dict[int, EFGNode],
    cg_functions: Optional[dict], fn_name: str
) -> None:
    if not cg_functions:
        return
    for e in edges:
        src_node = nodes.get(e.src)
        if not src_node or not src_node.has_call:
            continue
        callee = extract_callee_name(src_node.text)
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


def mark_hot_edges(edges: list[EFGEdge], nodes: dict[int, EFGNode],
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


_extract_callee_name = extract_callee_name
_get_callee_calls = get_callee_calls
_compute_loop_depths = compute_loop_depths
_infer_uninstrumented_energy = infer_uninstrumented_energy
_assign_tiers = assign_tiers
_estimate_loop_iterations = estimate_loop_iterations
_collect_body = collect_body
_build_edges = build_edges
_prorate_call_edges = prorate_call_edges
_mark_hot_edges = mark_hot_edges
