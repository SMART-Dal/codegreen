"""One contract for every CodeGreen metric provider (CPU counters, GPU metrics, line samplers, ...).

Providers register in a Registry by name and report their capability as Availability; core code iterates a registry and
never branches on a provider, vendor, architecture or language. Every value any provider measures is one MetricRecord,
so consumers read all providers the same way. A metric a host cannot measure is a record with available=False and the
reason, never a missing key.

lift has a per-metric base, stated in the record's detail["lift_base"] by the provider that computes it (for example the
target's CPU-sample share for counter attribution, or the run-wide value of the same metric for GPU series).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Callable, Generic, Optional, TypeVar

SCOPES = ("run", "function", "line", "kernel", "op")


@dataclass(frozen=True)
class Availability:
    provider: str
    available: bool
    reason: str = ""                       # why not, when unavailable (required then)
    device: str = ""
    details: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.available and not self.reason:
            raise ValueError(f"{self.provider}: an unavailable provider must state its reason")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class MetricRecord:
    metric: str                            # logical name: cache_misses, ipc, dram_util_pct, cpu_samples, roofline_class, ...
    unit: str                              # count, ratio, pct, samples, bytes, w, mhz, c, ns, class, ...
    scope: str                             # one of SCOPES
    key: str                               # what the value is about ("" for run scope): function, file:function:line, kernel, op
    value: float | str | None              # None only when unavailable
    provider: str
    share: Optional[float] = None          # percent of the run's samples/events/time attributed to key
    lift: Optional[float] = None           # relative to detail["lift_base"]
    n: int = 0                             # samples, kernels or windows behind the value
    detail: dict = field(default_factory=dict)
    available: bool = True
    reason: str = ""                       # why unavailable, or a qualifier of an available value (e.g. multiplexing)

    def __post_init__(self):
        if self.scope not in SCOPES:
            raise ValueError(f"unknown metric scope {self.scope!r}; use one of {SCOPES}")
        if not self.available and not self.reason:
            raise ValueError(f"{self.provider}: unavailable metric {self.metric!r} needs a reason")

    def to_dict(self) -> dict:
        return asdict(self)


def unavailable(metric: str, unit: str, scope: str, provider: str, reason: str, key: str = "") -> MetricRecord:
    return MetricRecord(metric, unit, scope, key, None, provider, available=False, reason=reason)


class MetricUnavailable(RuntimeError):
    """A provider asked to measure what it cannot on this host."""


T = TypeVar("T")


class Registry(Generic[T]):
    """name -> provider; a provider exposes `name` and `probe() -> Availability`. Each provider is probed once (probes
    run tools such as perf or ncu); registering or replacing it drops its cached Availability."""

    def __init__(self, kind: str):
        self.kind, self._items, self._probed = kind, {}, {}

    def register(self, provider: T) -> T:
        name = getattr(provider, "name")
        if name in self._items:
            raise ValueError(f"{self.kind} provider {name!r} is already registered")
        return self.put(provider)

    def put(self, provider: T) -> T:
        """Register or replace (for registries whose entries are assembled from parts, e.g. language adapters)."""
        name = getattr(provider, "name")
        self._items[name] = provider
        self._probed.pop(name, None)
        return provider

    def get(self, name: str) -> T:
        if name not in self._items:
            raise KeyError(f"no {self.kind} provider {name!r}; registered: {sorted(self._items)}")
        return self._items[name]

    def names(self) -> list[str]:
        return list(self._items)

    def all(self) -> list[T]:
        return list(self._items.values())

    def probe(self) -> list[Availability]:
        for name, p in self._items.items():
            if name not in self._probed:
                self._probed[name] = p.probe()
        return [self._probed[name] for name in self._items]

    def available(self) -> list[T]:
        return [p for p, a in zip(self._items.values(), self.probe()) if a.available]


PROVIDERS: Registry = Registry("metric")   # run-scope metric providers (hw_counters, ...); GPU kinds have their own registries


def register_provider(provider: T) -> T:
    return PROVIDERS.register(provider)


def get_provider(name: str):
    return PROVIDERS.get(name)


def attribute(metric: str, provider: str, stacks: list[tuple[tuple, float]], targets: dict[str, Callable[[tuple], bool]],
              cpu_share_pct: dict[str, Optional[float]]) -> list[MetricRecord]:
    """Function-scope records of one sampled event: per target, the percent of the event's weight whose stack holds a frame
    the target owns (inclusive, once per stack), and its lift over the target's CPU-sample share. `stacks` are normalized
    frames from a language's event sampler, `targets` {key: frame -> owned?}."""
    total = sum(w for _, w in stacks)
    if not total:
        return [unavailable(metric, "pct", "function", provider, "no samples", key) for key in targets]
    held: Counter = Counter()
    for frames, w in stacks:
        for key, owns in targets.items():
            if any(owns(f) for f in frames):
                held[key] += w
    out = []
    for key in targets:
        share = 100.0 * held[key] / total
        base = cpu_share_pct.get(key)
        out.append(MetricRecord(metric, "pct", "function", key, share, provider, share=share, lift=share / base if base else None,
                                n=int(held[key]), detail={"lift_base": "cpu_sample_share"}))
    return out
