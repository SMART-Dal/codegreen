"""Lightweight CFG + dataflow for Java, built on tree-sitter 0.25.

Adapted from tree-climber (submodules/tree-climber) patterns, ported to
tree-sitter 0.25 API with added support for synchronized, try/catch,
try-with-resources, and lambda bodies.

Module structure:
  cfg/types.py    - CNode, CFG, NType data structures
  cfg/builder.py  - Java CFG builder (visitor pattern)
  cfg/dataflow.py - Reaching definitions, def-use chains
  cfg/features.py - FlowFeatures extraction
"""

from src.analysis.cfg.types import CFG, CNode, NType
from src.analysis.cfg.builder import build_cfg, build_per_method_cfgs
from src.analysis.cfg.callgraph import CallGraph, build_call_graph, build_call_graph_from_dir
from src.analysis.cfg.dataflow import reaching_defs, def_use_chains, use_def_chains
from src.analysis.cfg.features import FlowFeatures, extract_flow_features
from src.analysis.cfg.pdg import PDGFeatures, extract_pdg_features, compute_post_dominators, compute_control_dependencies

try:
    from src.analysis.cfg.builder import _HAS_TS
except ImportError:
    _HAS_TS = False

__all__ = [
    "CFG", "CNode", "NType",
    "build_cfg", "build_per_method_cfgs", "reaching_defs", "def_use_chains", "use_def_chains",
    "FlowFeatures", "extract_flow_features",
    "_HAS_TS",
]
