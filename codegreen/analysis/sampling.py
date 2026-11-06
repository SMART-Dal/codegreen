"""Stack-sampling profiles as a second, low-overhead hotspot signal.

CodeGreen's per-method attribution instruments every method entry and exit.
Probes add fixed work per call and stop the JIT from inlining the probed
method, so short methods called very often look hotter than they are; stack
sampling at an odd rate perturbs neither (Gregg, "CPU Flame Graphs").

Java uses async-profiler (AsyncGetCallTrace + perf_events; no
-XX:+PreserveFramePointer needed), one collapsed file per process (`%p`).
`java_agent_command` injects the agent: a JMH jar gets it through JMH's
-jvmArgsAppend so only the measured forks load it (through JAVA_TOOL_OPTIONS
the fork received it twice, env plus the launcher's own JVM arguments, and the
second load aborted the fork); any other JVM gets JAVA_TOOL_OPTIONS.
Shares are time-proportional: a method's share of CPU samples, not of energy;
for a compute-bound pinned workload package power is near constant, so a
share times the run's measured energy is a time-proportional estimate.
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from codegreen.analysis import languages
from codegreen.instrumentation.language_runtimes.python.codegreen_runtime import load_config

ASYNC_PROFILER_ENV = "CODEGREEN_ASYNC_PROFILER"
TIME_EVENTS = ("cpu", "wall", "itimer")   # async-profiler events whose interval is time; any other is a perf event count
_ANNOT = re.compile(r"_\[([jiIk0-9]+)\]$")


def async_profiler_lib(root: str = "") -> Path:
    """libasyncProfiler.so in the async-profiler release directory `root`
    (default: $CODEGREEN_ASYNC_PROFILER)."""
    root = root or os.environ.get(ASYNC_PROFILER_ENV, "")
    if not root:
        raise RuntimeError(f"no async-profiler directory: pass one or set {ASYNC_PROFILER_ENV}")
    lib = Path(root) / "lib" / "libasyncProfiler.so"
    if not lib.is_file():
        raise FileNotFoundError(f"{lib} not found ({ASYNC_PROFILER_ENV}={root})")
    return lib


def java_agent_option(out_dir: Path, interval: int, event: str = "cpu", root: str = "") -> str:
    """-agentpath option sampling `event` into out_dir/<pid>.collapsed; `ann` marks
    JIT-compiled (_[j]) and inlined (_[i]) frames. `interval` is microseconds for
    a time event (TIME_EVENTS) and occurrences for a perf event (cache-misses,
    ...), which async-profiler's perf_events mode samples with JIT frames that
    perf alone cannot resolve. Use an interval that is not a multiple of common
    timer periods (e.g. 997 us) so samples do not lock step with periodic work.
    The profiled JVM resolves `file=` against its own working directory and does
    not create directories, so the path is made absolute here (a relative one
    silently yields no profile)."""
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    return (f"-agentpath:{async_profiler_lib(root)}=start,event={event},interval={int(interval)}"
            f"{'us' if event in TIME_EVENTS else ''},ann,collapsed,file={out_dir}/%p.collapsed")


def is_jmh_jar(path: str) -> bool:
    import zipfile
    with zipfile.ZipFile(path) as z:
        return "Main-Class: org.openjdk.jmh.Main" in z.read("META-INF/MANIFEST.MF").decode(errors="replace")


def java_agent_command(argv: list[str], agent: str, env: dict) -> tuple[list[str], dict]:
    """(argv, env) running `argv` with `agent` loaded where the work runs:
    JMH forks via -jvmArgsAppend, any other JVM via JAVA_TOOL_OPTIONS."""
    jar = argv[argv.index("-jar") + 1] if "-jar" in argv else ""
    if jar and is_jmh_jar(jar):
        # JMH splits one -jvmArgsAppend value on spaces but passes a second occurrence's values unsplit, so the fork gets
        # "-Xms4g -Xmx4g" as one token, cannot start, and JMH still exits 0: merge into the existing value instead.
        if "-jvmArgsAppend" in argv:
            i = argv.index("-jvmArgsAppend") + 1
            return [*argv[:i], f"{argv[i]} {agent}", *argv[i + 1:]], dict(env)
        return [*argv, "-jvmArgsAppend", agent], dict(env)
    return list(argv), {**env, "JAVA_TOOL_OPTIONS": " ".join(x for x in (env.get("JAVA_TOOL_OPTIONS", ""), agent) if x)}


def _frame(raw: str) -> tuple[str, bool]:
    """('pkg.Class.method', inlined) from a collapsed frame."""
    m = _ANNOT.search(raw)
    name = raw[:m.start()] if m else raw
    return name.replace("/", "."), bool(m and m.group(1) == "i")


def parse_collapsed(paths: list[Path]) -> dict:
    """Per-method sample shares over every collapsed file:
    {"samples": N, "methods": {name: {"self_pct", "total_pct", "inlined_pct"}}}.
    self = leaf frame; total = anywhere on the stack (counted once per stack);
    inlined_pct = share of the method's stack appearances where it ran inlined."""
    if not paths:
        raise ValueError("no collapsed profile files: the agent wrote nothing "
                         "(not loaded into the measured JVM, or its file= path was not writable there)")
    self_n, total_n, seen_n, inlined_n = Counter(), Counter(), Counter(), Counter()
    samples = 0
    for p in paths:
        for line in Path(p).read_text().splitlines():
            stack, _, count = line.rpartition(" ")
            if not stack:
                continue
            n = int(count)
            samples += n
            frames = [_frame(f) for f in stack.split(";")]
            self_n[frames[-1][0]] += n
            for name in {f for f, _ in frames}:
                total_n[name] += n
            for name, inl in frames:
                seen_n[name] += n
                inlined_n[name] += n * inl
    if samples == 0:
        raise ValueError(f"no samples in {[str(p) for p in paths]}")
    return {"samples": samples, "methods": {
        name: {"self_pct": 100.0 * self_n[name] / samples, "total_pct": 100.0 * total_n[name] / samples,
               "inlined_pct": 100.0 * inlined_n[name] / seen_n[name]}
        for name in total_n}}


def monotonic_minus_realtime_ns() -> int:
    """CLOCK_MONOTONIC minus CLOCK_REALTIME in ns, from two sandwiched reads:
    add it to a wall-clock sample time (JFR startTime) to put the sample on
    NEMB's time-series clock (t_ns is CLOCK_MONOTONIC). Taken once per run."""
    import time
    m0 = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
    r = time.time_ns()
    m1 = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
    return (m0 + m1) // 2 - r


def energy_by_method(samples: list[tuple[int, tuple[str, ...]]],
                     series: list[tuple[int, float]]) -> dict:
    """Per-method energy from timestamped stack samples and a cumulative
    energy series on the same clock (NEMB time series: t_ns, energy_j).

    Each series interval's energy is split equally across the CPU samples
    that fall in it (a fixed-interval sampler gives each sample equal CPU
    time, so concurrent threads share the package energy of the interval);
    self energy goes to the leaf frame, total energy once to every distinct
    frame of the stack. Intervals without samples are reported as
    unattributed rather than dropped, so methods + unattributed = measured.
    `frames` is leaf-last."""
    series = sorted(series)
    if len(series) < 2:
        raise ValueError("energy series needs at least two readings")
    t0, t1 = series[0][0], series[-1][0]
    inside = sorted((t, f) for t, f in samples if t0 <= t < t1)
    if samples and not inside:
        raise ValueError("no sample falls inside the energy series: clocks not aligned")
    self_j: dict[str, float] = {}
    total_j: dict[str, float] = {}
    unattributed, i = 0.0, 0
    for k in range(len(series) - 1):
        (_, ea), (tb, eb) = series[k], series[k + 1]
        j = i
        while j < len(inside) and inside[j][0] < tb:
            j += 1
        if j == i:
            unattributed += eb - ea
            continue
        share = (eb - ea) / (j - i)
        for _, frames in inside[i:j]:
            self_j[frames[-1]] = self_j.get(frames[-1], 0.0) + share
            for name in set(frames):
                total_j[name] = total_j.get(name, 0.0) + share
        i = j
    return {"energy_j": series[-1][1] - series[0][1], "unattributed_j": unattributed,
            "samples_used": len(inside), "samples_outside": len(samples) - len(inside),
            "methods": {n: {"self_j": self_j.get(n, 0.0), "total_j": total_j[n]} for n in total_j}}


# --- Event samplers (the `events` component of a language adapter, codegreen.analysis.languages) ---------------------
# How to sample an event (a CPU timer or a hardware event) with call stacks, where the collapsed stacks land, and how a
# collapsed frame normalizes to (scope, name, line). Metric providers (metrics.py) attribute their events through these,
# so a language gets every provider's function shares by registering one event sampler.

_OFFSET = re.compile(r"\+0x[0-9a-f]+$")
_PYPERF = re.compile(r"py::(?P<func>[^:]+):(?P<file>.+)")
Frame = Optional[tuple[str, str, Optional[int]]]


def perf_record_argv(argv: list[str], event: str, period: int, out: Path, perf: str) -> list[str]:
    """`perf record` sampling `event` every `period` occurrences with call stacks into `out`."""
    return [perf, "record", "-e", event, "-c", str(int(period)), "-g", "-o", str(out), "--", *argv]


def parse_perf_script(text: str) -> Counter:
    """{root-first frame tuple: samples} from `perf script -F comm,period,event,ip,sym`: a header line per sample
    (comm, period, event:) then its frames leaf first ('ip sym+0xoff'), a blank line between samples. Weights are sample
    counts, as in async-profiler's collapsed output, so every backend's stacks share one unit (each sample stands for the
    recording's fixed period of events). A header without an integer period means the output is not in the requested
    format and raises; a sample without frames is kept as an [unknown] stack, so no sample's weight is lost."""
    out: Counter = Counter()
    head, frames = None, []
    for line in [*text.splitlines(), ""]:
        if not line.strip():
            if head is not None:
                out[tuple(reversed(frames)) or ("[unknown]",)] += 1
            head, frames = None, []
        elif line[0].isspace():
            frames.append(_OFFSET.sub("", line.strip().partition(" ")[2].strip() or "[unknown]"))
        elif not any(t.isdigit() for t in line.split()):
            raise ValueError(f"perf script sample header without an integer period: {line!r}")
        else:
            head = line
    return out


def perf_script_to_collapsed(perf_data: Path, out: Path, perf: str) -> Path:
    """`perf script` of a recording written as collapsed stacks (root first, sample counts) to `out`."""
    argv = [perf, "script", "-F", "comm,period,event,ip,sym", "-i", str(perf_data)]
    p = subprocess.run(argv, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"{shlex.join(argv)} exited {p.returncode}: {p.stderr.strip()[-300:]}")
    stacks = parse_perf_script(p.stdout)
    if not stacks:
        raise ValueError(f"{perf_data}: perf recorded no samples")
    Path(out).write_text("".join(f"{';'.join(fr)} {n}\n" for fr, n in stacks.items()))
    return Path(out)


@dataclass(frozen=True)
class EventSampler:
    command: Callable[[list[str], dict, Path, str, int], tuple[list[str], dict]]   # (argv, env, out_dir, event, period)
    read: Callable[[Path], list[Path]]                                             # out_dir -> collapsed files
    frames: Callable[[], Callable[[str], Frame]]                                   # -> collapsed frame -> (scope, name, line)


def register_backend(language: str, backend: EventSampler) -> EventSampler:
    languages.add(language, events=backend)
    return backend


def backend_for(language: str) -> EventSampler:
    return languages.component(language, "events")


def event_languages() -> list[str]:
    """Languages with a registered event sampler."""
    return languages.supporting("events")


def sampled_stacks(language: str, files: list[Path]) -> list[tuple[tuple, float]]:
    """Normalized stacks [(frames root first, weight)] of a backend's collapsed files; frames the backend does not
    recognize are kept as ("", raw, None) so a stack's weight is never lost."""
    norm = backend_for(language).frames()
    out = []
    for p in files:
        for line in Path(p).read_text().splitlines():
            stack, _, count = line.rpartition(" ")
            if stack:
                out.append((tuple(norm(f) or ("", f, None) for f in stack.split(";")), float(count)))
    return out


def _perf_backend(env_extra: dict, frame: Callable[[str], Frame]) -> EventSampler:
    """perf record with call stacks, through the perf binary of config hw_counters.perf."""
    def command(argv, env, out_dir, event, period):
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        return perf_record_argv(argv, event, period, Path(out_dir) / "perf.data", load_config()["hw_counters"]["perf"]), {**env, **env_extra}

    def read(out_dir):
        return [perf_script_to_collapsed(Path(out_dir) / "perf.data", Path(out_dir) / "perf.collapsed", load_config()["hw_counters"]["perf"])]
    return EventSampler(command, read, lambda: frame)


def _python_perf_frame(raw: str) -> Frame:
    m = _PYPERF.fullmatch(raw)
    return (m["file"], m["func"], None) if m else None


def _java_frames() -> Callable[[str], Frame]:
    from codegreen.analysis import line_sampling   # the Java frame grammar is data of its line sampler (config.json)
    return line_sampling.frame_parser("java")


register_backend("java", EventSampler(
    lambda argv, env, out_dir, event, period: java_agent_command(
        argv, java_agent_option(out_dir, period, event, root=env.get(ASYNC_PROFILER_ENV, "")), env),
    lambda out_dir: sorted(Path(out_dir).glob("*.collapsed")), _java_frames))
register_backend("python", _perf_backend({"PYTHONPERFSUPPORT": "1"}, _python_perf_frame))   # CPython >= 3.12 perf trampoline
register_backend("native", _perf_backend({}, lambda raw: ("", raw, None)))
