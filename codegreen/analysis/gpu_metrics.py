"""GPU metrics beside energy: device time series and per-kernel efficiency, attributed to the ops and
annotated source ranges that launched each kernel.

Three registries, all open for extension (a new vendor, replay tool or framework registers one object;
nothing here branches on vendor or architecture):
  GPU_SERIES     device time series sampled during a profiled run (NVML):
                 provider.sample(interval_s, device) -> context manager whose .rows are
                 {t_ns (CLOCK_MONOTONIC), <metric>: value} and whose .overhead_s is the sampler's CPU time.
  GPU_REPLAY     per-kernel counters from a replay tool (ncu), opt-in and expensive:
                 provider.command(argv, out) -> argv to run, provider.parse(out) -> [{kernel, <metric>: value}].
  GPU_FRAMEWORKS framework traces -> launched kernels with their op and enclosing annotations:
                 adapter.kernels(doc) -> [Kernel].
Metric names, replay counters and roofline thresholds are data (config.json "gpu_metrics"); per-device
peaks are host data the user declares (gpu_metrics.peaks in the user config, each with its source).
Everything rides a profiled run, never a measured one.
NVML utilization is a device-level ratio over the driver's sampling window (1/6 s to 1 s), so a
kernel's value describes the windows it ran in, not the kernel alone; replay counters are per kernel.
"""
from __future__ import annotations

import bisect
import os
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from codegreen.analysis.metrics import Availability, MetricRecord, MetricUnavailable, Registry
from codegreen.instrumentation.language_runtimes.python.codegreen_runtime import load_config

GPU_SERIES: Registry = Registry("gpu_series")
GPU_REPLAY: Registry = Registry("gpu_replay")
GPU_FRAMEWORKS: Registry = Registry("gpu_framework")


def config() -> dict:
    """gpu_metrics from the one config resolver (CODEGREEN_CONFIG, ~/.codegreen/config.json, bundled)."""
    return load_config()["gpu_metrics"]


def peaks(device: str) -> dict:
    """Declared peaks of a device (dram_gbps, fp32_tflops, source) from gpu_metrics.peaks; raises when undeclared."""
    declared = config()["peaks"]
    if device not in declared:
        raise MetricUnavailable(f"no peaks declared for {device!r}: add gpu_metrics.peaks[{device!r}] = "
                                "{dram_gbps, fp32_tflops, source} to the user config (CODEGREEN_CONFIG or ~/.codegreen/config.json)")
    return declared[device]


@dataclass(frozen=True)
class Kernel:
    name: str
    start_ns: int
    dur_ns: int
    op: str                       # launching framework op ("" when the trace links none)
    annotations: tuple = ()       # enclosing user annotations of the launching op, outermost first


class _Sampler:
    def __init__(self, read, interval_s: float):
        self.read, self.interval_s, self.rows, self.overhead_s = read, interval_s, [], 0.0
        self._stop, self._error = threading.Event(), None

    def _loop(self):
        t0 = time.thread_time()
        try:
            while not self._stop.is_set():
                self.rows.append({"t_ns": time.monotonic_ns(), **self.read()})
                self._stop.wait(self.interval_s)
            self.rows.append({"t_ns": time.monotonic_ns(), **self.read()})
        except Exception as e:   # surfaced by __exit__, never swallowed
            self._error = e
        self.overhead_s = time.thread_time() - t0

    def __enter__(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join()
        if self._error is not None and exc[0] is None:
            raise MetricUnavailable(f"device sampling failed: {self._error}") from self._error
        return False


class NvmlSeries:
    """power_w duplicates the NEMB nvidia_gpu provider's reading; it is a profiled-run series, never energy."""
    name = "nvml"
    metrics = {"sm_util_pct": "pct", "mem_util_pct": "pct", "power_w": "w", "sm_clock_mhz": "mhz",
               "mem_clock_mhz": "mhz", "temp_c": "c"}

    def probe(self) -> Availability:
        try:
            import pynvml
            pynvml.nvmlInit()
            if not pynvml.nvmlDeviceGetCount():
                return Availability(self.name, False, "NVML reports no device")
            h = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(h)
            return Availability(self.name, True, device=name.decode() if isinstance(name, bytes) else name,
                                details={"devices": pynvml.nvmlDeviceGetCount()})
        except Exception as e:
            return Availability(self.name, False, f"NVML unavailable: {type(e).__name__}: {e}")

    def sample(self, interval_s: float, device: int = 0) -> _Sampler:
        import pynvml
        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(device)

        def read() -> dict:
            u = pynvml.nvmlDeviceGetUtilizationRates(h)
            return {"sm_util_pct": float(u.gpu), "mem_util_pct": float(u.memory),
                    "power_w": pynvml.nvmlDeviceGetPowerUsage(h) / 1000.0,
                    "sm_clock_mhz": float(pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_SM)),
                    "mem_clock_mhz": float(pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_MEM)),
                    "temp_c": float(pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU))}
        return _Sampler(read, interval_s)


class NcuReplay:
    name = "ncu"
    params_path = Path("/proc/driver/nvidia/params")

    def probe(self) -> Availability:
        if not shutil.which("ncu"):
            return Availability(self.name, False, "ncu not found")
        admin_only = self.params_path.exists() and "RmProfilingAdminOnly: 1" in self.params_path.read_text()
        if admin_only and os.geteuid() != 0:
            return Availability(self.name, False, "GPU performance counters are restricted to admin (RmProfilingAdminOnly: 1)")
        return Availability(self.name, True, details={"ncu": shutil.which("ncu")})

    def command(self, argv: list[str], out: Path) -> list[str]:
        c = config()["ncu"]
        return ["ncu", "--csv", "--page", "raw", "--target-processes", "all", "--launch-count", str(c["launch_count"]),
                "--metrics", ",".join(c["metrics"].values()), "--log-file", str(out), *argv]

    def parse(self, out: Path) -> list[dict]:
        """One row per profiled kernel launch: {kernel, <metric>: float} named as in config ncu.metrics."""
        import csv
        names = config()["ncu"]["metrics"]
        lines = [ln for ln in Path(out).read_text().splitlines() if ln.startswith('"')]
        if not lines:
            raise MetricUnavailable(f"ncu wrote no CSV rows to {out}")
        rows = list(csv.DictReader(lines))
        missing = [m for m in names.values() if m not in rows[0]]
        if missing:
            raise MetricUnavailable(f"ncu output lacks metrics {missing}")
        data = [r for r in rows if r.get("Kernel Name")]   # the units row carries no kernel name
        return [{"kernel": r["Kernel Name"], **{k: float(r[m].replace(",", "")) for k, m in names.items()}} for r in data]


class TorchTrace:
    """torch.profiler export_chrome_trace: kernels (cat kernel) link to their launching cpu_op through args
    "External id"; user_annotation ranges (record_function) containing that op are its annotations.
    ts/dur are us on Kineto's clock; `offset_ns` moves them onto the sampler's monotonic clock."""
    name = "torch"

    def probe(self) -> Availability:
        return Availability(self.name, True)

    def kernels(self, doc: dict, offset_ns: int = 0) -> list[Kernel]:
        if "traceEvents" not in doc:
            raise ValueError("not a Chrome trace (no traceEvents)")
        ev = [e for e in doc["traceEvents"] if e.get("ph") == "X"]
        ops = {(e.get("args") or {}).get("External id"): e for e in ev if e.get("cat") == "cpu_op"}
        notes = sorted((e["ts"], e["ts"] + e.get("dur", 0), e["name"]) for e in ev if e.get("cat") == "user_annotation")
        out = []
        for e in ev:
            if e.get("cat") != "kernel":
                continue
            op = ops.get((e.get("args") or {}).get("External id"))
            at = op["ts"] if op else None
            out.append(Kernel(e.get("name", ""), int(e["ts"] * 1000) + offset_ns, int(e.get("dur", 0) * 1000),
                              op["name"] if op else "",
                              tuple(n for s, t, n in notes if at is not None and s <= at <= t)))
        return out


def series_per_kernel(rows: list[dict], kernels: list[Kernel], metrics: list[str]) -> list[dict]:
    """Time-weighted mean of each series metric over each kernel's interval; a sample at t describes the
    interval since the previous sample. Kernels outside the sampled span get no values (n_windows 0).
    O((rows + kernels) log rows + windows): each kernel bisects to its first overlapping window."""
    pts = sorted(rows, key=lambda r: r["t_ns"])
    ts = [r["t_ns"] for r in pts]
    out = []
    for k in kernels:
        s, e, acc, w, n = k.start_ns, k.start_ns + max(k.dur_ns, 1), dict.fromkeys(metrics, 0.0), 0, 0
        for i in range(max(bisect.bisect_right(ts, s) - 1, 0), len(pts) - 1):
            if ts[i] >= e:
                break
            ov = min(e, ts[i + 1]) - max(s, ts[i])
            if ov > 0:
                w, n = w + ov, n + 1
                for m in metrics:
                    acc[m] += pts[i + 1][m] * ov
        out.append({"kernel": k, "n_windows": n, **({m: acc[m] / w for m in metrics} if w else {})})
    return out


def roofline_class(dram_pct: float, sm_pct: float) -> str:
    """memory_bound / compute_bound by the larger speed-of-light share; latency_bound when both stay
    under the configured latency threshold (thresholds are data, set a priori)."""
    if max(dram_pct, sm_pct) < config()["roofline"]["latency_pct"]:
        return "latency_bound"
    return "memory_bound" if dram_pct >= sm_pct else "compute_bound"


def aggregate(per_kernel: list[dict], key, metrics: dict, provider: str, scope: str) -> list[MetricRecord]:
    """MetricRecords per key(kernel) (an op, a line, ...): kernel-time-weighted mean per metric, share of
    all kernel time, lift against the run-wide kernel-time-weighted mean."""
    rows = [r for r in per_kernel if all(m in r for m in metrics)]
    total = sum(r["kernel"].dur_ns for r in rows)
    if not total:
        return []
    run = {m: sum(r[m] * r["kernel"].dur_ns for r in rows) / total for m in metrics}
    groups: dict = {}
    for r in rows:
        groups.setdefault(key(r["kernel"]), []).append(r)
    out = []
    for g, rs in groups.items():
        t = sum(r["kernel"].dur_ns for r in rs)
        if not t:
            continue
        for m, unit in metrics.items():
            v = sum(r[m] * r["kernel"].dur_ns for r in rs) / t
            out.append(MetricRecord(m, unit, scope, g, v, provider, share=100.0 * t / total,
                                    lift=v / run[m] if run[m] else None, n=len(rs), detail={"lift_base": "run_kernel_time_weighted_mean"}))
    return out


GPU_SERIES.register(NvmlSeries())
GPU_REPLAY.register(NcuReplay())
GPU_FRAMEWORKS.register(TorchTrace())
