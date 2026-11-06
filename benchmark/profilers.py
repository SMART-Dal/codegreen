"""Energy profiler interfaces for CodeGreen and perf RAPL."""
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmark.config import PERF_CPU_EVENT_SETS

@dataclass
class ProfileResult:
    energy_joules: Optional[float]
    time_seconds: float
    output: str
    checkpoints: List[Dict[str, Any]]
    raw_data: Dict[str, Any]
    validity: Optional[Dict[str, Any]] = None

class ProfilerInterface(ABC):
    @abstractmethod
    def run(self, cmd: List[str], timeout: int = 300) -> ProfileResult:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

    def unavailable_reason(self) -> str:
        return f"{type(self).__name__} is not available on this host"

def perf_power_events() -> List[str]:
    """RAPL events the kernel power PMU offers through perf (empty without perf or without a power PMU)."""
    if not shutil.which("perf"):
        return []
    out = subprocess.run(["perf", "list", "power"], capture_output=True, text=True, timeout=60).stdout
    return sorted(set(re.findall(r"power/(energy-[\w-]+)/", out)))

class CodeGreenProfiler(ProfilerInterface):
    """Uses codegreen measure CLI for energy measurement."""
    def __init__(self):
        self.source_path: Path | None = None
        self.language: str | None = None
        self.extra_args: List[str] = []

    def set_source(self, source: Path, language: str = None):
        """Set source file and language for measurement."""
        self.source_path = source
        self.language = language

    def run(self, cmd: List[str], timeout: int = 300) -> ProfileResult:
        # Use stored source/language if available (unified approach)
        if self.source_path and self.language:
            source = str(self.source_path)
            lang = self.language
            # Extract args from the original command (skip interpreter/binary)
            if cmd[0] == "python3":
                args = cmd[2:] if len(cmd) > 2 else []
            elif cmd[0] == "java":
                args = cmd[3:] if len(cmd) > 3 else []  # java -cp dir class args
            else:
                args = cmd[1:] if len(cmd) > 1 else []  # binary args
        else:
            # Fallback: detect from command
            lang, source, args = self._detect_from_cmd(cmd)

        full_cmd = ["codegreen", "measure", lang, source, "--json", "--timeout", str(timeout), *self.extra_args] + args
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}

        start = time.perf_counter()
        result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout + 30, env=env)
        elapsed = time.perf_counter() - start
        # The JSON result is printed on every exit code (exit 3 = invalid measurement); signed energy is kept as reported.
        try:
            raw = json.loads(result.stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"codegreen measure exit {result.returncode} without a JSON result: {result.stderr[-500:]}")
        validity = raw.get("validity")
        if validity is None or result.returncode not in (0, 3):
            detail = {**(validity or {}).get("detail", {}),
                      "MEASURE_FAILED": raw.get("error") or f"codegreen measure exit {result.returncode}"}
            validity = {**(validity or {"warnings": {}}), "status": "invalid", "reasons": list(detail), "detail": detail}
        return ProfileResult((raw.get("summary") or {}).get("total_energy_j"), elapsed, "",
                             raw.get("checkpoints") or [], raw, validity)

    def _detect_from_cmd(self, cmd: List[str]) -> tuple:
        """Fallback: detect language, source, args from command."""
        if cmd[0] == "python3":
            return "python", cmd[1] if len(cmd) > 1 else cmd[0], cmd[2:] if len(cmd) > 2 else []
        elif cmd[0] == "java":
            # java -cp dir class args -> need source from set_source
            return "java", str(self.source_path) if self.source_path else "", cmd[3:] if len(cmd) > 3 else []
        else:
            # Compiled binary
            source = str(self.source_path) if self.source_path else cmd[0]
            lang = "cpp" if (".gpp" in source or "cpp" in source) else "c"
            return lang, source, cmd[1:] if len(cmd) > 1 else []

    def is_available(self) -> bool:
        return shutil.which("codegreen") is not None

class PerfProfiler(ProfilerInterface):
    """perf stat -a over the command: system-wide RAPL energy at the CPU domain set of PERF_CPU_EVENT_SETS, the
    truth source for `codegreen run/measure --sensors rapl`."""
    def __init__(self):
        offered = perf_power_events()
        self.events = next(([e for e in s if e in offered] for s in PERF_CPU_EVENT_SETS if s[0] in offered), [])
        self.repeat_count: int = 1

    def run(self, cmd: List[str], timeout: int = 300) -> ProfileResult:
        body = cmd if self.repeat_count == 1 else [
            "bash", "-c", f"for i in $(seq {self.repeat_count}); do {shlex.join(cmd)}; done"]
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            out = Path(f.name)
        try:
            start = time.perf_counter()
            result = subprocess.run(["perf", "stat", "-a", "-x,", "-e", ",".join(f"power/{e}/" for e in self.events),
                                     "-o", str(out), "--", *body], capture_output=True, text=True, timeout=timeout)
            elapsed = time.perf_counter() - start
            text = out.read_text()
        finally:
            out.unlink()
        if result.returncode:
            raise RuntimeError(f"perf stat exit {result.returncode}: {result.stderr[-500:]}")
        events = {}
        for f in (line.split(",") for line in text.splitlines()):
            if len(f) > 2 and f[2].startswith("power/"):
                if not f[0][:1].isdigit():
                    raise RuntimeError(f"perf could not count {f[2]}: {f[0]}")
                events[f[2][6:-1]] = float(f[0]) / self.repeat_count
        if sorted(events) != sorted(self.events):
            raise RuntimeError(f"perf counted {sorted(events)}, expected {self.events}")
        return ProfileResult(sum(events.values()), elapsed / self.repeat_count, result.stdout, [],
                             {"events_j": events, "repeat_count": self.repeat_count})

    def is_available(self) -> bool:
        return bool(self.events)

    def unavailable_reason(self) -> str:
        return (f"perf offers none of the power events {PERF_CPU_EVENT_SETS} (`perf list power`: "
                f"{perf_power_events() or 'none'}); install perf on a host with a RAPL power PMU")

class NativeProfiler(ProfilerInterface):
    """Runs without energy profiling - for baseline timing."""
    def run(self, cmd: List[str], timeout: int = 300) -> ProfileResult:
        start = time.perf_counter()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        elapsed = time.perf_counter() - start
        return ProfileResult(
            energy_joules=None,
            time_seconds=elapsed,
            output=result.stdout,
            checkpoints=[],
            raw_data={}
        )

    def is_available(self) -> bool:
        return True

class CodeCarbonProfiler(ProfilerInterface):
    """Wraps CodeCarbon for energy measurement (requires: pip install codecarbon)."""
    def run(self, cmd: List[str], timeout: int = 300) -> ProfileResult:
        try:
            from codecarbon import EmissionsTracker
        except ImportError:
            raise RuntimeError("codecarbon not installed")
        tracker = EmissionsTracker(log_level="error", save_to_file=False)
        tracker.start()
        start = time.perf_counter()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        elapsed = time.perf_counter() - start
        emissions = tracker.stop()
        energy = tracker._total_energy.kWh * 3_600_000  # kWh -> J
        return ProfileResult(energy, elapsed, result.stdout, [],
                             {"emissions_kg_co2": emissions, "energy_kwh": tracker._total_energy.kWh})

    def is_available(self) -> bool:
        import importlib.util
        return importlib.util.find_spec("codecarbon") is not None


class JoularJXProfiler(ProfilerInterface):
    """Wraps JoularJX for Java energy measurement (requires JoularJX agent jar)."""
    def __init__(self, agent_path: str = ""):
        self.agent_path = agent_path or self._find_agent()

    def _find_agent(self) -> str:
        for p in [Path("joularjx-agent.jar"), Path.home() / ".joularjx" / "joularjx-agent.jar"]:
            if p.exists():
                return str(p)
        return ""

    def run(self, cmd: List[str], timeout: int = 300) -> ProfileResult:
        if not self.agent_path:
            raise RuntimeError("JoularJX agent not found")
        jx_cmd = cmd.copy()
        if cmd[0] == "java":
            jx_cmd.insert(1, f"-javaagent:{self.agent_path}")
        start = time.perf_counter()
        result = subprocess.run(jx_cmd, capture_output=True, text=True, timeout=timeout)
        elapsed = time.perf_counter() - start
        energy = self._parse_joularjx_output()
        return ProfileResult(energy, elapsed, result.stdout, [], {"agent": self.agent_path})

    def _parse_joularjx_output(self) -> float:
        csv_path = Path("joularJX-all-methods-energy.csv")
        if not csv_path.exists():
            raise RuntimeError(f"JoularJX wrote no {csv_path}")
        total = 0.0
        for line in csv_path.read_text().splitlines()[1:]:
            parts = line.split(",")
            if len(parts) >= 2:
                try:
                    total += float(parts[-1])
                except ValueError:
                    pass
        return total

    def is_available(self) -> bool:
        return bool(self.agent_path) and Path(self.agent_path).exists()


def get_profiler(name: str) -> ProfilerInterface:
    profilers = {
        "codegreen": CodeGreenProfiler,
        "perf": PerfProfiler,
        "native": NativeProfiler,
        "codecarbon": CodeCarbonProfiler,
        "joularjx": JoularJXProfiler,
    }
    if name not in profilers:
        raise ValueError(f"Unknown profiler: {name}. Available: {list(profilers.keys())}")
    return profilers[name]()
