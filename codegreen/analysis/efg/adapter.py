"""Bridge from codegreen.analysis.cfg to build_efg's plain node/edge lists.

build_efg is deliberately CFG-representation-agnostic: it takes `cfg_nodes: list`
and `cfg_edges: list[(src, dst, label)]`, not a CFG object, so it can sit behind
any front end. Nothing in this package closed that gap for codegreen's own
tree-sitter CFG builder until now. The only conversion that existed was 14
inline lines in a downstream consumer, so every other caller had to reinvent it.
"""

from typing import Optional

from codegreen.analysis.cfg.builder import build_per_method_cfgs
from codegreen.analysis.cfg.types import CFG
from codegreen.analysis.efg.graph import build_efg
from codegreen.analysis.efg.heuristics import EFGConfig
from codegreen.analysis.efg.types import EnergyFlowGraph


def cfg_to_efg_inputs(cfg: CFG) -> tuple[list, list[tuple[int, int, str]]]:
    """(cfg_nodes, cfg_edges) in the shape build_efg expects, from a real CFG."""
    nodes = list(cfg.nodes.values())
    edges = [(nid, succ, node.edge_labels.get(succ, ""))
             for nid, node in cfg.nodes.items() for succ in node.succs]
    return nodes, edges


def strip_to_short(fqn: str) -> str:
    """Bare method name: drop a class prefix and any JVM-style descriptor."""
    return fqn.split(".")[-1].split(":")[-1]


def build_efg_for_method(
    source: str, fqn: str, fn_file: str = "",
    cg_entry: Optional[dict] = None, cg_functions: Optional[dict] = None,
    config: Optional[EFGConfig] = None,
) -> EnergyFlowGraph:
    """Parse `source`, find the method matching `fqn`, and build its EFG.

    `fqn` may be the bare method name or `Class.method`; both are tried
    because CodeGreen's own energy data and a tree-sitter CFG don't always
    agree on which form they key by. Raises KeyError naming every method
    found in `source` if none matches, so a caller sees the actual mismatch
    instead of a bare "not found".
    """
    short = strip_to_short(fqn)
    per_method = build_per_method_cfgs(source)
    match = next((cfg for name, cfg in per_method if name in (fqn, short)), None)
    if match is None:
        found = [name for name, _ in per_method]
        raise KeyError(f"{fqn!r} not found; methods in source: {found}")
    nodes, edges = cfg_to_efg_inputs(match)
    return build_efg(nodes, edges, fqn, fn_file,
                     cg_entry=cg_entry or {}, cg_functions=cg_functions, config=config)
