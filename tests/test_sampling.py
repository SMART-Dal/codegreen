import pytest
from pathlib import Path

from codegreen.analysis.sampling import java_agent_command, java_agent_option, jfr_to_collapsed, parse_collapsed


def test_collapsed_shares_self_total_and_inlining(tmp_path):
    f = tmp_path / "1.collapsed"
    f.write_text("java.lang.Thread.run;org/rb/RoaringBitmap.checkedAdd_[j];org/rb/Util.lowbits_[i] 30\n"
                 "java.lang.Thread.run;org/rb/RoaringBitmap.checkedAdd_[j] 60\n"
                 "java.lang.Thread.run;org/rb/RoaringBitmap.checkedAdd_[j];org/rb/Util.lowbits_[j] 10\n")
    r = parse_collapsed([f])
    m = r["methods"]
    assert r["samples"] == 100
    assert m["org.rb.RoaringBitmap.checkedAdd"]["self_pct"] == 60.0
    assert m["org.rb.RoaringBitmap.checkedAdd"]["total_pct"] == 100.0
    assert m["org.rb.Util.lowbits"]["self_pct"] == 40.0
    assert m["org.rb.Util.lowbits"]["inlined_pct"] == 75.0


def test_empty_profile_and_missing_profiler_fail_loud(tmp_path, monkeypatch):
    (tmp_path / "e.collapsed").write_text("")
    with pytest.raises(ValueError, match="no samples"):
        parse_collapsed([tmp_path / "e.collapsed"])
    monkeypatch.delenv("CODEGREEN_ASYNC_PROFILER", raising=False)
    with pytest.raises(RuntimeError, match="CODEGREEN_ASYNC_PROFILER"):
        java_agent_option(tmp_path, 997)


def test_agent_output_path_is_absolute_and_no_files_fails_loud(tmp_path, monkeypatch):
    """A relative file= path resolved against the JVM's cwd wrote no profile
    at all (ADEPT RoaringBitmap run, 2026-09-29)."""
    lib = tmp_path / "ap" / "lib"
    lib.mkdir(parents=True)
    (lib / "libasyncProfiler.so").write_text("")
    monkeypatch.chdir(tmp_path)
    opt = java_agent_option(Path("rel") / "sampling", 997, root=str(tmp_path / "ap"))
    assert f"file={tmp_path}/rel/sampling/%p.collapsed" in opt
    with pytest.raises(ValueError, match="no collapsed profile files"):
        parse_collapsed([])


def test_jmh_forks_get_the_agent_once_other_jvms_via_tool_options(tmp_path):
    import zipfile
    jmh, app = tmp_path / "benchmarks.jar", tmp_path / "app.jar"
    for jar, main in ((jmh, "org.openjdk.jmh.Main"), (app, "com.example.Main")):
        with zipfile.ZipFile(jar, "w") as z:
            z.writestr("META-INF/MANIFEST.MF", f"Manifest-Version: 1.0\nMain-Class: {main}\n")
    argv, env = java_agent_command(["java", "-jar", str(jmh), "Bench"], "-agentpath:x", {"A": "1"})
    assert argv[-2:] == ["-jvmArgsAppend", "-agentpath:x"] and "JAVA_TOOL_OPTIONS" not in env
    argv, env = java_agent_command(["java", "-jar", str(app)], "-agentpath:x", {"JAVA_TOOL_OPTIONS": "-Xmx1g"})
    assert argv == ["java", "-jar", str(app)] and env["JAVA_TOOL_OPTIONS"] == "-Xmx1g -agentpath:x"
    argv, _ = java_agent_command(["java", "-jar", str(jmh), "Bench", "-jvmArgsAppend", "-Xms4g -Xmx4g", "-rf", "json"], "-agentpath:x", {})
    assert argv == ["java", "-jar", str(jmh), "Bench", "-jvmArgsAppend", "-Xms4g -Xmx4g -agentpath:x", "-rf", "json"]



def _release(tmp_path):
    (tmp_path / "ap" / "lib").mkdir(parents=True)
    (tmp_path / "ap" / "lib" / "libasyncProfiler.so").write_text("")
    return str(tmp_path / "ap")


LINES = ("java/lang/Thread.run:829;org/rb/Bitmap.add:10;org/rb/Util.low:5 30\n"
         "java.lang.Thread.run:829;org.rb.Bitmap.add:10;org.rb.Util.low:5 20\n"
         "java.lang.Thread.run:829;org.rb.Bitmap.add:12 25\n"
         "java.lang.Thread.run:829;org.rb.Bitmap.add:12;org.rb.Bitmap$Node.lambda$add$0:0 15\n"
         "java.lang.Thread.run:829;org.rb.Bitmap.add:10;org.rb.Util.low:5;libjvm.so 6\n"
         "JavaThread::thread_main_inner 4\n")


def test_jfr_agent_option_and_converter_command(tmp_path, monkeypatch):
    root = _release(tmp_path)
    jfr = java_agent_option(tmp_path / "o", 997, root=root, fmt="jfr")
    assert jfr.endswith(f"event=cpu,interval=997us,jfr,file={tmp_path}/o/%p.jfr")
    assert java_agent_option(tmp_path / "o", 997, root=root).endswith(f"interval=997us,ann,collapsed,file={tmp_path}/o/%p.collapsed")
    with pytest.raises(ValueError, match="unknown async-profiler output"):
        java_agent_option(tmp_path / "o", 997, root=root, fmt="flamegraph")
    seen = []

    def fake(cmd, **kw):
        import subprocess
        seen.append(cmd)
        Path(cmd[-1]).write_text("a.B.m:1 1\n")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr("subprocess.run", fake)
    outs = jfr_to_collapsed([tmp_path / "o" / "42.jfr"], tmp_path / "c", root=root)
    assert outs == [tmp_path / "c" / "42.collapsed"]
    assert seen == [[f"{root}/bin/jfrconv", "--cpu", "--lines", "-o", "collapsed", str(tmp_path / "o" / "42.jfr"), str(outs[0])]]


def test_jfrconv_failures_carry_the_command_and_stderr(tmp_path, monkeypatch):
    import subprocess
    root = _release(tmp_path)
    monkeypatch.setattr("subprocess.run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 3, "", "bad jfr\n"))
    with pytest.raises(RuntimeError, match=r"jfrconv --cpu --lines .* exited 3: bad jfr"):
        jfr_to_collapsed([tmp_path / "1.jfr"], tmp_path / "c", root=root)

    def missing(cmd, **kw):
        raise FileNotFoundError(2, "No such file")
    monkeypatch.setattr("subprocess.run", missing)
    with pytest.raises(FileNotFoundError, match=r"jfrconv --cpu --lines .*No such file"):
        jfr_to_collapsed([tmp_path / "1.jfr"], tmp_path / "c", root=root)


def test_method_shares_accept_line_suffixed_frames_and_leave_inlining_unknown(tmp_path):
    f = tmp_path / "1.collapsed"
    f.write_text(LINES)
    m = parse_collapsed([f], annotated=False)["methods"]
    assert m["org.rb.Util.low"]["self_pct"] == 50.0 and m["org.rb.Util.low"]["total_pct"] == 56.0
    assert m["org.rb.Bitmap.add"]["self_pct"] == 25.0 and m["org.rb.Bitmap.add"]["total_pct"] == 96.0
    assert all(v["inlined_pct"] is None for v in m.values())
    assert parse_collapsed([f])["methods"]["org.rb.Util.low"]["inlined_pct"] == 0.0

def test_energy_by_method_splits_each_interval_across_its_samples():
    from codegreen.analysis.sampling import energy_by_method
    series = [(0, 0.0), (10, 4.0), (20, 10.0), (30, 10.5)]
    samples = [(2, ("main", "a")), (5, ("main", "b")),      # interval 1: 4 J over 2 samples
               (12, ("main", "a")),                          # interval 2: 6 J
               (40, ("main", "a"))]                          # outside the series
    r = energy_by_method(samples, series)
    assert r["energy_j"] == 10.5 and r["unattributed_j"] == 0.5 and r["samples_outside"] == 1
    assert r["methods"]["a"] == {"self_j": 8.0, "total_j": 8.0}
    assert r["methods"]["b"]["self_j"] == 2.0 and r["methods"]["main"] == {"self_j": 0.0, "total_j": 10.0}
    assert sum(m["self_j"] for m in r["methods"].values()) + r["unattributed_j"] == r["energy_j"]


def test_energy_by_method_refuses_misaligned_clocks():
    from codegreen.analysis.sampling import energy_by_method, monotonic_minus_realtime_ns
    with pytest.raises(ValueError, match="clocks not aligned"):
        energy_by_method([(10**18, ("m",))], [(0, 0.0), (10, 1.0)])
    assert isinstance(monotonic_minus_realtime_ns(), int)


def test_energy_by_method_keeps_a_decreasing_series_signed_and_flags_it_invalid():
    from codegreen.analysis.sampling import energy_by_method
    r = energy_by_method([(5, ("m",)), (15, ("m",))], [(0, 2.0), (10, 1.0), (20, 4.0)])
    assert r["methods"]["m"]["self_j"] == pytest.approx(2.0) and r["energy_j"] == 2.0
    assert (r["valid"], r["invalid_reason"], r["negative_intervals"]) == (False, "negative_energy", 1)
    ok = energy_by_method([(5, ("m",))], [(0, 0.0), (10, 1.0)])
    assert (ok["valid"], ok["invalid_reason"], ok["negative_intervals"]) == (True, None, 0)
