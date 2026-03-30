"""Flow-sensitive feature extraction from per-method CFG + dataflow."""

from collections import deque
from dataclasses import dataclass

from src.analysis.cfg.types import CFG, NType
from src.analysis.cfg.builder import build_cfg, build_per_method_cfgs
from src.analysis.cfg.dataflow import reaching_defs, def_use_chains
from src.analysis.cfg.pdg import extract_pdg_features, PDGFeatures


@dataclass
class FlowFeatures:
    hot_path_allocs: int = 0
    loop_carried_vars: int = 0
    live_vars_at_loops: int = 0
    cfg_node_count: int = 0
    cfg_edge_count: int = 0
    loop_count: int = 0
    branch_count: int = 0
    max_cfg_depth: int = 0
    def_use_chain_count: int = 0
    cyclomatic_complexity: int = 0
    total_callsite_count: int = 0
    alloc_site_count: int = 0
    cold_path_allocs: int = 0
    hot_unconditional_allocs: int = 0
    control_dependent_stmts: int = 0
    data_dep_on_loop_var: int = 0
    max_control_depth: int = 0

    def to_dict(self) -> dict:
        return {
            "hot_path_allocs": self.hot_path_allocs,
            "loop_carried_vars": self.loop_carried_vars,
            "live_vars_at_loops": self.live_vars_at_loops,
            "cfg_node_count": self.cfg_node_count,
            "cfg_edge_count": self.cfg_edge_count,
            "loop_count": self.loop_count,
            "branch_count": self.branch_count,
            "max_cfg_depth": self.max_cfg_depth,
            "def_use_chain_count": self.def_use_chain_count,
            "cyclomatic_complexity": self.cyclomatic_complexity,
            "total_callsite_count": self.total_callsite_count,
            "alloc_site_count": self.alloc_site_count,
            "cold_path_allocs": self.cold_path_allocs,
            "hot_unconditional_allocs": self.hot_unconditional_allocs,
            "control_dependent_stmts": self.control_dependent_stmts,
            "data_dep_on_loop_var": self.data_dep_on_loop_var,
            "max_control_depth": self.max_control_depth,
        }

    def to_vector(self) -> list[float]:
        return [float(v) for v in self.to_dict().values()]


def extract_flow_features(code: str) -> FlowFeatures:
    method_cfgs = build_per_method_cfgs(code)
    if not method_cfgs:
        return _features_from_cfg(build_cfg(code))

    total = FlowFeatures()
    for _, cfg in method_cfgs:
        f = _features_from_cfg(cfg)
        total.hot_path_allocs += f.hot_path_allocs
        total.loop_carried_vars += f.loop_carried_vars
        total.live_vars_at_loops += f.live_vars_at_loops
        total.cfg_node_count += f.cfg_node_count
        total.cfg_edge_count += f.cfg_edge_count
        total.loop_count += f.loop_count
        total.branch_count += f.branch_count
        total.max_cfg_depth = max(total.max_cfg_depth, f.max_cfg_depth)
        total.def_use_chain_count += f.def_use_chain_count
        total.cyclomatic_complexity += f.cyclomatic_complexity
        total.total_callsite_count += f.total_callsite_count
        total.alloc_site_count += f.alloc_site_count
        total.cold_path_allocs += f.cold_path_allocs
        total.hot_unconditional_allocs += f.hot_unconditional_allocs
        total.control_dependent_stmts += f.control_dependent_stmts
        total.data_dep_on_loop_var += f.data_dep_on_loop_var
        total.max_control_depth = max(total.max_control_depth, f.max_control_depth)
    return total


def _features_from_cfg(cfg: CFG) -> FlowFeatures:
    in_f = reaching_defs(cfg)
    chains = def_use_chains(cfg, in_f)

    loop_nodes = {nid for nid, n in cfg.nodes.items() if n.ntype == NType.LOOP}
    cond_nodes = {nid for nid, n in cfg.nodes.items() if n.ntype == NType.COND}

    hot_allocs = 0
    for nid, node in cfg.nodes.items():
        if node.has_alloc and _enclosing_loops(cfg, nid, loop_nodes):
            hot_allocs += 1

    carried = set()
    for var, def_nid, use_nid in chains:
        if def_nid in loop_nodes or use_nid in loop_nodes:
            carried.add(var)
        for ln in loop_nodes:
            ln_node = cfg.nodes[ln]
            if def_nid in ln_node.succs and use_nid in ln_node.succs:
                carried.add(var)

    live_at_loops = 0
    for ln in loop_nodes:
        live_at_loops += len({v for v, _ in in_f.get(ln, set())})

    edges = sum(len(n.succs) for n in cfg.nodes.values())
    alloc_sites = sum(1 for n in cfg.nodes.values() if n.has_alloc)
    callsites = sum(len(n.calls) for n in cfg.nodes.values())
    cyclomatic = len(cond_nodes) + len(loop_nodes) + 1

    pdg = extract_pdg_features(cfg, in_f=in_f, chains=chains)

    return FlowFeatures(
        hot_path_allocs=hot_allocs,
        loop_carried_vars=len(carried),
        live_vars_at_loops=live_at_loops,
        cfg_node_count=len(cfg.nodes),
        cfg_edge_count=edges,
        loop_count=len(loop_nodes),
        branch_count=len(cond_nodes),
        max_cfg_depth=_max_depth(cfg),
        def_use_chain_count=len(chains),
        cyclomatic_complexity=cyclomatic,
        total_callsite_count=callsites,
        alloc_site_count=alloc_sites,
        cold_path_allocs=pdg.cold_path_allocs,
        hot_unconditional_allocs=pdg.hot_unconditional_allocs,
        control_dependent_stmts=pdg.control_dependent_stmts,
        data_dep_on_loop_var=pdg.data_dep_on_loop_var,
        max_control_depth=pdg.max_control_depth,
    )


def _enclosing_loops(cfg: CFG, nid: int, loop_nodes: set[int]) -> set[int]:
    visited: set[int] = set()
    stack = [nid]
    while stack:
        cur = stack.pop()
        if cur in visited:
            continue
        visited.add(cur)
        for p in cfg.nodes[cur].preds:
            stack.append(p)
    return visited & loop_nodes


def _max_depth(cfg: CFG) -> int:
    if cfg.entry == -1:
        return 0
    depth: dict[int, int] = {}
    queue = deque([(cfg.entry, 0)])
    max_visits = len(cfg.nodes) * 2
    visits = 0
    while queue and visits < max_visits:
        nid, d = queue.popleft()
        visits += 1
        if nid in depth and depth[nid] >= d:
            continue
        depth[nid] = d
        for s in cfg.nodes[nid].succs:
            nd = d + 1
            if s not in depth or nd > depth[s]:
                queue.append((s, nd))
    return max(depth.values()) if depth else 0
