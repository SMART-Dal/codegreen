"""Dataflow analyses: reaching definitions and def-use chains."""

from src.analysis.cfg.types import CFG


def reaching_defs(cfg: CFG, max_iterations: int = 0) -> dict[int, set[tuple[str, int]]]:
    """Iterative fixpoint reaching definitions solver."""
    if max_iterations <= 0:
        max_iterations = max(len(cfg.nodes) * 10, 100)
    in_f: dict[int, set[tuple[str, int]]] = {n: set() for n in cfg.nodes}
    out_f: dict[int, set[tuple[str, int]]] = {n: set() for n in cfg.nodes}
    changed = True
    iters = 0
    while changed and iters < max_iterations:
        changed = False
        iters += 1
        for nid, node in cfg.nodes.items():
            new_in: set[tuple[str, int]] = set()
            for p in node.preds:
                new_in |= out_f[p]
            gen = {(v, nid) for v in node.defs}
            kill = {f for f in new_in if f[0] in node.defs}
            new_out = (new_in - kill) | gen
            if new_out != out_f[nid]:
                out_f[nid] = new_out
                changed = True
            in_f[nid] = new_in
    return in_f


def def_use_chains(cfg: CFG, in_facts: dict[int, set[tuple[str, int]]]) -> list[tuple[str, int, int]]:
    """Extract def-use chains: (variable, def_node, use_node)."""
    chains = []
    for nid, node in cfg.nodes.items():
        for var in node.uses:
            for def_var, def_nid in in_facts.get(nid, set()):
                if def_var == var:
                    chains.append((var, def_nid, nid))
    return chains


def use_def_chains(cfg: CFG, in_facts: dict[int, set[tuple[str, int]]]) -> dict[str, list[tuple[int, list[int]]]]:
    """Extract use-def chains: for each variable, maps use_node -> [def_nodes].

    Adapted from tree-climber UseDefSolver. Reverse direction of def-use chains.
    """
    result: dict[str, list[tuple[int, list[int]]]] = {}
    for nid, node in cfg.nodes.items():
        for var in node.uses:
            defs = [d for v, d in in_facts.get(nid, set()) if v == var]
            if defs:
                result.setdefault(var, []).append((nid, sorted(defs)))
    return result
