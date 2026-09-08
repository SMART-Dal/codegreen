"""Tunable constants, EFGConfig, and static branch prediction.

The Ball & Larus (1993) probabilities are module globals rather than config
fields because `configure_heuristics` mutates them process-wide, and
`classify_edge_probability` reads them at call time. Keep the two together in
this module: splitting them would silently freeze the values at import.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from codegreen.analysis.efg.types import EFGNode, EnergyTier

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


_NULL_PATTERN = re.compile(r'(==\s*null|!=\s*null|null\s*==|null\s*!=)', re.IGNORECASE)


def is_null_check(text: str) -> bool:
    """Detect null comparisons from CFG node text. Post-migration (task #48),
    replace with CNode.is_null_check set via tree-sitter query at build time."""
    return bool(_NULL_PATTERN.search(text))


def classify_edge_probability(label: str, src_node: Optional[EFGNode],
                              dst_node: Optional[EFGNode]) -> float:
    if not label:
        return 1.0
    label_lower = label.lower()
    if label_lower in ("exception", "catch"):
        return BL_ERROR
    if src_node and is_null_check(src_node.text):
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


_is_null_check = is_null_check
_classify_edge_probability = classify_edge_probability
