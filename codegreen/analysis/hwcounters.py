"""Hardware performance counters as a registered metric provider (metrics.py), over Linux perf_event.

Run scope: `perf stat` wraps a non-measured run (the sampled cross-check run) in counting mode, so energy readings never
carry counters; derived ratios follow (IPC, miss rates, MPKI, stall fractions). Function scope: each event listed in
config.json hw_counters.attribution is sampled once with call stacks through the language's event sampler
(codegreen.analysis.languages), so any registered language gets counter shares with no counter-specific code per language.

Events are logical names. Their perf names live in data files (codegreen/hw_events/*.json), one per architecture, each
with /proc/cpuinfo match rules and a priority; the generic file matches every host and the highest-priority matching
file overlays it. A new architecture is a new file. An event the host cannot count is a record with available=False and
the reason, never dropped. A host without /proc/cpuinfo (no perf_event) gets an unavailable provider, not an error.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from codegreen.analysis.metrics import PROVIDERS, Availability, MetricRecord, MetricUnavailable, register_provider, unavailable
from codegreen.instrumentation.language_runtimes.python.codegreen_runtime import load_config

EVENTS_DIR = Path(__file__).parents[1] / "hw_events"
CPUINFO = Path("/proc/cpuinfo")
PMU_EVENT = re.compile(r"[\w.-]+/(.+)/")   # hybrid CPUs print an event per core PMU: cpu_core/cycles/, cpu_atom/cycles/
UNITS = {"ipc": "ratio", "cache_miss_rate": "ratio", "branch_miss_rate": "ratio", "mpki": "per_kilo_instruction",
         "frontend_stall_fraction": "ratio", "backend_stall_fraction": "ratio"}


def cpuinfo_fields(text: str) -> dict[str, str]:
    """The first processor block of /proc/cpuinfo as {field: value}."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            if out:
                break
            continue
        k, sep, v = line.partition(":")
        if sep:
            out.setdefault(k.strip(), v.strip())
    return out


def _holds(rule, value: str | None) -> bool:
    if value is None:
        return False
    if isinstance(rule, dict):
        return all({"min": lambda x: int(value, 0) >= x, "max": lambda x: int(value, 0) <= x,
                    "in": lambda xs: value.lower() in [str(x).lower() for x in xs]}[op](arg) for op, arg in rule.items())
    return value.lower() == str(rule).lower()


def event_map(fields: dict[str, str], events_dir: Path = EVENTS_DIR) -> tuple[str, dict[str, str]]:
    """(map name, {logical: perf event}) for a host: generic overlaid by the highest-priority matching data file."""
    maps = [json.loads(p.read_text()) for p in sorted(Path(events_dir).glob("*.json"))]
    generic = next((m for m in maps if m["name"] == "generic"), None)
    if generic is None:
        raise FileNotFoundError(f"no generic.json event map in {events_dir}")
    hits = [m for m in maps if all(_holds(rule, fields.get(k)) for k, rule in m["match"].items())]
    best = max(hits, key=lambda m: m["priority"])
    return best["name"], {**generic["events"], **best["events"]}


def parse_stat(text: str, events: dict[str, str]) -> dict:
    """{counts: {logical: value}, unavailable: {logical: why}, running_pct: {logical: pct}} from `perf stat -x,` output.
    running_pct below 100 means the kernel multiplexed the counter and scaled the count. On a hybrid CPU an event is
    reported once per core PMU (cpu_core/cycles/): the counts add up, running_pct is the lowest, and the event is
    unavailable only when no PMU counted it (a PMU whose cores never ran the process reports <not counted>)."""
    by_event = {e: k for k, e in events.items()}
    counts, why, running = {}, {}, {}
    for line in text.splitlines():
        f = line.split(",")
        if line.startswith("#") or len(f) < 3:
            continue
        pmu = PMU_EVENT.fullmatch(f[2])
        k = by_event.get(f[2]) or (by_event.get(pmu[1]) if pmu else None)
        if k is None:
            continue
        if f[0].startswith("<"):
            why.setdefault(k, f[0].strip("<>"))
            continue
        counts[k] = counts.get(k, 0.0) + float(f[0])
        if len(f) > 4 and f[4]:
            running[k] = min(running.get(k, 100.0), float(f[4]))
    return {"counts": counts, "unavailable": {k: why.get(k, "not reported") for k in events if k not in counts},
            "running_pct": running}


def derived(counts: dict[str, float]) -> dict[str, tuple[float | None, str]]:
    """{metric: (value or None, reason)}. mpki uses LLC misses when counted, else all cache misses (the reason says which).
    Stall fractions are of cycles as the CPU defines its stall events: an indicator of pressure, not a top-down measure."""
    def r(a: str, b: str, scale: float = 1.0):
        if counts.get(a) is None or not counts.get(b):
            return None, f"needs {a} and {b}"
        return scale * counts[a] / counts[b], ""
    basis = "llc_misses" if counts.get("llc_misses") is not None else "cache_misses"
    mpki, why = r(basis, "instructions", 1000.0)
    return {"ipc": r("instructions", "cycles"), "cache_miss_rate": r("cache_misses", "cache_references"),
            "branch_miss_rate": r("branch_misses", "branches"), "mpki": (mpki, why or f"basis {basis}"),
            "frontend_stall_fraction": r("stalled_frontend", "cycles"), "backend_stall_fraction": r("stalled_backend", "cycles")}


class PerfCounters:
    """MetricProvider for CPU hardware counters (name "hw_counters")."""
    name = "hw_counters"

    def __init__(self, cfg: dict | None = None, cpuinfo: str | None = None, events_dir: Path = EVENTS_DIR):
        self.cfg = cfg if cfg is not None else load_config()["hw_counters"]
        self.missing = "" if cpuinfo is not None or CPUINFO.is_file() else f"{CPUINFO} not found: perf_event counters need Linux"
        if self.missing:
            self.arch, self.events = "", {}
            return
        self.arch, self.events = event_map(cpuinfo_fields(cpuinfo if cpuinfo is not None else CPUINFO.read_text()), events_dir)
        unknown = set(self.cfg["attribution"]) - set(self.events)
        if unknown:
            raise ValueError(f"hw_counters.attribution names events outside the {self.arch} map: {sorted(unknown)}")

    def require(self) -> None:
        if self.missing:
            raise MetricUnavailable(self.missing)

    def probe(self) -> Availability:
        """Availability of the provider with one {available, reason} entry per logical event in details["events"]."""
        if self.missing:
            return Availability(self.name, False, self.missing)
        if shutil.which(self.cfg["perf"]) is None:
            return Availability(self.name, False, f"perf binary {self.cfg['perf']!r} not found", details={"arch": self.arch})
        out = {}
        for k, e in self.events.items():
            p = subprocess.run([self.cfg["perf"], "stat", "-x", ",", "-e", e, "--", "true"], capture_output=True, text=True)
            res = parse_stat(p.stderr, {k: e})
            ok = p.returncode == 0 and k in res["counts"]
            out[k] = {"available": ok, "reason": "" if ok else res["unavailable"].get(k) or f"perf exited {p.returncode}"}
        if not any(v["available"] for v in out.values()):
            return Availability(self.name, False, "no event of the architecture map is countable", details={"arch": self.arch, "events": out})
        return Availability(self.name, True, details={"arch": self.arch, "events": out})

    def wrap(self, argv: list[str], env: dict, out_dir) -> tuple[list[str], dict]:
        self.require()
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        return [self.cfg["perf"], "stat", "-x", ",", "--no-big-num", "-e", ",".join(self.events.values()),
                "-o", str(Path(out_dir) / "perf_stat.csv"), "--", *argv], dict(env)

    def read(self, out_dir) -> list[MetricRecord]:
        self.require()
        res = parse_stat((Path(out_dir) / "perf_stat.csv").read_text(), self.events)
        rows = [MetricRecord(k, "count", "run", "", v, self.name, detail={"arch": self.arch},
                             reason=f"multiplexed {res['running_pct'][k]:.0f}% of run time" if res["running_pct"].get(k, 100.0) < 100.0 else "")
                for k, v in res["counts"].items()]
        rows += [unavailable(k, "count", "run", self.name, why) for k, why in res["unavailable"].items()]
        rows += [MetricRecord(k, UNITS[k], "run", "", v, self.name, detail={"arch": self.arch}, reason=why) if v is not None
                 else unavailable(k, UNITS[k], "run", self.name, why) for k, (v, why) in derived(res["counts"]).items()]
        return rows

    def sampled_events(self) -> dict[str, tuple[str, int]]:
        self.require()
        return {k: (self.events[k], int(period)) for k, period in self.cfg["attribution"].items()}


def provider() -> PerfCounters:
    """Register (once) and return the host's counter provider."""
    return PROVIDERS.get(PerfCounters.name) if PerfCounters.name in PROVIDERS.names() else register_provider(PerfCounters())
