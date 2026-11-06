import types

import pytest

from codegreen.analysis import hwcounters as hw
from codegreen.analysis import metrics, sampling

AMD = "processor\t: 0\nvendor_id\t: AuthenticAMD\ncpu family\t: 25\nmodel\t\t: 17\n\nprocessor\t: 1\nvendor_id\t: other\n"
INTEL = "vendor_id\t: GenuineIntel\ncpu family\t: 6\n"
NEOVERSE = "processor\t: 0\nCPU implementer\t: 0x41\nCPU part\t: 0xd40\n"
OLD_AMD = "vendor_id\t: AuthenticAMD\ncpu family\t: 21\n"
STAT = ("# started on x\n\n"
        "4000000,,cycles,1000,100.00,,\n8000000,,instructions,1000,100.00,2.00,insn per cycle\n"
        "1000,,cache-references,1000,100.00,,\n250,,cache-misses,1000,62.50,,\n2000,,branch-instructions,1000,100.00,,\n"
        "20,,branch-misses,1000,100.00,,\n<not supported>,,LLC-load-misses,0,100.00,,\n<not counted>,,stalled-cycles-backend,0,0.00,,\n")


def test_event_maps_are_data_selected_by_cpuinfo_with_generic_fallback():
    assert hw.event_map(hw.cpuinfo_fields(AMD))[0] == "amd_zen"
    assert hw.cpuinfo_fields(AMD)["vendor_id"] == "AuthenticAMD"          # first processor block only
    assert hw.event_map(hw.cpuinfo_fields(INTEL))[0] == "intel"
    name, ev = hw.event_map(hw.cpuinfo_fields(NEOVERSE))
    assert name == "arm_neoverse" and ev["stalled_backend"] == "stall_backend" and ev["cycles"] == "cycles"
    assert hw.event_map(hw.cpuinfo_fields(OLD_AMD))[0] == "generic"           # family below the amd_zen rule
    assert hw.event_map({})[0] == "generic"


def test_a_new_architecture_is_a_data_file(tmp_path):
    for p in hw.EVENTS_DIR.glob("*.json"):
        (tmp_path / p.name).write_text(p.read_text())
    (tmp_path / "riscv.json").write_text('{"name": "riscv", "priority": 10, "match": {"isa": "rv64imafdc"}, "events": {"cycles": "riscv_cycles"}}')
    name, ev = hw.event_map({"isa": "rv64imafdc"}, tmp_path)
    assert name == "riscv" and ev["cycles"] == "riscv_cycles" and ev["instructions"] == "instructions"


def test_counts_unavailable_and_multiplexing_are_recorded_never_dropped(tmp_path):
    p = hw.PerfCounters({"perf": "perf", "attribution": {"cache_misses": 10007}}, cpuinfo=AMD)
    argv, env = p.wrap(["java", "-jar", "b.jar"], {"A": "1"}, tmp_path)
    assert argv[:4] == ["perf", "stat", "-x", ","] and argv[-3:] == ["java", "-jar", "b.jar"] and env == {"A": "1"}
    (tmp_path / "perf_stat.csv").write_text(STAT)
    rows = {r.metric: r for r in p.read(tmp_path)}
    assert rows["ipc"].value == 2.0 and rows["ipc"].unit == "ratio" and rows["ipc"].scope == "run"
    assert rows["cache_miss_rate"].value == 0.25 and rows["branch_miss_rate"].value == 0.01
    assert rows["mpki"].value == pytest.approx(1000 * 250 / 8e6) and rows["mpki"].reason == "basis cache_misses"
    assert rows["cache_misses"].reason == "multiplexed 62% of run time"
    assert not rows["llc_misses"].available and rows["llc_misses"].reason == "not supported"
    assert not rows["stalled_backend"].available and not rows["backend_stall_fraction"].available
    assert not rows["l1i_misses"].available and rows["l1i_misses"].reason == "not reported"
    assert p.sampled_events() == {"cache_misses": ("cache-misses", 10007)}


def test_attribution_events_must_be_in_the_map_and_probe_reports_each_event(monkeypatch):
    with pytest.raises(ValueError, match="outside the amd_zen map"):
        hw.PerfCounters({"perf": "perf", "attribution": {"bogus": 1}}, cpuinfo=AMD)
    p = hw.PerfCounters({"perf": "perf", "attribution": {}}, cpuinfo=AMD)

    def run(argv, **kw):
        ev = argv[argv.index("-e") + 1]
        return types.SimpleNamespace(returncode=0, stderr="<not supported>,,LLC-load-misses,,,\n" if ev == "LLC-load-misses"
                                     else f"5,,{ev},1,100.00,,\n")
    monkeypatch.setattr(hw.subprocess, "run", run)
    monkeypatch.setattr(hw.shutil, "which", lambda b: "/usr/bin/perf")
    r = p.probe()
    assert r.available and r.details["arch"] == "amd_zen" and r.details["events"]["cycles"]["available"]
    assert r.details["events"]["llc_misses"] == {"available": False, "reason": "not supported"}
    monkeypatch.setattr(hw.shutil, "which", lambda b: None)
    assert not p.probe().available and "not found" in p.probe().reason


def test_hybrid_pmus_add_up_and_an_uncounted_core_type_does_not_hide_the_count():
    text = ("3000,,cpu_core/cycles/,800,100.00,,\n1000,,cpu_atom/cycles/,200,40.00,,\n"
            "<not counted>,,cpu_atom/instructions/,0,0.00,,\n5000,,cpu_core/instructions/,800,100.00,,\n"
            "<not supported>,,cpu_atom/cache-misses/,0,100.00,,\n<not supported>,,cpu_core/cache-misses/,0,100.00,,\n")
    res = hw.parse_stat(text, {"cycles": "cycles", "instructions": "instructions", "cache_misses": "cache-misses"})
    assert res["counts"] == {"cycles": 4000.0, "instructions": 5000.0} and res["running_pct"]["cycles"] == 40.0
    assert res["unavailable"] == {"cache_misses": "not supported"}


def test_a_host_without_cpuinfo_reports_an_unavailable_provider(monkeypatch, tmp_path):
    monkeypatch.setattr(hw, "CPUINFO", tmp_path / "absent")
    monkeypatch.setattr("sys.platform", "darwin")
    p = hw.PerfCounters({"perf": "perf", "attribution": {"cache_misses": 10007}})
    a = p.probe()
    assert not a.available and "perf_event counters need Linux" in a.reason
    with pytest.raises(metrics.MetricUnavailable, match="need Linux"):
        p.wrap(["true"], {}, tmp_path)


def test_metric_records_share_one_schema_and_providers_register_once():
    with pytest.raises(ValueError, match="unknown metric scope"):
        metrics.MetricRecord("x", "count", "module", "", 1.0, "p")
    with pytest.raises(ValueError, match="needs a reason"):
        metrics.MetricRecord("x", "count", "run", "", None, "p", available=False)
    stub = types.SimpleNamespace(name="stub_provider_for_test")
    assert metrics.register_provider(stub) is stub and metrics.get_provider("stub_provider_for_test") is stub
    with pytest.raises(ValueError, match="already registered"):
        metrics.register_provider(stub)
    del metrics.PROVIDERS._items["stub_provider_for_test"]
    with pytest.raises(KeyError, match="no metric provider"):
        metrics.get_provider("stub_provider_for_test")


def test_attribution_gives_inclusive_shares_and_lift_over_the_cpu_share():
    stacks = [((("", "main", None), ("A", "f", None)), 60.0), ((("", "main", None), ("A", "g", None)), 40.0)]
    rows = {r.key: r for r in metrics.attribute("cache_misses", "hw_counters", stacks,
                                                   {"A.f": lambda fr: fr[:2] == ("A", "f"), "A.g": lambda fr: fr[:2] == ("A", "g")},
                                                   {"A.f": 30.0, "A.g": None})}
    assert rows["A.f"].share == 60.0 and rows["A.f"].lift == 2.0 and rows["A.f"].scope == "function"
    assert rows["A.g"].share == 40.0 and rows["A.g"].lift is None
    none = metrics.attribute("m", "p", [], {"A.f": lambda fr: True}, {})
    assert not none[0].available and none[0].reason == "no samples"


def test_a_registry_probes_each_provider_once_until_it_is_replaced():
    calls = []

    class P:
        name = "p"

        def probe(self):
            calls.append(1)
            return metrics.Availability("p", True)
    r = metrics.Registry("t")
    r.register(P())
    assert r.probe()[0].available and r.available() and len(calls) == 1
    r.put(P())
    assert r.available() and len(calls) == 2


def test_perf_script_becomes_root_first_weighted_stacks():
    text = ("python3 10007 cache-misses: \n\t 7f12 py::work:/src/app.py\n\t 7f00 _PyEval_EvalFrameDefault+0x1a2\n\t 7e00 main+0x5\n\n"
            "python3 10007 cache-misses: \n\t 7f12 py::work:/src/app.py\n\t 7e00 main+0x9\n\npython3 10007 cache-misses: \n")
    st = sampling.parse_perf_script(text)
    assert st[("main", "_PyEval_EvalFrameDefault", "py::work:/src/app.py")] == 1
    assert st[("main", "py::work:/src/app.py")] == 1 and st[("[unknown]",)] == 1   # a stackless sample keeps its weight
    with pytest.raises(ValueError, match="without an integer period"):
        sampling.parse_perf_script("python3 cache-misses: \n\t 7f12 main+0x5\n")


def test_backends_sample_any_event_per_language_and_normalize_frames(tmp_path, monkeypatch):
    lib = tmp_path / "ap" / "lib"
    lib.mkdir(parents=True)
    (lib / "libasyncProfiler.so").write_text("")
    env = {sampling.ASYNC_PROFILER_ENV: str(tmp_path / "ap")}
    argv, env2 = sampling.backend_for("java").command(["java", "-cp", "x", "Main"], env, tmp_path / "o", "cache-misses", 10007)
    assert "event=cache-misses,interval=10007,ann,collapsed" in env2["JAVA_TOOL_OPTIONS"]
    _, env3 = sampling.backend_for("java").command(["java", "Main"], env, tmp_path / "o", "cpu", 997)
    assert "event=cpu,interval=997us" in env3["JAVA_TOOL_OPTIONS"]
    monkeypatch.setattr(sampling, "load_config", lambda: {"hw_counters": {"perf": "/opt/perf"}})
    argv, env4 = sampling.backend_for("python").command(["python", "app.py"], {}, tmp_path / "p", "cache-misses", 10007)
    assert argv[:2] == ["/opt/perf", "record"] and "-g" in argv and env4["PYTHONPERFSUPPORT"] == "1"
    (tmp_path / "o" / "1.collapsed").write_text("java.lang.Thread.run;org/rb/Util.lowbits_[j] 7\nlibjvm.so 3\n")
    (tmp_path / "p" / "perf.collapsed").write_text("main;py::work:/src/app.py 5\n")
    js = sampling.sampled_stacks("java", sampling.backend_for("java").read(tmp_path / "o"))
    assert ((("java.lang.Thread", "run", None), ("org.rb.Util", "lowbits", None)), 7.0) in js and ((("", "libjvm.so", None),), 3.0) in js
    py = sampling.sampled_stacks("python", [tmp_path / "p" / "perf.collapsed"])
    assert py == [((("", "main", None), ("/src/app.py", "work", None)), 5.0)]
    with pytest.raises(KeyError, match="no events sampler for language .cobol."):
        sampling.backend_for("cobol")


def test_one_language_registry_holds_every_sampler_component_and_refuses_duplicates():
    from codegreen.analysis import languages, line_sampling
    assert {"java", "python", "native"} <= set(languages.supporting("events")) and "python" in languages.supporting("lines")
    py = languages.get("python")
    assert py.events is sampling.backend_for("python") and py.lines is line_sampling.adapter("python")
    with pytest.raises(ValueError, match="already has a events component"):
        languages.add("python", events=py.events)
    with pytest.raises(ValueError, match="unknown language component"):
        languages.add("python", grammar=object())
    with pytest.raises(KeyError, match="no lines sampler for language 'native'"):
        languages.component("native", "lines")


def test_capability_report_covers_every_registry_through_their_probes(monkeypatch):
    from codegreen.analysis import gpu_metrics, languages
    from codegreen.cli import cli
    for reg in (gpu_metrics.GPU_SERIES, gpu_metrics.GPU_REPLAY, gpu_metrics.GPU_FRAMEWORKS, languages.LANGUAGES):
        monkeypatch.setattr(reg, "probe", lambda reg=reg: [metrics.Availability(n, False, "stubbed") for n in reg.names()])
    monkeypatch.setattr(hw, "provider", lambda: None)
    monkeypatch.setattr(metrics.PROVIDERS, "probe", lambda: [metrics.Availability("hw_counters", True, details={"arch": "amd_zen"})])
    rep = cli.capability_report()
    assert set(rep) == {"metric", "gpu_series", "gpu_replay", "gpu_framework", "language"}
    assert rep["metric"][0]["details"]["arch"] == "amd_zen" and [a["provider"] for a in rep["gpu_series"]] == ["nvml"]
    assert {"java", "python", "native"} <= {a["provider"] for a in rep["language"]}
    assert set(cli.capability_report(["metric"])) == {"metric"}
    with pytest.raises(cli.typer.BadParameter, match="unknown registries"):
        cli.capability_report(["gpu"])


def test_capabilities_metric_reports_unavailable_counters_on_a_host_without_perf_event(monkeypatch, tmp_path):
    import json

    from typer.testing import CliRunner

    from codegreen.cli.cli import app
    fresh = metrics.Registry("metric")
    monkeypatch.setattr(hw, "PROVIDERS", fresh)
    monkeypatch.setattr(metrics, "PROVIDERS", fresh)
    monkeypatch.setattr(hw, "CPUINFO", tmp_path / "absent")
    monkeypatch.setattr("sys.platform", "darwin")
    r = CliRunner().invoke(app, ["capabilities", "metric"])
    assert r.exit_code == 0, r.output
    rep = json.loads(r.output)
    assert list(rep) == ["metric"] and rep["metric"][0]["provider"] == "hw_counters"
    assert not rep["metric"][0]["available"] and "need Linux" in rep["metric"][0]["reason"]
