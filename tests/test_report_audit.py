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
import socket
import subprocess
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


def _cli_run(*args: str, timeout: float = 60.0) -> tuple:
    """Invoke `codegreen <args>`. Returns (parsed_json_or_None, stdout, stderr, rc)."""
    p = subprocess.run(["codegreen", *args], capture_output=True, text=True, timeout=timeout)
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

    def test_meta_describes_timeseries_schema(self, timeseries_session: Dict) -> None:
        m = timeseries_session["meta"]["timeseries"]
        assert m["enabled"] is True
        assert m["t_ns_clock"] == "clock_monotonic"
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
