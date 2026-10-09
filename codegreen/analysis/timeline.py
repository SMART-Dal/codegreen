"""One time axis for a whole run: power, CPU stacks, GC, allocation and GPU
activity as tracks on CLOCK_MONOTONIC nanoseconds, exported as a Perfetto /
Chrome Trace Event file and summarised into phases and bottlenecks.

Importers:
  from_nemb   NEMB time series (nemb_get_time_series_json): t_ns monotonic,
              cumulative energy_j, total power_w, per-domain domain_j/domain_w.
  from_jfr    `jfr print --json <file.jfr>`: jdk.ExecutionSample stacks,
              jdk.GarbageCollection / jdk.GCPhasePause slices, allocation
              (jdk.ObjectAllocationSample weight, JDK 16+; jdk.ObjectAllocation
              In/OutsideTLAB allocationSize, JDK 11). startTime is wall clock and
              is moved onto the monotonic clock with `offset_ns`
              (sampling.monotonic_minus_realtime_ns, taken during the run).
  from_torch  torch.profiler export_chrome_trace JSON: `kernel`, `gpu_memcpy`,
              `gpu_memset` slices and `cuda_runtime` launch slices; ts/dur in us.
              Kineto's clock base is not the monotonic clock, so the caller
              passes `offset_ns` (trace ts + offset = monotonic ns).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from codegreen.analysis.sampling import energy_by_method


@dataclass
class Trace:
    counters: dict = field(default_factory=dict)   # track -> [(t_ns, value)]
    slices: list = field(default_factory=list)     # (track, name, start_ns, dur_ns)
    samples: list = field(default_factory=list)    # (t_ns, thread, frames leaf-last)
    energy: list = field(default_factory=list)     # cumulative (t_ns, joules)

    def merge(self, other: "Trace") -> "Trace":
        return Trace({**self.counters, **other.counters}, self.slices + other.slices,
                     self.samples + other.samples, self.energy or other.energy)

    def span(self) -> tuple[int, int]:
        ts = ([t for pts in self.counters.values() for t, _ in pts] + [s[2] for s in self.slices]
              + [s[2] + s[3] for s in self.slices] + [t for t, _, _ in self.samples])
        if not ts:
            raise ValueError("empty trace")
        return min(ts), max(ts)


def from_nemb(series: list) -> Trace:
    if not isinstance(series, list) or not series:
        raise ValueError("NEMB time series must be a non-empty JSON list")
    tr = Trace(energy=[(int(r["t_ns"]), float(r["energy_j"])) for r in series])
    tr.counters["power_w/total"] = [(int(r["t_ns"]), float(r["power_w"])) for r in series]
    for r in series:
        for dom, w in r.get("domain_w", {}).items():
            tr.counters.setdefault(f"power_w/{dom}", []).append((int(r["t_ns"]), float(w)))
    return tr


_ISO = re.compile(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d{1,9}))?(Z|[+-]\d\d:?\d\d)?$")


def _wall_ns(stamp: str) -> int:
    m = _ISO.match(stamp)
    if not m:
        raise ValueError(f"unparseable JFR timestamp {stamp!r}")
    base = datetime.fromisoformat(m.group(1) + (m.group(3) or "+00:00").replace("Z", "+00:00"))
    return int(base.timestamp()) * 10**9 + int((m.group(2) or "0").ljust(9, "0"))


def _dur_ns(value) -> int:
    """JFR durations print as ISO-8601 (PT0.001S) or as numbers of ns."""
    if isinstance(value, (int, float)):
        return int(value)
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?", str(value))
    if not m:
        raise ValueError(f"unparseable JFR duration {value!r}")
    h, mi, s = (float(g) if g else 0.0 for g in m.groups())
    return int(round((h * 3600 + mi * 60 + s) * 1e9))


def _frame(f: dict) -> str:
    meth = f.get("method") or {}
    cls = ((meth.get("type") or {}).get("name") or "").replace("/", ".")
    return f"{cls}.{meth.get('name', '?')}" if cls else str(meth.get("name", "?"))


def from_jfr(doc: dict, offset_ns: int) -> Trace:
    try:
        events = doc["recording"]["events"]
    except (KeyError, TypeError) as e:
        raise ValueError("not `jfr print --json` output (no recording.events)") from e
    tr, alloc = Trace(), []
    for ev in events:
        typ, v = ev.get("type"), ev.get("values") or {}
        if typ not in ("jdk.ExecutionSample", "jdk.GarbageCollection", "jdk.GCPhasePause",
                       "jdk.ObjectAllocationSample", "jdk.ObjectAllocationInNewTLAB",
                       "jdk.ObjectAllocationOutsideTLAB"):
            continue
        t = _wall_ns(v["startTime"]) + offset_ns
        if typ == "jdk.ExecutionSample":
            frames = [_frame(f) for f in (v.get("stackTrace") or {}).get("frames", [])]
            if frames:
                thread = (v.get("sampledThread") or {}).get("javaName") or "?"
                tr.samples.append((t, thread, tuple(reversed(frames))))
        elif typ in ("jdk.GarbageCollection", "jdk.GCPhasePause"):
            tr.slices.append((f"jvm/{typ.split('.')[-1]}", str(v.get("name", "gc")), t, _dur_ns(v.get("duration", 0))))
        else:
            alloc.append((t, float(v.get("weight", v.get("allocationSize", 0)))))
    if alloc:
        tr.counters["alloc_bytes/event"] = sorted(alloc)
    return tr


_TORCH_TRACKS = {"kernel": "gpu/kernel", "gpu_memcpy": "gpu/memcpy", "gpu_memset": "gpu/memset",
                 "cuda_runtime": "cpu/cuda_runtime"}


def from_torch(doc: dict, offset_ns: int) -> Trace:
    if "traceEvents" not in doc:
        raise ValueError("not a Chrome trace (no traceEvents)")
    return Trace(slices=[(_TORCH_TRACKS[e["cat"]], e.get("name", ""), int(e["ts"] * 1000) + offset_ns,
                          int(e.get("dur", 0) * 1000))
                         for e in doc["traceEvents"] if e.get("ph") == "X" and e.get("cat") in _TORCH_TRACKS])


def to_perfetto(tr: Trace) -> dict:
    """Chrome Trace Event JSON (open in ui.perfetto.dev); times in us."""
    tracks = sorted({s[0] for s in tr.slices} | {f"cpu/samples/{th}" for _, th, _ in tr.samples})
    tid = {name: i + 1 for i, name in enumerate(tracks)}
    ev = [{"ph": "M", "name": "thread_name", "pid": 1, "tid": i, "args": {"name": n}} for n, i in tid.items()]
    ev += [{"ph": "C", "name": track, "pid": 1, "ts": t / 1e3, "args": {"value": val}}
           for track, pts in tr.counters.items() for t, val in pts]
    ev += [{"ph": "X", "name": name, "pid": 1, "tid": tid[track], "ts": s / 1e3, "dur": d / 1e3}
           for track, name, s, d in tr.slices]
    ev += [{"ph": "i", "s": "t", "name": frames[-1], "pid": 1, "tid": tid[f"cpu/samples/{th}"], "ts": t / 1e3,
            "args": {"stack": " <- ".join(reversed(frames))}} for t, th, frames in tr.samples]
    return {"traceEvents": ev, "displayTimeUnit": "ns"}


def _union(intervals: list) -> list:
    out = []
    for s, e in sorted(intervals):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def _overlap(a: list, b: list) -> int:
    i = j = tot = 0
    while i < len(a) and j < len(b):
        tot += max(0, min(a[i][1], b[j][1]) - max(a[i][0], b[j][0]))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return tot


def phases(power: list, rel_change: float, confirm: int) -> list:
    """Split a power series into phases: a new phase starts where `confirm`
    consecutive samples differ from the running phase mean by more than
    `rel_change` (fraction). NEMB power describes the interval ending at its
    sample, so a phase of samples [i, j) spans t[i-1]..t[j-1]. Returns
    [(start_ns, end_ns, mean_w, i, j)] over the time-sorted series."""
    pts = sorted(power)
    if len(pts) < 2:
        raise ValueError("power series needs at least two samples")
    bounds, start, vals, pend = [], 0, [], []
    for k, (_, w) in enumerate(pts):
        mean = sum(vals) / len(vals) if vals else w
        if vals and abs(w - mean) > rel_change * abs(mean):
            pend.append(k)
            if len(pend) >= confirm:
                bounds.append((start, pend[0], mean))
                start, vals, pend = pend[0], [pts[i][1] for i in pend], []
            continue
        vals += [pts[i][1] for i in pend] + [w]
        pend = []
    vals += [pts[i][1] for i in pend]
    bounds.append((start, len(pts), sum(vals) / len(vals)))
    return [(pts[max(i - 1, 0)][0], pts[j - 1][0], m, i, j) for i, j, m in bounds]


def _energy(tr: Trace, power: list, i: int, j: int) -> float:
    """Joules over samples [i, j): the cumulative series when it shares the
    power timestamps (NEMB), else power x interval."""
    pts, cum = sorted(power), dict(tr.energy)
    a, b = pts[max(i - 1, 0)][0], pts[j - 1][0]
    if a in cum and b in cum:
        return cum[b] - cum[a]
    return sum(pts[k][1] * (pts[k][0] - pts[k - 1][0]) for k in range(max(i, 1), j)) / 1e9


def analyze(tr: Trace, *, rel_change: float, confirm: int, gap_min_ns: int, launch_bound_frac: float) -> dict:
    """Phases (power level changes) with energy, time and the dominant method
    and GPU kernel; GPU busy fraction, idle gaps and whether the CPU was busy
    launching during them; GC share of wall time; allocation rate."""
    t0, t1 = tr.span()
    wall = max(t1 - t0, 1)
    out: dict = {"wall_s": wall / 1e9}
    kernels = [s for s in tr.slices if s[0] == "gpu/kernel"]
    power = tr.counters.get("power_w/total")
    if power:
        ph = []
        for a, b, mean, i, j in phases(power, rel_change, confirm):
            sub = [(t, f) for t, _, f in tr.samples if a <= t < b]
            leaves: dict = {}
            for _, f in sub:
                leaves[f[-1]] = leaves.get(f[-1], 0) + 1
            ktime: dict = {}
            for _, name, s, d in kernels:
                ktime[name] = ktime.get(name, 0) + max(0, min(s + d, b) - max(s, a))
            ph.append({"start_s": (a - t0) / 1e9, "dur_s": (b - a) / 1e9, "mean_power_w": mean,
                       "energy_j": _energy(tr, power, i, j),
                       "top_method": max(leaves, key=leaves.get) if leaves else None,
                       "top_kernel": max(ktime, key=ktime.get) if any(ktime.values()) else None})
        out["phases"] = ph
    if tr.samples and len(tr.energy) >= 2:
        out["method_energy"] = energy_by_method([(t, f) for t, _, f in tr.samples], tr.energy)
    if kernels:
        busy = _union([(s, s + d) for _, _, s, d in kernels])
        gaps = [[a[1], b[0]] for a, b in zip(busy, busy[1:]) if b[0] - a[1] > gap_min_ns]
        launch = _union([(s, s + d) for tk, _, s, d in tr.slices if tk == "cpu/cuda_runtime"])
        gap_ns = sum(b - a for a, b in gaps)
        covered = _overlap(gaps, launch) / gap_ns if gap_ns else 0.0
        out["gpu"] = {"busy_frac": sum(b - a for a, b in busy) / wall, "idle_gaps": len(gaps),
                      "gap_frac": gap_ns / wall, "gap_launch_covered_frac": covered,
                      "launch_bound": bool(gaps) and covered >= launch_bound_frac}
    gc = [(s, s + d) for tk, _, s, d in tr.slices if tk.startswith("jvm/")]
    if gc:
        out["gc_frac"] = sum(b - a for a, b in _union(gc)) / wall
    if "alloc_bytes/event" in tr.counters:
        out["alloc_bytes_per_s"] = sum(v for _, v in tr.counters["alloc_bytes/event"]) / (wall / 1e9)
    return out
