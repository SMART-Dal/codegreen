"""
CodeGreen Runtime Module for Python
Provides runtime energy measurement functionality for instrumented Python code.
Designed for minimal overhead and high accuracy energy measurements using the NEMB C++ backend.
"""

import time
import threading
import json
import os
import sys
import socket
import uuid
import platform as _platform
import ctypes
from datetime import datetime, timezone
from ctypes import c_double, c_char_p, c_uint64, c_int, byref
from typing import Dict, List, Optional, NamedTuple, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path


def _iso_utc_now() -> str:
    """RFC 3339 UTC timestamp, microsecond precision, +00:00 offset.

    Contract documented in config.measurement.report.iso_timestamp_format.
    Any language runtime must emit timestamps in this format for cross-runtime
    log correlation. Do not switch to "Z" suffix — older Python parsers reject it.
    """
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _iso_local_now() -> str:
    """Same instant as `_iso_utc_now()` rendered in the host's local timezone
    with explicit offset, e.g. "2026-05-10T11:16:56.209074-07:00". Display-only
    companion to the canonical UTC field; never use for joins/sorts."""
    return datetime.now().astimezone().isoformat(timespec="microseconds")


def _host_timezone_label() -> str:
    """Best-effort local timezone label, e.g. 'PDT' or '+05:30'."""
    tz = datetime.now().astimezone().tzinfo
    return tz.tzname(datetime.now()) if tz else "unknown"


def _runtime_version() -> str:
    try:
        from importlib.metadata import version as _v
        return _v("codegreen")
    except Exception:
        return "unknown"


def _report_config() -> Dict:
    """Single source of truth for report/quality thresholds. All thresholds
    that were previously magic numbers (CV%, drop ratio, run-id length) live
    here. Loaded from bundled config.json with defensive defaults."""
    cfg_path = Path(__file__).resolve().parents[3] / "config.json"
    defaults = {
        "schema_version": "1",
        "iso_timestamp_format": "rfc3339_utc",
        "run_id_bytes": 6,
        "outlier_method": "iqr_1.5",
        "noise_warning": {
            "within_task_power_cv_pct_threshold": 10.0,
            "sampling_drop_ratio_threshold": 0.20,
            "quality_excellent_below_cv_pct": 2.0,
            "quality_good_below_cv_pct": 5.0,
            "quality_moderate_below_cv_pct": 10.0,
        },
    }
    try:
        with open(cfg_path) as f:
            d = json.load(f)
        cfg = d["measurement"]["report"]
        out = dict(defaults); out.update(cfg)
        nw = dict(defaults["noise_warning"]); nw.update(cfg.get("noise_warning", {}))
        out["noise_warning"] = nw
        return out
    except Exception:
        return defaults


# --- HW/OS adapter layer (shared interface; new platforms slot in by adding
# a branch to the resolver, not by editing callers) ---------------------------

def _cpu_model_label() -> str:
    """Best-effort CPU brand string. Adapter resolver picks the per-OS source.
    No-op fallback returns platform.processor()."""
    try:
        if sys.platform.startswith("linux"):
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        return line.split(":", 1)[1].strip()
        elif sys.platform == "darwin":
            import subprocess
            out = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                                 capture_output=True, text=True, timeout=2)
            if out.returncode == 0:
                return out.stdout.strip()
    except Exception:
        pass
    return _platform.processor() or "unknown"


def _codegreen_env_snapshot() -> Dict[str, str]:
    """All CODEGREEN_* env vars at meta-build time. Same shape across langs."""
    return {k: v for k, v in os.environ.items() if k.startswith("CODEGREEN_")}


# Domain-name patterns are RAPL/NVML conventions, NOT hardcoded magic. The
# matchers below are open for extension — adding a new hardware family means
# adding a new tuple in _DOMAIN_PATTERNS, not editing _domain_topology.
_DOMAIN_PATTERNS: List[Tuple[str, str, Tuple[str, ...]]] = [
    # (kind, top-level prefix(es), nested children)
    ("cpu_package", "package|pkg", ("pp0", "pp1", "core", "uncore")),
    ("dram",        "dram",        ()),
    ("gpu",         "gpu",         ()),
    ("psys",        "psys",        ("package", "pkg", "dram")),
]


def _domain_topology(domain_keys) -> Dict[str, Dict]:
    """Machine-readable nesting structure built from observed domain names.
    Reports only what was measured. Driven by _DOMAIN_PATTERNS so new hardware
    is added by appending a pattern, not by changing this function."""
    topo: Dict[str, Dict] = {}
    keys = [str(k) for k in domain_keys]
    nested_set = set()
    for kind, prefix, nested in _DOMAIN_PATTERNS:
        prefixes = tuple(p.lower() for p in prefix.split("|"))
        tops = [k for k in keys if k.lower().startswith(prefixes)]
        for t in tops:
            children = [n for n in keys if n.lower() in nested]
            topo[t] = {"top_level": True, "kind": kind, "includes": children}
            nested_set.update(children)
    for k in keys:
        if k in topo: continue
        topo[k] = {
            "top_level": k not in nested_set,
            "kind": "nested" if k in nested_set else "independent",
            "includes": [],
        }
    return topo


def build_meta_block(
    *,
    run_id: str,
    started_at_iso: str,
    ended_at_iso: str,
    duration_total_s: float,
    hostname: str,
    session_name: Optional[str] = None,
    nemb_abi_version: int = 0,
    measurement_quality: str = "ok",
    domain_support: str = "none",
    domains: Optional[Dict[str, float]] = None,
    record_time_series: bool = False,
    started_at_local_iso: str = "",
    ended_at_local_iso: str = "",
    extras: Optional[Dict] = None,
) -> Dict:
    """Single canonical meta-block builder. Shared by Session._build_report()
    and CLI run_command (and any future language runtime). Adding a meta field
    means editing this function once, not every call site."""
    rcfg = _report_config()
    meta: Dict = {
        "schema_version": rcfg["schema_version"],
        "codegreen_version": _runtime_version(),
        "run_id": run_id,
        "started_at": started_at_iso,
        "ended_at": ended_at_iso,
        "duration_total_s": round(duration_total_s, 6),
        "hostname": hostname,
        "pid": _os.getpid(),
        "platform": sys.platform,
        "python_version": _platform.python_version(),
        "cpu_model": _cpu_model_label(),
        "kernel": _platform.platform(),
        "cwd": _os.getcwd(),
        "argv": list(_sys.argv),
        "codegreen_env": _codegreen_env_snapshot(),
        "measurement_quality": measurement_quality,
        "domain_support": domain_support,
        "outlier_method": rcfg["outlier_method"],
        "iso_timestamp_format": rcfg["iso_timestamp_format"],
        "started_at_local": started_at_local_iso or _iso_local_now(),
        "ended_at_local": ended_at_local_iso or _iso_local_now(),
        "host_timezone": _host_timezone_label(),
        "nemb_abi_version": nemb_abi_version,
        "domain_topology": _domain_topology(domains or {}),
        "timeseries": ({
            "enabled": True,
            "schema_version": "1",
            "sample_keys": ["t_ns", "energy_j", "power_w", "domains"],
            "t_ns_clock": "clock_monotonic",
            "inclusive_of_children": True,
        } if record_time_series else {"enabled": False}),
    }
    if session_name is not None:
        meta["session_name"] = session_name
    if extras:
        meta.update(extras)
    return meta


# --- C++ Backend Interface ---

def _find_nemb_library() -> Optional[str]:
    """Find the path to the shared NEMB library."""
    possible_names = ["libcodegreen-nemb.so", "libcodegreen-nemb.dylib", "codegreen-nemb.dll"]

    # Project root: /home/user/codegreen
    # This file: src/instrumentation/language_runtimes/python/codegreen_runtime.py
    # python -> language_runtimes -> instrumentation -> src -> codegreen (5 levels)
    project_root = Path(__file__).resolve().parent.parent.parent.parent.parent

    search_paths = [
        project_root / "lib",
        project_root / "build" / "lib",
        project_root / "codegreen" / "lib",
        Path("/usr/local/lib"),
        Path("/usr/lib"),
    ]
    if os.environ.get("CODEGREEN_LIB_PATH"):
        search_paths.insert(0, Path(os.environ["CODEGREEN_LIB_PATH"]))

    for path in search_paths:
        if not path.exists():
            continue
        for name in possible_names:
            lib_path = path / name
            if lib_path.exists():
                return str(lib_path)

    return None

class NEMBClient:
    """Interface to the Native Energy Measurement Backend (C++)"""

    def __init__(self):
        lib_path = _find_nemb_library()
        if not lib_path:
            self.lib = None
            return

        try:
            self.lib = ctypes.CDLL(lib_path)
            self.lib.nemb_initialize.argtypes = []
            self.lib.nemb_initialize.restype = c_int
            
            # Instantaneous reading API
            self.lib.nemb_read_current.argtypes = [ctypes.POINTER(c_double), ctypes.POINTER(c_double)]
            self.lib.nemb_read_current.restype = c_int
            
            # High-accuracy "Signal Generator" API
            self.lib.nemb_mark_checkpoint.argtypes = [c_char_p]
            self.lib.nemb_mark_checkpoint.restype = None
            
            self.lib.nemb_get_checkpoints_json.argtypes = [c_char_p, c_int]
            self.lib.nemb_get_checkpoints_json.restype = c_int

            # Session API (manual span-based measurement)
            self.lib.nemb_start_session.argtypes = [c_char_p]
            self.lib.nemb_start_session.restype = ctypes.c_uint64
            self.lib.nemb_stop_session_v2.argtypes = [
                ctypes.c_uint64,
                ctypes.POINTER(c_double), ctypes.POINTER(c_double), ctypes.POINTER(c_double),
                c_char_p, c_int,
            ]
            self.lib.nemb_stop_session_v2.restype = c_int
            self.lib.nemb_abi_version.argtypes = []
            self.lib.nemb_abi_version.restype = c_int
            if self.lib.nemb_abi_version() < 2:
                raise RuntimeError(
                    "libcodegreen-nemb.so ABI < 2; rebuild required for Session API"
                )

            # Time-series API (ABI 3+)
            self._has_timeseries = self.lib.nemb_abi_version() >= 3
            if self._has_timeseries:
                self.lib.nemb_get_time_series_json.argtypes = [
                    c_char_p, c_int, ctypes.c_uint64,
                ]
                self.lib.nemb_get_time_series_json.restype = c_int
                self.lib.nemb_set_buffer_size.argtypes = [c_int]
                self.lib.nemb_set_buffer_size.restype = c_int
                self.lib.nemb_set_measurement_interval_ms.argtypes = [c_int]
                self.lib.nemb_set_measurement_interval_ms.restype = c_int

            if not self.lib.nemb_initialize():
                self.lib = None
        except Exception:
            self.lib = None

    def mark_checkpoint(self, name: str):
        """Send a lightweight signal to the C++ backend"""
        if self.lib:
            self.lib.nemb_mark_checkpoint(name.encode('utf-8'))

    def get_final_measurements(self) -> List[Dict]:
        """Retrieve correlated time-series measurements from C++ backend"""
        if not self.lib:
            return []
        buf_size = 1024 * 1024
        buf = ctypes.create_string_buffer(buf_size)
        ret = self.lib.nemb_get_checkpoints_json(buf, buf_size)
        if ret < 0:
            # Buffer too small; C++ returns -(required_size)
            buf_size = (-ret) + 1
            buf = ctypes.create_string_buffer(buf_size)
            ret = self.lib.nemb_get_checkpoints_json(buf, buf_size)
        if ret > 0:
            try:
                data = json.loads(buf.value.decode('utf-8'))
                return data.get("checkpoints", [])
            except Exception:
                return []
        return []

    def read_energy(self) -> tuple:
        """Returns (joules, watts) - kept for compatibility"""
        if not self.lib:
            return (0.0, 0.0)

        energy = c_double()
        power = c_double()
        if self.lib.nemb_read_current(byref(energy), byref(power)):
            return (energy.value, power.value)
        return (0.0, 0.0)

# --- Runtime Implementation ---

_nemb_client: Optional[NEMBClient] = None
_client_lock = threading.Lock()
_is_child_process = False

def _get_nemb_client() -> NEMBClient:
    """Get or create global NEMB client"""
    global _nemb_client
    if _nemb_client is None:
        with _client_lock:
            if _nemb_client is None:
                _nemb_client = NEMBClient()
    return _nemb_client

def _after_fork_child():
    """Reset NEMB state in forked child to avoid corrupting parent measurements.

    Nullify the ctypes library handle so child processes don't call into
    the NEMB backend (which shares file descriptors with the parent).
    """
    global _nemb_client, _output_reported, _is_child_process
    if _nemb_client is not None and _nemb_client.lib is not None:
        _nemb_client.lib = None  # Detach without closing parent's FDs
    _nemb_client = None
    _output_reported = True
    _is_child_process = True

try:
    os.register_at_fork(after_in_child=_after_fork_child)
except AttributeError:
    pass

_output_reported = False
_throttle_interval_ns = int(os.environ.get("CODEGREEN_CHECKPOINT_THROTTLE_MS", "0")) * 1_000_000
_last_checkpoint_time: Dict[str, int] = {}

def _report_at_exit():
    """Report measurements to stdout in a way that CLI can parse.
    Emits both auto-instrumenter checkpoints and any tasks captured by an
    active Session that did not call .stop() explicitly. Both surfaces share
    the same `meta` block via build_meta_block() so consumers get one schema."""
    global _output_reported
    if _output_reported or _is_child_process:
        return
    _output_reported = True

    client = _get_nemb_client()
    measurements = client.get_final_measurements()

    sess = _active_session
    if sess is not None:
        try:
            sess.stop()
        except Exception:
            try:
                sess._auto_finalize()
            except Exception:
                pass

    if sess is not None and sess._finalized_report:
        payload = dict(sess._finalized_report)
        payload["measurements"] = measurements
    else:
        if not measurements:
            return
        try:
            import socket as _sk, uuid as _u
            host = _sk.gethostname()
        except Exception:
            host = "unknown"
        ended = _iso_utc_now()
        payload = {
            "meta": build_meta_block(
                run_id=_u.uuid4().hex[:12] if 'uuid' not in dir() else uuid.uuid4().hex[:12],
                started_at_iso=ended,
                ended_at_iso=ended,
                duration_total_s=0.0,
                hostname=host,
                session_name="auto_instrumentation",
                measurement_quality="checkpoints_only",
                domain_support="none",
                domains={},
                record_time_series=False,
            ),
            "measurements": measurements,
        }

    print("\n--- CODEGREEN_RESULT_START ---", flush=True)
    print(json.dumps(payload), flush=True)
    print("--- CODEGREEN_RESULT_END ---", flush=True)

import atexit
import signal as _signal
_atexit_registered = False

def _signal_flush_handler(signum, frame):
    """SIGTERM/SIGINT handler: persist whatever was captured, then re-raise the
    signal's default disposition. SIGKILL is unrecoverable by definition."""
    try:
        _report_at_exit()
    finally:
        _signal.signal(signum, _signal.SIG_DFL)
        try:
            _os.kill(_os.getpid(), signum)
        except Exception:
            pass

def _ensure_atexit():
    """Defer atexit registration until something is actually measured.
    Also installs SIGTERM/SIGINT handlers to flush partial reports on graceful
    termination. SIGKILL bypasses signal delivery so cannot be handled."""
    global _atexit_registered
    if not _atexit_registered:
        atexit.register(_report_at_exit)
        for sig_name in ("SIGTERM", "SIGINT"):
            sig = getattr(_signal, sig_name, None)
            if sig is None:
                continue
            try:
                prev = _signal.getsignal(sig)
                if prev in (_signal.SIG_DFL, None):
                    _signal.signal(sig, _signal_flush_handler)
            except (ValueError, OSError):
                pass
        _atexit_registered = True


def measure_checkpoint(checkpoint_id: str, checkpoint_type: str,
                      name: str, line_number: int, context: str):
    """Record a checkpoint marker with ultra-low overhead."""
    _ensure_atexit()
    client = _get_nemb_client()
    # Signal name contains ID and metadata for later correlation
    signal_name = f"{checkpoint_type}:{name}:{checkpoint_id}"
    client.mark_checkpoint(signal_name)


def checkpoint(checkpoint_id: str, name: str, checkpoint_type: str):
    """Mark a checkpoint in the energy measurement stream.
    Throttling via CODEGREEN_CHECKPOINT_THROTTLE_MS env var (0=disabled)."""
    if _throttle_interval_ns > 0:
        now = time.monotonic_ns()
        last = _last_checkpoint_time.get(checkpoint_id, 0)
        if now - last < _throttle_interval_ns:
            return
        _last_checkpoint_time[checkpoint_id] = now
    measure_checkpoint(checkpoint_id, checkpoint_type, name, 0, "")


# --- Manual span-based measurement (Session API) ---

import csv
import functools
import os as _os
import sys as _sys
import warnings as _warnings
import statistics as _statistics
from contextlib import contextmanager as _contextmanager

_active_session: Optional["Session"] = None
_session_lock = threading.Lock()
_PIDFILE = Path(
    _os.environ.get("XDG_RUNTIME_DIR", "/tmp")
) / f"codegreen-{_os.getuid() if hasattr(_os, 'getuid') else 0}.pids"


def _other_codegreen_pids() -> List[int]:
    """Return live PIDs of other codegreen processes on this host."""
    if not _PIDFILE.exists():
        return []
    try:
        raw = _PIDFILE.read_text().splitlines()
    except OSError:
        return []
    self_pid = _os.getpid()
    alive = []
    for line in raw:
        try:
            pid = int(line.strip())
        except ValueError:
            continue
        if pid == self_pid:
            continue
        try:
            _os.kill(pid, 0)
            alive.append(pid)
        except (ProcessLookupError, PermissionError):
            pass
    return alive


def _register_pid():
    try:
        _PIDFILE.parent.mkdir(parents=True, exist_ok=True)
        with _PIDFILE.open("a") as f:
            f.write(f"{_os.getpid()}\n")
    except OSError:
        pass


def _unregister_pid():
    if not _PIDFILE.exists():
        return
    try:
        keep = []
        self_pid = _os.getpid()
        for line in _PIDFILE.read_text().splitlines():
            try:
                pid = int(line.strip())
            except ValueError:
                continue
            if pid == self_pid:
                continue
            keep.append(str(pid))
        if keep:
            _PIDFILE.write_text("\n".join(keep) + "\n")
        else:
            _PIDFILE.unlink()
    except OSError:
        pass


@dataclass
class TaskResult:
    name: str
    energy_j: float
    avg_power_w: float
    duration_s: float
    started_at: float                                    # wall-clock POSIX seconds (display)
    ended_at: float
    depth: int
    parent: Optional[str]
    domains: Dict[str, float]                            # joules per domain
    # RAPL domain semantics: NESTED, not disjoint. Intel: `package` includes
    # `pp0`+`pp1`; `dram` is separate on most chips; `gpu*` (NVML) is independent.
    # AMD EPYC: only `package-0`. `sum(domains) != energy_j`. `energy_j` = top-level
    # CPU domain (`package-0`/`pkg-0`) + independent domains (gpu, dram-when-separate).
    domains_power_w: Dict[str, float] = None             # watts per domain (j / duration_s)
    started_at_mono_ns: int = 0                          # CLOCK_MONOTONIC stamp at task open
    ended_at_mono_ns: int = 0                            # CLOCK_MONOTONIC stamp at task close
    timeseries: Optional[List[Dict[str, float]]] = None  # [{t_ns,energy_j,power_w,domains}], inclusive of children
    noise: Optional[Dict[str, float]] = None             # populated when timeseries present


# Sample size estimate (matches SynchronizedReading on 64-bit) for buffer sizing
_BYTES_PER_SAMPLE_EST = 800
_DEFAULT_SAMPLE_INTERVAL_MS = 10  # NEMB default; mirror in Session for sizing math


def _bundled_sample_interval_ms() -> int:
    """Read the NEMB default sample interval from bundled config.json. The
    correct path is `measurement.nemb.coordinator.measurement_interval_ms`;
    earlier versions looked it up at the top level and silently fell back."""
    cfg = Path(__file__).resolve().parents[3] / "config.json"
    try:
        with open(cfg) as f:
            d = json.load(f)
        return int(d["measurement"]["nemb"]["coordinator"]["measurement_interval_ms"])
    except Exception:
        return _DEFAULT_SAMPLE_INTERVAL_MS


def _quality_label(cv_percent: float) -> str:
    nw = _report_config()["noise_warning"]
    if cv_percent < nw["quality_excellent_below_cv_pct"]: return "excellent"
    if cv_percent < nw["quality_good_below_cv_pct"]:      return "good"
    if cv_percent < nw["quality_moderate_below_cv_pct"]:  return "moderate"
    return "high-noise"


def _compute_task_noise(task: "TaskResult", sample_interval_ms: int) -> Optional[Dict]:
    """Power-CV + sample-drop summary for one task. Returns None ONLY when
    timeseries is None (recording disabled). Empty list -> drop_ratio=1.0."""
    ts = task.timeseries
    if ts is None:
        return None
    powers = [s.get("power_w", 0.0) for s in ts if s.get("power_w") is not None]
    n = len(powers)
    if n >= 2:
        mean_w = _statistics.fmean(powers)
        std_w  = _statistics.stdev(powers) if n >= 2 else 0.0
    else:
        mean_w = powers[0] if n == 1 else 0.0
        std_w = 0.0
    cv = (100.0 * std_w / mean_w) if mean_w > 0 else 0.0
    if n >= 3:
        intervals_ns = [ts[i]["t_ns"] - ts[i-1]["t_ns"] for i in range(1, len(ts))]
        intervals_ns = [iv for iv in intervals_ns if iv > 0]
        if intervals_ns:
            observed_ms = _statistics.median(intervals_ns) / 1e6
            expected = max(1, int(round(task.duration_s * 1000.0 / observed_ms)))
            expected_method = "observed_median"
        else:
            expected = max(1, int(round(task.duration_s * 1000.0 / max(1, sample_interval_ms))))
            expected_method = "configured"
    else:
        expected = max(1, int(round(task.duration_s * 1000.0 / max(1, sample_interval_ms))))
        expected_method = "configured"
    drop_ratio = max(0.0, 1.0 - n / expected) if expected > 0 else 1.0
    return {
        "samples_captured":  n,
        "samples_expected":  expected,
        "samples_expected_method": expected_method,
        "drop_ratio":        round(drop_ratio, 4),
        "power_mean_w":      round(mean_w, 4),
        "power_std_w":       round(std_w,  4),
        "power_cv_percent":  round(cv,     3),
        "sample_interval_ms": sample_interval_ms,
        "quality":           _quality_label(cv),
    }


class Session:
    """Manual span-based energy measurement.

    Mirrors NEMB's start_session/end_session semantics. Use .task() for nested
    spans. Single instance per process; auto-instrumenter checkpoints in the
    same process are merged into the same JSON output envelope.

        with codegreen.Session("training-run") as s:
            with s.task("data_load"):
                load()
            with s.task("train"):
                train()
    """

    def __init__(
        self,
        name: str = "default",
        output_file: Optional[str] = None,
        output_format: str = "auto",     # "auto" | "json" | "csv" | "none"
        save_to_file: bool = True,
        warn_on_concurrent: bool = True,
        record_time_series: bool = False,
        buffer_samples: Optional[int] = None,    # advanced: override C++ ring size
        sample_interval_ms: Optional[int] = None,  # advanced: override sampling rate
        sampling_mode: str = "fixed",            # "fixed" | "adaptive" (future)
    ):
        global _active_session
        with _session_lock:
            if _active_session is not None:
                raise RuntimeError(
                    "codegreen.Session already active in this process "
                    "(only one allowed); call .stop() on the prior instance first."
                )
            _active_session = self

        self.name = name
        self._client = _get_nemb_client()
        self._noop = self._client.lib is None
        self._tasks: List[TaskResult] = []
        self._tasks_lock = threading.Lock()
        self._tls = threading.local()  # per-thread stack of (name, sid, t_start, depth)
        self._all_open: Dict[int, Tuple[str, int, float, int]] = {}  # sid -> meta (for cleanup)
        self._started = False
        self._stopped = False
        self._finalized_report: Optional[Dict] = None
        self._t0_wall: float = 0.0
        self._t0_mono: float = 0.0
        self._started_at_iso: str = ""
        self._ended_at_iso: str = ""
        self._started_at_local_iso: str = ""
        self._ended_at_local_iso: str = ""
        self._run_id: str = uuid.uuid4().hex[:12]
        try:
            self._hostname: str = socket.gethostname()
        except Exception:
            self._hostname = "unknown"
        self._save_to_file = save_to_file
        # Format resolution: explicit > extension sniff > json default
        fmt = output_format.lower()
        if fmt == "none":
            self._save_to_file = False
        if output_file is None:
            ext = "json" if fmt in ("auto", "json") else "csv"
            self._output_file = f"codegreen_{_os.getpid()}.{ext}"
            self._output_format = "csv" if ext == "csv" else "json"
        else:
            self._output_file = output_file
            if fmt == "auto":
                self._output_format = (
                    "csv" if output_file.lower().endswith(".csv") else "json"
                )
            else:
                self._output_format = fmt if fmt in ("json", "csv") else "json"
        if warn_on_concurrent:
            others = _other_codegreen_pids()
            if others:
                _warnings.warn(
                    f"codegreen: {len(others)} other codegreen process(es) "
                    f"active on this host (pids={others}); RAPL is system-wide "
                    f"so readings may overlap. See docs.",
                    RuntimeWarning, stacklevel=2,
                )
        if self._noop:
            _warnings.warn(
                "codegreen: NEMB library not loaded; Session is a no-op. "
                "Tasks will record zero energy.",
                RuntimeWarning, stacklevel=2,
            )

        # --- Time-series state ---
        self._record_ts = record_time_series and not self._noop
        self._ts_samples: List[Dict] = []
        self._ts_lock = threading.Lock()
        self._ts_thread: Optional[threading.Thread] = None
        self._ts_stop = threading.Event()
        self._ts_last_ts: int = 0
        # Adaptive drain bounds and saturation thresholds
        self._drain_min_s = 0.05    # floor: 50 ms
        self._drain_max_s = 2.0     # ceiling: 2 s
        self._drain_interval_s = 0.5
        self._low_saturation_streak = 0
        self._buffer_samples = 1000  # NEMB default
        if self._record_ts:
            has_ts = getattr(self._client, "_has_timeseries", False)
            if not has_ts:
                _warnings.warn(
                    "codegreen: NEMB ABI < 3 — time-series unavailable; "
                    "rebuild libcodegreen-nemb.so. Continuing without time series.",
                    RuntimeWarning, stacklevel=2,
                )
                self._record_ts = False
            else:
                if buffer_samples is not None:
                    # Power-user override (rarely needed; drain is adaptive).
                    try:
                        self._client.lib.nemb_set_buffer_size(int(buffer_samples))
                        self._buffer_samples = int(buffer_samples)
                    except Exception:
                        pass
                effective_interval = int(sample_interval_ms) if sample_interval_ms is not None \
                                     else _bundled_sample_interval_ms()
                try:
                    self._client.lib.nemb_set_measurement_interval_ms(effective_interval)
                except Exception:
                    pass
        # Effective sample interval for noise / drop-ratio math.
        self._sample_interval_ms = int(sample_interval_ms) if sample_interval_ms is not None \
                                   else _bundled_sample_interval_ms()
        self._sampling_mode = sampling_mode  # "adaptive" reserved for future

    def start(self) -> "Session":
        if self._started:
            _warnings.warn("codegreen.Session.start() called twice; ignored.",
                          RuntimeWarning, stacklevel=2)
            return self
        self._started = True
        self._t0_wall = time.time()
        self._t0_mono = time.monotonic()
        self._started_at_iso = _iso_utc_now()
        self._started_at_local_iso = _iso_local_now()
        _register_pid()
        _ensure_atexit()
        if self._record_ts:
            self._ts_stop.clear()
            self._ts_thread = threading.Thread(
                target=self._drain_loop, name="codegreen-drain", daemon=True
            )
            self._ts_thread.start()
        return self

    def _drain_once(self) -> int:
        """Pull samples from C++ ring buffer since last drain. Returns count."""
        if not self._record_ts:
            return 0
        buf_size = max(64 * 1024, self._buffer_samples * 200)
        buf = ctypes.create_string_buffer(buf_size)
        ret = self._client.lib.nemb_get_time_series_json(
            buf, buf_size, ctypes.c_uint64(self._ts_last_ts + 1)
        )
        if ret < 0:
            buf = ctypes.create_string_buffer((-ret) + 1)
            ret = self._client.lib.nemb_get_time_series_json(
                buf, len(buf), ctypes.c_uint64(self._ts_last_ts + 1)
            )
        if ret <= 0:
            return 0
        try:
            samples = json.loads(buf.value.decode("utf-8"))
        except Exception:
            return 0
        if not samples:
            return 0
        with self._ts_lock:
            self._ts_samples.extend(samples)
        self._ts_last_ts = samples[-1]["t_ns"]
        return len(samples)

    def _drain_loop(self):
        """Adaptive drain. The drain op is cheap (locked vector copy ~µs),
        so we tune frequency, not buffer size, to keep the C++ ring at <50%
        saturation. Resizing the buffer mid-session would clear samples,
        which is why we never do that here."""
        while not self._ts_stop.wait(self._drain_interval_s):
            n = self._drain_once()
            if self._buffer_samples <= 0:
                continue
            saturation = n / self._buffer_samples
            if saturation > 0.5:
                # Buffer half-full from one drain pass: speed up
                self._drain_interval_s = max(
                    self._drain_min_s, self._drain_interval_s * 0.5
                )
                self._low_saturation_streak = 0
                if saturation > 0.9:
                    _warnings.warn(
                        f"codegreen: drain saturated buffer "
                        f"({saturation*100:.0f}%); samples lost. "
                        f"Restart with buffer_samples={self._buffer_samples * 4} "
                        f"(buffer cannot be resized mid-run).",
                        RuntimeWarning, stacklevel=2,
                    )
            elif saturation < 0.1:
                self._low_saturation_streak += 1
                if self._low_saturation_streak >= 3:
                    self._drain_interval_s = min(
                        self._drain_max_s, self._drain_interval_s * 1.5
                    )
                    self._low_saturation_streak = 0
            else:
                self._low_saturation_streak = 0

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc, tb):
        self.stop()
        return False

    def _stack(self) -> List[Tuple[str, int, float, int]]:
        if not hasattr(self._tls, "stack"):
            self._tls.stack = []
        return self._tls.stack

    def _begin_task(self, name: str) -> int:
        if not self._started:
            raise RuntimeError("Session not started; call .start() or use 'with'.")
        if self._stopped:
            raise RuntimeError("Session already stopped.")
        if _is_child_process or self._noop:
            return -1
        sid = int(self._client.lib.nemb_start_session(name.encode("utf-8")))
        stack = self._stack()
        depth = len(stack)
        # Track both monotonic (matches C++ sample timestamps) and wall clock
        meta = (name, sid, time.monotonic_ns(), time.time(), depth)
        stack.append(meta)
        with self._tasks_lock:
            self._all_open[sid] = meta
        return sid

    def _end_task(self, expected_name: Optional[str] = None) -> Optional[TaskResult]:
        if _is_child_process or self._noop:
            return None
        stack = self._stack()
        if not stack:
            raise RuntimeError("end_task called with no active task in this thread")
        name, sid, t_mono_ns, t_start, depth = stack.pop()
        if expected_name is not None and expected_name != name:
            stack.append((name, sid, t_mono_ns, t_start, depth))
            raise RuntimeError(
                f"task mismatch in thread: trying to end '{expected_name}' "
                f"but innermost open task is '{name}'"
            )
        with self._tasks_lock:
            self._all_open.pop(sid, None)
        parent = stack[-1][0] if stack else None
        return self._close_by_sid(name, sid, t_mono_ns, t_start, depth, parent)

    def _close_by_sid(self, name: str, sid: int, t_mono_ns: int, t_start: float,
                      depth: int, parent: Optional[str]) -> Optional[TaskResult]:
        e, p, dur = c_double(), c_double(), c_double()
        buf = ctypes.create_string_buffer(4096)
        ret = self._client.lib.nemb_stop_session_v2(
            ctypes.c_uint64(sid), byref(e), byref(p), byref(dur), buf, len(buf)
        )
        if ret < 0:
            buf = ctypes.create_string_buffer((-ret) + 1)
            ret = self._client.lib.nemb_stop_session_v2(
                ctypes.c_uint64(sid), byref(e), byref(p), byref(dur), buf, len(buf)
            )
        if ret <= 0:
            domains: Dict[str, float] = {}
        else:
            try:
                domains = json.loads(buf.value.decode("utf-8"))
            except Exception:
                domains = {}
        t_end = time.time()
        t_end_mono_ns = time.monotonic_ns()
        ts: Optional[List[Dict]] = None
        if self._record_ts:
            self._drain_once()
            with self._ts_lock:
                raw = [s for s in self._ts_samples
                       if t_mono_ns <= s["t_ns"] <= t_end_mono_ns]
            seen = set()
            uniq = []
            for s in sorted(raw, key=lambda x: x["t_ns"]):
                if s["t_ns"] in seen:
                    continue
                seen.add(s["t_ns"])
                uniq.append(s)
            ts = uniq
        _dur = dur.value if dur.value > 0 else ((t_end_mono_ns - t_mono_ns) / 1e9)
        domains_power = {d: (j / _dur) for d, j in domains.items()} if _dur > 0 \
                       else {d: None for d in domains}
        result = TaskResult(
            name=name, energy_j=e.value, avg_power_w=p.value,
            duration_s=_dur,
            started_at=t_start, ended_at=t_end,
            depth=depth, parent=parent, domains=domains,
            domains_power_w=domains_power,
            started_at_mono_ns=t_mono_ns, ended_at_mono_ns=t_end_mono_ns,
            timeseries=ts,
        )
        with self._tasks_lock:
            self._tasks.append(result)
        return result

    def start_task(self, name: str) -> int:
        return self._begin_task(name)

    def stop_task(self, expected_name: Optional[str] = None) -> Optional[TaskResult]:
        return self._end_task(expected_name)

    @_contextmanager
    def task(self, name: str):
        self._begin_task(name)
        try:
            yield
        finally:
            self._end_task(name)

    def _auto_finalize(self):
        """Called by atexit / SIGTERM if user did not call stop().
        Closes open sessions in LIFO order (deepest first) so children are
        closed before parents. Parent-name linkage is preserved by re-deriving
        from the remaining `_all_open` set after each close."""
        while True:
            with self._tasks_lock:
                if not self._all_open:
                    break
                items = sorted(self._all_open.items(),
                               key=lambda kv: (-kv[1][4], -kv[1][2]))
                sid, (name, _sid, t_mono_ns, t_start, depth) = items[0]
                self._all_open.pop(sid, None)
                remaining = list(self._all_open.values())
            parent_name = None
            best_depth = -1
            for (rn, _rs, _rm, _rt, rd) in remaining:
                if rd < depth and rd > best_depth:
                    parent_name = rn
                    best_depth = rd
            self._close_by_sid(name, sid, t_mono_ns, t_start, depth, parent=parent_name)
        self._build_report()

    def _build_report(self) -> Dict:
        if self._finalized_report is not None:
            return self._finalized_report
        if not self._ended_at_iso:
            self._ended_at_iso = _iso_utc_now()
            self._ended_at_local_iso = _iso_local_now()
        total_e = sum(t.energy_j for t in self._tasks if t.depth == 0)
        wall_d = (time.monotonic() - self._t0_mono) if self._started else 0.0
        depth0 = [t for t in self._tasks if t.depth == 0]
        task_d = sum(t.duration_s for t in depth0)
        if depth0 and all(t.started_at_mono_ns and t.ended_at_mono_ns for t in depth0):
            ivs = sorted([(t.started_at_mono_ns, t.ended_at_mono_ns) for t in depth0])
            merged_ns = 0
            cur_s, cur_e = ivs[0]
            for s, e in ivs[1:]:
                if s <= cur_e:
                    cur_e = max(cur_e, e)
                else:
                    merged_ns += cur_e - cur_s
                    cur_s, cur_e = s, e
            merged_ns += cur_e - cur_s
            union_task_d = merged_ns / 1e9
            concurrent_overlap_s = max(0.0, task_d - union_task_d)
            gap_d = max(0.0, wall_d - union_task_d)
        else:
            concurrent_overlap_s = 0.0
            gap_d = max(0.0, wall_d - task_d)
        rcfg = _report_config()
        cv_thr = rcfg["noise_warning"]["within_task_power_cv_pct_threshold"]
        drop_thr = rcfg["noise_warning"]["sampling_drop_ratio_threshold"]
        warnings_list: List[Dict] = []
        worst_cv = 0.0
        report_error: Optional[str] = None
        try:
            for t in self._tasks:
                if t.timeseries is not None:
                    t.noise = _compute_task_noise(t, self._sample_interval_ms)
                    if t.noise:
                        cv = t.noise["power_cv_percent"]
                        drop = t.noise["drop_ratio"]
                        if cv > worst_cv: worst_cv = cv
                        reasons = []
                        if drop >= drop_thr: reasons.append(f"sampling_drop_above_{int(drop_thr*100)}pct")
                        if cv >= cv_thr:     reasons.append(f"within_task_power_cv_above_{int(cv_thr)}pct")
                        if reasons:
                            entry = {
                                "task": t.name,
                                "depth": t.depth,
                                "within_task_power_cv_percent": round(cv, 3),
                                "drop_ratio": round(drop, 4),
                                "quality": t.noise["quality"],
                                "reasons": reasons,
                            }
                            warnings_list.append(entry)
                            _warnings.warn(
                                f"codegreen: task '{t.name}': {','.join(reasons)} "
                                f"(cv={cv:.1f}%, drop={drop*100:.1f}%)",
                                RuntimeWarning, stacklevel=4,
                            )
        except Exception as ex:
            report_error = f"noise_calc: {type(ex).__name__}: {ex}"
        # Per-domain energy aggregated across depth-0 tasks. Domains are NESTED
        # (Intel: pkg includes pp0+pp1; dram/gpu independent). agg_domain_p is
        # the energy-weighted-mean power: sum(domain energy) / sum(task duration
        # over tasks where the domain was reported). Each domain uses its own
        # active window so a domain absent from some tasks is not diluted.
        agg_domain_e: Dict[str, float] = {}
        domain_active_d: Dict[str, float] = {}
        for t in depth0:
            if not t.domains:
                continue
            for d, j in t.domains.items():
                agg_domain_e[d] = agg_domain_e.get(d, 0.0) + j
                domain_active_d[d] = domain_active_d.get(d, 0.0) + t.duration_s
        agg_domain_p = {
            d: (agg_domain_e[d] / domain_active_d[d]) if domain_active_d.get(d, 0.0) > 0 else 0.0
            for d in agg_domain_e
        }
        if not depth0:
            measurement_quality = "no_tasks"
        elif self._noop:
            measurement_quality = "no_backend"
        elif total_e <= 0.0:
            measurement_quality = "energy_zero"
        else:
            measurement_quality = "ok"
        domain_support = "none" if self._noop else ("scalar_only" if not agg_domain_e else "full")
        totals = {
            "energy_j": total_e,
            "duration_s": task_d,
            "wall_duration_s": wall_d,
            "task_duration_s": task_d,
            "gap_duration_s": gap_d,
            "concurrent_overlap_s": round(concurrent_overlap_s, 6),
            "n_tasks": len(self._tasks),
            "n_top_level_tasks": len(depth0),
            "domains": agg_domain_e,
            "domains_power_w": agg_domain_p,
            "sample_interval_ms": self._sample_interval_ms if self._record_ts else None,
            "worst_within_task_power_cv_percent": round(worst_cv, 3) if self._record_ts else None,
            "noise_warnings": warnings_list,
        }
        meta = build_meta_block(
            run_id=self._run_id,
            started_at_iso=self._started_at_iso,
            ended_at_iso=self._ended_at_iso,
            started_at_local_iso=self._started_at_local_iso,
            ended_at_local_iso=self._ended_at_local_iso,
            duration_total_s=wall_d,
            hostname=self._hostname,
            session_name=self.name,
            nemb_abi_version=(self._client.lib.nemb_abi_version() if not self._noop else 0),
            measurement_quality=measurement_quality,
            domain_support=domain_support,
            domains=agg_domain_e,
            record_time_series=self._record_ts,
            extras={"error": report_error} if report_error else None,
        )
        report = {
            "meta": meta,
            "tasks": [t.__dict__ for t in self._tasks],
            "totals": totals,
        }
        self._finalized_report = report
        return report

    def stop(self) -> Dict:
        global _active_session
        if self._stopped:
            return self._finalized_report or {}
        self._stopped = True
        try:
            if self._record_ts and self._ts_thread is not None:
                self._ts_stop.set()
                self._ts_thread.join(timeout=5.0)
                self._drain_once()
            self._auto_finalize()
            report = self._build_report()
            if self._save_to_file and self._tasks:
                try:
                    if self._output_format == "csv":
                        self._write_csv(self._output_file)
                    else:
                        self._write_json(self._output_file, report)
                except OSError as e:
                    _warnings.warn(
                        f"codegreen: failed to write {self._output_file}: {e}",
                        RuntimeWarning, stacklevel=2,
                    )
        finally:
            _unregister_pid()
            with _session_lock:
                if _active_session is self:
                    _active_session = None
        return report

    def _write_json(self, path: str, report: Dict):
        tmp = f"{path}.{_os.getpid()}.tmp"
        with open(tmp, "w") as fp:
            json.dump(report, fp, indent=2, default=str)
            fp.flush()
            try:
                _os.fsync(fp.fileno())
            except OSError:
                pass
        _os.replace(tmp, path)

    def _write_csv(self, path: str):
        is_new = not _os.path.exists(path)
        with open(path, "a", newline="") as fp:
            w = csv.writer(fp)
            if is_new:
                w.writerow([
                    "session", "task", "depth", "parent",
                    "energy_j", "avg_power_w", "duration_s",
                    "started_at", "ended_at", "domains_json",
                    "domains_power_w_json",
                    "power_cv_percent", "samples_captured", "samples_expected",
                    "drop_ratio", "quality",
                ])
            for t in self._tasks:
                n = t.noise or {}
                w.writerow([
                    self.name, t.name, t.depth, t.parent or "",
                    f"{t.energy_j:.9f}", f"{t.avg_power_w:.6f}", f"{t.duration_s:.6f}",
                    f"{t.started_at:.6f}", f"{t.ended_at:.6f}",
                    json.dumps(t.domains, separators=(",", ":")),
                    json.dumps(t.domains_power_w or {}, separators=(",", ":")),
                    n.get("power_cv_percent", ""), n.get("samples_captured", ""),
                    n.get("samples_expected", ""), n.get("drop_ratio", ""),
                    n.get("quality", ""),
                ])

    @property
    def tasks(self) -> List[TaskResult]:
        return list(self._tasks)

    def export_plot(self, path) -> None:
        """Render power-vs-time chart of this session's tasks.
        Requires record_time_series=True. Format from extension: .html, .png, .svg, .pdf."""
        try:
            from codegreen.analyzer.plot import export_session_plot
        except Exception:
            _warnings.warn("codegreen: analyzer.plot unavailable", RuntimeWarning, stacklevel=2)
            return
        report = self._finalized_report or self._build_report()
        export_session_plot(report, path)


def task(name: Optional[str] = None):
    """Decorator: measure a function as a task within the active Session.
    Requires an active Session; raises if none. Falls back to function name."""
    def deco(fn):
        task_name = name or fn.__qualname__
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            sess = _active_session
            if sess is None or not sess._started:
                raise RuntimeError(
                    f"@codegreen.task('{task_name}') requires an active Session; "
                    f"wrap the call in `with codegreen.Session(): ...`"
                )
            with sess.task(task_name):
                return fn(*args, **kwargs)
        return wrapper
    return deco


# Export key functions for instrumented code
__all__ = [
    'measure_checkpoint',
    'checkpoint',
    'Session',
    'TaskResult',
    'task',
]