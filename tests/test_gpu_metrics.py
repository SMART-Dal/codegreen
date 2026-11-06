import sys
import types

import pytest

from codegreen.analysis import gpu_metrics as gm
from codegreen.analysis.metrics import Availability, MetricRecord, MetricUnavailable, Registry


def test_contract_records_and_registry():
    with pytest.raises(ValueError):
        Availability("x", False)
    with pytest.raises(ValueError):
        MetricRecord("m", "pct", "socket", "", 1.0, "x")

    class P:
        def __init__(self, name, ok):
            self.name, self.ok = name, ok

        def probe(self):
            return Availability(self.name, self.ok, "" if self.ok else "absent")
    r = Registry("t")
    r.register(P("a", True))
    r.register(P("b", False))
    with pytest.raises(ValueError):
        r.register(P("a", True))
    assert [p.name for p in r.available()] == ["a"] and [a.reason for a in r.probe()] == ["", "absent"]
    assert [p.name for p in gm.GPU_SERIES.all()] == ["nvml"] and [p.name for p in gm.GPU_REPLAY.all()] == ["ncu"]


def _fake_nvml(monkeypatch, fail=False):
    util = types.SimpleNamespace(gpu=80, memory=40)
    def boom(*a):
        raise RuntimeError("driver gone")
    mod = types.SimpleNamespace(
        nvmlInit=lambda: None, nvmlDeviceGetCount=lambda: 1, nvmlDeviceGetHandleByIndex=lambda i: i,
        nvmlDeviceGetName=lambda h: b"NVIDIA RTX 5000 Ada Generation",
        nvmlDeviceGetUtilizationRates=boom if fail else (lambda h: util), nvmlDeviceGetPowerUsage=lambda h: 150000,
        nvmlDeviceGetClockInfo=lambda h, c: 2000 if c == 0 else 9000, nvmlDeviceGetTemperature=lambda h, t: 55,
        NVML_CLOCK_SM=0, NVML_CLOCK_MEM=1, NVML_TEMPERATURE_GPU=0)
    monkeypatch.setitem(sys.modules, "pynvml", mod)


def test_nvml_probe_and_sampler_rows_and_failure(monkeypatch):
    _fake_nvml(monkeypatch)
    a = gm.NvmlSeries().probe()
    assert a.available and a.device == "NVIDIA RTX 5000 Ada Generation"
    with gm.NvmlSeries().sample(0.001) as s:
        pass
    assert s.rows and {"t_ns", "sm_util_pct", "mem_util_pct", "power_w", "temp_c"} <= set(s.rows[0]) and s.rows[0]["power_w"] == 150.0
    assert s.overhead_s >= 0.0
    _fake_nvml(monkeypatch, fail=True)
    with pytest.raises(MetricUnavailable, match="driver gone"):
        with gm.NvmlSeries().sample(0.001):
            pass


def test_ncu_probe_reports_admin_only_counters(monkeypatch, tmp_path):
    monkeypatch.setattr(gm.shutil, "which", lambda n: "/usr/local/cuda/bin/ncu" if n == "ncu" else None)
    p = gm.NcuReplay()
    p.params_path = tmp_path / "params"
    p.params_path.write_text("RmProfilingAdminOnly: 1\n")
    monkeypatch.setattr(gm.os, "geteuid", lambda: 1006)
    a = p.probe()
    assert not a.available and "restricted to admin" in a.reason
    monkeypatch.setattr(gm.os, "geteuid", lambda: 0)
    assert p.probe().available
    monkeypatch.setattr(gm.shutil, "which", lambda n: None)
    assert p.probe().reason == "ncu not found"


def test_ncu_parse_skips_the_units_row(tmp_path):
    m = gm.config()["ncu"]["metrics"]
    head = ["ID", "Kernel Name", *m.values()]
    rows = [head, ["", "", "%", "%", "%", "nsecond"], ["0", "gemm_k", "80.5", "20.0", "60.0", "1,200"],
            ["1", "elementwise_k", "10.0", "5.0", "30.0", "300"]]
    out = tmp_path / "ncu.csv"
    out.write_text("==PROF== noise\n" + "\n".join(",".join(f'"{c}"' for c in r) for r in rows) + "\n")
    got = gm.NcuReplay().parse(out)
    assert [g["kernel"] for g in got] == ["gemm_k", "elementwise_k"] and got[0]["dram_pct"] == 80.5 and got[0]["duration_ns"] == 1200.0
    cmd = gm.NcuReplay().command(["python", "x.py"], out)
    assert cmd[:2] == ["ncu", "--csv"] and cmd[-2:] == ["python", "x.py"] and m["dram_pct"] in cmd[cmd.index("--metrics") + 1]


def test_torch_trace_links_kernels_to_ops_and_annotations():
    doc = {"traceEvents": [
        {"ph": "X", "cat": "user_annotation", "name": "adept:L12", "ts": 0, "dur": 100},
        {"ph": "X", "cat": "cpu_op", "name": "aten::mm", "ts": 10, "dur": 5, "args": {"External id": 7}},
        {"ph": "X", "cat": "kernel", "name": "gemm_k", "ts": 20, "dur": 30, "args": {"External id": 7}},
        {"ph": "X", "cat": "kernel", "name": "orphan_k", "ts": 200, "dur": 10, "args": {"External id": 99}}]}
    k = gm.TorchTrace().kernels(doc, offset_ns=1000)
    assert k[0] == gm.Kernel("gemm_k", 21000, 30000, "aten::mm", ("adept:L12",)) and k[1].op == "" and k[1].annotations == ()
    with pytest.raises(ValueError):
        gm.TorchTrace().kernels({})


def test_series_attribution_aggregate_and_roofline():
    rows = [{"t_ns": 0, "mem_util_pct": 0.0}, {"t_ns": 100, "mem_util_pct": 80.0}, {"t_ns": 200, "mem_util_pct": 20.0}]
    ks = [gm.Kernel("a", 50, 100, "aten::mm"), gm.Kernel("b", 300, 10, "aten::add")]
    per = gm.series_per_kernel(rows, ks, ["mem_util_pct"])
    assert per[0]["mem_util_pct"] == pytest.approx(50.0) and per[0]["n_windows"] == 2 and "mem_util_pct" not in per[1]
    recs = gm.aggregate(per + [{"kernel": gm.Kernel("c", 0, 100, "aten::add"), "n_windows": 1, "mem_util_pct": 25.0}],
                        lambda k: k.op, {"mem_util_pct": "pct"}, "nvml", "op")
    by = {r.key: r for r in recs}
    assert by["aten::mm"].share == pytest.approx(50.0) and by["aten::mm"].lift == pytest.approx(50.0 / 37.5)
    assert gm.roofline_class(80, 20) == "memory_bound" and gm.roofline_class(20, 80) == "compute_bound" and gm.roofline_class(10, 20) == "latency_bound"



def test_series_per_kernel_matches_a_scan_of_every_window():
    import random
    rng = random.Random(7)
    rows = [{"t_ns": t, "m": rng.random()} for t in sorted(rng.sample(range(10_000), 300))]
    ks = [gm.Kernel(str(i), rng.randrange(-500, 10_500), rng.randrange(0, 400), "") for i in range(200)]
    for k, got in zip(ks, gm.series_per_kernel(rows, ks, ["m"])):
        s, e = k.start_ns, k.start_ns + max(k.dur_ns, 1)
        win = [(min(e, b["t_ns"]) - max(s, a["t_ns"]), b["m"]) for a, b in zip(rows, rows[1:])]
        win = [(ov, v) for ov, v in win if ov > 0]
        assert got["n_windows"] == len(win)
        if win:
            assert got["m"] == pytest.approx(sum(ov * v for ov, v in win) / sum(ov for ov, _ in win))


def test_peaks_are_host_data_and_fail_loud_when_undeclared(monkeypatch):
    with pytest.raises(MetricUnavailable, match="no peaks declared"):
        gm.peaks("NVIDIA RTX 5000 Ada Generation")
    monkeypatch.setattr(gm, "config", lambda: {"peaks": {"G": {"dram_gbps": 1.0, "source": "datasheet"}}})
    assert gm.peaks("G")["source"] == "datasheet"
