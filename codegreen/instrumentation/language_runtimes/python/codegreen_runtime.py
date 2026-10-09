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
import stat
import uuid
import functools
import platform as _platform
import ctypes
from abc import ABC, abstractmethod
from collections import deque
from datetime import datetime, timezone
from ctypes import c_double, c_char_p, c_uint64, c_int, byref
from queue import Queue, Empty, Full
from typing import Any, Dict, List, Optional, NamedTuple, Tuple
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


def _install_info_path() -> Path:
    """XDG-aware per-machine info file. Written once at first run; read
    instantly by every subsequent process."""
    base = _os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "codegreen" / "install_info.json"


_INSTALL_INFO_SCHEMA = 2


def _detect_install_info() -> Dict[str, Any]:
    """One-shot per-machine detection of the clock NEMB stamps samples with
    (PrecisionTimer::monotonic_timestamp_ns: CLOCK_MONOTONIC on POSIX,
    mach_continuous_time on macOS, QueryPerformanceCounter on Windows)."""
    info: Dict[str, Any] = {
        "schema": _INSTALL_INFO_SCHEMA,
        "detected_at": _iso_utc_now(),
        "platform": sys.platform,
        "kernel": _platform.platform(),
        "cpu_model": _cpu_model_label(),
        "codegreen_version_at_detect": _runtime_version(),
    }
    if sys.platform == "darwin":
        info["timeseries_clock"] = "mach_continuous_time"
    elif sys.platform.startswith("win"):
        info["timeseries_clock"] = "query_performance_counter"
    elif sys.platform.startswith("linux"):
        info["timeseries_clock"] = "clock_monotonic"
    else:
        info["timeseries_clock"] = "unknown"
    return info


@functools.lru_cache(maxsize=1)
def _machine_install_info() -> Dict[str, Any]:
    """Load (or create on first call) the per-machine install_info.json.
    Cached via lru_cache so detection runs ONCE per process and the file is
    read ONCE per machine after that. If the cached info's `platform` differs
    from the current `sys.platform` (e.g. site-packages was copied across
    machines) the file is regenerated."""
    path = _install_info_path()
    try:
        if path.exists():
            cached = json.loads(path.read_text())
            if (cached.get("schema") == _INSTALL_INFO_SCHEMA and cached.get("platform") == sys.platform
                    and "timeseries_clock" in cached):
                cached["source"] = "machine_install_cache"
                return cached
    except Exception:
        pass
    info = _detect_install_info()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(f"{path}.{_os.getpid()}.tmp")
        tmp.write_text(json.dumps(info, indent=2))
        _os.replace(tmp, path)
        info["source"] = "machine_install_detected"
    except OSError:
        info["source"] = "in_memory_only"
    return info


def _resolve_timeseries_clock(client: Optional[Any] = None) -> Dict[str, Any]:
    """Resolve the clock identity for timeseries[].t_ns. Four-tier with
    explicit provenance so consumers know how much to trust the value:

    1. **backend_reported** — NEMB ABI exposes a clock-name query (future
       v0.5.0+ ABI bump). Authoritative. Tried every call (cheap C call) so
       we pick it up as soon as the user upgrades the .so.
    2. **config_override** — non-empty
       `measurement.report.timeseries_clock_override` in config.json. Lets
       users pin the label for unusual builds.
    3. **machine_install_cache / machine_install_detected** — read from (or
       written to) `~/.config/codegreen/install_info.json` on first run.
       Detection happens ONCE per machine; every subsequent process reads
       the file in microseconds.
    4. **platform_unrecognised** — last-resort `unknown`."""
    if client is not None and getattr(client, "lib", None) is not None:
        fn = getattr(client.lib, "nemb_get_timeseries_clock_name", None)
        if fn is not None:
            try:
                buf = ctypes.create_string_buffer(128)
                ret = fn(buf, len(buf))
                if ret > 0:
                    return {"label": buf.value.decode("utf-8"),
                            "source": "backend_reported"}
            except Exception:
                pass
    override = _report_config().get("timeseries_clock_override")
    if override:
        return {"label": str(override), "source": "config_override"}
    info = _machine_install_info()
    return {"label": info.get("timeseries_clock", "unknown"),
            "source": info.get("source", "machine_install_cache")}


def _python_monotonic_vs_t_ns_offset_ns(client=None) -> Optional[int]:
    """Sanity probe: estimate the offset between Python's `time.monotonic_ns()`
    and a freshly-captured C++ sample's `t_ns`. Lets consumers verify the two
    domains agree within a usable bound. Returns None when no backend or no
    sampling support."""
    if client is None or getattr(client, "lib", None) is None:
        return None
    if not getattr(client, "_has_timeseries", False):
        return None
    fn = getattr(client.lib, "nemb_get_time_series_json", None)
    if fn is None:
        return None
    try:
        buf = ctypes.create_string_buffer(8192)
        py_a = time.monotonic_ns()
        ret = fn(buf, len(buf), ctypes.c_uint64(0))
        py_b = time.monotonic_ns()
        if ret <= 0:
            return None
        samples = json.loads(buf.value.decode("utf-8"))
        if not samples:
            return None
        t_ns = samples[-1].get("t_ns")
        if t_ns is None:
            return None
        return int((py_a + py_b) // 2) - int(t_ns)
    except Exception:
        return None


def _runtime_version() -> str:
    try:
        from importlib.metadata import version as _v
        return _v("codegreen")
    except Exception:
        return "unknown"


def _package_file(name: str) -> Optional[Path]:
    """Path of a file in the codegreen package. `codegreen project` copies this
    runtime into user projects, so prefer the install dir exported by the CLI
    over a location relative to this file; None when neither resolves."""
    install = os.environ.get("CODEGREEN_INSTALL_DIR")
    if install:
        return Path(install) / "codegreen" / name
    here = Path(__file__).resolve()
    return here.parents[3] / name if len(here.parents) > 3 else None


def _report_config() -> Dict:
    """Single source of truth for report/quality thresholds. All thresholds
    that were previously magic numbers (CV%, drop ratio, run-id length) live
    here. Loaded from bundled config.json with defensive defaults."""
    cfg_path = _package_file("config.json")
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
    client: Optional[Any] = None,
    timeseries_clock_offset_ns: Optional[int] = None,
    extras: Optional[Dict] = None,
) -> Dict:
    """Single canonical meta-block builder. Shared by Session._build_report()
    and CLI run_command (and any future language runtime). Adding a meta field
    means editing this function once, not every call site."""
    rcfg = _report_config()
    ts_clock = _resolve_timeseries_clock(client) if record_time_series else None
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
            "t_ns_clock": ts_clock["label"],
            "t_ns_clock_source": ts_clock["source"],
            "t_ns_python_monotonic_offset_ns": timeseries_clock_offset_ns,
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

    pkg = _package_file("")
    search_paths = [pkg / "lib", pkg.parent / "lib", pkg.parent / "build" / "lib"] if pkg else []
    search_paths += [Path("/usr/local/lib"), Path("/usr/lib")]
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

def _read_nemb_json(call, size: int) -> Optional[str]:
    """Drain a NEMB JSON exporter `call(buf, size) -> int`. The C side returns
    -required_size when buf is too small; sampling continues between calls, so
    the payload can grow before the retry. Retry with headroom, never return a
    silently truncated or empty result. None when the exporter has no data."""
    for _ in range(8):
        buf = ctypes.create_string_buffer(size)
        ret = call(buf, size)
        if ret >= 0:
            return buf.value.decode("utf-8") if ret > 0 else None
        size = 2 * -ret
    raise RuntimeError(f"NEMB JSON export kept outgrowing its buffer ({size} bytes)")


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
        payload = _read_nemb_json(self.lib.nemb_get_checkpoints_json, 1 << 20)
        return json.loads(payload)["checkpoints"] if payload else []

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

    if _SYNC_DEVICE:
        payload["device_sync"] = {"mode": _SYNC_DEVICE, "syncs": _device_syncs}
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


_SYNC_DEVICE = os.environ.get("CODEGREEN_SYNC_DEVICE", "")
_device_syncs = 0


def _sync_cuda() -> bool:
    """Drain the current CUDA device so the probe timestamp follows every kernel launched so far.
    No-op while torch is not imported or CUDA has no context (nothing can be pending)."""
    torch = sys.modules.get("torch")
    if torch is None:
        return False
    if not torch.cuda.is_available():
        raise RuntimeError("CODEGREEN_SYNC_DEVICE=cuda but torch.cuda.is_available() is False")
    if not torch.cuda.is_initialized():
        return False
    torch.cuda.synchronize()
    return True


_DEVICE_SYNCS = {"cuda": _sync_cuda}
if _SYNC_DEVICE and _SYNC_DEVICE not in _DEVICE_SYNCS:
    raise ValueError(f"CODEGREEN_SYNC_DEVICE={_SYNC_DEVICE!r}; supported: {sorted(_DEVICE_SYNCS)}")


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
    if _SYNC_DEVICE:
        global _device_syncs
        _device_syncs += _DEVICE_SYNCS[_SYNC_DEVICE]()
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
    cfg = _package_file("config.json")
    try:
        with open(cfg) as f:
            d = json.load(f)
        return int(d["measurement"]["nemb"]["coordinator"]["measurement_interval_ms"])
    except Exception:
        return _DEFAULT_SAMPLE_INTERVAL_MS


_MONITOR_DEFAULTS = {
    "interval_ms_default": 500,
    "interval_ms_min": 50,
    "interval_ms_warn_below": 100,
    "max_samples_in_memory": 10000,
    "rotate_mb_default": 0,
    "rotate_max_backups": 5,
    "attribution": {
        "mode_default": "auto",
        "cgroup_root": "/sys/fs/cgroup",
        "cgroup_unified_root": "/sys/fs/cgroup/unified",
        "allow_cgroup_v1": True,
    },
    "annotation": {
        "socket_path_default": "",
        "max_label_count": 64,
        "max_label_chars": 256,
        "summary_top_labels": 50,
        "listener_backlog": 16,
        "recv_buf_bytes": 65536,
        "max_labels": 1000,
        "overflow_bucket": "__other__",
    },
}


def _monitor_config(strict: bool = False) -> Dict:
    """Single source of truth for Monitor knobs. Magic numbers live in config.json
    under `monitor.*`; defaults here mirror that block for offline use.

    Args:
        strict: when True, raise instead of falling back to defaults on
            unreadable/malformed config. Used by SIGHUP-reload to fail loud."""
    cfg = _package_file("config.json")
    out = json.loads(json.dumps(_MONITOR_DEFAULTS))
    try:
        with open(cfg) as f:
            d = json.load(f)
    except (OSError, TypeError, json.JSONDecodeError):
        if strict:
            raise
        return out
    m = d.get("monitor", {}) or {}
    for k, v in m.items():
        if k in ("annotation", "attribution") and isinstance(v, dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


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
        self._ts_clock_resolved: Optional[Dict[str, Any]] = None
        self._ts_clock_offset_ns: Optional[int] = None
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
        since = ctypes.c_uint64(self._ts_last_ts + 1)
        payload = _read_nemb_json(
            lambda b, n: self._client.lib.nemb_get_time_series_json(b, n, since), buf_size)
        if payload is None:
            return 0
        try:
            samples = json.loads(payload)
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


_ATTRIBUTION_MODES = ("auto", "cgroup_v2", "cgroup_v1", "cpu_percent")


class _CgroupAttributor:
    """Per-PID energy attribution via Linux cgroups CPU accounting.

    cgroups v2 (cpu.stat: usage_usec)  -> microseconds of CPU time
    cgroups v1 (cpuacct.usage: ns)     -> nanoseconds of CPU time
    System busy time comes from /proc/stat (USER_HZ ticks).

    Share = (cgroup_cpu_delta / system_busy_delta), capped to [0, 1].
    Attributed energy = share * system_rapl_joules_delta.

    Fail-loud at start() if requested mode is unavailable. `auto` selects the
    best backend at start() and never silently downgrades mid-run.
    """

    def __init__(self, pid: int, mode: str, cfg: Dict):
        if mode not in _ATTRIBUTION_MODES:
            raise ValueError(f"attribution_mode must be one of {_ATTRIBUTION_MODES}, got {mode!r}")
        self.pid = int(pid)
        self.requested_mode = mode
        self.cfg = cfg
        self.backend: Optional[str] = None
        self.cgroup_cpu_path: Optional[Path] = None
        self._user_hz = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
        self._last_cgroup_usec: Optional[int] = None
        self._last_sys_usec: Optional[int] = None

    @staticmethod
    def _read_proc_cgroup(pid: int) -> List[str]:
        with open(f"/proc/{pid}/cgroup") as f:
            return [ln.rstrip("\n") for ln in f.readlines()]

    @staticmethod
    def _v2_path_for(pid: int, unified_root: Path) -> Optional[Path]:
        for line in _CgroupAttributor._read_proc_cgroup(pid):
            if line.startswith("0::"):
                rel = line.split("::", 1)[1].lstrip("/")
                p = unified_root / rel
                if (p / "cpu.stat").exists():
                    return p
        return None

    @staticmethod
    def _v1_path_for(pid: int, root: Path) -> Optional[Path]:
        for line in _CgroupAttributor._read_proc_cgroup(pid):
            parts = line.split(":", 2)
            if len(parts) != 3:
                continue
            controllers = parts[1]
            if any(c in controllers.split(",") for c in ("cpuacct", "cpu")):
                rel = parts[2].lstrip("/")
                p = root / controllers / rel
                if (p / "cpuacct.usage").exists():
                    return p
                for c in controllers.split(","):
                    pp = root / c / rel
                    if (pp / "cpuacct.usage").exists():
                        return pp
        return None

    def resolve(self) -> str:
        root = Path(self.cfg["cgroup_root"])
        unified = Path(self.cfg["cgroup_unified_root"])
        if not unified.exists() and (root / "cgroup.controllers").exists():
            unified = root
        if self.requested_mode in ("auto", "cgroup_v2"):
            p = self._v2_path_for(self.pid, unified) if unified.exists() else None
            if p is not None:
                self.cgroup_cpu_path = p
                self.backend = "cgroup_v2"
                return self.backend
            if self.requested_mode == "cgroup_v2":
                raise RuntimeError(f"cgroup_v2 attribution unavailable for pid {self.pid} (no cpu.stat in unified hierarchy)")
        if self.requested_mode in ("auto", "cgroup_v1") and self.cfg.get("allow_cgroup_v1", True):
            p = self._v1_path_for(self.pid, root)
            if p is not None:
                self.cgroup_cpu_path = p
                self.backend = "cgroup_v1"
                return self.backend
            if self.requested_mode == "cgroup_v1":
                raise RuntimeError(f"cgroup_v1 attribution unavailable for pid {self.pid} (no cpuacct.usage)")
        self.backend = "cpu_percent"
        return self.backend

    def _read_cgroup_usec(self) -> Optional[int]:
        if self.cgroup_cpu_path is None:
            return None
        if self.backend == "cgroup_v2":
            with open(self.cgroup_cpu_path / "cpu.stat") as f:
                for ln in f:
                    if ln.startswith("usage_usec"):
                        return int(ln.split()[1])
            raise RuntimeError(f"usage_usec missing in {self.cgroup_cpu_path}/cpu.stat")
        if self.backend == "cgroup_v1":
            with open(self.cgroup_cpu_path / "cpuacct.usage") as f:
                return int(f.read().strip()) // 1000
        return None

    def _read_system_usec(self) -> int:
        with open("/proc/stat") as f:
            parts = f.readline().split()
        if parts[0] != "cpu":
            raise RuntimeError("/proc/stat first line is not aggregate cpu")
        ticks = [int(x) for x in parts[1:]]
        idle = ticks[3] + (ticks[4] if len(ticks) > 4 else 0)
        total = sum(ticks)
        busy_ticks = total - idle
        return int(busy_ticks * 1_000_000 / self._user_hz)

    def prime(self) -> None:
        self._last_cgroup_usec = self._read_cgroup_usec()
        self._last_sys_usec = self._read_system_usec()

    def attribute(self, joules_delta: float) -> Dict:
        """Returns dict with cpu_share, attributed_joules, cgroup_cpu_usec_delta,
        system_cpu_usec_delta, backend. Caller appends to sample record."""
        cur_cg = self._read_cgroup_usec()
        cur_sys = self._read_system_usec()
        if self._last_cgroup_usec is None or self._last_sys_usec is None or cur_cg is None:
            self._last_cgroup_usec = cur_cg
            self._last_sys_usec = cur_sys
            return {"backend": self.backend, "cpu_share": 0.0, "attributed_joules": 0.0,
                    "cgroup_cpu_usec_delta": 0, "system_cpu_usec_delta": 0}
        d_cg = max(0, cur_cg - self._last_cgroup_usec)
        d_sys = max(0, cur_sys - self._last_sys_usec)
        self._last_cgroup_usec = cur_cg
        self._last_sys_usec = cur_sys
        share = (d_cg / d_sys) if d_sys > 0 else 0.0
        share = max(0.0, min(1.0, share))
        return {
            "backend": self.backend,
            "cpu_share": round(share, 6),
            "attributed_joules": round(float(joules_delta) * share, 6),
            "cgroup_cpu_usec_delta": int(d_cg),
            "system_cpu_usec_delta": int(d_sys),
        }


class Sink(ABC):
    """Abstract sample sink.

    A Monitor fan-outs each event to every registered sink IN ADDITION to its
    built-in JSONL writer (which is the in-process sink; semantics preserved
    byte-for-byte from pre-Sink-ABC behavior). The Sink ABC adds external
    sinks (OTLP today; Prometheus pull and remote-push in todo.txt D5+Q1).

    Wire:
      - feed_header(rec)             : header / header_rotated / reload records
      - feed_sample(rec)             : per-tick sample (cumulative joules, watts, t)
      - feed_annotation_start(rec)   : opened span (capped name + labels)
      - feed_annotation_end(rec)     : closed span (joules, duration_s, n_samples)
      - feed_aggregate(per_label)    : periodic snapshot of per-label totals
      - close() -> Dict              : drain + return per-sink summary

    Contract:
      * Every feed_* call MUST be non-blocking and constant-time wrt the
        sample interval. Backpressure is the sink's problem: bounded
        in-memory queue + drop-newest policy + dropped_* counters that
        surface through close().
      * close() is called by Monitor.stop() and must always return a dict
        (never raise). The dict is merged into summary["exporters"][name].
      * feed_aggregate is OPTIONAL (subclasses may ignore it).

    Concrete subclasses:
      - OTLPMetricSink (codegreen_otlp_sink.py): OpenTelemetry OTLP/gRPC.
      - PrometheusSink (codegreen_prometheus_sink.py): pull /metrics endpoint.
      - (future) RemotePushSink (Q1) — same wire.
    """

    name: str = "sink"

    def feed_header(self, rec: Dict) -> None: ...
    @abstractmethod
    def feed_sample(self, rec: Dict) -> None: ...
    @abstractmethod
    def feed_annotation_start(self, rec: Dict) -> None: ...
    @abstractmethod
    def feed_annotation_end(self, rec: Dict) -> None: ...
    def feed_aggregate(self, per_label: Dict[str, Dict[str, float]]) -> None: ...

    @abstractmethod
    def close(self) -> Dict: ...


def _build_sinks(monitor_cfg: Dict, requested: List[str],
                 cli_overrides: Optional[Dict[str, Dict]] = None,
                 resource: Optional[Dict[str, Any]] = None) -> List[Sink]:
    """Construct the requested exporter sinks from config + CLI overrides.

    Fail-loud: an exporter listed in `requested` whose dependencies are missing
    raises RuntimeError immediately with the exact `pip install` command to fix
    it. Never silently no-op — see the Energy-Readback Robustness Rule.

    Config schema lives under `monitor.exporters.<name>.*` in
    `codegreen/config.json`. CLI flags (e.g. `--otlp-endpoint`) override the
    config-file values via the `cli_overrides[name]` dict.
    """
    sinks: List[Sink] = []
    cli_overrides = cli_overrides or {}
    exporters_cfg = (monitor_cfg.get("exporters", {}) or {})
    for name in requested:
        if name == "otlp":
            from codegreen.instrumentation.language_runtimes.python.codegreen_otlp_sink import (
                OTLPMetricSink, _OTLP_AVAILABLE, OTLP_INSTALL_HINT,
            )
            if not _OTLP_AVAILABLE:
                raise RuntimeError(
                    f"--exporter otlp requires the OpenTelemetry SDK. Install with:\n"
                    f"  {OTLP_INSTALL_HINT}"
                )
            cfg = dict(exporters_cfg.get("otlp", {}) or {})
            cfg.update(cli_overrides.get("otlp", {}) or {})
            sinks.append(OTLPMetricSink(cfg, resource or {}))
        elif name == "prometheus":
            from codegreen.instrumentation.language_runtimes.python.codegreen_prometheus_sink import (
                PrometheusSink, _PROM_AVAILABLE, PROMETHEUS_INSTALL_HINT,
            )
            if not _PROM_AVAILABLE:
                raise RuntimeError(
                    f"--exporter prometheus requires the prometheus_client package. "
                    f"Install with:\n  {PROMETHEUS_INSTALL_HINT}"
                )
            cfg = dict(exporters_cfg.get("prometheus", {}) or {})
            cfg.update(cli_overrides.get("prometheus", {}) or {})
            sinks.append(PrometheusSink(cfg, resource or {}))
        else:
            raise ValueError(
                f"--exporter {name!r} is not registered. Known: ['otlp', 'prometheus']. "
                f"(Remote-push 'remote_push' is a placeholder tracked in todo.txt Q1.)"
            )
    return sinks


class Monitor:
    """Continuous energy sampler for long-running processes.

    Unlike Session (span-based), Monitor samples cumulative energy at fixed
    intervals from the NEMB backend without requiring instrumentation. Intended
    for already-running services (web servers, daemons) where embedding the
    Session API is impractical.

    Long-running deployments (days, weeks) require four noise/leak guards:
      * bounded in-memory deque (`max_samples_in_memory`, config: monitor)
      * size-based JSONL rotation (`rotate_mb`, config: monitor)
      * cardinality cap on annotation labels (`max_labels`, config:
        monitor.annotation.max_labels) — labels beyond the cap collapse into
        an overflow bucket (default key `__other__`) so high-cardinality
        sources (raw URLs, request UUIDs) cannot OOM the aggregator.
      * SIGHUP-triggered hot-reload of `interval_ms`, `rotate_mb`,
        `max_samples_in_memory`, and `max_labels` — in-flight annotations
        and the open JSONL file are NOT disturbed. `pid`, `duration_s`,
        `listen_socket_path`, and `output_file` require a full restart.

    Args:
        interval_ms: sample period; floor + warn threshold from config.
        duration_s: stop automatically after N seconds (None = run until stop()).
        pid: if set, also record per-process CPU% for attribution.
        output_file: stream JSON-lines samples to this path (None = in-memory only).
        include_children: when pid is set, sum CPU% of descendants.
        max_samples_in_memory: cap in-memory deque size; 0 = drop after write.
        rotate_mb: rotate JSONL when file exceeds N MB (0 = no rotation).
        listen_socket_path: bind UDS for annotation events (None = disabled,
            "default" = default_socket_path()).
        max_labels: cap distinct annotation labels (0 = unlimited).
    """

    def __init__(self, interval_ms: Optional[int] = None,
                 duration_s: Optional[float] = None,
                 pid: Optional[int] = None, output_file: Optional[str] = None,
                 include_children: bool = True,
                 max_samples_in_memory: Optional[int] = None,
                 rotate_mb: Optional[int] = None,
                 listen_socket_path: Optional[str] = None,
                 attribution_mode: Optional[str] = None,
                 max_labels: Optional[int] = None,
                 exporters: Optional[List[str]] = None,
                 exporter_overrides: Optional[Dict[str, Dict[str, Any]]] = None):
        cfg = _monitor_config()
        if interval_ms is None:
            interval_ms = int(cfg["interval_ms_default"])
        floor = int(cfg["interval_ms_min"])
        if interval_ms < floor:
            raise ValueError(f"interval_ms must be >= {floor} (sub-{floor}ms sampling causes RAPL noise)")
        warn_below = int(cfg["interval_ms_warn_below"])
        if interval_ms < warn_below and duration_s is None:
            _warnings.warn(
                f"codegreen.Monitor: interval_ms={interval_ms} < {warn_below} in run-forever mode "
                f"adds non-trivial sampling overhead; consider >= {warn_below}ms",
                RuntimeWarning, stacklevel=2,
            )
        if duration_s is not None and duration_s <= 0:
            raise ValueError("duration_s must be > 0 when provided")
        max_in_mem = int(cfg["max_samples_in_memory"]) if max_samples_in_memory is None else int(max_samples_in_memory)
        if max_in_mem < 0:
            raise ValueError("max_samples_in_memory must be >= 0")
        rot_mb = int(cfg["rotate_mb_default"]) if rotate_mb is None else int(rotate_mb)
        if rot_mb < 0:
            raise ValueError("rotate_mb must be >= 0")
        ann_cfg0 = cfg.get("annotation", {})
        max_lbl = int(ann_cfg0.get("max_labels", 1000)) if max_labels is None else int(max_labels)
        if max_lbl < 0:
            raise ValueError("max_labels must be >= 0 (0 = unlimited)")
        self._cfg = cfg
        self._interval_s = interval_ms / 1000.0
        self._duration_s = duration_s
        self._pid = int(pid) if pid is not None else None
        self._include_children = bool(include_children)
        self._output_file = output_file
        self._max_in_mem = max_in_mem
        self._rotate_bytes = rot_mb * 1024 * 1024
        self._rotate_max_backups = int(cfg["rotate_max_backups"])
        self._listen_path = default_socket_path() if listen_socket_path == "default" else listen_socket_path
        self._max_labels = max_lbl
        self._overflow_key = str(ann_cfg0.get("overflow_bucket", "__other__"))
        self._reload_requested = threading.Event()
        self._reload_lock = threading.Lock()
        self._reload_count = 0
        self._client: Optional[NEMBClient] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._proc = None
        self._samples: "deque[Dict]" = deque(maxlen=max_in_mem if max_in_mem > 0 else 1)
        self._samples_count = 0
        self._t0: Optional[float] = None
        self._j0: Optional[float] = None
        self._j_last: Optional[float] = None
        self._fp = None
        self._fp_bytes = 0
        self._fp_lock = threading.Lock()
        self._started = False
        self._stopped = False
        self._terminated_reason: Optional[str] = None
        self._ncores = max(1, os.cpu_count() or 1)
        self._child_cache: Dict[int, Any] = {}
        self._annotations_open: Dict[str, Dict] = {}
        self._per_label: Dict[str, Dict[str, float]] = {}
        self._listener: Optional["_AnnotationListener"] = None
        attr_cfg = cfg.get("attribution", {})
        mode = attribution_mode if attribution_mode is not None else attr_cfg.get("mode_default", "auto")
        if mode not in _ATTRIBUTION_MODES:
            raise ValueError(f"attribution_mode must be one of {_ATTRIBUTION_MODES}, got {mode!r}")
        self._attribution_mode_req = mode
        self._attr_cfg = attr_cfg
        self._attributor: Optional[_CgroupAttributor] = None
        self._attribution_backend: Optional[str] = None
        self._cgroup_attributed_total = 0.0
        self._extra_sinks: List[Sink] = []
        self._exporters_requested: List[str] = list(exporters or [])
        self._exporter_overrides: Dict[str, Dict[str, Any]] = dict(exporter_overrides or {})

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()

    def start(self) -> "Monitor":
        if self._started:
            raise RuntimeError("Monitor already started")
        self._client = _get_nemb_client()
        if self._client is None or self._client.lib is None:
            raise RuntimeError("NEMB backend unavailable; install/rebuild codegreen with native library")
        if self._pid is not None:
            try:
                import psutil
            except ImportError:
                raise RuntimeError("--pid requires psutil: pip install psutil")
            if not psutil.pid_exists(self._pid):
                raise RuntimeError(f"cannot attach to pid {self._pid}: no such process")
            self._proc = psutil.Process(self._pid)
            self._proc.cpu_percent(None)
            if self._include_children:
                for c in self._proc.children(recursive=True):
                    try:
                        c.cpu_percent(None)
                    except psutil.NoSuchProcess:
                        pass
            self._attributor = _CgroupAttributor(self._pid, self._attribution_mode_req, self._attr_cfg)
            self._attribution_backend = self._attributor.resolve()
            if self._attribution_backend == "cpu_percent":
                if self._attribution_mode_req == "auto":
                    _warnings.warn(
                        f"codegreen.Monitor: cgroup attribution unavailable for pid {self._pid}; "
                        f"falling back to cpu_percent (less accurate under heavy contention)",
                        RuntimeWarning, stacklevel=2,
                    )
            else:
                self._attributor.prime()
        j, _ = self._client.read_energy()
        self._t0 = time.monotonic()
        self._j0 = float(j)
        self._j_last = float(j)
        if self._output_file:
            try:
                self._fp = open(self._output_file, "w", buffering=1)
                header = {
                    "type": "header", "interval_ms": int(self._interval_s * 1000),
                    "pid": self._pid, "start_ts": _iso_utc_now(),
                    "rotate_mb": self._rotate_bytes // (1024 * 1024),
                    "max_samples_in_memory": self._max_in_mem,
                    "max_labels": self._max_labels,
                    "overflow_bucket": self._overflow_key,
                    "listen_socket": self._listen_path,
                    "attribution_mode_requested": self._attribution_mode_req,
                    "attribution_backend": self._attribution_backend,
                }
                self._write_record(header)
            except OSError as e:
                raise RuntimeError(f"cannot open output_file {self._output_file!r}: {e}") from e
        # Build external sinks (potentially slow: gRPC channel construction)
        # BEFORE binding the UDS listener and marking _started=True. A client
        # racing through the UDS would otherwise see "Monitor must be started"
        # for the first few requests while OTel SDK initializes its threads.
        if self._exporters_requested:
            try:
                resource = {
                    "service.name": "codegreen-monitor",
                    "host.name": _platform.node() or "",
                    "process.pid": int(self._pid or os.getpid()),
                    "attribution_backend": self._attribution_backend or "host",
                    "codegreen.version": _runtime_version(),
                }
                self._extra_sinks = _build_sinks(
                    self._cfg, self._exporters_requested,
                    cli_overrides=self._exporter_overrides, resource=resource,
                )
            except (RuntimeError, ValueError):
                self._safe_close_fp()
                raise
            hdr_rec = {
                "type": "header", "interval_ms": int(self._interval_s * 1000),
                "pid": self._pid, "start_ts": _iso_utc_now(),
                "max_labels": self._max_labels,
                "overflow_bucket": self._overflow_key,
                "attribution_backend": self._attribution_backend,
            }
            for s in self._extra_sinks:
                try:
                    s.feed_header(hdr_rec)
                except Exception as e:
                    _warnings.warn(
                        f"codegreen.Monitor: sink {s.name!r} feed_header raised "
                        f"({type(e).__name__}: {e}); continuing",
                        RuntimeWarning, stacklevel=2,
                    )
        if self._listen_path:
            try:
                self._listener = _AnnotationListener(self, self._listen_path, self._cfg["annotation"])
                self._listener.start()
            except OSError as e:
                self._safe_close_fp()
                for s in self._extra_sinks:
                    try:
                        s.close()
                    except Exception:  # noqa: BLE001
                        pass
                self._extra_sinks = []
                raise RuntimeError(f"cannot bind annotation socket {self._listen_path!r}: {e}") from e
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._loop, name="codegreen-monitor", daemon=True)
        self._started = True
        try:
            self._thread.start()
        except BaseException:
            self._safe_close_fp()
            if self._listener is not None:
                self._listener.stop()
                self._listener = None
            raise
        return self

    def _write_record(self, rec: Dict) -> None:
        """Single durable writer: line-buffered JSON-lines + size-rotation gate.
        Holds fp_lock so annotation events (other thread) and sample loop never
        interleave. Rotation is size-based and fail-loud on OSError."""
        if self._fp is None:
            return
        line = json.dumps(rec, separators=(",", ":")) + "\n"
        data = line.encode("utf-8")
        with self._fp_lock:
            self._fp.write(line)
            self._fp.flush()
            self._fp_bytes += len(data)
            if self._rotate_bytes > 0 and self._fp_bytes >= self._rotate_bytes:
                self._rotate_locked()

    def _fanout(self, rec: Dict) -> None:
        """Non-blocking fan-out to every registered external Sink. The sample
        loop and the annotation paths invoke this AFTER the durable JSONL
        write so a slow / unreachable sink can never wedge the cadence (each
        Sink owns its bounded queue + drop-newest policy). All sink errors
        are swallowed-with-warning here: the OTLP sink's own dropped_*
        counter surfaces the real failure mode through close().
        """
        if not self._extra_sinks:
            return
        rtype = rec.get("type", "")
        for s in self._extra_sinks:
            try:
                if rtype == "sample":
                    s.feed_sample(rec)
                elif rtype == "annotation_start":
                    s.feed_annotation_start(rec)
                elif rtype == "annotation_end":
                    s.feed_annotation_end(rec)
                elif rtype in ("header", "header_rotated", "reload"):
                    s.feed_header(rec)
            except Exception as e:  # noqa: BLE001
                _warnings.warn(
                    f"codegreen.Monitor: sink {s.name!r} feed raised "
                    f"({type(e).__name__}: {e}); continuing",
                    RuntimeWarning, stacklevel=2,
                )

    def _rotate_locked(self) -> None:
        """Roll energy.jsonl -> energy.jsonl.1 -> .2 ... up to rotate_max_backups.
        Caller holds _fp_lock. Fails loud on OSError per design philosophy."""
        path = self._output_file
        if not path:
            return
        self._fp.close()
        for i in range(self._rotate_max_backups, 0, -1):
            src = f"{path}.{i - 1}" if i > 1 else path
            dst = f"{path}.{i}"
            if os.path.exists(src):
                if os.path.exists(dst):
                    os.remove(dst)
                os.rename(src, dst)
        self._fp = open(path, "w", buffering=1)
        self._fp_bytes = 0
        self._write_rotated_header_locked()

    def _write_rotated_header_locked(self) -> None:
        rec = {
            "type": "header_rotated", "ts": _iso_utc_now(),
            "interval_ms": int(self._interval_s * 1000),
        }
        line = json.dumps(rec, separators=(",", ":")) + "\n"
        self._fp.write(line)
        self._fp.flush()
        self._fp_bytes += len(line.encode("utf-8"))

    def _safe_close_fp(self) -> None:
        if self._fp is not None:
            try:
                self._fp.close()
            finally:
                self._fp = None

    def request_reload(self) -> None:
        """Request a hot-reload of reloadable config fields on the next sample tick.
        Thread-safe: called from a signal handler in the main thread; the sample
        loop services it. In-flight annotations and the open JSONL file are NOT
        disturbed."""
        self._reload_requested.set()

    def _reload_config(self) -> None:
        """Re-read config.json and reapply hot-reloadable fields. Per-field
        validation: bad values stay at the previous value and emit a
        RuntimeWarning. NEVER mutates _output_file / _listen_path / _pid /
        _duration_s — those require a full restart."""
        with self._reload_lock:
            try:
                new_cfg = _monitor_config(strict=True)
            except Exception as e:
                _warnings.warn(
                    f"codegreen.Monitor: SIGHUP reload failed to read config "
                    f"({type(e).__name__}: {e}); keeping previous values",
                    RuntimeWarning, stacklevel=2,
                )
                return
            new_ival_ms = new_cfg.get("interval_ms_default", int(self._interval_s * 1000))
            floor = int(new_cfg.get("interval_ms_min", 50))
            if isinstance(new_ival_ms, int) and new_ival_ms >= floor:
                self._interval_s = new_ival_ms / 1000.0
            else:
                _warnings.warn(
                    f"codegreen.Monitor: SIGHUP reload rejected interval_ms_default={new_ival_ms!r} "
                    f"(< {floor} or wrong type); keeping {int(self._interval_s*1000)}",
                    RuntimeWarning, stacklevel=2,
                )
            new_max_mem = new_cfg.get("max_samples_in_memory", self._max_in_mem)
            if isinstance(new_max_mem, int) and new_max_mem >= 0:
                self._max_in_mem = new_max_mem
            else:
                _warnings.warn(
                    f"codegreen.Monitor: SIGHUP reload rejected max_samples_in_memory="
                    f"{new_max_mem!r}; keeping {self._max_in_mem}",
                    RuntimeWarning, stacklevel=2,
                )
            new_rot_mb = new_cfg.get("rotate_mb_default", self._rotate_bytes // (1024 * 1024))
            if isinstance(new_rot_mb, int) and new_rot_mb >= 0:
                self._rotate_bytes = new_rot_mb * 1024 * 1024
            else:
                _warnings.warn(
                    f"codegreen.Monitor: SIGHUP reload rejected rotate_mb_default={new_rot_mb!r}; "
                    f"keeping {self._rotate_bytes // (1024*1024)}",
                    RuntimeWarning, stacklevel=2,
                )
            ann_cfg = new_cfg.get("annotation", {}) or {}
            new_max_lbl = ann_cfg.get("max_labels", self._max_labels)
            if isinstance(new_max_lbl, int) and new_max_lbl >= 0:
                self._max_labels = new_max_lbl
            else:
                _warnings.warn(
                    f"codegreen.Monitor: SIGHUP reload rejected annotation.max_labels="
                    f"{new_max_lbl!r}; keeping {self._max_labels}",
                    RuntimeWarning, stacklevel=2,
                )
            self._cfg = new_cfg
            self._reload_count += 1
            rec = {
                "type": "reload", "ts": _iso_utc_now(),
                "interval_ms": int(self._interval_s * 1000),
                "max_samples_in_memory": self._max_in_mem,
                "rotate_mb": self._rotate_bytes // (1024 * 1024),
                "max_labels": self._max_labels,
                "reload_count": self._reload_count,
            }
            if self._fp:
                self._write_record(rec)

    def _loop(self):
        next_t = self._t0
        while not self._stop_evt.is_set():
            if self._reload_requested.is_set():
                self._reload_requested.clear()
                self._reload_config()
            next_t += self._interval_s
            wait = next_t - time.monotonic()
            if wait > 0:
                if self._stop_evt.wait(wait):
                    break
            if self._duration_s is not None and (time.monotonic() - self._t0) >= self._duration_s:
                self._stop_evt.set()
                break
            j, w = self._client.read_energy()
            t_rel = time.monotonic() - self._t0
            sample = {
                "type": "sample",
                "t": round(t_rel, 4),
                "joules_total": round(float(j) - self._j0, 6),
                "joules_delta": round(float(j) - self._j_last, 6),
                "watts": round(float(w), 4),
            }
            if self._proc is not None:
                import psutil as _psutil
                try:
                    cpu = self._proc.cpu_percent(None)
                except _psutil.NoSuchProcess:
                    self._terminated_reason = f"pid {self._pid} exited"
                    self._stop_evt.set()
                    break
                n_children = 0
                if self._include_children:
                    try:
                        current = self._proc.children(recursive=True)
                    except _psutil.NoSuchProcess:
                        self._terminated_reason = f"pid {self._pid} exited"
                        self._stop_evt.set()
                        break
                    seen = set()
                    for c in current:
                        seen.add(c.pid)
                        cached = self._child_cache.get(c.pid)
                        if cached is None:
                            try:
                                c.cpu_percent(None)
                            except _psutil.NoSuchProcess:
                                continue
                            self._child_cache[c.pid] = c
                            n_children += 1
                            continue
                        try:
                            cpu += cached.cpu_percent(None)
                            n_children += 1
                        except _psutil.NoSuchProcess:
                            self._child_cache.pop(c.pid, None)
                    for dead in set(self._child_cache) - seen:
                        self._child_cache.pop(dead, None)
                sample["proc_cpu_percent"] = round(cpu, 2)
                sample["proc_n_children"] = n_children
                if self._attributor is not None and self._attribution_backend != "cpu_percent":
                    attr = self._attributor.attribute(sample["joules_delta"])
                    sample["proc_attribution_backend"] = attr["backend"]
                    sample["proc_cpu_share"] = attr["cpu_share"]
                    sample["proc_attributed_joules"] = attr["attributed_joules"]
                    sample["cgroup_cpu_usec_delta"] = attr["cgroup_cpu_usec_delta"]
                    sample["system_cpu_usec_delta"] = attr["system_cpu_usec_delta"]
                    self._cgroup_attributed_total += attr["attributed_joules"]
                else:
                    sample["proc_attribution_backend"] = "cpu_percent"
                    sample["proc_attributed_joules"] = round(
                        sample["joules_delta"] * (cpu / (100.0 * self._ncores)), 6
                    )
            self._j_last = float(j)
            self._samples_count += 1
            if self._max_in_mem > 0:
                self._samples.append(sample)
            self._attribute_to_open_annotations(sample)
            if self._fp:
                self._write_record(sample)
            self._fanout(sample)

    def _attribute_to_open_annotations(self, sample: Dict) -> None:
        """For every currently-open annotation span, accumulate sample energy.
        Snapshot under fp_lock so listener-thread mutations of self._annotations_open
        cannot raise RuntimeError('dict changed size during iteration')."""
        with self._fp_lock:
            open_anns = list(self._annotations_open.values())
        if not open_anns:
            return
        dj = sample.get("joules_delta", 0.0)
        for ann in open_anns:
            ann["joules"] += dj
            ann["n_samples"] += 1

    def annotate_start(self, name: str, labels: Optional[Dict[str, str]] = None,
                       token: Optional[str] = None) -> str:
        """Open a labelled span; returns token to pass to annotate_end.

        Cardinality cap: if max_labels > 0 and the number of distinct names
        already aggregated has reached the cap, a NEW label collapses into the
        overflow bucket (default key ``__other__``). Already-seen labels and
        the overflow bucket itself always pass. The original requested name is
        preserved as ``labels["__requested_name__"]`` for debugging.
        """
        if not self._started or self._stopped:
            raise RuntimeError("Monitor must be started before annotate_start")
        if not isinstance(name, str) or not name:
            raise ValueError("annotation name must be non-empty str")
        ann_cfg = self._cfg["annotation"]
        if labels and (len(labels) > ann_cfg["max_label_count"]):
            raise ValueError(f"too many labels (max {ann_cfg['max_label_count']})")
        eff_labels = dict(labels) if labels else {}
        eff_name = name
        cap = self._max_labels
        if cap > 0:
            with self._fp_lock:
                seen = name in self._per_label
                at_cap = len(self._per_label) >= cap
            if not seen and at_cap and name != self._overflow_key:
                eff_labels["__requested_name__"] = name
                eff_name = self._overflow_key
        tok = token or uuid.uuid4().hex
        t_open = round(time.monotonic() - self._t0, 6) if self._t0 is not None else 0.0
        rec = {
            "type": "annotation_start", "token": tok, "name": eff_name,
            "labels": eff_labels, "t": t_open, "ts": _iso_utc_now(),
        }
        with self._fp_lock:
            self._annotations_open[tok] = {
                "name": eff_name, "labels": eff_labels, "t_open": t_open,
                "joules": 0.0, "n_samples": 0,
            }
        if self._fp:
            self._write_record(rec)
        self._fanout(rec)
        return tok

    def annotate_end(self, token: str, status: str = "ok") -> Dict:
        """Close span and update per-label totals. Returns the closed record."""
        if not self._started or self._stopped:
            raise RuntimeError("Monitor must be started before annotate_end")
        with self._fp_lock:
            open_ann = self._annotations_open.pop(token, None)
        if open_ann is None:
            raise KeyError(f"annotation token {token!r} not open")
        t_close = round(time.monotonic() - self._t0, 6) if self._t0 is not None else 0.0
        dur = max(0.0, t_close - open_ann["t_open"])
        joules = round(open_ann["joules"], 6)
        rec = {
            "type": "annotation_end", "token": token, "name": open_ann["name"],
            "labels": open_ann["labels"], "status": status,
            "t_open": open_ann["t_open"], "t_close": t_close,
            "duration_s": round(dur, 6), "joules": joules,
            "n_samples": open_ann["n_samples"], "ts": _iso_utc_now(),
        }
        bucket = self._per_label.setdefault(open_ann["name"], {
            "count": 0, "joules_total": 0.0, "duration_total_s": 0.0,
            "_durations_ms": [],
        })
        bucket["count"] += 1
        bucket["joules_total"] += joules
        bucket["duration_total_s"] += dur
        bucket["_durations_ms"].append(dur * 1000.0)
        if self._fp:
            self._write_record(rec)
        self._fanout(rec)
        return rec

    def stop(self) -> Dict:
        if not self._started or self._stopped:
            return self._summary() if self._stopped else {}
        self._stop_evt.set()
        if self._thread:
            self._thread.join(timeout=max(2.0, self._interval_s * 4))
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        try:
            j, _ = self._client.read_energy()
            self._j_last = float(j)
        except (OSError, AttributeError, RuntimeError) as e:
            _warnings.warn(
                f"codegreen.Monitor.stop: final read_energy failed ({type(e).__name__}: {e}); "
                f"using last sample's j",
                RuntimeWarning, stacklevel=2,
            )
        # Snapshot per_label aggregate to sinks (give OTLP one last chance to
        # observe final totals); then close sinks and merge their per-sink
        # summary dicts into summary["exporters"][<name>].
        if self._extra_sinks:
            for s in self._extra_sinks:
                try:
                    s.feed_aggregate(self._per_label)
                except Exception as e:  # noqa: BLE001
                    _warnings.warn(
                        f"codegreen.Monitor.stop: sink {s.name!r} feed_aggregate "
                        f"raised ({type(e).__name__}: {e}); continuing",
                        RuntimeWarning, stacklevel=2,
                    )
        summary = self._summary()
        exporters_summary: Dict[str, Dict] = {}
        for s in self._extra_sinks:
            try:
                exporters_summary[s.name] = s.close() or {}
            except Exception as e:  # noqa: BLE001
                exporters_summary[s.name] = {
                    "error": f"{type(e).__name__}: {e}",
                }
        if exporters_summary:
            summary["exporters"] = exporters_summary
        self._extra_sinks = []
        if self._fp:
            try:
                self._write_record({"type": "summary", **summary})
            finally:
                self._safe_close_fp()
        self._stopped = True
        return summary

    def _summary(self) -> Dict:
        duration = (time.monotonic() - self._t0) if self._t0 is not None else 0.0
        total_j = (self._j_last - self._j0) if (self._j_last is not None and self._j0 is not None) else 0.0
        avg_w = (total_j / duration) if duration > 0 else 0.0
        proc_total = None
        if self._proc is not None:
            if self._attributor is not None and self._attribution_backend != "cpu_percent":
                proc_total = round(self._cgroup_attributed_total, 6)
            elif self._samples:
                proc_total = round(sum(s.get("proc_attributed_joules", 0.0) for s in self._samples), 6)
        per_label_out: Dict[str, Dict] = {}
        top_n = int(self._cfg["annotation"]["summary_top_labels"])
        items = sorted(self._per_label.items(), key=lambda kv: kv[1]["joules_total"], reverse=True)[:top_n]
        overflow = self._per_label.get(self._overflow_key)
        if overflow is not None and self._overflow_key not in dict(items):
            items.append((self._overflow_key, overflow))
        for name, b in items:
            durs = sorted(b["_durations_ms"])
            n = len(durs)
            p50 = durs[n // 2] if n else 0.0
            p95 = durs[int(0.95 * (n - 1))] if n else 0.0
            per_label_out[name] = {
                "count": b["count"],
                "joules_total": round(b["joules_total"], 6),
                "duration_total_s": round(b["duration_total_s"], 6),
                "joules_per_call_avg": round(b["joules_total"] / b["count"], 6) if b["count"] else 0.0,
                "latency_ms_p50": round(p50, 3),
                "latency_ms_p95": round(p95, 3),
            }
        return {
            "duration_s": round(duration, 4),
            "total_joules": round(total_j, 6),
            "avg_watts": round(avg_w, 4),
            "samples": self._samples_count,
            "samples_in_memory": len(self._samples) if self._max_in_mem > 0 else 0,
            "pid": self._pid,
            "proc_attributed_joules": proc_total,
            "attribution_mode_requested": self._attribution_mode_req,
            "attribution_backend": self._attribution_backend,
            "terminated_reason": self._terminated_reason,
            "annotations_open": len(self._annotations_open),
            "per_label": per_label_out,
            "max_labels": self._max_labels,
            "overflow_bucket": self._overflow_key,
            "distinct_labels": len(self._per_label),
            "reload_count": self._reload_count,
            "end_ts": _iso_utc_now(),
        }

    @property
    def samples(self) -> List[Dict]:
        return list(self._samples)


def default_socket_path() -> str:
    """Per-user annotation socket path shared by Monitor and annotate_request:
    $XDG_RUNTIME_DIR/codegreen.sock, else /tmp/codegreen-<uid>/codegreen.sock."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    base = runtime_dir if runtime_dir else f"/tmp/codegreen-{os.getuid()}"
    return os.path.join(base, "codegreen.sock")


def _ensure_private_dir(path: str) -> None:
    os.makedirs(path, mode=0o700, exist_ok=True)
    st = os.lstat(path)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise OSError(f"socket dir {path} must be a directory owned by uid {os.getuid()} with mode 0700")


class _AnnotationListener:
    """Unix-domain-socket server accepting line-delimited JSON annotation events.
    Wire format (one JSON per line):
      {"op":"start","name":"GET /users","labels":{...},"token":"opt"}  -> {"ok":true,"token":...}
      {"op":"end","token":"...","status":"ok"}                           -> {"ok":true,"joules":...}
    Designed for in-process Flask/Django middleware. Low-overhead (kernel-buffered),
    language-agnostic (any client that can speak JSON over UDS works)."""

    def __init__(self, monitor: "Monitor", path: str, ann_cfg: Dict):
        self._mon = monitor
        self._path = path
        self._backlog = int(ann_cfg["listener_backlog"])
        self._recv_buf = int(ann_cfg["recv_buf_bytes"])
        self._sock: Optional[socket.socket] = None
        self._stop = threading.Event()
        self._accept_thread: Optional[threading.Thread] = None
        self._client_threads: List[threading.Thread] = []
        self._client_lock = threading.Lock()

    def start(self) -> None:
        parent = os.path.dirname(os.path.abspath(self._path))
        if parent == os.path.dirname(default_socket_path()):
            _ensure_private_dir(parent)
        elif not os.path.isdir(parent):
            raise OSError(f"socket parent dir does not exist: {parent}")
        try:
            st = os.lstat(self._path)
        except FileNotFoundError:
            pass
        else:
            if not stat.S_ISSOCK(st.st_mode) or st.st_uid != os.getuid():
                raise OSError(f"refusing to replace {self._path}: not a socket owned by uid {os.getuid()}")
            os.unlink(self._path)
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        old_umask = os.umask(0o177)
        try:
            s.bind(self._path)
            os.chmod(self._path, 0o600)
            s.listen(self._backlog)
            s.settimeout(0.5)
        except BaseException:
            s.close()
            raise
        finally:
            os.umask(old_umask)
        self._sock = s
        self._stop.clear()
        self._accept_thread = threading.Thread(target=self._accept_loop,
                                               name="codegreen-monitor-uds", daemon=True)
        self._accept_thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._accept_thread is not None:
            self._accept_thread.join(timeout=2.0)
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None
        try:
            if stat.S_ISSOCK(os.lstat(self._path).st_mode):
                os.unlink(self._path)
        except FileNotFoundError:
            pass
        with self._client_lock:
            threads = list(self._client_threads)
        for t in threads:
            t.join(timeout=1.0)

    def _accept_loop(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            t = threading.Thread(target=self._serve_client, args=(conn,),
                                 name="codegreen-monitor-uds-cli", daemon=True)
            with self._client_lock:
                self._client_threads.append(t)
            t.start()

    def _serve_client(self, conn: socket.socket) -> None:
        conn.settimeout(1.0)
        buf = b""
        try:
            while not self._stop.is_set():
                try:
                    chunk = conn.recv(self._recv_buf)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    resp = self._handle(line)
                    try:
                        conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                    except OSError:
                        return
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def _handle(self, line: bytes) -> Dict:
        try:
            msg = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            return {"ok": False, "error": f"bad_json: {e}"}
        op = msg.get("op")
        try:
            if op == "start":
                if "name" not in msg:
                    return {"ok": False, "error": "missing_field: name"}
                tok = self._mon.annotate_start(msg["name"], msg.get("labels"), msg.get("token"))
                return {"ok": True, "token": tok}
            if op == "end":
                if "token" not in msg:
                    return {"ok": False, "error": "missing_field: token"}
                try:
                    rec = self._mon.annotate_end(msg["token"], msg.get("status", "ok"))
                except KeyError as e:
                    return {"ok": False, "error": f"unknown_token: {e.args[0]}"}
                return {"ok": True, "joules": rec["joules"], "duration_s": rec["duration_s"]}
        except (ValueError, RuntimeError) as e:
            return {"ok": False, "error": str(e)}
        return {"ok": False, "error": f"unknown_op: {op!r}"}


class annotate_request:
    """Context manager wrapper that emits start/end events to a Monitor over UDS.
    socket_path defaults to default_socket_path(), matching `--listen-on-socket default`.

    Example (Flask):
        @app.before_request
        def _cg_start():
            g._cg = annotate_request(f"{request.method} {request.path}").__enter__()
        @app.teardown_request
        def _cg_end(exc):
            g._cg.__exit__(None, None, None)
    """

    def __init__(self, name: str, labels: Optional[Dict[str, str]] = None,
                 socket_path: Optional[str] = None, timeout_s: float = 0.25):
        self._name = name
        self._labels = labels or {}
        self._path = socket_path or default_socket_path()
        self._timeout = timeout_s
        self._sock: Optional[socket.socket] = None
        self._token: Optional[str] = None
        self._buf = b""

    def __enter__(self) -> "annotate_request":
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(self._timeout)
        s.connect(self._path)
        self._sock = s
        msg = {"op": "start", "name": self._name, "labels": self._labels}
        s.sendall((json.dumps(msg) + "\n").encode("utf-8"))
        resp = self._recv_one()
        if not resp.get("ok"):
            self._close()
            raise RuntimeError(f"annotation_start failed: {resp.get('error')}")
        self._token = resp["token"]
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._sock is None or self._token is None:
            return
        try:
            status = "ok" if exc is None else "error"
            self._sock.sendall((json.dumps({"op": "end", "token": self._token,
                                            "status": status}) + "\n").encode("utf-8"))
            self._recv_one()
        except OSError:
            pass
        finally:
            self._close()

    def _recv_one(self) -> Dict:
        assert self._sock is not None
        while b"\n" not in self._buf:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise RuntimeError("annotation socket closed unexpectedly")
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        return json.loads(line.decode("utf-8"))

    def _close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None




# Export key functions for instrumented code
__all__ = [
    'measure_checkpoint',
    'checkpoint',
    'Session',
    'Monitor',
    'annotate_request',
    'TaskResult',
    'task',
]