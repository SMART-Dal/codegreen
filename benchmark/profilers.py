"""Energy profiler interfaces for CodeGreen and perf RAPL."""
import json
import re
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

@dataclass
class ProfileResult:
    energy_joules: float
    time_seconds: float
    output: str
    checkpoints: List[Dict[str, Any]]
    raw_data: Dict[str, Any]

class ProfilerInterface(ABC):
    @abstractmethod
    def run(self, cmd: List[str], timeout: int = 300) -> ProfileResult:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

class CodeGreenProfiler(ProfilerInterface):
    """Uses codegreen measure CLI for energy measurement.

    Unified approach for all languages:
    1. Pass source file to codegreen measure
    2. CLI instruments source code
    3. CLI compiles (if needed) and runs instrumented code
    4. Energy measured via NEMB checkpoints
    """
    def __init__(self):
        self.source_path: Path | None = None
        self.language: str | None = None

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

        import os
        full_cmd = ["codegreen", "measure", lang, source, "--json", "--timeout", str(timeout)] + args
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}

        start = time.perf_counter()
        result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout + 30, env=env)
        elapsed = time.perf_counter() - start

        energy, checkpoints, raw, program_output = self._parse_output(result.stdout)
        return ProfileResult(energy_joules=energy, time_seconds=elapsed, output=program_output, checkpoints=checkpoints, raw_data=raw)

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

    def _parse_output(self, stdout: str) -> tuple:
        energy, checkpoints, raw, program_output = 0.0, [], {}, ""
        try:
            raw = json.loads(stdout)
        except (json.JSONDecodeError, ValueError):
            return energy, checkpoints, raw, stdout
        measurement = raw.get("measurement", {})
        raw_output = measurement.get("output", "")
        # Program output is between NEMB init (ends with "Measurements started")
        # and CODEGREEN_RESULT markers. Extract that region.
        lines = raw_output.splitlines()
        start_idx = 0
        end_idx = len(lines)
        for i, line in enumerate(lines):
            if "Measurements started" in line:
                start_idx = i + 1
            if "CODEGREEN_RESULT_START" in line:
                end_idx = i
                break
        program_output = "\n".join(l for l in lines[start_idx:end_idx] if l.strip())
        if measurement.get("success"):
            checkpoints = measurement.get("checkpoints", [])
            if len(checkpoints) >= 2:
                energy = checkpoints[-1].get("joules", 0) - checkpoints[0].get("joules", 0)
        return energy, checkpoints, raw, program_output

    def is_available(self) -> bool:
        return True

class PerfProfiler(ProfilerInterface):
    def __init__(self):
        self.perf_output_file: Path | None = None
        self._events = self._detect_events()

    def __del__(self):
        self._cleanup()

    def _detect_events(self) -> str:
        try:
            result = subprocess.run(["perf", "list", "power"], capture_output=True, text=True, timeout=5)
            events = []
            if "energy-pkg" in result.stdout:
                events.append("power/energy-pkg/")
            if "energy-ram" in result.stdout:
                events.append("power/energy-ram/")
            return ",".join(events) if events else "power/energy-pkg/"
        except Exception:
            return "power/energy-pkg/"

    def run(self, cmd: List[str], timeout: int = 300) -> ProfileResult:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            self.perf_output_file = Path(f.name)
        full_cmd = ["perf", "stat", "-e", self._events, "-o", str(self.perf_output_file), "--"] + cmd
        start = time.perf_counter()
        result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
        elapsed = time.perf_counter() - start
        energy = self._parse_perf_output()
        return ProfileResult(
            energy_joules=energy,
            time_seconds=elapsed,
            output=result.stdout,
            checkpoints=[],
            raw_data={"perf_output": self.perf_output_file.read_text() if self.perf_output_file.exists() else ""}
        )

    def _parse_perf_output(self) -> float:
        if not self.perf_output_file or not self.perf_output_file.exists():
            return 0.0
        content = self.perf_output_file.read_text()
        total = 0.0
        pkg_match = re.search(r'([\d.,]+)\s+Joules\s+power/energy-pkg/', content)
        if pkg_match:
            total += float(pkg_match.group(1).replace(',', ''))
        ram_match = re.search(r'([\d.,]+)\s+Joules\s+power/energy-ram/', content)
        if ram_match:
            total += float(ram_match.group(1).replace(',', ''))
        return total

    def _cleanup(self):
        if self.perf_output_file and self.perf_output_file.exists():
            try:
                self.perf_output_file.unlink()
            except OSError:
                pass
            self.perf_output_file = None

    def is_available(self) -> bool:
        try:
            result = subprocess.run(["perf", "list", "power"], capture_output=True, text=True, timeout=5)
            return "energy-pkg" in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

class NativeProfiler(ProfilerInterface):
    """Runs without energy profiling - for baseline timing."""
    def run(self, cmd: List[str], timeout: int = 300) -> ProfileResult:
        start = time.perf_counter()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        elapsed = time.perf_counter() - start
        return ProfileResult(
            energy_joules=0.0,
            time_seconds=elapsed,
            output=result.stdout,
            checkpoints=[],
            raw_data={}
        )

    def is_available(self) -> bool:
        return True

def get_profiler(name: str) -> ProfilerInterface:
    profilers = {
        "codegreen": CodeGreenProfiler,
        "perf": PerfProfiler,
        "native": NativeProfiler,
    }
    if name not in profilers:
        raise ValueError(f"Unknown profiler: {name}. Available: {list(profilers.keys())}")
    return profilers[name]()
