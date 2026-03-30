"""Program Dependence Graph: control + data dependency edges.

Computes post-dominators on the CFG to derive control dependencies,
then combines with def-use chains for data dependencies.

Control dependency: node S is control-dependent on node C if
C is a branch/loop whose outcome determines whether S executes.
This distinguishes hot-path code (always executes in loop body)
from cold-path code (only executes on a rare branch within a loop).

Energy-relevant features derived from PDG:
- cold_path_allocs: allocations control-dependent on a branch inside a loop
  (vs hot_path_allocs which counts all loop allocations)
- control_dependent_stmts: total statements under conditional control
- data_dependent_on_loop_var: statements whose values depend on loop induction variables
"""

from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field

from codegreen.analysis.cfg.types import CFG, CNode, NType
from codegreen.analysis.cfg.dataflow import reaching_defs, def_use_chains


def compute_post_dominators(cfg: CFG) -> dict[int, set[int]]:
    """Compute post-dominator sets for each node.

    A node P post-dominates node N if every path from N to any exit
    must pass through P. Uses iterative intersection algorithm.
    """
    if not cfg.nodes or cfg.entry == -1:
        return {}

    all_ids = set(cfg.nodes.keys())
    exit_ids = set()
    for nid, node in cfg.nodes.items():
        if node.ntype == NType.EXIT or not node.succs:
            exit_ids.add(nid)
    if not exit_ids:
        exit_ids = {max(cfg.nodes.keys())}

    pdom: dict[int, set[int]] = {}
    for nid in cfg.nodes:
        if nid in exit_ids:
            pdom[nid] = {nid}
        else:
            pdom[nid] = set(all_ids)

    changed = True
    max_iters = len(cfg.nodes) * 3
    iters = 0
    while changed and iters < max_iters:
        changed = False
        iters += 1
        for nid in cfg.nodes:
            if nid in exit_ids:
                continue
            node = cfg.nodes[nid]
            succs = [s for s in node.succs if s in pdom]
            if not succs:
                new_pdom = {nid}
            else:
                new_pdom = set.intersection(*(pdom[s] for s in succs))
                new_pdom = new_pdom | {nid}
            if new_pdom != pdom[nid]:
                pdom[nid] = new_pdom
                changed = True

    return pdom


def compute_immediate_post_dominator(cfg: CFG, pdom: dict[int, set[int]]) -> dict[int, int | None]:
    """Compute immediate post-dominator for each node.

    The ipdom of N is the closest strict post-dominator: the node P such that
    P post-dominates N, P != N, and no other strict post-dominator of N
    is post-dominated by P.
    """
    ipdom: dict[int, int | None] = {}
    for nid in cfg.nodes:
        strict = pdom.get(nid, set()) - {nid}
        if not strict:
            ipdom[nid] = None
            continue
        candidates = list(strict)
        candidates.sort(key=lambda c: len(pdom.get(c, set())))
        ipdom[nid] = candidates[0]
    return ipdom


@dataclass
class ControlDep:
    source: int
    target: int
    label: str  # "true", "false", or ""


def compute_control_dependencies(cfg: CFG, ipdom: dict[int, int | None]) -> list[ControlDep]:
    """Compute control dependency edges.

    Node S is control-dependent on node C if:
    1. There exists a path from C to S in the CFG
    2. S post-dominates every node on that path (except C)
    3. S does NOT post-dominate C

    Equivalently: for each edge (A, B) in CFG where B does NOT
    post-dominate A, all nodes on the path from B to ipdom(A)
    (exclusive) in the post-dominator tree are control-dependent on A.
    """
    pdom = compute_post_dominators(cfg)
    deps: list[ControlDep] = []
    seen = set()

    for a_id, a_node in cfg.nodes.items():
        for b_id in a_node.succs:
            if b_id not in pdom.get(a_id, set()) or b_id == a_id:
                label = a_node.edge_labels.get(b_id, "")
                ipd_a = ipdom.get(a_id)
                runner = b_id
                visited = set()
                while runner is not None and runner != ipd_a and runner not in visited:
                    visited.add(runner)
                    key = (a_id, runner)
                    if key not in seen:
                        seen.add(key)
                        deps.append(ControlDep(source=a_id, target=runner, label=label))
                    runner = ipdom.get(runner)

    return deps


@dataclass
class PDGFeatures:
    cold_path_allocs: int = 0
    hot_unconditional_allocs: int = 0
    control_dependent_stmts: int = 0
    data_dep_on_loop_var: int = 0
    max_control_depth: int = 0
    total_control_edges: int = 0
    total_data_edges: int = 0

    def to_dict(self) -> dict:
        return {
            "cold_path_allocs": self.cold_path_allocs,
            "hot_unconditional_allocs": self.hot_unconditional_allocs,
            "control_dependent_stmts": self.control_dependent_stmts,
            "data_dep_on_loop_var": self.data_dep_on_loop_var,
            "max_control_depth": self.max_control_depth,
            "total_control_edges": self.total_control_edges,
            "total_data_edges": self.total_data_edges,
        }

    def to_vector(self) -> list[float]:
        return [float(v) for v in self.to_dict().values()]


def extract_pdg_features(cfg: CFG, in_f: dict | None = None, chains: list | None = None) -> PDGFeatures:
    """Extract PDG-based features from a single method CFG.

    Accepts pre-computed reaching defs and def-use chains to avoid
    duplicate dataflow computation when called from _features_from_cfg.
    """
    pdom = compute_post_dominators(cfg)
    ipdom = compute_immediate_post_dominator(cfg, pdom)
    ctrl_deps = compute_control_dependencies(cfg, ipdom)

    if in_f is None:
        in_f = reaching_defs(cfg)
    if chains is None:
        chains = def_use_chains(cfg, in_f)

    loop_nodes = {nid for nid, n in cfg.nodes.items() if n.ntype == NType.LOOP}
    cond_nodes = {nid for nid, n in cfg.nodes.items() if n.ntype == NType.COND}
    branch_nodes = loop_nodes | cond_nodes

    ctrl_dep_targets = {d.target for d in ctrl_deps}
    ctrl_dep_by_target: dict[int, list[ControlDep]] = {}
    for d in ctrl_deps:
        ctrl_dep_by_target.setdefault(d.target, []).append(d)

    allocs_on_branch_in_loop = 0
    allocs_unconditional_in_loop = 0
    for nid, node in cfg.nodes.items():
        if not node.has_alloc:
            continue
        in_loop = _is_in_loop(cfg, nid, loop_nodes)
        if not in_loop:
            continue
        dep_on_branch = any(
            d.source in cond_nodes for d in ctrl_dep_by_target.get(nid, [])
        )
        if dep_on_branch:
            allocs_on_branch_in_loop += 1
        else:
            allocs_unconditional_in_loop += 1

    loop_var_defs = set()
    for ln in loop_nodes:
        for v in cfg.nodes[ln].uses:
            loop_var_defs.add(v)

    data_dep_on_loop = 0
    for var, def_nid, use_nid in chains:
        if var in loop_var_defs and use_nid not in loop_nodes:
            data_dep_on_loop += 1

    max_ctrl_depth = 0
    if ctrl_deps:
        depth: dict[int, int] = {}
        for d in ctrl_deps:
            src_d = depth.get(d.source, 0)
            depth[d.target] = max(depth.get(d.target, 0), src_d + 1)
        max_ctrl_depth = max(depth.values()) if depth else 0

    return PDGFeatures(
        cold_path_allocs=allocs_on_branch_in_loop,
        hot_unconditional_allocs=allocs_unconditional_in_loop,
        control_dependent_stmts=len(ctrl_dep_targets),
        data_dep_on_loop_var=data_dep_on_loop,
        max_control_depth=max_ctrl_depth,
        total_control_edges=len(ctrl_deps),
        total_data_edges=len(chains),
    )


def _is_in_loop(cfg: CFG, nid: int, loop_nodes: set[int]) -> bool:
    visited: set[int] = set()
    stack = [nid]
    while stack:
        cur = stack.pop()
        if cur in visited:
            continue
        visited.add(cur)
        if cur in loop_nodes:
            return True
        for p in cfg.nodes[cur].preds:
            stack.append(p)
    return False
