import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from codegreen.analysis.metrics import MetricRecord

from codegreen.analysis import line_sampling as ls


def _raw(tmp_path, root):
    p = tmp_path / "rec.raw"
    app, lib = f"{root}/app/work.py", "/usr/lib/python3.11/site-packages/numpy/core/numeric.py"
    p.write_text(f"main ({app}:3);inner ({app}:7) 6\n"
                 f"main ({app}:3);inner ({app}:8);dot ({lib}:10);cblas_dgemm (libopenblas.so) 3\n"
                 f"main ({app}:4) 1\n")
    return p


def test_line_profile_splits_lines_functions_and_leaf_kinds_in_the_common_schema(tmp_path):
    root = str(tmp_path / "proj")
    lp = ls.line_profile("python", [_raw(tmp_path, root)], root)
    assert lp["samples"] == 10
    top = lp["lines"][0]
    assert (top.metric, top.scope, top.detail["function"], top.detail["line"], top.value, top.share) == ("cpu_samples", "line", "inner", 7, 6, 60.0)
    assert top.key.endswith(":inner:7") and top.provider == "line_sampler"
    assert {(r.detail["line"], r.value, r.detail["total_samples"]) for r in lp["lines"]} == {(7, 6, 6), (8, 0, 3), (3, 0, 9), (4, 1, 1)}
    fn = {r.detail["function"]: (r.value, r.detail["total_samples"]) for r in lp["functions"]}
    assert fn == {"inner": (6, 9), "main": (1, 10)}
    run = {r.metric: r.value for r in lp["run"]}
    assert run == {"project_leaf_samples": 7, "library_leaf_samples": 0, "native_leaf_samples": 3, "irreducible_leaf_samples": 3}
    assert {(c["function"], c["line"], c["callee_function"], c["samples"]) for c in lp["call_sites"]} == {("main", 3, "inner", 9), ("inner", 8, "dot", 3)}
    assert all(isinstance(r, MetricRecord) for r in lp["lines"] + lp["functions"] + lp["run"])


def test_empty_recordings_and_unknown_languages_fail_loud(tmp_path):
    (tmp_path / "e.raw").write_text("")
    with pytest.raises(ValueError, match="no samples"):
        ls.line_profile("python", [tmp_path / "e.raw"], str(tmp_path))
    with pytest.raises(ValueError, match="no line-sampler recording"):
        ls.line_profile("python", [], str(tmp_path))
    with pytest.raises(ValueError, match="no lines sampler for language 'cobol'"):
        ls.adapter("cobol")
    with pytest.raises(ValueError, match="needs a reason"):
        ls.metric("x", "s", "line", None, available=False)
    with pytest.raises(ValueError, match="scope"):
        ls.metric("x", "s", "process", 1)


def test_command_adds_features_and_pass_flags_and_refuses_unknown_passes(tmp_path):
    argv, env = ls.command("python", ["python3", "w.py"], tmp_path / "o.raw", 97, {"native": True}, "idle", env={"A": "1"})
    assert argv[:5] == ["py-spy", "record", "--format", "raw", "--full-filenames"] and "--native" in argv and "--idle" in argv
    assert argv[-3:] == ["--", "python3", "w.py"] and "--gil" not in argv and env == {"A": "1"}
    argv, _ = ls.command("python", ["python3", "w.py"], tmp_path / "o.raw", None, {"binary": "/opt/py-spy"}, "cpu")
    assert argv[0] == "/opt/py-spy" and "--native" not in argv and argv[argv.index("--rate") + 1] == str(ls.settings("python")["rate_hz"])
    with pytest.raises(ValueError, match="no pass 'perf'"):
        ls.command("python", ["python3"], tmp_path / "o.raw", 97, {}, "perf")


def test_capabilities_record_every_requested_feature_the_sampler_lacks(monkeypatch):
    monkeypatch.setattr(ls.shutil, "which", lambda b: "/usr/bin/py-spy")
    help_text = "record --native --idle --rate"
    monkeypatch.setattr(ls.subprocess, "run", lambda argv, **k: SimpleNamespace(stdout="py-spy 0.3.14" if "--version" in argv else help_text))
    cap = ls.capabilities("python", {"native": True, "passes": ["idle", "gil"]})
    assert cap["available"] and cap["version"] == "py-spy 0.3.14" and cap["unavailable"] == {"gil": "sampler lacks --gil"}
    monkeypatch.setattr(ls.shutil, "which", lambda b: None)
    cap = ls.capabilities("python", {"native": True})
    assert not cap["available"] and cap["unavailable"]["native"].startswith("sampler not available: py-spy binary")


def test_pass_ratio_keeps_the_raw_per_second_ratio_and_flags_values_above_one(tmp_path):
    root = str(tmp_path / "proj")
    cpu = _raw(tmp_path, root)
    idle = tmp_path / "idle.raw"
    idle.write_text(f"main ({root}/app/work.py:3);inner ({root}/app/work.py:7) 18\n")
    r = {x.detail["function"]: x.value for x in ls.pass_ratio("python", [cpu], 1.0, [idle], 1.0, root, "on_cpu_fraction")}
    assert r == {"inner": 0.5, "main": 0.5556}
    up = {x.detail["function"]: x for x in ls.pass_ratio("python", [idle], 1.0, [cpu], 1.0, root, "x")}
    assert up["inner"].value == 2.0 and up["inner"].detail["above_one"] and up["inner"].unit == "ratio"
    with pytest.raises(ValueError, match="durations"):
        ls.pass_ratio("python", [cpu], 0.0, [idle], 1.0, root, "x")


def test_pyalloc_writes_line_hot_spots_read_back_as_line_records(tmp_path):
    script = tmp_path / "w.py"
    script.write_text("keep = [bytearray(1 << 16) for _ in range(20)]\n")
    out = tmp_path / "alloc.json"
    argv, env = ls.adapter("python").alloc([sys.executable, str(script)], out, {"alloc_top": 5})
    subprocess.run(argv, env=env, check=True, timeout=60)
    recs = ls.read_alloc(out)
    assert recs[0].metric == "alloc_bytes" and (recs[0].detail["file"], recs[0].detail["line"]) == (str(script), 1) and recs[0].value >= 20 * (1 << 16)
    assert json.loads(out.read_text())["frames"] == 1
    argv, _ = ls.adapter("python").alloc(["taskset", "-c", "2", sys.executable, str(script), "-v"], out, {})
    assert argv[:4] == ["taskset", "-c", "2", sys.executable] and argv[4:6] == ["-m", "codegreen.analysis.pyalloc"]
    assert argv[-3:] == ["--", str(script), "-v"] and argv[argv.index("--top") + 1] == str(ls.settings("python")["alloc_top"])
    with pytest.raises(ValueError, match="needs a Python interpreter"):
        ls.adapter("python").alloc(["./run.sh"], out, {})


JAVA = ("java/lang/Thread.run:829;org/rb/Bitmap.add:10;org/rb/Util.low:5 30\n"
        "java.lang.Thread.run:829;org.rb.Bitmap.add:10;org.rb.Util.low:5 20\n"
        "java.lang.Thread.run:829;org.rb.Bitmap.add:12 25\n"
        "java.lang.Thread.run:829;org.rb.Bitmap.add:12;org.rb.Bitmap$Node.lambda$add$0:0 15\n"
        "java.lang.Thread.run:829;org.rb.Bitmap.add:10;org.rb.Util.low:5;libjvm.so 6\n"
        "JavaThread::thread_main_inner 4\n")


def test_java_lines_come_from_the_config_frame_grammar_as_common_schema_records(tmp_path, monkeypatch):
    (tmp_path / "ap" / "lib").mkdir(parents=True)
    (tmp_path / "ap" / "lib" / "libasyncProfiler.so").write_text("")
    (tmp_path / "ap" / "bin").mkdir()
    (tmp_path / "ap" / "bin" / "jfrconv").write_text("")
    root, proj = str(tmp_path / "ap"), str(tmp_path / "proj")
    argv, env = ls.command("java", ["java", "-cp", "x", "Main"], tmp_path / "o", None, {"async_profiler": root}, env={})
    assert argv == ["java", "-cp", "x", "Main"] and env["JAVA_TOOL_OPTIONS"].endswith(
        f"event=cpu,interval=997us,jfr,file={tmp_path}/o/%p.jfr -XX:+UnlockDiagnosticVMOptions -XX:+DebugNonSafepoints")

    def jfrconv(cmd, **kw):
        Path(cmd[-1]).write_text(JAVA)
        return subprocess.CompletedProcess(cmd, 0, "", "")
    (tmp_path / "o" / "7.jfr").write_text("")
    monkeypatch.setattr("subprocess.run", jfrconv)
    files = ls.read("java", tmp_path / "o", {"async_profiler": root})
    lp = ls.line_profile("java", files, proj)
    assert lp["samples"] == 100 and all(isinstance(r, MetricRecord) for r in lp["lines"])
    assert [(r.detail["file"], r.detail["function"], r.detail["line"], r.value, r.detail["total_samples"]) for r in lp["lines"]] == [
        ("org.rb.Util", "low", 5, 50, 56), ("org.rb.Bitmap", "add", 12, 25, 40),
        ("org.rb.Bitmap$Node", "lambda$add$0", None, 15, 15), ("org.rb.Bitmap", "add", 10, 0, 56)]
    run = {r.metric: r for r in lp["run"]}
    assert (run["project_leaf_samples"].value, run["library_leaf_samples"].value, run["native_leaf_samples"].value) == (90, 0, 10)
    assert not run["irreducible_leaf_samples"].available and "no irreducible_re" in run["irreducible_leaf_samples"].reason
    assert {(c["function"], c["line"], c["callee_function"], c["samples"]) for c in lp["call_sites"]} == {
        ("add", 10, "low", 56), ("add", 12, "lambda$add$0", 15), ("low", 5, "libjvm.so", 6)}
    with pytest.raises(FileNotFoundError, match="no JFR recording"):
        ls.read("java", tmp_path / "empty", {"async_profiler": root})
    assert ls.capabilities("java", {"async_profiler": root})["available"]
    assert not ls.capabilities("java", {"async_profiler": str(tmp_path)})["available"]
