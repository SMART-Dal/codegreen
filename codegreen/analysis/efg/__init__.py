"""Energy Flow Graph: CFG nodes annotated with measured CodeGreen energy.

    from codegreen.analysis.efg import build_efg, efg_to_text
    efg = build_efg(cfg_nodes, cfg_edges, "Class.method", "File.java", cg_entry)
    print(efg_to_text(efg))

Module map:
    types.py       EFGNode, EFGEdge, EnergyFlowGraph, Accuracy, EnergyTier
    heuristics.py  Ball & Larus branch probabilities, EFGConfig, tunables
    graph.py       build_efg and the annotation passes it runs
    paths.py       Tarjan SCC collapse and longest-path hot path
    serialize.py   efg_to_text / efg_to_dot / efg_to_mermaid / efg_to_json
    adapter.py     bridge from codegreen.analysis.cfg (CFG/CNode) to build_efg

See README.md in this folder for a runnable quickstart and the list of known
issues (loop-depth misdetection, a recursion-depth crash on ~1000+ node
methods, several EFGNode fields that are always 0.0) an intern should expect
to hit first.

The Ball & Larus constants are re-exported through __getattr__ rather than bound
at import, so `configure_heuristics` stays visible through this package the way
it is through the module that owns them.
"""

from codegreen.analysis.efg import heuristics as _heuristics
from codegreen.analysis.efg.adapter import (
    build_efg_for_method, cfg_to_efg_inputs, strip_to_short)
from codegreen.analysis.efg.graph import (
    assign_tiers, build_edges, build_efg, collect_body, compute_loop_depths,
    estimate_loop_iterations, extract_callee_name, get_callee_calls,
    infer_uninstrumented_energy, mark_hot_edges, prorate_call_edges)
from codegreen.analysis.efg.heuristics import (
    BL_HEURISTICS, DEFAULT_CONFIG, DOT_LABEL_MAX_LEN, EFGConfig,
    HOT_EDGE_FRACTION, INSTRUMENTATION_MARKERS, MIN_RANK_FOR_DISPLAY,
    NODE_TEXT_MAX_LEN, NTYPE_SHAPES, RANK_WEIGHTS, TIER_COLORS,
    TIER_FONT_COLORS, TIER_HOT_THRESHOLD, TIER_WARM_THRESHOLD,
    classify_edge_probability, configure_heuristics, is_null_check)
from codegreen.analysis.efg.paths import find_sccs, longest_path_dag
from codegreen.analysis.efg.serialize import (
    dot_escape, efg_to_dot, efg_to_json, efg_to_mermaid, efg_to_text,
    truncate_label)
from codegreen.analysis.efg.types import (
    Accuracy, EFGEdge, EFGNode, EnergyFlowGraph, EnergyTier)

_MUTABLE = ("BL_LOOP_BACK", "BL_ERROR", "BL_NULL", "BL_DEFAULT")


def __getattr__(name: str):
    if name in _MUTABLE:
        return getattr(_heuristics, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Accuracy", "BL_DEFAULT", "BL_ERROR", "BL_HEURISTICS", "BL_LOOP_BACK", "BL_NULL",
    "DEFAULT_CONFIG", "DOT_LABEL_MAX_LEN", "EFGConfig", "EFGEdge", "EFGNode",
    "EnergyFlowGraph", "EnergyTier", "HOT_EDGE_FRACTION", "INSTRUMENTATION_MARKERS",
    "MIN_RANK_FOR_DISPLAY", "NODE_TEXT_MAX_LEN", "NTYPE_SHAPES", "RANK_WEIGHTS",
    "TIER_COLORS", "TIER_FONT_COLORS", "TIER_HOT_THRESHOLD", "TIER_WARM_THRESHOLD",
    "assign_tiers", "build_edges", "build_efg", "build_efg_for_method",
    "cfg_to_efg_inputs", "classify_edge_probability", "collect_body",
    "compute_loop_depths", "configure_heuristics", "dot_escape", "efg_to_dot",
    "efg_to_json", "efg_to_mermaid", "efg_to_text", "estimate_loop_iterations",
    "extract_callee_name", "find_sccs", "get_callee_calls", "infer_uninstrumented_energy",
    "is_null_check", "longest_path_dag", "mark_hot_edges", "prorate_call_edges",
    "strip_to_short", "truncate_label"
]
