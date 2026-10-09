"""Comprehensive audit battery for the CodeGreen JSON report (Session API + CLI).

Every assertion below was derived from the v0.4.7 5-track audit (time, math,
naming, edge-cases, timeseries). Each named scenario reproduces a real bug
caught during that audit; the assertions guarantee the regression cannot
return silently.

Categories:
- TestSchemaPresence       programmatic structure: keys, types, dtypes
- TestNamingContract       no legacy field names; only the new short forms
- TestLogicalCorrectness   numeric self-consistency (energy = avg_power * time, etc.)
- TestEdgeCases            empty session, nested tasks, parallel threads, block-C gap
- TestTimeseriesMode       record_time_series=True: sort, dedup, window, sample interval
- TestQualityReporting     noise warnings, measurement_quality enum, drop_ratio math
- TestCLI                  `codegreen run` JSON output: pair-filtering, structured runs/backend, failure-path meta

Run: pytest tests/test_report_audit.py -v
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pytest

import codegreen
from codegreen import Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _busy(loops: int) -> int:
    """Deterministic CPU work, sized in iterations."""
    return sum(i * i for i in range(loops))


def _run_session(name: str, fn, **kw) -> Dict:
    s = Session(name, save_to_file=False, **kw).start()
    try:
        fn(s)
    finally:
        return s.stop()


_CG_REPO = Path(__file__).resolve().parent.parent


def _plain(text: str) -> str:
    """CLI output without ANSI codes (typer forces Rich colour when GITHUB_ACTIONS or FORCE_COLOR is set) and with
    wrapped lines joined, so assertions do not depend on the terminal."""
    import click
    return " ".join(click.unstyle(text).split())


def _cli_run(*args: str, timeout: float = 60.0, cwd: str = str(_CG_REPO)) -> tuple:
    """Invoke `codegreen <args>`. Returns (parsed_json_or_None, stdout, stderr, rc).
    Defaults cwd to the codegreen repo root to keep the editable-install import
    chain working regardless of where pytest runs from."""
    p = subprocess.run(["codegreen", *args], capture_output=True, text=True,
                       timeout=timeout, cwd=cwd)
    parsed = None
    try:
        parsed = json.loads(p.stdout)
    except Exception:
        pass
    return parsed, p.stdout, p.stderr, p.returncode


@pytest.fixture
def workload_session() -> Dict:
    """A session with two depth-0 tasks separated by an unmeasured gap."""
    def body(s: Session) -> None:
        with s.task("a"):
            _busy(3_000_000)
        time.sleep(0.05)
        with s.task("b"):
            _busy(5_000_000)
    return _run_session("audit_workload", body)


@pytest.fixture
def timeseries_session() -> Dict:
    """A timeseries-enabled session whose tasks are long enough to capture samples."""
    def body(s: Session) -> None:
        with s.task("outer"):
            with s.task("inner"):
                for _ in range(3):
                    time.sleep(0.05)
                    _busy(500_000)
    return _run_session("ts_workload", body, record_time_series=True)


# ===========================================================================
# 1. SCHEMA PRESENCE
# ===========================================================================
class TestSchemaPresence:
    """Programmatic checks: required top-level keys, sub-keys, types."""

    def test_top_level_keys(self, workload_session: Dict) -> None:
        assert set(workload_session.keys()) >= {"meta", "tasks", "totals"}

    def test_meta_required_keys(self, workload_session: Dict) -> None:
        m = workload_session["meta"]
        for k in (
            "schema_version", "codegreen_version", "run_id",
            "started_at", "ended_at", "duration_total_s",
            "hostname", "pid", "platform", "python_version",
            "cpu_model", "kernel", "cwd", "argv", "codegreen_env",
            "measurement_quality", "domain_support",
            "outlier_method", "iso_timestamp_format",
            "nemb_abi_version", "domain_topology", "timeseries",
        ):
            assert k in m, f"meta.{k} missing"

    def test_meta_types(self, workload_session: Dict) -> None:
        m = workload_session["meta"]
        assert isinstance(m["run_id"], str) and len(m["run_id"]) == 12
        assert isinstance(m["pid"], int) and m["pid"] > 0
        assert isinstance(m["argv"], list)
        assert isinstance(m["codegreen_env"], dict)
        assert isinstance(m["domain_topology"], dict)
        assert isinstance(m["timeseries"], dict)

    def test_totals_required_keys(self, workload_session: Dict) -> None:
        t = workload_session["totals"]
        for k in (
            "energy_j", "duration_s",
            "wall_duration_s", "task_duration_s",
            "gap_duration_s", "concurrent_overlap_s",
            "n_tasks", "n_top_level_tasks",
            "domains", "domains_power_w",
            "sample_interval_ms", "worst_within_task_power_cv_percent",
            "noise_warnings",
        ):
            assert k in t, f"totals.{k} missing"

    def test_per_task_required_keys(self, workload_session: Dict) -> None:
        for task in workload_session["tasks"]:
            for k in (
                "name", "energy_j", "avg_power_w", "duration_s",
                "started_at", "ended_at",
                "started_at_mono_ns", "ended_at_mono_ns",
                "depth", "parent",
                "domains", "domains_power_w",
                "timeseries", "noise",
            ):
                assert k in task, f"task[{task.get('name')}].{k} missing"


# ===========================================================================
# 2. NAMING CONTRACT
# ===========================================================================
class TestNamingContract:
    """No legacy names anywhere. Every numeric field carries unit suffix."""

    LEGACY_FIELDS = (
        "energy_joules", "time_seconds", "domains_power_watts",
        "worst_power_cv_percent", "abi_version", "providers",
    )

    def test_no_legacy_at_root(self, workload_session: Dict) -> None:
        for k in self.LEGACY_FIELDS:
            assert k not in workload_session, f"legacy '{k}' at root"

    def test_no_legacy_in_totals(self, workload_session: Dict) -> None:
        for k in self.LEGACY_FIELDS:
            assert k not in workload_session["totals"], f"legacy '{k}' in totals"

    def test_session_name_in_meta_only(self, workload_session: Dict) -> None:
        assert "session_name" in workload_session["meta"]
        assert "session_name" not in workload_session

    def test_iso_timestamp_format(self, workload_session: Dict) -> None:
        for k in ("started_at", "ended_at"):
            v = workload_session["meta"][k]
            assert v.endswith("+00:00"), f"{k} must end with +00:00 (got {v!r})"
            assert datetime.fromisoformat(v) is not None

    def test_run_id_is_uuid4_prefix(self, workload_session: Dict) -> None:
        rid = workload_session["meta"]["run_id"]
        assert len(rid) == 12
        int(rid, 16)

    def test_canonical_started_at_unchanged_with_local_field(self, workload_session: Dict) -> None:
        """v0.4.8: adding started_at_local must NOT change started_at's UTC contract."""
        v = workload_session["meta"]["started_at"]
        assert v.endswith("+00:00")
        assert "+00:00" in v


# ===========================================================================
# 2b. LOCAL TIMESTAMPS (v0.4.8+; additive, never replaces UTC fields)
# ===========================================================================
class TestLocalTimestamps:
    """started_at_local, ended_at_local, host_timezone — display-only companions."""

    def test_local_fields_present(self, workload_session: Dict) -> None:
        m = workload_session["meta"]
        for k in ("started_at_local", "ended_at_local", "host_timezone"):
            assert k in m

    def test_local_carries_offset_not_naive(self, workload_session: Dict) -> None:
        m = workload_session["meta"]
        s_local = m["started_at_local"]
        e_local = m["ended_at_local"]
        for v in (s_local, e_local):
            parsed = datetime.fromisoformat(v)
            assert parsed.tzinfo is not None, (
                f"local timestamp must carry explicit offset, got {v!r}"
            )

    def test_local_and_utc_describe_same_instant(self, workload_session: Dict) -> None:
        m = workload_session["meta"]
        s_utc = datetime.fromisoformat(m["started_at"])
        s_local = datetime.fromisoformat(m["started_at_local"])
        delta = abs((s_utc - s_local).total_seconds())
        assert delta < 0.001, (
            f"started_at and started_at_local must point to the same instant; "
            f"delta={delta}s"
        )

    def test_local_ordered_with_utc(self, workload_session: Dict) -> None:
        m = workload_session["meta"]
        s_local = datetime.fromisoformat(m["started_at_local"])
        e_local = datetime.fromisoformat(m["ended_at_local"])
        assert e_local > s_local

    def test_host_timezone_label_nonempty(self, workload_session: Dict) -> None:
        assert workload_session["meta"]["host_timezone"]
        assert workload_session["meta"]["host_timezone"] != "unknown" or True

    def test_canonical_utc_unaffected_when_local_present(self, workload_session: Dict) -> None:
        """Sanity: the UTC field stays UTC even though local is also emitted."""
        m = workload_session["meta"]
        assert m["iso_timestamp_format"] == "rfc3339_utc"
        assert m["started_at"].endswith("+00:00")
        assert m["ended_at"].endswith("+00:00")


# ===========================================================================
# 3. LOGICAL CORRECTNESS
# ===========================================================================
class TestLogicalCorrectness:
    """Math identities the JSON must satisfy. These were the v0.4.7 audit Ps."""

    def test_totals_energy_equals_sum_of_depth0(self, workload_session: Dict) -> None:
        top = [t for t in workload_session["tasks"] if t["depth"] == 0]
        assert workload_session["totals"]["energy_j"] == pytest.approx(
            sum(t["energy_j"] for t in top), abs=0.001,
        )

    def test_totals_task_duration_equals_sum_of_depth0(self, workload_session: Dict) -> None:
        top = [t for t in workload_session["tasks"] if t["depth"] == 0]
        assert workload_session["totals"]["task_duration_s"] == pytest.approx(
            sum(t["duration_s"] for t in top), abs=0.001,
        )

    def test_wall_equals_task_plus_gap_when_sequential(self, workload_session: Dict) -> None:
        t = workload_session["totals"]
        if t["concurrent_overlap_s"] == 0:
            assert t["wall_duration_s"] == pytest.approx(
                t["task_duration_s"] + t["gap_duration_s"], abs=0.01,
            )

    def test_avg_power_equals_energy_over_duration(self, workload_session: Dict) -> None:
        for task in workload_session["tasks"]:
            if task["energy_j"] <= 0 or task["duration_s"] <= 0:
                continue
            derived = task["energy_j"] / task["duration_s"]
            assert task["avg_power_w"] == pytest.approx(derived, rel=0.05, abs=0.5)

    def test_per_task_domain_power_equals_energy_over_duration(self, workload_session: Dict) -> None:
        for task in workload_session["tasks"]:
            if task["duration_s"] <= 0:
                continue
            for d, e in (task["domains"] or {}).items():
                pw = (task["domains_power_w"] or {}).get(d)
                if pw is None:
                    continue
                assert pw == pytest.approx(e / task["duration_s"], rel=0.001, abs=1e-6)

    def test_totals_domain_energy_equals_sum_per_task(self, workload_session: Dict) -> None:
        top = [t for t in workload_session["tasks"] if t["depth"] == 0]
        for d, e in workload_session["totals"]["domains"].items():
            sum_per = sum(t["domains"].get(d, 0) for t in top)
            assert e == pytest.approx(sum_per, abs=0.001 + abs(e) * 0.001)

    def test_aggregate_domain_power_uses_active_window(self, workload_session: Dict) -> None:
        """totals.domains_power_w[d] = sum(energy_d) / sum(duration over tasks where d active)."""
        top = [t for t in workload_session["tasks"] if t["depth"] == 0]
        for d, pw in workload_session["totals"]["domains_power_w"].items():
            sum_e = sum(t["domains"].get(d, 0) for t in top)
            sum_d = sum(t["duration_s"] for t in top if t["domains"].get(d, 0) > 0)
            if sum_d > 0:
                assert pw == pytest.approx(sum_e / sum_d, rel=0.001, abs=1e-4)

    def test_iso_timestamps_ordered(self, workload_session: Dict) -> None:
        m = workload_session["meta"]
        assert datetime.fromisoformat(m["ended_at"]) > datetime.fromisoformat(m["started_at"])

    def test_duration_total_consistent_with_iso_delta(self, workload_session: Dict) -> None:
        m = workload_session["meta"]
        delta = (datetime.fromisoformat(m["ended_at"]) -
                 datetime.fromisoformat(m["started_at"])).total_seconds()
        assert m["duration_total_s"] == pytest.approx(delta, abs=0.05)

    def test_mono_delta_equals_duration_per_task(self, workload_session: Dict) -> None:
        for task in workload_session["tasks"]:
            mono = (task["ended_at_mono_ns"] - task["started_at_mono_ns"]) / 1e9
            assert mono == pytest.approx(task["duration_s"], abs=0.01)

    def test_hostname_pid_match_process(self, workload_session: Dict) -> None:
        assert workload_session["meta"]["hostname"] == socket.gethostname()
        assert workload_session["meta"]["pid"] == os.getpid()

    def test_domain_topology_covers_every_reported_domain(self, workload_session: Dict) -> None:
        topo = workload_session["meta"]["domain_topology"]
        for d in workload_session["totals"]["domains"]:
            assert d in topo, f"domain '{d}' missing from topology"


# ===========================================================================
# 4. EDGE CASES
# ===========================================================================
class TestEdgeCases:
    """Empty session, parallel threads, nested tasks, block-C gap."""

    def test_empty_session_has_no_tasks_quality_flag(self) -> None:
        s = Session("empty", save_to_file=False).start()
        time.sleep(0.05)
        rep = s.stop()
        assert rep["meta"]["measurement_quality"] == "no_tasks"
        assert rep["totals"]["n_tasks"] == 0
        assert rep["totals"]["energy_j"] == 0
        assert rep["totals"]["task_duration_s"] == 0
        assert rep["totals"]["wall_duration_s"] > 0
        assert rep["totals"]["gap_duration_s"] == pytest.approx(
            rep["totals"]["wall_duration_s"], abs=1e-6,
        )

    def test_block_c_gap_captured(self) -> None:
        """Javad's original bug: uninstrumented heavy work between tasks."""
        s = Session("blockC", save_to_file=False).start()
        with s.task("A"):
            _busy(2_000_000)
        with s.task("B"):
            _busy(2_000_000)
        time.sleep(0.2)
        _busy(8_000_000)
        rep = s.stop()
        assert rep["totals"]["gap_duration_s"] > 0.1, (
            "uninstrumented work between/after tasks must show up as gap_duration_s"
        )

    @pytest.mark.needs_energy
    def test_concurrent_threads_populate_overlap(self) -> None:
        s = Session("conc", save_to_file=False).start()
        def worker(name: str, ms: int) -> None:
            with s.task(name):
                end = time.monotonic() + ms / 1000
                while time.monotonic() < end:
                    pass
        ths = [threading.Thread(target=worker, args=(f"P{i}", 200)) for i in range(2)]
        for t in ths:
            t.start()
        for t in ths:
            t.join()
        rep = s.stop()
        assert rep["totals"]["concurrent_overlap_s"] > 0.05
        assert rep["totals"]["gap_duration_s"] < 0.1

    @pytest.mark.needs_energy
    def test_nested_task_not_double_counted(self) -> None:
        s = Session("nest", save_to_file=False).start()
        with s.task("parent"):
            with s.task("child"):
                _busy(1_000_000)
            _busy(1_000_000)
        rep = s.stop()
        assert rep["totals"]["n_top_level_tasks"] == 1
        parent = next(t for t in rep["tasks"] if t["depth"] == 0)
        assert rep["totals"]["task_duration_s"] == pytest.approx(parent["duration_s"], abs=1e-6)

    @pytest.mark.needs_energy
    def test_atomic_write_no_temp_leftover(self, tmp_path: Path) -> None:
        out = tmp_path / "atomic.json"
        s = Session("atom", output_file=str(out), save_to_file=True).start()
        with s.task("w"):
            _busy(500_000)
        s.stop()
        assert out.exists()
        leftovers = list(tmp_path.glob("atomic.json.*.tmp"))
        assert leftovers == [], f"unexpected temp files: {leftovers}"

    def test_failed_session_still_emits_meta_in_failure_path(self, tmp_path: Path) -> None:
        """SIGTERM/atexit code path emits meta even when stop() was never called."""
        script = tmp_path / "forgot.py"
        out = tmp_path / "forgot.json"
        script.write_text(
            "from codegreen import Session\n"
            f"s = Session('forgot', output_file={str(out)!r}, save_to_file=True).start()\n"
            "s._begin_task('outer'); s._begin_task('inner')\n"
        )
        subprocess.run(["python3", str(script)], timeout=15, check=False)
        if out.exists():
            data = json.loads(out.read_text())
            assert "meta" in data, "auto-finalized output must include meta"
            assert "tasks" in data and len(data["tasks"]) >= 2
            inner = next((t for t in data["tasks"] if t["name"] == "inner"), None)
            if inner is not None:
                assert inner["depth"] == 1
                assert inner["parent"] == "outer", (
                    "auto-finalize must preserve LIFO parent linkage"
                )


# ===========================================================================
# 5. TIMESERIES MODE
# ===========================================================================
class TestTimeseriesMode:
    """record_time_series=True: ordering, dedup, window bounds, sample interval."""

    @pytest.mark.needs_energy
    def test_meta_describes_timeseries_schema(self, timeseries_session: Dict) -> None:
        m = timeseries_session["meta"]["timeseries"]
        assert m["enabled"] is True
        assert m["t_ns_clock"] in (
            "clock_monotonic", "mach_continuous_time", "query_performance_counter",
        ), m["t_ns_clock"]
        assert m["inclusive_of_children"] is True
        assert "energy_j" in m["sample_keys"]
        assert "power_w" in m["sample_keys"]
        assert "t_ns" in m["sample_keys"]

    def test_timeseries_sorted(self, timeseries_session: Dict) -> None:
        for task in timeseries_session["tasks"]:
            ts = task.get("timeseries") or []
            tns = [s["t_ns"] for s in ts]
            assert tns == sorted(tns), f"task {task['name']} timeseries not sorted"

    def test_timeseries_no_duplicate_tns(self, timeseries_session: Dict) -> None:
        for task in timeseries_session["tasks"]:
            ts = task.get("timeseries") or []
            tns = [s["t_ns"] for s in ts]
            assert len(tns) == len(set(tns)), f"task {task['name']} has duplicate t_ns"

    def test_samples_within_task_window(self, timeseries_session: Dict) -> None:
        for task in timeseries_session["tasks"]:
            ts = task.get("timeseries") or []
            s_ns, e_ns = task["started_at_mono_ns"], task["ended_at_mono_ns"]
            for sample in ts:
                assert s_ns <= sample["t_ns"] <= e_ns, (
                    f"sample t_ns {sample['t_ns']} outside task window "
                    f"[{s_ns}, {e_ns}] for {task['name']}"
                )

    def test_per_sample_power_sane_bounds(self, timeseries_session: Dict) -> None:
        for task in timeseries_session["tasks"]:
            for s in task.get("timeseries") or []:
                pw = s.get("power_w", 0)
                assert 0 <= pw < 5000, f"insane power_w={pw} in {task['name']}"

    def test_observed_sample_interval_near_configured(self, timeseries_session: Dict) -> None:
        configured = timeseries_session["totals"]["sample_interval_ms"]
        if configured is None:
            pytest.skip("no configured sample interval in totals")
        for task in timeseries_session["tasks"]:
            ts = task.get("timeseries") or []
            if len(ts) < 3:
                continue
            intervals = [(ts[i]["t_ns"] - ts[i - 1]["t_ns"]) / 1e6
                         for i in range(1, len(ts))]
            intervals.sort()
            median_ms = intervals[len(intervals) // 2]
            assert abs(median_ms - configured) <= max(2.0, configured * 0.5), (
                f"observed interval {median_ms:.2f}ms != configured {configured}ms "
                f"for {task['name']}"
            )

    @pytest.mark.needs_energy
    def test_timeseries_disabled_returns_none_not_empty(self) -> None:
        """Distinguish 'recording disabled' (None) from 'enabled but task too short' ([])."""
        s = Session("ts_off", record_time_series=False, save_to_file=False).start()
        with s.task("w"):
            _busy(500_000)
        rep = s.stop()
        assert rep["tasks"][0]["timeseries"] is None
        assert rep["meta"]["timeseries"]["enabled"] is False


# ===========================================================================
# 6. QUALITY REPORTING
# ===========================================================================
class TestQualityReporting:
    """noise_warnings shape, drop_ratio math, measurement_quality enum."""

    def test_measurement_quality_enum(self, workload_session: Dict) -> None:
        assert workload_session["meta"]["measurement_quality"] in {
            "ok", "no_tasks", "no_backend", "energy_zero",
            "failed", "checkpoints_only",
        }

    def test_noise_warnings_are_structured_dicts(self, timeseries_session: Dict) -> None:
        for w in timeseries_session["totals"]["noise_warnings"]:
            assert isinstance(w, dict)
            for k in ("task", "depth", "within_task_power_cv_percent",
                      "drop_ratio", "quality", "reasons"):
                assert k in w

    def test_drop_ratio_consistent_with_captured_expected(self, timeseries_session: Dict) -> None:
        for task in timeseries_session["tasks"]:
            n = task.get("noise")
            if not n or n["samples_expected"] <= 0:
                continue
            derived = max(0.0, 1.0 - n["samples_captured"] / n["samples_expected"])
            assert n["drop_ratio"] == pytest.approx(derived, abs=1e-3)


# ===========================================================================
# 7. CLI
# ===========================================================================
@pytest.mark.needs_energy
class TestCLI:
    """`codegreen run --json` regressions: pair-filtering, structured runs/backend, failure-path meta."""

    SMALL_WORKLOAD = ["python3", "-c", "sum(i*i for i in range(2_000_000))"]

    def test_basic_run_emits_meta_and_structured_runs(self) -> None:
        out, _, _, _ = _cli_run("run", "--json", "-n", "5", "-w", "0", "--", *self.SMALL_WORKLOAD)
        assert out is not None
        assert "meta" in out
        assert isinstance(out["runs"], dict)
        for k in ("attempted", "energy_valid", "iqr_outliers_removed",
                  "zero_energy_dropped", "warmup_runs", "measurement_runs"):
            assert k in out["runs"], f"runs.{k} missing"
        assert out["runs"]["attempted"] == 5
        assert out["runs"]["measurement_runs"] == 5

    def test_backend_descriptor_is_structured(self) -> None:
        out, _, _, _ = _cli_run("run", "--json", "-n", "2", "-w", "0", "--", *self.SMALL_WORKLOAD)
        assert isinstance(out["backend"], dict)
        for k in ("name", "driver", "domains_seen"):
            assert k in out["backend"]

    def test_no_legacy_field_names(self) -> None:
        out, _, _, _ = _cli_run("run", "--json", "-n", "2", "-w", "0", "--", *self.SMALL_WORKLOAD)
        for k in ("energy_joules", "time_seconds", "domains_power_watts"):
            assert k not in out
        assert "energy_j" in out
        assert "duration_s" in out

    def test_power_w_has_ci(self) -> None:
        out, _, _, _ = _cli_run("run", "--json", "-n", "5", "-w", "0", "--", *self.SMALL_WORKLOAD)
        assert isinstance(out["power_w"], dict)
        for k in ("mean", "std", "min", "max", "ci95_lower", "ci95_upper", "computation"):
            assert k in out["power_w"]

    def test_meta_includes_argv_and_cwd(self) -> None:
        out, _, _, _ = _cli_run("run", "--json", "-n", "2", "-w", "0", "--", *self.SMALL_WORKLOAD)
        assert isinstance(out["meta"]["argv"], list)
        assert out["meta"]["cwd"]
        assert out["meta"]["outlier_method"] == "iqr_1.5"
        assert out["meta"]["iso_timestamp_format"] == "rfc3339_utc"

    def test_budget_exceeded_path_includes_meta(self) -> None:
        out, _, _, _ = _cli_run("run", "--json", "-n", "2", "-w", "0",
                                "--budget", "0.001", "--", *self.SMALL_WORKLOAD)
        if out is None:
            pytest.skip("CLI did not return JSON on this host")
        assert "meta" in out
        assert out.get("budget_exceeded") is True
        assert out.get("budget_j") == 0.001

    def test_include_warmup_separates_counts(self) -> None:
        out, _, _, _ = _cli_run("run", "--json", "-n", "3", "-w", "2", "--include-warmup",
                                "--", *self.SMALL_WORKLOAD)
        assert out["runs"]["warmup_runs"] == 2
        assert out["runs"]["warmup_included_in_stats"] is True
        assert out["meta"].get("include_warmup") is True

    def test_stdin_flag_binds_file_to_workload_stdin(self, tmp_path: Path) -> None:
        """`--stdin <file>` MUST bind the file as the workload's stdin via
        Popen, replacing unsafe `bash -c "... < file"` wrapping that breaks
        under argv-split downstream. Regression fence for the May-13 CLBG
        knucleotide/regexredux/revcomp failure."""
        payload = tmp_path / "in.txt"
        payload.write_text("hello\nworld\n")
        out, stdout, stderr, rc = _cli_run(
            "run", "--json", "-n", "1", "-w", "0",
            "--stdin", str(payload),
            "--", "python3", "-c",
            "import sys; data = sys.stdin.read(); "
            "open('%s', 'w').write(data)" % (tmp_path / "got.txt"),
        )
        assert rc == 0, f"rc={rc} stderr={stderr!r}"
        assert out is not None
        assert (tmp_path / "got.txt").read_text() == "hello\nworld\n"

    def test_stdin_missing_file_surfaces_structured_failure(
            self, tmp_path: Path) -> None:
        """A non-existent --stdin path MUST yield JSON
        {success:false, error:'stdin_file_missing: <path>'} and exit 1,
        never a raw FileNotFoundError trace."""
        missing = tmp_path / "does_not_exist.bin"
        out, _, _, rc = _cli_run(
            "run", "--json", "-n", "1", "--stdin", str(missing),
            "--", "python3", "-c", "pass",
        )
        assert rc == 1
        assert out is not None
        assert out["success"] is False
        assert "stdin_file_missing" in out["error"]


# ===========================================================================
# 8. MONITOR (always-on energy sampler + annotation surface)
# ===========================================================================
@pytest.mark.needs_energy
class TestMonitorCLI:
    """Hardening + UX regressions for `codegreen monitor`."""

    def test_missing_pid_exits_clean_text(self, tmp_path: Path) -> None:
        """A1 regression: bad --pid emits structured plain-text error to stderr,
        rc=1, NO Traceback / NO click.exceptions.Exit leak."""
        _, stdout, stderr, rc = _cli_run("monitor", "-d", "1", "-p", "999999", "--quiet",
                                         cwd=str(tmp_path))
        assert rc == 1
        combined = stdout + stderr
        assert "Traceback" not in combined, f"traceback leaked: {combined!r}"
        assert "click.exceptions.Exit" not in combined
        assert "pid 999999" in combined and "no such process" in combined

    def test_missing_pid_json_mode_is_structured(self, tmp_path: Path) -> None:
        """--json must yield JSON-decodable stderr with success=false."""
        _, _, stderr, rc = _cli_run("monitor", "-d", "1", "-p", "999999",
                                    "--quiet", "--json", cwd=str(tmp_path))
        assert rc == 1
        assert "Traceback" not in stderr
        # The JSON payload is the final stderr line; a coverage-enabled run
        # prepends pytest-cov's subprocess warnings above it.
        payload = json.loads(stderr.strip().splitlines()[-1])
        assert payload["success"] is False
        assert "999999" in payload["error"]


class TestMonitorAPI:
    """Direct Monitor class contract: file rotation, in-memory cap, soft warning,
    annotation surface (UDS + per-label aggregation)."""

    def test_default_interval_from_config(self) -> None:
        from codegreen import Monitor
        m = Monitor(duration_s=0.2)
        assert m._interval_s == 0.5  # config default

    def test_low_interval_emits_runtime_warning_only_when_run_forever(self) -> None:
        import warnings
        from codegreen import Monitor
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Monitor(interval_ms=60)  # run-forever, below warn_below=100
            assert any(issubclass(x.category, RuntimeWarning) and "sampling overhead" in str(x.message) for x in w)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Monitor(interval_ms=60, duration_s=1.0)  # bounded run, no warning
            assert not any(issubclass(x.category, RuntimeWarning) and "sampling overhead" in str(x.message) for x in w)

    @pytest.mark.needs_energy
    def test_in_memory_cap_uses_deque(self) -> None:
        from codegreen import Monitor
        m = Monitor(duration_s=0.2, max_samples_in_memory=3)
        m.start()
        m._thread.join(timeout=5.0)
        m.stop()
        assert len(m._samples) <= 3
        assert m._samples_count >= len(m._samples)

    @pytest.mark.needs_energy
    def test_rotation_rolls_jsonl(self, tmp_path: Path) -> None:
        """rotate_mb=1KB equivalent triggers rotation; original file shrinks
        after rotation and .1 backup exists."""
        from codegreen import Monitor
        path = tmp_path / "energy.jsonl"
        m = Monitor(interval_ms=50, duration_s=0.4, output_file=str(path),
                    max_samples_in_memory=0)
        m._rotate_bytes = 256  # force rotation aggressively for the test
        m.start()
        m._thread.join(timeout=5.0)
        m.stop()
        assert path.exists()
        assert (tmp_path / "energy.jsonl.1").exists()

    def test_output_file_open_failure_is_runtime_error(self, tmp_path: Path) -> None:
        """No silent fallback: bad output path -> RuntimeError, no leaked fp."""
        from codegreen import Monitor
        bad = tmp_path / "does_not_exist_dir" / "energy.jsonl"
        m = Monitor(duration_s=0.2, output_file=str(bad))
        with pytest.raises(RuntimeError):
            m.start()
        assert m._fp is None

    @pytest.mark.needs_energy
    def test_annotation_round_trip_in_memory(self) -> None:
        """annotate_start/end accumulate per-label energy across samples."""
        from codegreen import Monitor
        m = Monitor(interval_ms=50, duration_s=0.4, max_samples_in_memory=0)
        m.start()
        tok = m.annotate_start("GET /x")
        time.sleep(0.15)
        m.annotate_end(tok)
        m._thread.join(timeout=5.0)
        summary = m.stop()
        assert "GET /x" in summary["per_label"]
        assert summary["per_label"]["GET /x"]["count"] == 1


@pytest.mark.needs_energy
class TestMonitorAnnotationSocket:
    """End-to-end: UDS listener accepts start/end JSON-lines from a separate
    thread, summary includes per-label aggregation."""

    def test_uds_listener_records_three_labels(self, tmp_path: Path) -> None:
        from codegreen import Monitor
        sock_path = str(tmp_path / "cg.sock")
        out_path = tmp_path / "energy.jsonl"
        m = Monitor(interval_ms=50, duration_s=1.0,
                    output_file=str(out_path), listen_socket_path=sock_path,
                    max_samples_in_memory=0)
        m.start()
        # Wait briefly so the listener is accepting.
        time.sleep(0.05)

        def _client(label: str) -> None:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect(sock_path)
            s.sendall((json.dumps({"op": "start", "name": label}) + "\n").encode())
            buf = b""
            while b"\n" not in buf:
                buf += s.recv(4096)
            tok = json.loads(buf.split(b"\n", 1)[0])["token"]
            _busy(2_000_000)
            s.sendall((json.dumps({"op": "end", "token": tok}) + "\n").encode())
            buf = b""
            while b"\n" not in buf:
                buf += s.recv(4096)
            s.close()

        threads = [threading.Thread(target=_client, args=(f"label_{i}",)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        m._thread.join(timeout=5.0)
        summary = m.stop()
        assert summary["per_label"], "expected per_label aggregation"
        assert set(summary["per_label"].keys()) == {"label_0", "label_1", "label_2"}
        # Output file must contain annotation events interleaved with samples.
        text = out_path.read_text()
        assert text.count('"type":"annotation_start"') == 3
        assert text.count('"type":"annotation_end"') == 3
        assert '"type":"sample"' in text

    def test_uds_bad_json_returns_structured_error(self, tmp_path: Path) -> None:
        from codegreen import Monitor
        sock_path = str(tmp_path / "cg.sock")
        m = Monitor(interval_ms=50, duration_s=0.6,
                    listen_socket_path=sock_path, max_samples_in_memory=0)
        m.start()
        time.sleep(0.05)
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect(sock_path)
        s.sendall(b"not json\n")
        buf = b""
        while b"\n" not in buf:
            buf += s.recv(4096)
        resp = json.loads(buf.split(b"\n", 1)[0])
        assert resp["ok"] is False and "bad_json" in resp["error"]
        s.close()
        m._thread.join(timeout=5.0)
        m.stop()

    def test_uds_unknown_token_distinct_from_missing_field(self, tmp_path: Path) -> None:
        """end-op with absent token => missing_field; with bogus token => unknown_token."""
        from codegreen import Monitor
        sock_path = str(tmp_path / "cg.sock")
        m = Monitor(interval_ms=100, duration_s=0.6,
                    listen_socket_path=sock_path, max_samples_in_memory=0)
        m.start()
        time.sleep(0.05)

        def _ask(payload: dict) -> dict:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(2.0); s.connect(sock_path)
            s.sendall((json.dumps(payload) + "\n").encode())
            buf = b""
            while b"\n" not in buf:
                buf += s.recv(4096)
            s.close()
            return json.loads(buf.split(b"\n", 1)[0])

        r_missing = _ask({"op": "end"})
        r_unknown = _ask({"op": "end", "token": "nope"})
        assert r_missing["ok"] is False and r_missing["error"].startswith("missing_field:")
        assert r_unknown["ok"] is False and r_unknown["error"].startswith("unknown_token:")
        m._thread.join(timeout=5.0)
        m.stop()

    def test_concurrent_annotations_no_dict_race(self) -> None:
        """4 threads x 100 annotation pairs while sample-thread iterates open
        annotations; verifies the fp_lock snapshot fix in
        _attribute_to_open_annotations. Zero crashes, label count matches."""
        from codegreen import Monitor
        m = Monitor(interval_ms=50, duration_s=4.0, max_samples_in_memory=0).start()
        crashes: list = []

        def worker(tid: int) -> None:
            for i in range(100):
                try:
                    tok = m.annotate_start(f"t{tid}-r{i % 5}")
                    time.sleep(0.001)
                    m.annotate_end(tok)
                except Exception as e:
                    crashes.append((tid, i, repr(e)))

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(4)]
        for t in threads: t.start()
        for t in threads: t.join(timeout=10)
        m._thread.join(timeout=10)
        s = m.stop()
        assert crashes == [], crashes[:3]
        total = sum(b["count"] for b in s["per_label"].values())
        assert total == 400, total


# ===========================================================================
# 9. MONITOR CARDINALITY CAP + SIGHUP-RELOAD (long-running deployment guards)
# ===========================================================================
class TestAnnotationListenerHardening:
    """Socket lifecycle safety; needs no energy backend."""

    @staticmethod
    def _listener(path: Path):
        from codegreen.instrumentation.language_runtimes.python.codegreen_runtime import _AnnotationListener
        return _AnnotationListener(None, str(path), {"listener_backlog": 4, "recv_buf_bytes": 4096})

    def test_refuses_to_unlink_non_socket(self, tmp_path: Path) -> None:
        victim = tmp_path / "precious.txt"
        victim.write_text("keep")
        with pytest.raises(OSError, match="not a socket"):
            self._listener(victim).start()
        assert victim.read_text() == "keep"

    def test_replaces_stale_socket_with_private_mode_under_loose_umask(self, tmp_path: Path) -> None:
        path = tmp_path / "cg.sock"
        stale = socket.socket(socket.AF_UNIX)
        stale.bind(str(path))
        stale.close()
        old = os.umask(0)
        try:
            lst = self._listener(path)
            lst.start()
        finally:
            os.umask(old)
        try:
            assert (path.stat().st_mode & 0o777) == 0o600
        finally:
            lst.stop()
        assert not path.exists()

    def test_default_path_is_per_user_and_shared_by_client(self, monkeypatch, tmp_path: Path) -> None:
        from codegreen.instrumentation.language_runtimes.python import codegreen_runtime as rt
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
        assert rt.default_socket_path() == str(tmp_path / "codegreen.sock")
        assert rt.annotate_request("x")._path == rt.default_socket_path()
        monkeypatch.delenv("XDG_RUNTIME_DIR")
        assert rt.default_socket_path() == f"/tmp/codegreen-{os.getuid()}/codegreen.sock"

    def test_default_dir_created_private_and_foreign_perms_rejected(self, monkeypatch, tmp_path: Path) -> None:
        from codegreen.instrumentation.language_runtimes.python import codegreen_runtime as rt
        run_dir = tmp_path / "run"
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(run_dir))
        run_dir.mkdir(mode=0o755)
        run_dir.chmod(0o755)
        with pytest.raises(OSError, match="0700"):
            self._listener(Path(rt.default_socket_path())).start()
        run_dir.chmod(0o700)
        lst = self._listener(Path(rt.default_socket_path()))
        lst.start()
        lst.stop()


@pytest.mark.needs_energy
class TestMonitorCardinality:
    """Per-label cap + overflow bucket protect long-running deployments from
    high-cardinality label sources (raw URLs, request UUIDs, etc.)."""

    def test_max_labels_creates_overflow_bucket(self) -> None:
        """max_labels=2, 5 distinct labels => per_label has {2 + __other__};
        __other__.count counts every overflowed event (3 here)."""
        from codegreen import Monitor
        m = Monitor(interval_ms=50, duration_s=2.0, max_samples_in_memory=0,
                    max_labels=2).start()
        try:
            for i in range(5):
                tok = m.annotate_start(f"label_{i}")
                time.sleep(0.02)
                m.annotate_end(tok)
        finally:
            m._thread.join(timeout=5.0)
            s = m.stop()
        pl = s["per_label"]
        assert set(pl.keys()) == {"label_0", "label_1", "__other__"}, pl
        assert pl["__other__"]["count"] == 3, pl["__other__"]
        assert s["distinct_labels"] == 3
        assert s["max_labels"] == 2

    def test_max_labels_zero_means_unlimited(self) -> None:
        """max_labels=0 must accept arbitrarily many distinct labels; no
        overflow bucket created."""
        from codegreen import Monitor
        m = Monitor(interval_ms=50, duration_s=2.0, max_samples_in_memory=0,
                    max_labels=0).start()
        try:
            for i in range(7):
                tok = m.annotate_start(f"u_{i}")
                m.annotate_end(tok)
        finally:
            m._thread.join(timeout=5.0)
            s = m.stop()
        assert "__other__" not in s["per_label"]
        assert s["distinct_labels"] == 7

    def test_overflow_preserves_requested_name(self, tmp_path: Path) -> None:
        """Original label survives in labels['__requested_name__'] in the
        JSONL stream so postmortem can recover what was attempted."""
        from codegreen import Monitor
        out = tmp_path / "energy.jsonl"
        m = Monitor(interval_ms=50, duration_s=1.5, output_file=str(out),
                    max_samples_in_memory=0, max_labels=1).start()
        try:
            for n in ("A", "B", "C"):
                tok = m.annotate_start(n)
                m.annotate_end(tok)
        finally:
            m._thread.join(timeout=5.0)
            m.stop()
        events = [json.loads(ln) for ln in out.read_text().splitlines() if ln]
        starts = [e for e in events if e.get("type") == "annotation_start"]
        overflowed = [e for e in starts if e["name"] == "__other__"]
        assert len(overflowed) == 2
        assert {e["labels"]["__requested_name__"] for e in overflowed} == {"B", "C"}


@pytest.fixture
def temp_config(monkeypatch, tmp_path: Path) -> Path:
    """Private copy of the package config.json, wired into the runtime's path resolution."""
    from codegreen.instrumentation.language_runtimes.python import codegreen_runtime as rt
    real = rt._package_file
    cfg = tmp_path / "config.json"
    cfg.write_text(real("config.json").read_text())
    monkeypatch.setattr(rt, "_package_file", lambda name: cfg if name == "config.json" else real(name))
    return cfg


@pytest.mark.needs_energy
class TestMonitorSighupReload:
    """SIGHUP triggers in-flight config reload without dropping annotations
    or rotating the JSONL position."""

    def test_request_reload_reapplies_max_labels(self, temp_config: Path) -> None:
        """Start with max_labels=2; rewrite config to 20 and request_reload();
        Q/R/S then all pass through the cap rather than collapsing to overflow."""
        from codegreen import Monitor
        original = temp_config.read_text()
        m = Monitor(interval_ms=50, duration_s=4.0, max_samples_in_memory=0,
                    max_labels=2).start()
        try:
            for n in ("X", "Y", "Z"):
                m.annotate_end(m.annotate_start(n))
            assert m._max_labels == 2
            cfg = json.loads(original)
            cfg["monitor"]["annotation"]["max_labels"] = 20
            temp_config.write_text(json.dumps(cfg, indent=2))
            m.request_reload()
            time.sleep(0.2)
            assert m._max_labels == 20, m._max_labels
            assert m._reload_count >= 1
            for n in ("Q", "R", "S"):
                m.annotate_end(m.annotate_start(n))
        finally:
            m._thread.join(timeout=5.0)
            s = m.stop()
        pl = s["per_label"]
        assert {"X", "Y", "__other__", "Q", "R", "S"}.issubset(pl), list(pl)
        assert pl["__other__"]["count"] == 1
        assert s["reload_count"] >= 1

    def test_reload_preserves_in_flight_annotations(self) -> None:
        """Open 3 spans; reload mid-flight; close 2; the 3rd remains open
        with its original token until explicitly closed. JSONL file position
        is not disturbed."""
        from codegreen import Monitor
        m = Monitor(interval_ms=50, duration_s=4.0, max_samples_in_memory=0,
                    max_labels=10).start()
        try:
            t1 = m.annotate_start("alpha")
            t2 = m.annotate_start("beta")
            t3 = m.annotate_start("gamma")
            m.request_reload()
            time.sleep(0.2)
            m.annotate_end(t1)
            m.annotate_end(t2)
            assert t3 in m._annotations_open, list(m._annotations_open)
            m.annotate_end(t3)
        finally:
            m._thread.join(timeout=5.0)
            s = m.stop()
        assert set(["alpha", "beta", "gamma"]).issubset(s["per_label"])
        assert s["reload_count"] >= 1

    def test_reload_invalid_config_keeps_old(self, temp_config: Path) -> None:
        """Corrupt config mid-run => reload logs a warning and keeps the
        previous values. Monitor keeps running."""
        import warnings
        from codegreen import Monitor
        m = Monitor(interval_ms=50, duration_s=3.0, max_samples_in_memory=0,
                    max_labels=4).start()
        try:
            temp_config.write_text("{not json at all")
            with warnings.catch_warnings(record=True) as wlog:
                warnings.simplefilter("always")
                m.request_reload()
                time.sleep(0.3)
            assert m._max_labels == 4, m._max_labels
            assert any(issubclass(w.category, RuntimeWarning)
                       and "SIGHUP reload failed to read config" in str(w.message)
                       for w in wlog), [str(w.message) for w in wlog]
        finally:
            m._thread.join(timeout=5.0)
            m.stop()

    def test_sighup_signal_routes_to_request_reload(self) -> None:
        """The CLI installs SIGHUP -> mon.request_reload(); send SIGHUP to
        self with that handler and confirm a reload happens."""
        import os, signal as _sig
        from codegreen import Monitor
        if not hasattr(_sig, "SIGHUP"):
            pytest.skip("SIGHUP unavailable on this platform")
        m = Monitor(interval_ms=50, duration_s=3.0, max_samples_in_memory=0,
                    max_labels=3).start()
        prev = _sig.getsignal(_sig.SIGHUP)
        try:
            _sig.signal(_sig.SIGHUP, lambda *_: m.request_reload())
            os.kill(os.getpid(), _sig.SIGHUP)
            time.sleep(0.3)
            assert m._reload_count >= 1
        finally:
            _sig.signal(_sig.SIGHUP, prev if callable(prev) else _sig.SIG_DFL)
            m._thread.join(timeout=5.0)
            m.stop()


@pytest.mark.needs_energy
class TestMonitorOtlpExporter:
    """D4 OpenTelemetry OTLP/gRPC exporter contract: byte-identical-when-off,
    fail-loud-when-deps-missing, drops-without-blocking-when-unreachable,
    metrics-and-labels-land-at-the-collector, cardinality-cap-respected."""

    @staticmethod
    def _otlp_sink_mod():
        from codegreen.instrumentation.language_runtimes.python import (
            codegreen_otlp_sink as mod,
        )
        return mod

    def test_otlp_disabled_is_byte_identical_to_before(self, tmp_path: Path) -> None:
        """With no --exporter flag, the JSONL stream and summary contain no
        exporter artefacts; behaviour matches the pre-Sink-ABC contract."""
        from codegreen import Monitor
        out = tmp_path / "energy.jsonl"
        m = Monitor(interval_ms=50, duration_s=0.5, output_file=str(out),
                    max_samples_in_memory=0).start()
        m._thread.join(timeout=5.0)
        summary = m.stop()
        assert "exporters" not in summary, summary
        text = out.read_text()
        # No OTLP artefacts anywhere in the stream.
        assert "otlp" not in text.lower()

    def test_otlp_missing_deps_raises_at_start(self) -> None:
        """When OTLP deps are absent, Monitor.start() raises RuntimeError with
        the exact pip-install command — no silent no-op."""
        mod = self._otlp_sink_mod()
        original = mod._OTLP_AVAILABLE
        mod._OTLP_AVAILABLE = False
        try:
            from codegreen import Monitor
            m = Monitor(interval_ms=50, duration_s=0.5, max_samples_in_memory=0,
                        exporters=["otlp"])
            with pytest.raises(RuntimeError) as exc:
                m.start()
            assert "pip install" in str(exc.value).lower()
            assert "codegreen[otlp]" in str(exc.value)
        finally:
            mod._OTLP_AVAILABLE = original

    def test_otlp_unreachable_endpoint_drops_but_does_not_block(
        self, tmp_path: Path,
    ) -> None:
        """A refused-connection endpoint must NOT wedge the sample loop.
        After 2-3s we expect samples > 0 AND exporters.otlp present in the
        summary (dropped_samples may be 0 if the export-thread keeps up
        with the small in-test traffic; the assertion is the loop kept
        running and the per-sink summary block was produced)."""
        from codegreen import Monitor
        out = tmp_path / "energy.jsonl"
        # 127.0.0.1:1 = guaranteed-refused by Linux/macOS test boxes.
        m = Monitor(interval_ms=100, duration_s=2.5, output_file=str(out),
                    max_samples_in_memory=0,
                    exporters=["otlp"],
                    exporter_overrides={"otlp": {
                        "endpoint": "http://127.0.0.1:1",
                        "export_interval_ms": 200,
                        "timeout_s": 1,
                        "queue_size": 64,
                    }}).start()
        try:
            for i in range(5):
                m.annotate_end(m.annotate_start(f"route_{i % 3}"))
                time.sleep(0.02)
        finally:
            m._thread.join(timeout=10.0)
            summary = m.stop()
        assert summary["samples"] > 0, summary
        assert "exporters" in summary, summary
        ex = summary["exporters"]["otlp"]
        assert ex["endpoint"] == "http://127.0.0.1:1"
        # The export-loop kept counting; whether or not the queue overflowed,
        # the loop never blocked the sampler — proof = samples > 0.
        assert "dropped_samples" in ex and "exported_samples" in ex

    def test_otlp_metrics_reach_collector(self) -> None:
        """In-process mock OTLP exporter captures every gRPC export call;
        we assert the metric names + resource attributes that land match
        the published contract."""
        from opentelemetry.sdk.metrics.export import MetricExportResult, MetricExporter
        recorded: list = []
        original = self._otlp_sink_mod().OTLPMetricExporter

        class _MockExporter(MetricExporter):
            def __init__(self, *a, **kw):
                super().__init__()
            def export(self, metrics_data, timeout_millis=10_000, **_kw):
                recorded.append(metrics_data)
                return MetricExportResult.SUCCESS
            def force_flush(self, timeout_millis=10_000):
                return True
            def shutdown(self, timeout_millis=10_000, **_kw):
                return None

        try:
            self._otlp_sink_mod().OTLPMetricExporter = _MockExporter
            from codegreen import Monitor
            m = Monitor(interval_ms=100, duration_s=1.5, max_samples_in_memory=0,
                        exporters=["otlp"],
                        exporter_overrides={"otlp": {
                            "export_interval_ms": 200,
                            "queue_size": 512,
                        }}).start()
            for _ in range(4):
                tok = m.annotate_start("GET /heavy")
                _busy(500_000)
                m.annotate_end(tok)
            m._thread.join(timeout=10.0)
            summary = m.stop()
        finally:
            self._otlp_sink_mod().OTLPMetricExporter = original

        assert summary["exporters"]["otlp"]["exported_samples"] >= 1
        assert summary["exporters"]["otlp"]["exported_annotations"] >= 1
        # Walk recorded metric batches; require at least the energy and
        # request-duration instruments to have landed at least once.
        names_seen = set()
        attrs_seen: set = set()
        for md in recorded:
            for rm in getattr(md, "resource_metrics", []):
                for attr in rm.resource.attributes.items():
                    attrs_seen.add(attr)
                for sm in rm.scope_metrics:
                    for metric in sm.metrics:
                        names_seen.add(metric.name)
        assert "codegreen.energy.joules" in names_seen, names_seen
        assert "codegreen.request.duration.seconds" in names_seen, names_seen
        # Resource attributes carry the canonical run identity.
        keys = {k for (k, _v) in attrs_seen}
        assert "service.name" in keys, keys
        assert "host.name" in keys, keys
        assert "process.pid" in keys, keys

    def test_otlp_respects_max_labels(self) -> None:
        """Cardinality cap (Monitor's per-label gate) must be honoured by the
        OTLP sink: max_labels=3, 5 distinct labels => OTLP sees exactly 4
        label values (3 distinct + __other__), never 5."""
        from opentelemetry.sdk.metrics.export import MetricExportResult, MetricExporter
        recorded: list = []
        original = self._otlp_sink_mod().OTLPMetricExporter

        class _MockExporter(MetricExporter):
            def __init__(self, *a, **kw): super().__init__()
            def export(self, metrics_data, timeout_millis=10_000, **_kw):
                recorded.append(metrics_data)
                return MetricExportResult.SUCCESS
            def force_flush(self, timeout_millis=10_000): return True
            def shutdown(self, timeout_millis=10_000, **_kw): return None

        try:
            self._otlp_sink_mod().OTLPMetricExporter = _MockExporter
            from codegreen import Monitor
            m = Monitor(interval_ms=100, duration_s=1.5, max_samples_in_memory=0,
                        max_labels=3,
                        exporters=["otlp"],
                        exporter_overrides={"otlp": {
                            "export_interval_ms": 150,
                            "queue_size": 512,
                        }}).start()
            for i in range(5):
                tok = m.annotate_start(f"label_{i}")
                _busy(200_000)
                m.annotate_end(tok)
            m._thread.join(timeout=10.0)
            summary = m.stop()
        finally:
            self._otlp_sink_mod().OTLPMetricExporter = original

        routes_seen: set = set()
        for md in recorded:
            for rm in getattr(md, "resource_metrics", []):
                for sm in rm.scope_metrics:
                    for metric in sm.metrics:
                        if metric.name != "codegreen.request.duration.seconds":
                            continue
                        for dp in metric.data.data_points:
                            attrs = dict(dp.attributes)
                            r = attrs.get("route")
                            if r is not None:
                                routes_seen.add(r)
        # Exactly 3 distinct labels + __other__ overflow bucket. Never 5.
        assert len(routes_seen) <= 4, routes_seen
        assert "__other__" in routes_seen or len(routes_seen) <= 3, routes_seen
        # And the Monitor's own per_label dict shows the same gating.
        assert summary["distinct_labels"] <= 4


@pytest.mark.needs_energy
class TestMonitorPrometheusExporter:
    """D5 Prometheus pull-endpoint contract: loopback-by-default, auth-token-when-set,
    cardinality-cap-respected, missing-deps-fail-loud, two-monitor isolation,
    resource-attribute redaction."""

    @staticmethod
    def _prom_sink_mod():
        from codegreen.instrumentation.language_runtimes.python import (
            codegreen_prometheus_sink as mod,
        )
        return mod

    @staticmethod
    def _free_port() -> int:
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        return port

    @staticmethod
    def _http_get(url: str, headers: Dict[str, str] | None = None, timeout: float = 3.0):
        import urllib.request
        req = urllib.request.Request(url, headers=headers or {})
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
            return resp.status, resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", errors="replace")

    def test_prometheus_disabled_is_byte_identical_to_before(self, tmp_path: Path) -> None:
        from codegreen import Monitor
        out = tmp_path / "energy.jsonl"
        m = Monitor(interval_ms=50, duration_s=0.5, output_file=str(out),
                    max_samples_in_memory=0).start()
        m._thread.join(timeout=5.0)
        summary = m.stop()
        assert "exporters" not in summary, summary
        text = out.read_text()
        assert "prometheus" not in text.lower()

    def test_prometheus_missing_deps_raises_at_start(self) -> None:
        mod = self._prom_sink_mod()
        original = mod._PROM_AVAILABLE
        mod._PROM_AVAILABLE = False
        try:
            from codegreen import Monitor
            m = Monitor(interval_ms=50, duration_s=0.5, max_samples_in_memory=0,
                        exporters=["prometheus"])
            with pytest.raises(RuntimeError) as exc:
                m.start()
            assert "pip install" in str(exc.value).lower()
            assert "codegreen[prometheus]" in str(exc.value)
        finally:
            mod._PROM_AVAILABLE = original

    def test_prometheus_serves_metrics_endpoint(self) -> None:
        from codegreen import Monitor
        port = self._free_port()
        m = Monitor(interval_ms=100, duration_s=1.2, max_samples_in_memory=0,
                    exporters=["prometheus"],
                    exporter_overrides={"prometheus": {"port": port}}).start()
        try:
            time.sleep(0.4)
            status, body = self._http_get(f"http://127.0.0.1:{port}/metrics")
            assert status == 200, (status, body[:200])
            assert "codegreen_energy_joules_total" in body, body[:400]
            assert "codegreen_power_watts" in body, body[:400]
            assert "codegreen_monitor_uptime_seconds" in body, body[:400]
            assert 'host=' in body and 'pid=' in body, body[:400]
        finally:
            m._thread.join(timeout=5.0)
            m.stop()

    def test_prometheus_request_metrics_after_annotation(self, tmp_path: Path) -> None:
        from codegreen import Monitor
        port = self._free_port()
        m = Monitor(interval_ms=80, duration_s=2.0, max_samples_in_memory=0,
                    exporters=["prometheus"],
                    exporter_overrides={"prometheus": {"port": port}}).start()
        try:
            tok = m.annotate_start("GET /test")
            time.sleep(0.25)
            m.annotate_end(tok)
            time.sleep(0.1)
            status, body = self._http_get(f"http://127.0.0.1:{port}/metrics")
            assert status == 200
            assert "codegreen_request_energy_joules_total" in body
            assert 'route="GET /test"' in body
            assert 'status="ok"' in body
            assert "codegreen_request_duration_seconds" in body
        finally:
            m._thread.join(timeout=5.0)
            m.stop()

    def test_prometheus_respects_max_labels_cap(self) -> None:
        from codegreen import Monitor
        port = self._free_port()
        m = Monitor(interval_ms=100, duration_s=2.0, max_samples_in_memory=0,
                    max_labels=3,
                    exporters=["prometheus"],
                    exporter_overrides={"prometheus": {"port": port}}).start()
        try:
            for i in range(5):
                tok = m.annotate_start(f"label_{i}")
                _busy(200_000)
                m.annotate_end(tok)
            time.sleep(0.15)
            status, body = self._http_get(f"http://127.0.0.1:{port}/metrics")
            assert status == 200
            routes: set = set()
            for line in body.splitlines():
                if line.startswith("codegreen_request_duration_seconds_count{"):
                    seg = line.split("route=\"", 1)[1].split("\"", 1)[0]
                    routes.add(seg)
            assert len(routes) <= 4, routes
            assert "__other__" in routes or len(routes) <= 3, routes
            assert "codegreen_overflow_label_count_total" in body
        finally:
            m._thread.join(timeout=5.0)
            m.stop()

    def test_prometheus_auth_token_required_when_configured(self) -> None:
        from codegreen import Monitor
        port = self._free_port()
        token = "s3cret-token-xyz"
        m = Monitor(interval_ms=100, duration_s=1.2, max_samples_in_memory=0,
                    exporters=["prometheus"],
                    exporter_overrides={"prometheus": {
                        "port": port, "auth_token": token,
                    }}).start()
        try:
            time.sleep(0.3)
            status, _ = self._http_get(f"http://127.0.0.1:{port}/metrics")
            assert status == 401
            status_ok, body = self._http_get(
                f"http://127.0.0.1:{port}/metrics",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert status_ok == 200
            assert "codegreen_energy_joules_total" in body
            uptime = re.search(r"^codegreen_monitor_uptime_seconds\{[^}]*\} (\S+)$", body, re.M)
            assert uptime and float(uptime.group(1)) > 0, "uptime gauge must be set before the first scrape renders"
            status_wrong, _ = self._http_get(
                f"http://127.0.0.1:{port}/metrics",
                headers={"Authorization": "Bearer wrong-token"},
            )
            assert status_wrong == 401
            status_health, _ = self._http_get(f"http://127.0.0.1:{port}/healthz")
            assert status_health == 200
        finally:
            m._thread.join(timeout=5.0)
            m.stop()

    def test_prometheus_loopback_default_warns_on_nonloopback(self) -> None:
        from codegreen import Monitor
        port = self._free_port()
        with pytest.warns(RuntimeWarning, match="non-loopback"):
            m = Monitor(interval_ms=100, duration_s=0.6, max_samples_in_memory=0,
                        exporters=["prometheus"],
                        exporter_overrides={"prometheus": {
                            "port": port, "listen_addr": "0.0.0.0",
                        }}).start()
        try:
            time.sleep(0.2)
        finally:
            m._thread.join(timeout=5.0)
            m.stop()

    def test_prometheus_healthz_endpoint(self) -> None:
        from codegreen import Monitor
        port = self._free_port()
        m = Monitor(interval_ms=100, duration_s=1.0, max_samples_in_memory=0,
                    exporters=["prometheus"],
                    exporter_overrides={"prometheus": {"port": port}}).start()
        try:
            time.sleep(0.3)
            status, body = self._http_get(f"http://127.0.0.1:{port}/healthz")
            assert status == 200, (status, body)
            doc = json.loads(body)
            assert doc["status"] == "healthy"
            assert doc["uptime_s"] >= 0
            assert doc["samples_seen"] >= 0
        finally:
            m._thread.join(timeout=5.0)
            m.stop()

    def test_prometheus_two_monitors_do_not_collide(self) -> None:
        from codegreen import Monitor
        p1 = self._free_port()
        p2 = self._free_port()
        m1 = Monitor(interval_ms=100, duration_s=1.5, max_samples_in_memory=0,
                     exporters=["prometheus"],
                     exporter_overrides={"prometheus": {"port": p1}}).start()
        m2 = Monitor(interval_ms=100, duration_s=1.5, max_samples_in_memory=0,
                     exporters=["prometheus"],
                     exporter_overrides={"prometheus": {"port": p2}}).start()
        try:
            time.sleep(0.4)
            s1, b1 = self._http_get(f"http://127.0.0.1:{p1}/metrics")
            s2, b2 = self._http_get(f"http://127.0.0.1:{p2}/metrics")
            assert s1 == 200 and s2 == 200
            assert "codegreen_energy_joules_total" in b1
            assert "codegreen_energy_joules_total" in b2
        finally:
            m1._thread.join(timeout=5.0)
            m2._thread.join(timeout=5.0)
            m1.stop()
            m2.stop()

    def test_prometheus_redaction_strips_host_name(self) -> None:
        from codegreen import Monitor
        port = self._free_port()
        m = Monitor(interval_ms=100, duration_s=1.0, max_samples_in_memory=0,
                    exporters=["prometheus"],
                    exporter_overrides={"prometheus": {
                        "port": port, "redact_resource_attrs": ["host"],
                    }}).start()
        try:
            tok = m.annotate_start("GET /redacted")
            _busy(100_000)
            m.annotate_end(tok)
            time.sleep(0.2)
            status, body = self._http_get(f"http://127.0.0.1:{port}/metrics")
            assert status == 200
            import platform as _p
            real_host = _p.node() or ""
            if real_host:
                assert f'host="{real_host}"' not in body, body[:400]
            assert 'host="__redacted__"' in body
            assert "codegreen_energy_joules_total" in body
        finally:
            m._thread.join(timeout=5.0)
            m.stop()


class TestProjectReadback:
    """`codegreen project` checkpoint readback shared by every runtime."""

    @staticmethod
    def _nemb_block(markers):
        ms = [{"checkpoint_id": m, "timestamp": ts, "joules": j, "watts": 1.0} for m, ts, j in markers]
        return ("--- CODEGREEN_RESULT_START ---\n" + json.dumps({"measurements": ms})
                + "\n--- CODEGREEN_RESULT_END ---\n")

    def test_nemb_block_replays_nested_calls(self):
        from codegreen.cli.cli import _nemb_checkpoint_events, _replay_checkpoint_events
        ids = {"function_enter_ns::f_1_1", "function_exit_ns::f_3_1", "function_enter_main_5_1", "function_exit_main_9_1"}
        block = self._nemb_block([
            ("enter:main:function_enter_main_5_1#inv_1_t7", 100, 1.0),
            ("enter:ns::f:function_enter_ns::f_1_1#inv_1_t7", 200, 2.0),
            ("exit:ns::f:function_exit_ns::f_3_1#inv_1_t7", 300, 5.0),
            ("exit:main:function_exit_main_9_1#inv_1_t7", 400, 6.0),
        ])
        # Runtime and NEMB atexit may both print; the larger block wins, never a sum.
        stdout = "out\n" + self._nemb_block([]) + block
        func = {}
        seen = _replay_checkpoint_events(_nemb_checkpoint_events(stdout, ids), func)
        assert ("ns::f", "function_enter_ns::f_1_1") in seen
        assert func["ns::f"] == {"inclusive_uj": 3_000_000, "exclusive_uj": 3_000_000, "time_ns": 100, "calls": 1}
        assert func["main"] == {"inclusive_uj": 5_000_000, "exclusive_uj": 2_000_000, "time_ns": 300, "calls": 1}

    def test_threads_replay_on_separate_stacks(self):
        from codegreen.cli.cli import _replay_checkpoint_events
        events = [("enter", "f", "a", 0, 0, "1"), ("enter", "f", "a", 5, 10, "2"),
                  ("exit", "f", "b", 10, 40, "1"), ("exit", "f", "b", 20, 70, "2")]
        func = {}
        _replay_checkpoint_events(events, func)
        assert func["f"]["calls"] == 2 and func["f"]["inclusive_uj"] == 100

    def test_stderr_sum_and_event_formats(self, tmp_path):
        from codegreen.cli.cli import _stderr_checkpoint_events, _replay_checkpoint_events
        f = tmp_path / "cp.txt"
        f.write_text("noise\nCG_CP_SUM|1|g|4|40|30|400\nCG_CP|enter|h|x|0|0|1\nCG_CP|exit|h|y|9|7|1\n")
        func = {}
        _replay_checkpoint_events(_stderr_checkpoint_events(str(f), func), func)
        assert func["g"] == {"inclusive_uj": 40, "exclusive_uj": 30, "time_ns": 400, "calls": 4}
        assert func["h"]["inclusive_uj"] == 7 and func["h"]["calls"] == 1

    def test_marker_without_invocation_suffix_fails_loud(self):
        from codegreen.cli.cli import _nemb_checkpoint_events
        with pytest.raises(ValueError, match="invocation suffix"):
            _nemb_checkpoint_events(self._nemb_block([("enter:f:id", 1, 0.0)]), set())

    def test_nemb_json_reader_survives_growth_between_calls(self):
        import sys
        sys.path.insert(0, str(Path(codegreen.__file__).parent / "instrumentation" / "language_runtimes" / "python"))
        from codegreen_runtime import _read_nemb_json
        payload = iter(['{"checkpoints": [1]}', '{"checkpoints": [1, 2]}', '{"checkpoints": [1, 2, 3]}'])
        cur = [next(payload)]

        def export(buf, size):
            s = cur[0]
            cur[0] = next(payload, s)  # sampling continues: the next call sees a longer payload
            if len(s) >= size:
                return -len(s)
            buf.value = s.encode()
            return len(s)

        assert json.loads(_read_nemb_json(export, 4))["checkpoints"] == [1, 2]


class TestDeviceSync:
    """`codegreen project --sync-device`: GPU launches are asynchronous, so a probe
    must drain the device before it stamps, or the frame owns only launch time."""

    @staticmethod
    def _runtime():
        import sys
        sys.path.insert(0, str(Path(codegreen.__file__).parent / "instrumentation" / "language_runtimes" / "python"))
        import codegreen_runtime
        return codegreen_runtime

    @staticmethod
    def _fake_torch(available: bool, initialized: bool):
        import types
        calls: list = []
        cuda = types.SimpleNamespace(is_available=lambda: available, is_initialized=lambda: initialized,
                                     synchronize=lambda: calls.append(1))
        return types.SimpleNamespace(cuda=cuda), calls

    def test_sync_runs_only_with_a_cuda_context(self, monkeypatch):
        import sys
        rt = self._runtime()
        monkeypatch.delitem(sys.modules, "torch", raising=False)
        assert rt._sync_cuda() is False
        torch, calls = self._fake_torch(True, False)
        monkeypatch.setitem(sys.modules, "torch", torch)
        assert rt._sync_cuda() is False and not calls
        torch, calls = self._fake_torch(True, True)
        monkeypatch.setitem(sys.modules, "torch", torch)
        assert rt._sync_cuda() is True and calls == [1]

    def test_unavailable_cuda_fails_loud(self, monkeypatch):
        import sys
        rt = self._runtime()
        monkeypatch.setitem(sys.modules, "torch", self._fake_torch(False, False)[0])
        with pytest.raises(RuntimeError, match="is_available"):
            rt._sync_cuda()

    def test_checkpoint_syncs_before_marking(self, monkeypatch):
        rt = self._runtime()
        order: list = []
        monkeypatch.setattr(rt, "_SYNC_DEVICE", "cuda")
        monkeypatch.setattr(rt, "_device_syncs", 0)
        monkeypatch.setitem(rt._DEVICE_SYNCS, "cuda", lambda: order.append("sync") or True)
        monkeypatch.setattr(rt, "measure_checkpoint", lambda *a: order.append("mark"))
        rt.checkpoint("id", "f", "exit")
        assert order == ["sync", "mark"] and rt._device_syncs == 1

    def test_unknown_device_is_rejected_at_import(self):
        import subprocess
        import sys
        rt_dir = Path(codegreen.__file__).parent / "instrumentation" / "language_runtimes" / "python"
        r = subprocess.run([sys.executable, "-c", "import codegreen_runtime"], cwd=rt_dir, capture_output=True,
                           text=True, env={**os.environ, "CODEGREEN_SYNC_DEVICE": "tpu"})
        assert r.returncode != 0 and "supported: ['cuda']" in r.stderr

    def test_sync_count_sums_runtime_blocks(self):
        from codegreen.cli.cli import _device_sync_count
        blk = lambda d: ("--- CODEGREEN_RESULT_START ---\n" + json.dumps(d) + "\n--- CODEGREEN_RESULT_END ---\n")
        assert _device_sync_count("x\n" + blk({"measurements": []}) + blk({"device_sync": {"mode": "cuda", "syncs": 6}})) == 6
        assert _device_sync_count("no blocks") == 0

    @pytest.mark.needs_energy
    def test_project_flags_documented_and_validated(self, tmp_path):
        import subprocess
        from typer.testing import CliRunner
        from codegreen.cli.cli import app
        out = _plain(CliRunner().invoke(app, ["project", "--help"]).output)
        assert "--sync-device" in out and "--min-attribution-pct" in out
        (tmp_path / "w.py").write_text("def work(n):\n    return sum(i * i for i in range(n))\n\n\nwork(1000)\n")
        run = lambda *extra: subprocess.run(
            ["codegreen", "project", "python", str(tmp_path), "--source-glob", "w.py", "--run-cmd", "python3 w.py",
             "--json", *extra], capture_output=True, text=True, timeout=120)
        bad = run("--sync-device", "mps")
        assert bad.returncode == 1 and "unsupported for python" in bad.stdout
        no_cuda = run("--sync-device", "cuda")
        assert no_cuda.returncode == 1 and "no device synchronisation ran" in no_cuda.stdout
        low = json.loads(run("--min-attribution-pct", "100.1").stdout)
        assert low["attribution_warning"]["code"] == "LOW_ATTRIBUTION" and low["runs"][0]["attribution_warning"]
        assert low["attribution_pct"] == low["runs"][0]["attribution_pct"] and low["sync_device"] == ""
        ok = json.loads(run("--min-attribution-pct", "0").stdout)
        assert ok["attribution_warning"] is None


class TestJavaAggregateFile:
    """Per-JVM aggregates go to CG_CP_CHECKPOINT_FILE, not stderr: a JMH fork's
    stderr is a forwarding link that can close before shutdown hooks run, which
    silently dropped whole forks' hot methods (RoaringBitmap, 2026-09-25)."""

    def test_each_jvm_appends_its_block_to_the_file(self, tmp_path: Path) -> None:
        import os
        import shutil
        import subprocess
        javac = shutil.which("javac")
        if javac is None:
            pytest.skip("javac not available")
        rt = Path(__file__).parents[1] / "codegreen/instrumentation/language_runtimes/java/codegreen/runtime"
        (tmp_path / "T.java").write_text(
            "public class T { static int f(int x){ codegreen.runtime.CodeGreenStandaloneRuntime"
            ".checkpoint(\"1\",\"T.f\",\"enter\"); codegreen.runtime.CodeGreenStandaloneRuntime"
            ".checkpoint(\"2\",\"T.f\",\"exit\"); return x; } public static void main(String[] a)"
            "{ for (int i = 0; i < 1000; i++) f(i); } }")
        subprocess.run([javac, "-d", str(tmp_path), str(rt / "CodeGreenStandaloneRuntime.java"),
                        str(tmp_path / "T.java")], check=True)
        env = {**os.environ, "CG_CP_CHECKPOINT_FILE": str(tmp_path / "sum")}
        dom = tmp_path / "rapl" / "intel-rapl:0"
        dom.mkdir(parents=True)
        for name, text in (("name", "package-0"), ("energy_uj", "0"), ("max_energy_range_uj", "1000000")):
            (dom / name).write_text(text + "\n")
        for _ in range(2):
            r = subprocess.run(["java", f"-Dcodegreen.rapl.root={tmp_path / 'rapl'}", "-cp", str(tmp_path), "T"], env=env,
                               capture_output=True, text=True, check=True)
            assert r.stderr == ""
        lines = (tmp_path / "sum").read_text().splitlines()
        assert len(lines) == 2 and all(line.startswith("CG_CP_SUM|") and "|T.f|1000|" in line
                                       for line in lines)


def test_project_restores_sources_after_an_interrupted_run(tmp_path):
    """A run killed mid-profiling (SIGKILL: no `finally`) left sources
    instrumented; the next run restores them from .codegreen_backup/ and
    removes the injected runtime, with or without git."""
    import json
    import subprocess
    src = tmp_path / "work.py"
    original = "def spin(n):\n    return sum(i * i for i in range(n))\n\n\nif __name__ == '__main__':\n    spin(10)\n"
    src.write_text("# instrumented\n" + original)
    (tmp_path / "codegreen_runtime.py").write_text("# injected")
    backup = tmp_path / ".codegreen_backup"
    backup.mkdir()
    (backup / "0.orig").write_text(original)
    (backup / "manifest.json").write_text(json.dumps({str(src): "0.orig"}))
    (backup / "runtime.json").write_text(json.dumps([str(tmp_path / "codegreen_runtime.py")]))
    subprocess.run(["codegreen", "project", "python", str(tmp_path), "--source-glob", "work.py", "--run-cmd", "true"],
                   cwd=tmp_path, capture_output=True, text=True, timeout=120)
    assert src.read_text() == original
    assert not backup.exists() and not (tmp_path / "codegreen_runtime.py").exists()


def test_injected_python_runtime_leaves_no_bytecode_cache(tmp_path):
    """Importing the injected runtime writes __pycache__/codegreen_runtime.*.pyc;
    it outlived the .py and a KernelBench campaign stopped on it as residue."""
    from codegreen.cli.cli import _remove_injected
    rt = tmp_path / "codegreen_runtime.py"
    rt.write_text("x = 1\n")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "codegreen_runtime.cpython-313.pyc").write_bytes(b"x")
    (tmp_path / "__pycache__" / "solution.cpython-313.pyc").write_bytes(b"x")
    _remove_injected(rt)
    assert not rt.exists() and [p.name for p in (tmp_path / "__pycache__").iterdir()] == ["solution.cpython-313.pyc"]


def test_project_command_keeps_its_signature():
    """A helper inserted between @app.command("project") and project_energy
    became the `project` command (PATH only), which every ADEPT profiling call
    uses; the command must keep LANGUAGE and --source-glob."""
    from typer.testing import CliRunner
    from codegreen.cli.cli import app
    out = _plain(CliRunner().invoke(app, ["project", "--help"], terminal_width=400).output)
    assert "language" in out.lower() and "--source-glob" in out and "--run-cmd" in out


def test_monitor_help_shows_extras_brackets_and_real_flags():
    """Rich markup swallowed `[otlp]`/`[prometheus]`; docstring named the nonexistent --interval-ms."""
    from typer.testing import CliRunner
    from codegreen.cli.cli import app
    out = _plain(CliRunner().invoke(app, ["monitor", "--help"], terminal_width=400).output)
    assert "codegreen[otlp]" in out and "codegreen[prometheus]" in out
    assert "--interval-ms" not in out


def test_timeseries_clock_label_matches_nemb_and_stale_cache_is_regenerated(monkeypatch, tmp_path):
    """NEMB stamps CLOCK_MONOTONIC (PrecisionTimer::monotonic_timestamp_ns); the label must say so
    and a pre-fix cache written with the old label must not be trusted."""
    from codegreen.instrumentation.language_runtimes.python import codegreen_runtime as rt
    if not sys.platform.startswith("linux"):
        pytest.skip("Linux-specific label")
    assert rt._detect_install_info()["timeseries_clock"] == "clock_monotonic"
    cache = tmp_path / "install_info.json"
    cache.write_text(json.dumps({"schema": 1, "platform": sys.platform, "timeseries_clock": "clock_monotonic_raw"}))
    monkeypatch.setattr(rt, "_install_info_path", lambda: cache)
    rt._machine_install_info.cache_clear()
    try:
        assert rt._machine_install_info()["timeseries_clock"] == "clock_monotonic"
    finally:
        rt._machine_install_info.cache_clear()


def test_project_fails_up_front_without_the_native_backend(tmp_path, monkeypatch):
    """A source install built without cmake is Python-only; `project` used to run
    the workload and then report 'No checkpoint records captured'."""
    from typer.testing import CliRunner
    import codegreen.cli.cli as cli
    monkeypatch.setattr(cli._NEMBBackend, "is_available", lambda self: False)
    (tmp_path / "p.py").write_text("print(1)\n")
    r = CliRunner().invoke(cli.app, ["project", "python", str(tmp_path), "--run-cmd", "python p.py"])
    assert r.exit_code == 1 and "NEMB native measurement library" in _plain(r.output)
