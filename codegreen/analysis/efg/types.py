"""EFG data model: what a node, an edge, and a graph carry.

Kept free of construction logic and of the heuristic constants so that both
of those can import this without a cycle.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class Accuracy(Enum):
    """Provenance of a number, so a consumer never mistakes a guess for a
    measurement. MEASURED comes from CodeGreen checkpoints; ESTIMATED is
    derived from measured call counts; HEURISTIC is a static ranking weight;
    INFERRED is a distributed remainder."""
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
