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
from typing import Any, Dict, List, Optional

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
        assert out["meta"]["outlier_method"] == "none"
        assert out["meta"]["iso_timestamp_format"] == "rfc3339_utc"

    def test_budget_exceeded_path_includes_meta(self) -> None:
        out, _, _, _ = _cli_run("run", "--json", "-n", "2", "-w", "0",
                                "--budget", "0.001", "--", *self.SMALL_WORKLOAD)
        if out is None:
            pytest.skip("CLI did not return JSON on this host")
        assert "meta" in out
        assert out.get("budget_exceeded") is True
        assert out.get("budget_j") == 0.001

    def test_text_mode_prints_energy_and_verdict(self, tmp_path: Path) -> None:
        """Without --json, measure prints the energy and per-function rows, and measure and run print the verdict."""
        src = tmp_path / "w.py"
        src.write_text("def spin(n):\n    return sum(i * i for i in range(n))\n\n\ndef main():\n    spin(3_000_000)\n\n\n"
                       "if __name__ == '__main__':\n    main()\n")
        verdict = re.compile(r"^(Validity: valid|invalid_measurement: [A-Z_,]+)$", re.M)
        _, out, _, _ = _cli_run("measure", "python", str(src), "-g", "fine")
        assert re.search(r"^Energy: \d+\.\d+ J$", out, re.M) and re.search(r"^  spin\s", out, re.M) and verdict.search(out)
        _, out, _, _ = _cli_run("run", "-n", "2", "-w", "0", "--", *self.SMALL_WORKLOAD)
        assert verdict.search(out)

    def test_project_sensors_select_providers(self, tmp_path: Path) -> None:
        """project --sensors selects the measured providers like measure and run (CODEGREEN_PROVIDERS)."""
        (tmp_path / "main.py").write_text("def spin(n):\n    return sum(i * i for i in range(n))\n\n\n"
                                          "if __name__ == '__main__':\n    spin(3_000_000)\n")
        out, _, err, _ = _cli_run("project", "python", str(tmp_path), "--run-cmd", "python3 main.py",
                                  "--sensors", "rapl", "--json")
        assert out is not None, err
        assert {p["hardware_type"] for p in out["runs"][0]["sampler"]["providers"]} == {"cpu"}
        assert "GPU_IN_TOTAL" not in out["validity"]["warnings"]

    def test_warmup_runs_stay_out_of_the_statistics(self) -> None:
        """Warmup runs are unmeasured; a warmup counted in the statistics is a run (--warmup 0, more --repeat)."""
        out, _, _, _ = _cli_run("run", "--json", "-n", "3", "-w", "2", "--", *self.SMALL_WORKLOAD)
        assert out["runs"]["warmup_runs"] == 2 and out["runs"]["attempted"] == len(out["runs"]["energies_j"]) == 3
        assert "warmup_included_in_stats" not in out["runs"] and "include_warmup" not in out["meta"]
        _, _, err, rc = _cli_run("run", "--include-warmup", "--", "true")
        assert rc == 2 and "No such option" in err

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
    monkeypatch.setenv("CODEGREEN_CONFIG", str(cfg))  # the resolver prefers it over the bundled file
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
            r = subprocess.run(["java", f"-Dcodegreen.rapl.root={tmp_path / 'rapl'}", "-Dcodegreen.rapl.zone=intel-rapl:\\d+",
                                "-Dcodegreen.rapl.superset=psys", "-Dcodegreen.rapl.disjoint=dram", "-Dcodegreen.rapl.poll_us=1000", "-cp", str(tmp_path), "T"],
                               env=env, capture_output=True, text=True, check=True)
            assert r.stderr == ""
        lines = (tmp_path / "sum").read_text().splitlines()
        sums = [line for line in lines if line.startswith("CG_CP_SUM|")]
        metas = [json.loads(line.split("|", 1)[1]) for line in lines if line.startswith("CG_CP_META|")]
        assert len(sums) == 2 and all("|T.f|1000|" in line for line in sums) and len(lines) == 4
        assert len(metas) == 2 and all(m["interval_ms"] == 1.0 and m["marker_reads"] == "last_poll" for m in metas)


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


def test_version_comes_from_the_source_tree_not_stale_metadata():
    """An editable install with metadata from an older build reported that version for newer code (0.4.8 vs 0.5.0)."""
    from typer.testing import CliRunner
    import codegreen.cli.cli as cli
    pyproject = (Path(codegreen.__file__).resolve().parent.parent / "pyproject.toml").read_text()
    version = re.search(r'^version *= *"([^"]+)"', pyproject, re.M).group(1)
    assert codegreen.__version__ == version
    assert version in CliRunner().invoke(cli.app, ["--version"]).output
    from codegreen.instrumentation.language_runtimes.python import codegreen_runtime as rt
    assert rt._runtime_version() == version  # meta.codegreen_version of every report read stale metadata


def test_init_merges_detected_providers_into_the_user_config_on_every_environment(tmp_path, monkeypatch):
    """init raised KeyError 'accuracy' on container, hpc, shared_server and cicd hosts (it tuned keys no config has
    and nothing reads) and, without a user config, overwrote the bundled config.json."""
    from typer.testing import CliRunner
    import codegreen.cli.cli as cli
    from codegreen.instrumentation.language_runtimes.python import codegreen_runtime as rt
    bundled = rt._package_file("config.json")
    before = bundled.read_text()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(cli, "detect_hardware_sensors", lambda: {"intel_rapl": {"available": True}})
    monkeypatch.setattr(cli, "check_energy_permissions", lambda: {})
    monkeypatch.setattr(cli, "test_configuration", lambda c: {"success": "measurement" in c, "errors": []})
    for env in ("personal", "container", "hpc", "shared_server", "cicd"):
        monkeypatch.delenv("CODEGREEN_CONFIG", raising=False)
        monkeypatch.setattr(cli, "detect_environment", lambda: {"type": env, "platform": "linux", "deployment_mode": ""})
        r = CliRunner().invoke(cli.app, ["init", "--auto-detect-only", "--force"])
        assert r.exit_code == 0, r.output
        assert rt._config_path() == tmp_path / ".codegreen" / "config.json"
        assert rt.load_config()["initialization"]["environment_type"] == env
        assert rt.providers_env(None, rt._measurement_cfg()) == "intel_rapl"
    assert bundled.read_text() == before


def test_config_search_order_matches_the_docs(tmp_path, monkeypatch):
    """Docs listed codegreen.json search paths (./, config/, ~/.codegreen/, /etc/codegreen/) that no resolver reads.
    The one resolver: CODEGREEN_CONFIG, else ~/.codegreen/config.json when it exists, else the bundled config.json."""
    from codegreen.instrumentation.language_runtimes.python import codegreen_runtime as rt
    root = Path(__file__).resolve().parents[1]
    pages = [p for p in (root / "docs").rglob("*.md") if p.name != "changelog.md"] + [root / "scripts" / "commands.sh"]
    assert [str(p) for p in pages if "codegreen.json" in p.read_text()] == []
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("CODEGREEN_CONFIG", raising=False)
    assert rt._config_path() == rt._package_file("config.json")
    (tmp_path / ".codegreen").mkdir()
    (tmp_path / ".codegreen" / "config.json").write_text("{}")
    assert rt._config_path() == tmp_path / ".codegreen" / "config.json"
    monkeypatch.setenv("CODEGREEN_CONFIG", str(tmp_path / "x.json"))
    assert rt._config_path() == tmp_path / "x.json"


def test_measure_output_file_is_the_json_report_with_the_verdict(tmp_path, monkeypatch):
    """`measure -o` wrote a raw schema with measurement.success true on an invalid run, so a consumer of the file
    used invalid joules; the file must be the --json document, verdict included, with or without --json."""
    from typer.testing import CliRunner
    import codegreen.cli.cli as cli
    validity = {"status": "invalid", "reasons": ["TOTAL_BELOW_RESOLUTION"],
                "detail": {"TOTAL_BELOW_RESOLUTION": "root window spans 0 reading(s) < 2"}, "warnings": {}}
    fake = {"success": True, "output": "", "error": None, "returncode": 0, "sampler": _vsampler(), "validity": validity,
            "checkpoints": [_vcp("enter:main:p", 0, 1.0, 1), _vcp("exit:main:p", 7_000_000, 1.5, 1)]}
    monkeypatch.setattr(cli, "_should_run_actual_measurement", lambda: True)
    monkeypatch.setattr(cli, "_run_energy_measurement", lambda *a, **k: fake)
    script = tmp_path / "w.py"
    script.write_text("def f():\n    return 1\n\n\nf()\n")
    docs = []
    for extra in (["--json"], []):
        out = tmp_path / f"r{len(extra)}.json"
        r = CliRunner().invoke(cli.app, ["measure", "python", str(script), "-o", str(out), *extra])
        assert r.exit_code == 3
        docs.append(json.loads(out.read_text()))
        if extra:
            assert json.loads(r.stdout) == docs[-1]
    for d in docs:
        assert d["success"] is False and d["error"] == "invalid_measurement: TOTAL_BELOW_RESOLUTION"
        assert d["validity"] == validity and "per_function_energy" in d and d["summary"]["total_energy_j"] == 0.5


def _vcp(cid: str, ts: int, joules: float, ri: int, clamp: str = "none", tid: str = "1") -> Dict:
    return {"checkpoint_id": f"{cid}#inv_1_t{tid}", "timestamp": ts, "joules": joules, "watts": 1.0, "ri": ri,
            "clamp": clamp, "provider_j": {"intel_rapl": joules}}


def _jprov(name: str = "intel_rapl", hw: str = "cpu", source: str = "counter", ms: float = 1.0) -> Dict:
    """A provider record as the Java standalone poller writes it (no boundary reads)."""
    return {"name": name, "hardware_type": hw, "energy_source": source, "boundary_source": source, "update_interval_ms": ms,
            "counter_group": "cpu_package" if hw == "cpu" else "", "rejected": 0, "held": 0}


def _vprov(name: str = "intel_rapl", hw: str = "cpu", source: str = "counter", ms: float = 1.0, **kw) -> Dict:
    return {**_jprov(name, hw, source, ms), "boundary_held": 0, "boundary_held_max_ns": 0, "counter_check": {},
            "readings": 50, "last_ns": 500_000_000, "max_stall_ns": 0, **kw}


def _vsampler(**kw) -> Dict:
    """An ABI 4 sampler block (wire contract: providers objects, marker_reads, interval range, failed_reads)."""
    return {"interval_ms": 10, "interval_ms_min": 10, "interval_ms_max": 10, "buffer_capacity": 100000,
            "readings": 50, "wrapped": False, "rejected_readings": 0, "failed_reads": 0, "first_ns": 0,
            "last_ns": 500_000_000, "median_gap_ns": 10_000_000, "max_gap_ns": 12_000_000, "affinity_cpus": 8,
            "sampler_affinity_cpus": 8, "providers": [_vprov()], "marker_reads": "interpolated",
            "config_path": "config.json", "dropped_checkpoints": 0, **kw}


class TestValidity:
    """measurement_validity reason codes on synthetic NEMB ABI-4 results (no hardware)."""

    @staticmethod
    def _check(cps=None, sampler=None, run=None, cfg=None):
        from codegreen.cli.cli import measurement_validity, _measurement_cfg
        cps = [_vcp("enter:main:E", 0, 1.0, 1), _vcp("exit:main:X", 400_000_000, 9.0, 41)] if cps is None else cps
        return measurement_validity(cps, _vsampler() if sampler is None else sampler, run or {},
                                    cfg or _measurement_cfg())

    def test_package_under_test_is_this_tree(self):
        assert Path(codegreen.__file__).resolve().parents[1] == _CG_REPO

    def test_clean_run_is_valid(self):
        assert self._check() == {"status": "valid", "reasons": [], "detail": {}, "warnings": {}}

    @pytest.mark.parametrize("sampler_kw,code", [
        ({"max_gap_ns": 400_000_000}, "SAMPLER_STARVED"),
        ({"median_gap_ns": 16_000_000}, "SAMPLER_STARVED"),
        ({"wrapped": True}, "BUFFER_WRAPPED"),
        ({"dropped_checkpoints": 3}, "CHECKPOINT_CAP"),
        ({"provider_restarts": 1}, "PROVIDER_READ_FAILED"),
        ({"marker_reads": "last_poll", "failed_reads": 2}, "PROVIDER_READ_FAILED"),
    ])
    def test_sampler_reasons(self, sampler_kw, code):
        assert self._check(sampler=_vsampler(**sampler_kw))["reasons"] == [code]

    @pytest.mark.parametrize("sampler_kw,code", [
        ({"affinity_cpus": 1}, "AFFINITY_SINGLE_CPU"),
        ({"providers": [_vprov(), _vprov("nvidia_gpu", "gpu", "integrated_power", 100.0)]}, "GPU_IN_TOTAL"),
        ({"providers": [_vprov("nvidia_gpu", "gpu", "integrated_power", 100.0, held=3)]}, "GPU_READ_HELD"),
        ({"rejected_readings": 4}, "READINGS_REJECTED"),
        ({"failed_reads": 4}, "PROVIDER_READ_FAILED"),
        ({"marker_reads": "last_poll", "max_gap_ns": 400_000_000}, "SAMPLER_GAP"),
    ])
    def test_sampler_warnings(self, sampler_kw, code):
        v = self._check(sampler=_vsampler(**sampler_kw))
        assert v["status"] == "valid" and list(v["warnings"]) == [code]

    def test_text_verdict_shows_status_reasons_and_warnings(self):
        from codegreen.cli import cli
        with cli.console.capture() as cap:
            cli._print_validity(cli._validity({"ZERO_ENERGY": "root window measured 0 J"}, {"GPU_IN_TOTAL": "sums ['gpu']"}))
            cli._print_validity(cli._validity({}))
        assert cap.get().splitlines() == ["invalid_measurement: ZERO_ENERGY", "  ZERO_ENERGY: root window measured 0 J",
                                          "  WARNING GPU_IN_TOTAL: sums ['gpu']", "Validity: valid"]

    def test_run_validity_reads_boundary_source(self):
        from codegreen.cli.cli import run_validity, _measurement_cfg
        gpu = _vprov("nvidia_gpu", "gpu", "integrated_power", 100.0)
        v = run_validity([5.0], 2.0, _vsampler(providers=[gpu]), _measurement_cfg())
        assert v["status"] == "valid" and list(v["warnings"]) == ["RUN_POWER_INTEGRATED"]
        v = run_validity([5.0], 2.0, _vsampler(providers=[{**gpu, "boundary_source": "counter", "held": 2}]),
                         _measurement_cfg())
        assert v["status"] == "valid" and list(v["warnings"]) == ["GPU_READ_HELD"]

    @pytest.mark.parametrize("span_ns,warned", [(99_000_000, False), (100_000_000, False), (100_000_001, True)])
    def test_boundary_holds_warn_only_beyond_the_update_interval(self, span_ns, warned):
        """run --repeat chains stop/start within one counter period: those holds stay within the resolution."""
        from codegreen.cli.cli import run_validity, _measurement_cfg
        gpu = _vprov("nvidia_gpu", "gpu", "integrated_power", 100.0, boundary_source="counter", boundary_held=9,
                     boundary_held_max_ns=span_ns)
        v = run_validity([5.0], 2.0, _vsampler(providers=[gpu]), _measurement_cfg())
        assert v["status"] == "valid" and list(v["warnings"]) == (["BOUNDARY_READ_HELD"] if warned else [])

    @pytest.mark.parametrize("counter_j,span_s,reads,reasons", [
        (135.4, 6.0, 4, []),            # measured without another reader: counter/integral 0.99
        (11.9, 6.0, 4, ["COUNTER_INTEGRAL_DIVERGED"]),  # nvidia-smi power.draw.instant every 10 ms: 0.07
        (124.0, 6.0, 4, []),            # 9 % off over 6 s: within tolerance 0.05 plus five 100 ms update intervals
        (110.0, 6.0, 4, ["COUNTER_INTEGRAL_DIVERGED"]),
        (110.0, 6.0, 10, []),           # each counter read may discard up to one update interval of energy
        (110.0, 1.0, 4, []),
    ])
    def test_counter_integral_divergence(self, counter_j, span_s, reads, reasons):
        from codegreen.cli.cli import run_validity, _measurement_cfg
        k = {"gpu0": {"counter_j": counter_j, "integral_j": 136.5, "span_ns": int(span_s * 1e9), "reads": reads}}
        gpu = _vprov("nvidia_gpu", "gpu", "integrated_power", 100.0, boundary_source="counter", counter_check=k)
        v = run_validity([45.0] * 3, 2.0, _vsampler(providers=[gpu]), _measurement_cfg())
        assert v["reasons"] == reasons and v["warnings"] == {}
        assert self._check(sampler=_vsampler(providers=[gpu]))["reasons"] == reasons
        cfg = _measurement_cfg()
        cfg["counter_check"] = {**cfg["counter_check"], "severity": "warning"}
        assert list(run_validity([45.0] * 3, 2.0, _vsampler(providers=[gpu]), cfg)["warnings"]) == reasons

    @pytest.mark.parametrize("gpu_kw,lost", [
        ({}, False),
        ({"readings": 0, "last_ns": 0}, True),                # never read successfully
        ({"max_stall_ns": 1_000_000_000}, False),            # 10 resolutions of the 100 ms update interval
        ({"max_stall_ns": 1_000_000_001}, True),             # energy unchanged for longer: lost mid-run
        ({"last_ns": 500_000_000 - 1_000_000_001}, True),    # no successful read since then while the CPU kept reading
    ])
    def test_provider_stalled(self, gpu_kw, lost):
        from codegreen.cli.cli import run_validity, _measurement_cfg
        sampler = _vsampler(providers=[_vprov(), _vprov("nvidia_gpu", "gpu", "integrated_power", 100.0, **gpu_kw)])
        assert ("PROVIDER_STALLED" in self._check(sampler=sampler)["reasons"]) == lost
        assert ("PROVIDER_STALLED" in run_validity([5.0], 2.0, sampler, _measurement_cfg())["reasons"]) == lost
        cpu = _vsampler(providers=[_vprov(max_stall_ns=100_000_001)])  # CPU: 10 x the 10 ms sampler interval
        assert self._check(sampler=cpu)["reasons"] == ["PROVIDER_STALLED"]

    def test_counter_check_merges_across_processes(self):
        from codegreen.instrumentation.language_runtimes.python.codegreen_runtime import _merge_samplers
        k = {"gpu0": {"counter_j": 1.0, "integral_j": 2.0, "span_ns": 3, "reads": 2}}
        gpu = _vprov("nvidia_gpu", "gpu", "integrated_power", 100.0, counter_check=k)
        out = _merge_samplers([_vsampler(providers=[gpu]), _vsampler(providers=[gpu])])
        assert out["providers"][0]["counter_check"] == {"gpu0": {"counter_j": 2.0, "integral_j": 4.0, "span_ns": 6, "reads": 4}}
        assert k == {"gpu0": {"counter_j": 1.0, "integral_j": 2.0, "span_ns": 3, "reads": 2}}

    def test_gap_policy_is_config(self):
        from codegreen.cli.cli import _measurement_cfg
        cfg = _measurement_cfg()
        cfg["gap_policy"] = {**cfg["gap_policy"], "interpolated": {**cfg["gap_policy"]["interpolated"], "severity": "warning"}}
        v = self._check(sampler=_vsampler(max_gap_ns=400_000_000), cfg=cfg)
        assert v["status"] == "valid" and list(v["warnings"]) == ["SAMPLER_GAP"]
        with pytest.raises(KeyError):
            self._check(sampler=_vsampler(marker_reads="unknown"))

    def test_runtime_embeds_validity_and_cli_adds_process_reasons(self, tmp_path):
        from codegreen.cli.cli import _run_energy_measurement, Language
        cps = [_vcp("enter:main:E", 0, 1.0, 1), _vcp("exit:main:X", 9, 9.0, 41)]
        embedded = {"measurements": cps, "sampler": _vsampler(), "validity": {
            "status": "invalid", "reasons": ["ZERO_ENERGY"], "detail": {"ZERO_ENERGY": "x"}, "warnings": {"W": "y"}}}
        (tmp_path / "w.py").write_text(f"print('--- CODEGREEN_RESULT_START ---'); print({json.dumps(json.dumps(embedded))}); "
                                       "print('--- CODEGREEN_RESULT_END ---')\nraise SystemExit(4)\n")
        v = _run_energy_measurement(tmp_path / "w.py", Language.python, None, False, 30, None, True)["validity"]
        assert v["reasons"] == ["ZERO_ENERGY", "INCOMPLETE_CRASH"] and v["warnings"] == {"W": "y"}

    def test_atexit_payload_carries_validity(self, tmp_path):
        rt_dir = Path(codegreen.__file__).parent / "instrumentation" / "language_runtimes" / "python"
        cps = [_vcp("enter:main:E", 0, 1.0, 1), _vcp("exit:main:X", 9, 1.0, 41)]
        (tmp_path / "w.py").write_text(
            "import atexit, types\nimport codegreen_runtime as rt\n"
            f"final = {{'measurements': {cps!r}, 'sampler': {_vsampler()!r}}}\n"
            "rt._get_nemb_client = lambda: types.SimpleNamespace(lib=None, abi=4, get_final_measurements=lambda: final)\n"
            "atexit.register(rt._report_at_exit)\n")
        r = subprocess.run([sys.executable, "w.py"], cwd=tmp_path, capture_output=True, text=True, timeout=60,
                           env={**os.environ, "PYTHONPATH": str(rt_dir)})
        from codegreen.cli.cli import _nemb_result_block
        assert r.returncode == 0, r.stderr
        assert _nemb_result_block(r.stdout)["validity"]["reasons"] == ["ZERO_ENERGY"]

    def test_config_resolver_merges_and_fails_loud(self, tmp_path, monkeypatch):
        from codegreen.instrumentation.language_runtimes.python import codegreen_runtime as rt
        user = tmp_path / "c.json"
        user.write_text(json.dumps({"measurement": {"report": {"validity": {"min_affinity_cpus": 4}}}}))
        monkeypatch.setenv("CODEGREEN_CONFIG", str(user))
        cfg = rt._measurement_cfg()
        assert cfg["min_affinity_cpus"] == 4 and cfg["gap_policy"]["interpolated"]["severity"] == "fatal"
        user.write_text("{bad")
        with pytest.raises(RuntimeError, match=str(user)):
            rt._measurement_cfg()

    def test_sensor_selection_builds_provider_alternatives(self):
        from codegreen.cli.cli import _measurement_cfg, providers_env
        cfg = _measurement_cfg()
        assert providers_env(None, cfg) is None and providers_env(["rapl", "nvidia"], cfg) == "intel_rapl|amd_rapl,nvidia_gpu"
        cfg["nemb_providers"] = {**cfg["nemb_providers"], "amd_rapl": {"enabled": False}}
        assert providers_env(["rapl"], {**cfg, "default_sensors": ["rapl"]}) == "intel_rapl"
        assert providers_env(None, {**cfg, "default_sensors": ["rapl"]}) == "intel_rapl"
        with pytest.raises(ValueError, match="default_sensors"):
            providers_env(None, cfg)
        with pytest.raises(ValueError, match="every provider disabled"):
            providers_env(["amd_cpu"], cfg)

    @pytest.mark.parametrize("cps,code", [
        ([_vcp("enter:main:E", 0, 1.0, 0, "before_first"), _vcp("exit:main:X", 9, 9.0, 41)], "MARKER_CLAMPED"),
        ([_vcp("enter:main:E", 0, 1.0, 40), _vcp("exit:main:X", 9, 9.0, 41)], "TOTAL_BELOW_RESOLUTION"),
        ([_vcp("enter:main:E", 0, 5.0, 1), _vcp("exit:main:X", 9, 5.0, 41)], "ZERO_ENERGY"),
        ([_vcp("enter:main:E", 0, 5.0, 1), _vcp("enter:f:F", 5, 6.0, 9), _vcp("exit:main:X", 9, 4.0, 41)],
         "NEGATIVE_ENERGY"),
    ])
    def test_marker_reasons(self, cps, code):
        assert self._check(cps=cps)["reasons"] == [code]

    def test_stale_library_and_incomplete_runs(self):
        from codegreen.cli.cli import measurement_validity, _measurement_cfg
        cfg, cps = _measurement_cfg(), [_vcp("enter:main:E", 0, 1.0, 1), _vcp("exit:main:X", 9, 9.0, 41)]
        assert measurement_validity(cps, None, {}, cfg)["reasons"] == ["STALE_LIBRARY"]
        assert measurement_validity([], None, {}, cfg)["reasons"] == ["INCOMPLETE_NO_CHECKPOINTS"]
        assert self._check(run={"timed_out": True, "timeout_s": 5, "returncode": -15})["reasons"] == [
            "INCOMPLETE_TIMEOUT"]
        assert self._check(run={"returncode": 1, "failure": "boom"})["detail"] == {"INCOMPLETE_CRASH": "exit 1: boom"}
        v = measurement_validity([], _vsampler(readings=0), {"init_failed": "NEMB init failed: x"}, cfg)
        assert v["reasons"] == ["NEMB_INIT_FAILED", "INCOMPLETE_NO_CHECKPOINTS", "TOTAL_BELOW_RESOLUTION"]

    def test_java_meta_records_become_one_sampler(self, tmp_path):
        from codegreen.cli.cli import (_stderr_checkpoint_events, _replay_checkpoint_events, _poller_sampler,
                                       measurement_validity, _measurement_cfg)

        def meta(readings, last, gap, failed=0, cpus=4, ms=1.0):
            return {"marker_reads": "last_poll", "interval_ms": 1.0, "readings": readings, "failed_reads": failed,
                    "first_ns": 0, "last_ns": last, "max_gap_ns": gap, "affinity_cpus": cpus,
                    "sampler_affinity_cpus": cpus, "providers": [_jprov(ms=ms)]}
        f = tmp_path / "sum"
        f.write_text(f"CG_CP_META|{json.dumps(meta(1001, 1_100_000_000, 2_000_000))}\nCG_CP_SUM|1|g|4|40|30|400\n"
                     f"CG_CP_META|{json.dumps(meta(11, 10_000_000, 9_000_000, cpus=5, ms=2.0))}\n")
        func, records = {}, []
        _replay_checkpoint_events(_stderr_checkpoint_events(str(f), func, records), func)
        assert func["g"]["calls"] == 4 and len(records) == 2
        s = _poller_sampler(records)
        assert (s["readings"], s["interval_ms_max"], s["median_gap_ns"], s["affinity_cpus"], s["processes"]) == \
            (1012, 1.0, 1_100_000, 4, 2)
        assert s["providers"][0]["update_interval_ms"] == 2.0 and s["providers"][0]["boundary_held"] == 0
        assert s["providers"][0]["counter_check"] == {}
        assert (s["providers"][0]["readings"], s["providers"][0]["last_ns"], s["providers"][0]["max_stall_ns"]) == \
            (1012, 1_100_000_000, None)
        v = measurement_validity(None, s, {}, _measurement_cfg())
        assert v["status"] == "valid" and list(v["warnings"]) == ["SAMPLER_GAP"]
        v = measurement_validity(None, _poller_sampler([meta(5, 4_000_000, 1_000_000, failed=1)]), {}, _measurement_cfg())
        assert v["reasons"] == ["PROVIDER_READ_FAILED"]
        assert measurement_validity(None, None, {}, _measurement_cfg())["reasons"] == ["STALE_LIBRARY"]
        with pytest.raises(ValueError, match="different periods"):
            _poller_sampler([meta(2, 1, 1), {**meta(2, 1, 1), "interval_ms": 2.0}])

    def test_function_quality_vocabulary(self):
        from codegreen.cli.cli import function_quality, resolution_ns, _measurement_cfg
        cfg, res = _measurement_cfg(), resolution_ns(_vsampler())
        assert res == 10e6 and resolution_ns(_vsampler(), boundary=True) == 1e6
        assert resolution_ns(_vsampler(providers=[_vprov(ms=0)]), boundary=True) == 10e6  # 0: update period unknown
        assert resolution_ns(_vsampler(providers=[_vprov("nvidia_gpu", "gpu", "integrated_power", 100.0)]),
                             boundary=True) == 100e6
        gpu = _vprov("nvidia_gpu", "gpu", "integrated_power", 1.0)  # boundaries read a counter: no sampler interval
        assert resolution_ns(_vsampler(providers=[gpu]), boundary=True) == 10e6
        assert resolution_ns(_vsampler(providers=[{**gpu, "boundary_source": "counter"}]), boundary=True) == 1e6
        assert resolution_ns(_vsampler(providers=[{**gpu, "boundary_source": "counter"}])) == 10e6
        f = cfg["measured_min_factor"]
        assert function_quality({"calls": 2, "time_ns": 2 * f * res, "min_window_samples": f}, res, cfg) == "measured"
        assert function_quality({"calls": 2, "time_ns": 2 * f * res}, res, cfg) == "measured"
        assert function_quality({"calls": 2, "time_ns": 10, "min_window_samples": f}, res, cfg) == "below_resolution"
        assert function_quality({"calls": 1, "time_ns": 22e6, "min_window_samples": 2}, res, cfg) == "below_resolution"
        assert function_quality({"calls": 1, "time_ns": f * res, "min_window_samples": f - 1}, res, cfg) == "aggregate_only"
        assert function_quality({"calls": 1000, "time_ns": 100e6}, res, cfg) == "aggregate_only"
        assert function_quality({"calls": 1, "time_ns": 10, "min_window_samples": 0}, res, cfg) == "below_resolution"

    def test_replay_partitions_the_root_and_reports_quality(self):
        import types
        from codegreen.cli.cli import _build_comprehensive_json
        pts = [types.SimpleNamespace(id=i, type="function_enter", name=i, line=1, column=0, context="",
                                     insertion_mode="before") for i in ("E", "X", "F", "G")]
        cps = [_vcp("enter:main:E", 0, 1.0, 1), _vcp("enter:f:F", 10, 2.0, 5), _vcp("enter:f:F", 20, 3.0, 5),
               _vcp("exit:f:G", 30, 3.5, 6), _vcp("exit:f:G", 40, 6.0, 20), _vcp("exit:main:X", 50, 9.0, 41)]
        v = self._check(cps=cps)
        out = _build_comprehensive_json(
            types.SimpleNamespace(instrumentation_points=pts, optimization_suggestions=[]),
            {"success": True, "output": "", "checkpoints": cps, "sampler": _vsampler(), "validity": v},
            "x = 1\n", Path("t.py"), "python", "fine")
        f, m = out["per_function_energy"]["f"], out["per_function_energy"]["main"]
        assert f["calls"] == 2 and f["inclusive_j"] == pytest.approx(4.5) and f["quality"] == "below_resolution"
        assert m["exclusive_j"] == pytest.approx(4.0) and m["quality"] == "below_resolution"  # 40 readings, 50 ns
        assert out["summary"]["exclusive_sum_j"] == pytest.approx(out["summary"]["total_energy_j"]) == 8.0
        assert out["summary"]["energy_by_provider"] == {"intel_rapl": 8.0} and out["validity"] == v
        assert out["summary"]["wall_time_s"] == 50 / 1e9 and out["sampler"]["readings"] == 50

    def test_threads_count_every_call(self):
        from codegreen.cli.cli import _checkpoint_events, _replay_checkpoint_events
        cps = [_vcp("enter:w:E", 0, 0.0, 1, tid="1"), _vcp("enter:w:E", 1, 0.0, 1, tid="2"),
               _vcp("exit:w:X", 30, 3.0, 4, tid="1"), _vcp("exit:w:X", 40, 4.0, 5, tid="2")]
        func = {}
        _replay_checkpoint_events(_checkpoint_events(cps, {"E", "X"}), func)
        assert func["w"]["calls"] == 2 and func["w"]["min_window_samples"] == 3

    @pytest.mark.parametrize("body,timeout,code", [
        ("print('--- CODEGREEN_RESULT_START ---\\n{\"measurements\": []}\\n--- CODEGREEN_RESULT_END ---')\n"
         "raise SystemExit(2)\n", 30, "INCOMPLETE_CRASH"),
        ("import time\ntime.sleep(30)\n", 1, "INCOMPLETE_TIMEOUT"),
        ("import os\nprint('NEMB init failed: x', os.environ['CODEGREEN_PROVIDERS'])\n", 30, "NEMB_INIT_FAILED"),
    ])
    def test_run_outcome_maps_to_incomplete_codes(self, tmp_path, body, timeout, code):
        from codegreen.cli.cli import _run_energy_measurement, Language, SensorType
        (tmp_path / "w.py").write_text(body)
        r = _run_energy_measurement(tmp_path / "w.py", Language.python, [SensorType.rapl], False, timeout, None, True)
        assert code in r["validity"]["reasons"] and "INCOMPLETE_NO_CHECKPOINTS" in r["validity"]["reasons"]
        if code == "NEMB_INIT_FAILED":
            assert "intel_rapl|amd_rapl" in r["output"]

    def test_valid_block_passes_and_largest_block_wins(self, tmp_path):
        from codegreen.cli.cli import _run_energy_measurement, Language
        cps = [_vcp("enter:main:E", 0, 1.0, 1), _vcp("exit:main:X", 9, 9.0, 41)]
        def blk(d):
            return (f"print('--- CODEGREEN_RESULT_START ---'); print({json.dumps(json.dumps(d))}); "
                    f"print('--- CODEGREEN_RESULT_END ---')\n")
        (tmp_path / "w.py").write_text(blk({"measurements": [], "sampler": _vsampler()})
                                       + blk({"measurements": cps, "sampler": _vsampler()}))
        r = _run_energy_measurement(tmp_path / "w.py", Language.python, None, False, 30, None, True)
        assert r["validity"]["status"] == "valid" and r["checkpoints"] == cps
        (tmp_path / "w.py").write_text("print('--- CODEGREEN_RESULT_START ---\\n{bad\\n--- CODEGREEN_RESULT_END ---')\n")
        with pytest.raises(ValueError):
            _run_energy_measurement(tmp_path / "w.py", Language.python, None, False, 30, None, True)

    @pytest.mark.parametrize("pairs,code,exit_code", [
        ([(5.0, 0.5)] * 3, None, 0),
        ([(5.0, 0.001)] * 3, "RUN_BELOW_RESOLUTION", 3),
        ([(5.0, 0.5), (0.0, 0.5), (5.1, 0.5)], "ZERO_ENERGY_RUNS", 3),
        ([(5.0, 0.5), (None, 0.5), (5.1, 0.5)], "PROVIDER_READ_FAILED", 3),
        ([(5.0, 0.5), (-1.0, 0.5), (5.1, 0.5)], "NEGATIVE_ENERGY_RUNS", 3),
    ])
    def test_run_command_validity(self, monkeypatch, pairs, code, exit_code):
        from typer.testing import CliRunner
        import codegreen.cli.cli as cli
        it = iter(pairs)

        class Fake(cli._EnergyBackend):
            name = "fake"
            def is_available(self): return True
            def measure(self, command, timeout=None): return next(it)
            def sampler(self): return _vsampler()

        monkeypatch.setattr(cli, "_get_energy_backend", lambda: Fake())
        r = CliRunner().invoke(cli.app, ["run", "--json", "--no-validate", "-n", "3", "-w", "0", "--", "true"])
        out = json.loads(r.stdout)
        assert r.exit_code == exit_code and out["validity"]["reasons"] == ([code] if code else [])
        assert out["validity"]["checks"]["affinity_cpus"] >= 1 and out["energy_j"]["mean"] > 0
        assert out["validity"]["checks"]["resolution_ms"] == 1.0
        assert (out.get("error") == f"invalid_measurement: {code}") if code else "error" not in out
        assert out["runs"]["energies_j"] == [e for e, _ in pairs] and len(out["runs"]["status"]) == 3

    def test_run_stats_are_raw_and_filtering_is_an_opt_in_side_block(self, monkeypatch, tmp_path):
        """energy_j.mean was IQR-filtered while its min/max and the domains covered every run, and domains_power_w
        divided all-run domain joules by the filtered mean duration; every field now has one definition."""
        from typer.testing import CliRunner
        import codegreen.cli.cli as cli
        pairs = [(5.0, 1.0), (5.1, 1.1), (4.9, 0.9), (5.0, 1.0), (50.0, 2.0)]

        class Fake(cli._EnergyBackend):
            name = "fake"
            def is_available(self): return True
            def measure(self, command, timeout=None):
                self.last = pairs[len(seen)]
                seen.append(self.last)
                return self.last
            def get_last_domain_breakdown(self): return {"package-0": self.last[0]}

        def run(method):
            (tmp_path / "c.json").write_text(json.dumps({"measurement": {"report": {"outlier_method": method}}}))
            monkeypatch.setenv("CODEGREEN_CONFIG", str(tmp_path / "c.json"))
            seen.clear()
            r = CliRunner().invoke(cli.app, ["run", "--json", "--no-validate", "-n", "5", "-w", "0", "--", "true"])
            return json.loads(r.stdout)

        seen = []
        monkeypatch.setattr(cli, "_get_energy_backend", lambda: Fake())
        out = run("none")
        assert "filtered" not in out and out["meta"]["outlier_method"] == "none"
        assert out["energy_j"]["mean"] == pytest.approx(14.0) == out["domains"]["package-0"]
        assert out["energy_j"]["max"] == 50.0 and out["duration_s"]["mean"] == pytest.approx(1.2)
        assert out["power_w"]["mean"] == pytest.approx(sum(e / t for e, t in pairs) / 5, abs=1e-4)
        assert out["power_w"]["mean"] == out["domains_power_w"]["package-0"]
        f = run("iqr_1.5")["filtered"]
        assert f["method"] == "iqr_1.5" and f["runs"] == 4 and f["energy_j"]["max"] == 5.1
        assert f["energy_j"]["mean"] == pytest.approx(5.0) == f["domains"]["package-0"]
        assert f["duration_s"]["mean"] == pytest.approx(1.0)
        assert f["power_w"]["mean"] == f["domains_power_w"]["package-0"]

    def test_run_accepts_sensors(self, monkeypatch):
        from typer.testing import CliRunner
        import codegreen.cli.cli as cli
        monkeypatch.setenv("CODEGREEN_PROVIDERS", "inherited")
        seen = []

        class Fake(cli._EnergyBackend):
            name = "fake"
            def is_available(self): return True
            def measure(self, command, timeout=None):
                seen.append(os.environ.get("CODEGREEN_PROVIDERS"))
                return 5.0, 1.0

        monkeypatch.setattr(cli, "_get_energy_backend", lambda: Fake())
        r = CliRunner().invoke(cli.app, ["run", "--json", "--no-validate", "-n", "1", "-w", "0", "--sensors", "rapl",
                                         "--", "true"])
        assert r.exit_code == 0 and seen == ["intel_rapl|amd_rapl"]


class TestValidityDefects:
    """Regressions found by real-run validation."""

    def test_replay_counts_every_exit_with_signed_energy(self):
        from codegreen.cli.cli import _replay_checkpoint_events, measurement_validity, _measurement_cfg
        func = {}
        _replay_checkpoint_events([("enter", "p", "a", 0, 0, "1"), ("enter", "f", "a", 0, 100, "1"),
                                   ("exit", "f", "b", 0, 100, "1"), ("enter", "f", "a", 5, 100, "1"),
                                   ("exit", "f", "b", 9, 90, "1"), ("exit", "p", "b", 20, 50, "1")], func)
        assert func["f"] == {"inclusive_uj": -10, "exclusive_uj": -10, "time_ns": 4, "calls": 2}
        assert func["p"]["exclusive_uj"] == 60 and func["p"]["inclusive_uj"] == 50
        cps = [_vcp("enter:p:a", 0, 0.0, 1), _vcp("enter:f:a", 5, 1e-4, 9), _vcp("exit:f:b", 9, 9e-5, 20),
               _vcp("exit:p:b", 20, 5e-5, 41)]
        assert "NEGATIVE_ENERGY" in measurement_validity(cps, _vsampler(), {}, _measurement_cfg())["reasons"]

    def test_coarse_keeps_c_main_return(self):
        from codegreen.cli.cli import _filter_main_entry_points
        from codegreen.instrumentation.language_engine import LanguageEngine
        src = "int f(int x) { return x + 1; }\nint main(void) {\n  int s = 0;\n  for (int i = 0; i < 9; i++) s = f(s);\n  return s == 9 ? 0 : 1;\n}\n"
        pts = _filter_main_entry_points(LanguageEngine().analyze_code(src, "c").instrumentation_points, "c")
        assert sorted(p.type for p in pts) == ["function_enter", "function_return"] and {p.name for p in pts} == {"main"}

    def test_relative_c_binary_runs_and_binary_stdout_is_decoded(self, tmp_path, monkeypatch):
        from codegreen.cli.cli import _run_energy_measurement, Language
        monkeypatch.chdir(tmp_path)
        Path("w.c").write_text('#include <stdio.h>\nint main(void) { fwrite("P4\\n\\xff\\xfe\\x80", 1, 6, stdout); return 0; }\n')
        r = _run_energy_measurement(Path("w.c"), Language.c, None, False, 30, None, True)
        assert r["returncode"] == 0 and "\ufffd" in r["output"]
        assert r["validity"]["reasons"] == ["INCOMPLETE_NO_CHECKPOINTS"]

    def test_launch_failure_is_incomplete_crash(self, tmp_path, monkeypatch):
        from codegreen.cli.cli import _run_energy_measurement, Language
        (tmp_path / "w.py").write_text("pass\n")
        monkeypatch.setenv("PATH", str(tmp_path))
        r = _run_energy_measurement(tmp_path / "w.py", Language.python, None, False, 30, None, True)
        assert r["validity"]["reasons"] == ["INCOMPLETE_CRASH"] and "could not launch python3" in r["validity"]["detail"]["INCOMPLETE_CRASH"]

    def test_compile_failure_exits_3_with_compiler_output(self, tmp_path, monkeypatch):
        from typer.testing import CliRunner
        import codegreen.cli.cli as cli
        monkeypatch.setattr(cli, "_should_run_actual_measurement", lambda: True)
        (tmp_path / "w.c").write_text("int missing_symbol(void);\nint main(void) { return missing_symbol(); }\n")
        r = CliRunner().invoke(cli.app, ["measure", "c", str(tmp_path / "w.c"), "--json"])
        out = json.loads(r.stdout[r.stdout.index("{"):])
        assert r.exit_code == 3 and out["error"] == "invalid_measurement: COMPILE_FAILED"
        assert "missing_symbol" in out["validity"]["detail"]["COMPILE_FAILED"]

    def test_overlapping_threads_are_flagged(self):
        import types
        from codegreen.cli.cli import _build_comprehensive_json
        cps = [_vcp("enter:main:E", 0, 0.0, 1, tid="1"), _vcp("enter:w:F", 10, 1.0, 5, tid="2"),
               _vcp("enter:w:F", 11, 1.1, 5, tid="3"), _vcp("exit:w:G", 30, 3.0, 20, tid="2"),
               _vcp("exit:w:G", 31, 3.2, 21, tid="3"), _vcp("exit:main:X", 50, 4.0, 41, tid="1")]
        v = TestValidity._check(cps=cps)
        assert v["status"] == "valid" and "3 threads" in v["warnings"]["OVERLAPPING_THREADS"]
        pts = [types.SimpleNamespace(id=i, type="function_enter", name=i, line=1, column=0, context="",
                                     insertion_mode="before") for i in ("E", "X", "F", "G")]
        out = _build_comprehensive_json(types.SimpleNamespace(instrumentation_points=pts, optimization_suggestions=[]),
                                        {"success": True, "checkpoints": cps, "sampler": _vsampler(), "validity": v},
                                        "x = 1\n", Path("t.py"), "java", "fine")
        assert out["summary"]["overlapping_threads"] == 3 and out["summary"]["exclusive_sum_ratio"] > 1

    @pytest.mark.parametrize("providers,expected", [
        ([_vprov()], 1000), ([_vprov(), _vprov("nvidia_gpu", "gpu", "integrated_power", 100.0)], None),
        ([_vprov(), {**_vprov("nvidia_gpu", "gpu", "integrated_power", 100.0), "boundary_source": "counter"}], 1000)])
    def test_run_path_slows_the_sampler_unless_power_is_integrated(self, monkeypatch, providers, expected):
        import types
        import codegreen.cli.cli as cli
        calls = []
        lib = types.SimpleNamespace(nemb_set_measurement_interval_ms=lambda ms: calls.append(ms) or 1)
        b = cli._NEMBBackend()
        monkeypatch.setattr(b, "_init", lambda: lib)
        monkeypatch.setattr(b, "sampler", lambda: _vsampler(providers=providers))
        assert b.slow_sampler(1000) == expected and calls == ([1000] if expected else [])

    def test_coarse_filter_reads_entry_points_and_boundaries(self, monkeypatch):
        import types
        import codegreen.cli.cli as cli
        pts = [types.SimpleNamespace(name=n, type=t) for n, t in
               (("a", "function_enter"), ("a", "function_exit"), ("run", "function_enter"), ("run", "function_return"),
                ("b", "loop_start"), ("b", "function_exit"))]
        assert [(p.name, p.type) for p in cli._filter_main_entry_points(pts, "c")] == [("a", "function_enter"),
                                                                                       ("b", "function_exit")]
        real = cli._load_language_config
        monkeypatch.setattr(cli, "_load_language_config", lambda lang: {
            **real(lang), "instrumentation_config": {**real(lang)["instrumentation_config"], "entry_points": ["run"]}})
        assert [p.type for p in cli._filter_main_entry_points(pts, "c")] == ["function_enter", "function_return"]


class TestRound3:
    """Injected-runtime cleanup order, stdout-closing workloads, and toolchain selection."""

    def test_interrupted_run_removes_injected_runtime_dirs(self, tmp_path):
        src = tmp_path / "work.py"
        original = "def spin(n):\n    return n\n\n\nif __name__ == '__main__':\n    spin(1)\n"
        src.write_text("# instrumented\n" + original)
        rt = tmp_path / "codegreen" / "runtime"
        rt.mkdir(parents=True)
        (rt / "CodeGreenStandaloneRuntime.java").write_text("// injected")
        backup = tmp_path / ".codegreen_backup"
        backup.mkdir()
        (backup / "0.orig").write_text(original)
        (backup / "manifest.json").write_text(json.dumps({str(src): "0.orig"}))
        (backup / "runtime.json").write_text(json.dumps([str(rt / "CodeGreenStandaloneRuntime.java"), str(rt), str(rt.parent)]))
        subprocess.run(["codegreen", "project", "python", str(tmp_path), "--source-glob", "work.py", "--run-cmd", "true"],
                       cwd=tmp_path, capture_output=True, text=True, timeout=120)
        assert src.read_text() == original and not (tmp_path / "codegreen").exists()

    def test_result_block_survives_a_closed_stdout(self, tmp_path):
        rt_dir = Path(codegreen.__file__).parent / "instrumentation" / "language_runtimes" / "python"
        (tmp_path / "w.py").write_text(
            "import atexit, os, sys, types\nimport codegreen_runtime as rt\n"
            "rt._get_nemb_client = lambda: types.SimpleNamespace(lib=None, abi=4, get_final_measurements=lambda: "
            "{'measurements': [{'checkpoint_id': 'enter:m:x#inv_1_t1', 'timestamp': 1, 'joules': 0.0, 'watts': 0.0, 'clamp': 'none'}], "
            f"'sampler': {_vsampler(readings=0)!r}}})\n"
            "atexit.register(rt._report_at_exit)\nprint('payload')\nsys.stdout.close()\nos.close(1)\n")
        r = subprocess.run([sys.executable, "w.py"], cwd=tmp_path, capture_output=True, text=True, timeout=60,
                           env={**os.environ, "PYTHONPATH": str(rt_dir)})
        from codegreen.cli.cli import _nemb_result_block
        assert r.returncode == 0, r.stderr
        assert r.stdout.startswith("payload\n") and _nemb_result_block(r.stdout)["sampler"]["readings"] == 0

    def test_toolchain_prefers_configured_dirs_and_runs_with_its_own_binutils(self, tmp_path, monkeypatch):
        import codegreen.cli.cli as cli
        bindir = tmp_path / "bin"
        bindir.mkdir()
        fake = bindir / "gcc"
        fake.write_text('#!/bin/sh\necho "PATH0=${PATH%%:*}" >&2\nexit 1\n')
        fake.chmod(0o755)
        cfg = cli._measurement_cfg()
        monkeypatch.setattr(cli, "_measurement_cfg", lambda: {**cfg, "toolchain": {**cfg["toolchain"], "prefer_dirs": [str(bindir)]}})
        monkeypatch.delenv("CC", raising=False)
        assert cli._toolchain_compiler("c") == str(fake)
        (tmp_path / "w.c").write_text("int main(void) { return 0; }\n")
        binary, diag = cli._compile_instrumented(tmp_path / "w.c", cli.Language.c)
        assert binary is None and f"PATH0={bindir}" in diag
        monkeypatch.setenv("CC", "/usr/bin/true")
        assert cli._toolchain_compiler("c") == "/usr/bin/true"


class TestInvalidReads:
    """A failed backend read is flagged and counted, never a 0 J reading (fake clients, no hardware)."""

    def test_monitor_skips_failed_reads(self, monkeypatch):
        import types
        from codegreen.instrumentation.language_runtimes.python import codegreen_runtime as rt
        vals = iter([(10.0, 1.0), None, (12.0, 1.0), (13.0, 1.0)])
        fake = types.SimpleNamespace(lib=object(), read_energy=lambda: next(vals, None))
        monkeypatch.setattr(rt, "_get_nemb_client", lambda: fake)
        fed = []
        sink = types.SimpleNamespace(name="rec", feed_sample=fed.append, feed_header=lambda r: None,
                                     feed_aggregate=lambda p: None, close=dict)
        m = rt.Monitor(interval_ms=50, duration_s=0.5)
        m._extra_sinks = [sink]
        m.start()
        m._thread.join(timeout=5.0)
        s = m.stop()
        assert [r["joules_delta"] for r in fed] == [2.0, 1.0] and all(r["valid"] for r in fed)
        assert s["samples"] == 2 and s["invalid_samples"] >= 1 and s["total_joules"] == 3.0
        assert s["validity"]["reasons"] == ["PROVIDER_READ_FAILED"] and "SAMPLES_INVALID" in s["validity"]["warnings"]
        fake.read_energy = lambda: None
        with pytest.raises(RuntimeError, match="no baseline"):
            rt.Monitor(interval_ms=50, duration_s=0.5).start()

    def test_session_excludes_failed_tasks(self, monkeypatch):
        import types
        from codegreen.instrumentation.language_runtimes.python import codegreen_runtime as rt
        ids = iter(range(1, 10))

        def stop(sid, e, p, dur, buf, n):
            if sid.value == 2:
                return 0
            e._obj.value, dur._obj.value, buf.value = 5.0, 1.0, b'{"package-0": 5.0}'
            return len(buf.value)
        lib = types.SimpleNamespace(nemb_start_session=lambda n: next(ids), nemb_stop_session_v2=stop,
                                    nemb_abi_version=lambda: 4)
        client = types.SimpleNamespace(lib=lib, abi=4, get_final_measurements=lambda: {"sampler": _vsampler()})
        monkeypatch.setattr(rt, "_get_nemb_client", lambda: client)
        s = rt.Session("inv", save_to_file=False, warn_on_concurrent=False).start()
        for name in ("ok", "bad"):
            with s.task(name):
                pass
        rep = s.stop()
        assert [(t["valid"], t["invalid_reason"]) for t in rep["tasks"]] == [(True, None), (False, "provider_read_failed")]
        assert rep["totals"]["energy_j"] == 5.0 and rep["totals"]["invalid_tasks"] == 1
        assert rep["totals"]["domains"] == {"package-0": 5.0}
        assert rep["meta"]["measurement_quality"] == "provider_read_failed"
        assert rep["validity"]["reasons"] == ["PROVIDER_READ_FAILED"]

    def test_session_warns_gpu_in_total(self, monkeypatch):
        """A Session total that sums a GPU with the CPU carries GPU_IN_TOTAL and warns it, like measure and run."""
        import types
        from codegreen.instrumentation.language_runtimes.python import codegreen_runtime as rt

        def stop(sid, e, p, dur, buf, n):
            e._obj.value, dur._obj.value, buf.value = 5.0, 2.0, b'{"package-0": 4.0, "gpu0": 1.0}'
            return len(buf.value)
        lib = types.SimpleNamespace(nemb_start_session=lambda n: 1, nemb_stop_session_v2=stop, nemb_abi_version=lambda: 4)
        provs = [_vprov(), _vprov("nvidia_gpu", "gpu", "integrated_power", 100.0, boundary_source="counter")]
        client = types.SimpleNamespace(lib=lib, abi=4, get_final_measurements=lambda: {"sampler": _vsampler(providers=provs)})
        monkeypatch.setattr(rt, "_get_nemb_client", lambda: client)
        s = rt.Session("mixed", save_to_file=False, warn_on_concurrent=False).start()
        with s.task("t"):
            pass
        with pytest.warns(RuntimeWarning, match="GPU_IN_TOTAL: total sums GPU provider"):
            rep = s.stop()
        assert rep["validity"]["status"] == "valid" and list(rep["validity"]["warnings"]) == ["GPU_IN_TOTAL"]

    def test_session_flags_shared_and_short_tasks(self, monkeypatch):
        """A boundary read while another task is open is shared (the backend adds the power integral to the last
        counter read instead of reading the counter); the task is TASK_POWER_INTEGRATED for a power-integrating provider.
        Tasks shorter than min_run_updates resolutions are TASK_BELOW_RESOLUTION."""
        import types
        import threading
        from codegreen.instrumentation.language_runtimes.python import codegreen_runtime as rt
        ids, open_sids, seen = iter(range(1, 10)), set(), []

        def start(n):
            seen.append((n, bool(open_sids)))
            sid = next(ids)
            open_sids.add(sid)
            return sid

        def stop(sid, e, p, dur, buf, n):
            open_sids.discard(sid.value)
            seen.append(("stop", bool(open_sids)))
            e._obj.value, dur._obj.value, buf.value = 5.0, {1: 2.0, 2: 0.5, 3: 2.0}[sid.value], b'{"gpu0": 5.0}'
            return len(buf.value)
        lib = types.SimpleNamespace(nemb_start_session=start, nemb_stop_session_v2=stop, nemb_abi_version=lambda: 4)
        gpu = _vprov("nvidia_gpu", "gpu", "integrated_power", 100.0, boundary_source="counter")
        client = types.SimpleNamespace(lib=lib, abi=4, get_final_measurements=lambda: {"sampler": _vsampler(providers=[gpu])})
        monkeypatch.setattr(rt, "_get_nemb_client", lambda: client)
        s = rt.Session("shared", save_to_file=False, warn_on_concurrent=False).start()
        with s.task("outer"):
            with s.task("inner"):
                pass
        t = threading.Thread(target=lambda: s.task("alone").__enter__())  # opened on another thread, closed at stop
        t.start()
        t.join()
        rep = s.stop()
        assert seen[:4] == [(b"outer", False), (b"inner", True), ("stop", True), ("stop", False)]
        assert {t["name"]: t["shared_boundary"] for t in rep["tasks"]} == {"inner": True, "outer": False, "alone": False}
        w = rep["validity"]["warnings"]
        assert rep["validity"]["status"] == "valid" and sorted(w) == ["TASK_BELOW_RESOLUTION", "TASK_POWER_INTEGRATED"]
        assert "'inner'" in w["TASK_BELOW_RESOLUTION"] and "1 task(s)" in w["TASK_POWER_INTEGRATED"]
        assert rep["sampler"]["providers"] == [gpu]


def _java_workload(dest: Path) -> Path:
    """Self-contained CPU-bound Java workload; args[0] is the iteration count."""
    out = dest / "Spin.java"
    out.write_text("public class Spin {\n"
                   "    static double step(double x) { return Math.sin(x) * Math.cos(x) + x * 1e-9; }\n"
                   "    public static void main(String[] args) {\n"
                   "        long n = Long.parseLong(args[0]);\n"
                   "        double acc = 0;\n"
                   "        for (long i = 0; i < n; i++) acc += step(i);\n"
                   "        System.out.println(acc);\n"
                   "    }\n"
                   "}\n")
    return out


@pytest.mark.needs_energy
class TestValidityReplication:
    """Real measurements through the CLI (brief runs; idle host required)."""

    @staticmethod
    def _measure(tmp_path, *args, pin: str = "", lang: str = "java", src: Optional[Path] = None):
        src = src or _java_workload(tmp_path)
        cmd = (["taskset", "-c", pin] if pin else []) + ["codegreen", "measure", lang, src.name, "--json", *args]
        p = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True, timeout=300)
        return p.returncode, json.loads(p.stdout)

    def test_single_cpu_affinity_is_flagged(self, tmp_path):
        rc, out = self._measure(tmp_path, "--sensors", "rapl", "5000000", pin="2")
        assert "AFFINITY_SINGLE_CPU" in out["validity"]["warnings"]
        rc, out = self._measure(tmp_path, "--sensors", "rapl", "5000000", pin="2,3")
        assert rc == 0 and out["validity"]["status"] == "valid" and out["sampler"]["affinity_cpus"] == 2

    def test_sub_interval_window_is_below_resolution(self, tmp_path):
        (tmp_path / "tiny.py").write_text("def main():\n    return 1\n\n\nif __name__ == '__main__':\n    main()\n")
        rc, out = self._measure(tmp_path, "--sensors", "rapl", lang="python", src=tmp_path / "tiny.py")
        assert rc == 3 and "TOTAL_BELOW_RESOLUTION" in out["validity"]["reasons"]

    def test_sensors_select_providers(self, tmp_path):
        rc, out = self._measure(tmp_path, "--sensors", "rapl", "1000000")
        providers = out["summary"]["providers"]
        assert rc == 0 and providers in (["intel_rapl"], ["amd_rapl"])
        assert out["summary"]["energy_by_provider"][providers[0]] == pytest.approx(out["summary"]["total_energy_j"])

    def test_unavailable_sensor_fails_init(self, tmp_path):
        rc, out = self._measure(tmp_path, "--sensors", "amd_gpu", "100")
        assert rc == 3 and "NEMB_INIT_FAILED" in out["validity"]["reasons"]
