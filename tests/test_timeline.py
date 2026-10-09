import pytest

from codegreen.analysis import timeline as tl

S = 10**9


def _nemb():
    """NEMB time series as nemb_get_time_series_json writes it: 10 Hz, 50 W for
    1 s then 150 W for 1 s; AMD RAPL exposes no per-domain watts except here."""
    out, e = [], 0.0
    for k in range(21):
        w = 50.0 if k <= 10 else 150.0
        e += 0.0 if k == 0 else w * 0.1
        out.append({"t_ns": k * S // 10, "energy_j": e, "power_w": w,
                    "domain_j": {"package-0": e}, "domain_w": {"gpu0": w / 2}})
    return out


def _jfr(offset_s: int):
    """`jfr print --json` shape: recording.events[].type/values, frames top-first."""
    def sample(t, leaf):
        return {"type": "jdk.ExecutionSample", "values": {
            "startTime": f"1970-01-01T00:00:{offset_s + t:012.9f}Z", "sampledThread": {"javaName": "main"},
            "stackTrace": {"truncated": False, "frames": [
                {"method": {"type": {"name": "org/rb/Util"}, "name": leaf}},
                {"method": {"type": {"name": "org/rb/Bitmap"}, "name": "checkedAdd"}}]}}}
    ev = [sample(0.05 + 0.1 * k, "lowbits" if k < 10 else "search") for k in range(20)]
    ev.append({"type": "jdk.GarbageCollection", "values": {
        "startTime": f"1970-01-01T00:00:{offset_s + 1.2:012.9f}Z", "duration": "PT0.1S", "name": "G1New"}})
    ev.append({"type": "jdk.ObjectAllocationInNewTLAB", "values": {
        "startTime": f"1970-01-01T00:00:{offset_s + 0.5:012.9f}Z", "allocationSize": 4096}})
    ev.append({"type": "jdk.ThreadSleep", "values": {"startTime": "1970-01-01T00:00:00Z"}})
    return {"recording": {"events": ev}}


def _torch():
    """torch.profiler export_chrome_trace: us units, kernel/cuda_runtime cats."""
    ev = [{"ph": "X", "cat": "kernel", "name": "sgemm", "ts": 1000.0 + 100.0 * k, "dur": 50.0} for k in range(5)]
    ev += [{"ph": "X", "cat": "cuda_runtime", "name": "cudaLaunchKernel", "ts": 1050.0 + 100.0 * k, "dur": 50.0}
           for k in range(4)]
    ev += [{"ph": "X", "cat": "cpu_op", "name": "aten::mm", "ts": 1000.0, "dur": 500.0}]
    return {"traceEvents": ev}


def test_importers_put_every_source_on_one_clock_and_export_perfetto():
    tr = tl.from_nemb(_nemb()).merge(tl.from_jfr(_jfr(30), offset_ns=-30 * S)).merge(
        tl.from_torch(_torch(), offset_ns=0))
    assert tr.counters["power_w/gpu0"][0] == (0, 25.0) and len(tr.energy) == 21
    assert tr.samples[0] == (S // 20, "main", ("org.rb.Bitmap.checkedAdd", "org.rb.Util.lowbits"))
    assert ("jvm/GarbageCollection", "G1New", 12 * S // 10, S // 10) in tr.slices
    assert tr.counters["alloc_bytes/event"] == [(S // 2, 4096.0)]
    assert {s[0] for s in tr.slices} == {"jvm/GarbageCollection", "gpu/kernel", "cpu/cuda_runtime"}
    ev = tl.to_perfetto(tr)["traceEvents"]
    assert {e["ph"] for e in ev} == {"M", "C", "X", "i"}
    assert any(e["ph"] == "i" and e["name"] == "org.rb.Util.lowbits" for e in ev)


def test_analysis_finds_phases_energy_gpu_gaps_launch_bound_and_gc():
    tr = tl.from_nemb(_nemb()).merge(tl.from_jfr(_jfr(0), offset_ns=0)).merge(tl.from_torch(_torch(), offset_ns=0))
    out = tl.analyze(tr, rel_change=0.5, confirm=2, gap_min_ns=10_000, launch_bound_frac=0.9)
    p1, p2 = out["phases"]
    assert (p1["mean_power_w"], p2["mean_power_w"]) == (50.0, 150.0)
    assert p1["top_method"] == "org.rb.Util.lowbits" and p2["top_method"] == "org.rb.Util.search"
    assert p1["energy_j"] == pytest.approx(50.0) and p2["energy_j"] == pytest.approx(150.0)
    assert p1["top_kernel"] == "sgemm"
    g = out["gpu"]
    assert g["idle_gaps"] == 4 and g["gap_launch_covered_frac"] == pytest.approx(1.0) and g["launch_bound"]
    assert out["gc_frac"] == pytest.approx(0.1 / out["wall_s"])
    assert out["method_energy"]["energy_j"] == pytest.approx(200.0)


def test_malformed_inputs_fail_loud():
    with pytest.raises(ValueError, match="non-empty JSON list"):
        tl.from_nemb({})
    with pytest.raises(ValueError, match="recording.events"):
        tl.from_jfr({"events": []}, 0)
    with pytest.raises(ValueError, match="traceEvents"):
        tl.from_torch({}, 0)
    with pytest.raises(ValueError, match="timestamp"):
        tl._wall_ns("yesterday")
    with pytest.raises(ValueError, match="duration"):
        tl._dur_ns("1.5 ms")
    assert tl._dur_ns(1500) == 1500 and tl._dur_ns("PT1M0.5S") == 60_500_000_000


def test_cli_writes_perfetto_trace_and_summary(tmp_path):
    import json
    from typer.testing import CliRunner
    from codegreen.cli.cli import app
    (tmp_path / "n.json").write_text(json.dumps(_nemb()))
    (tmp_path / "t.json").write_text(json.dumps(_torch()))
    r = CliRunner().invoke(app, ["timeline", "--out", str(tmp_path / "trace.json"), "--nemb", str(tmp_path / "n.json"),
                                 "--torch", str(tmp_path / "t.json"), "--rel-change", "0.5", "--confirm", "2"])
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["gpu"]["idle_gaps"] == 4
    assert json.loads((tmp_path / "trace.json").read_text())["traceEvents"]
    assert CliRunner().invoke(app, ["timeline", "--out", str(tmp_path / "x.json")]).exit_code != 0
