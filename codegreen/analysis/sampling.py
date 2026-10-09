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
from collections import Counter
from pathlib import Path

ASYNC_PROFILER_ENV = "CODEGREEN_ASYNC_PROFILER"
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


def java_agent_option(out_dir: Path, interval_us: int, event: str = "cpu", root: str = "") -> str:
    """-agentpath option sampling into out_dir/<pid>.collapsed; `ann` marks
    JIT-compiled (_[j]) and inlined (_[i]) frames. Use an interval that is not
    a multiple of common timer periods (e.g. 997 us) so samples do not lock
    step with periodic work. The profiled JVM resolves `file=` against its own
    working directory and does not create directories, so the path is made
    absolute here (a relative one silently yields no profile)."""
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    return (f"-agentpath:{async_profiler_lib(root)}=start,event={event},interval={interval_us}us,"
            f"ann,collapsed,file={out_dir}/%p.collapsed")


def is_jmh_jar(path: str) -> bool:
    import zipfile
    with zipfile.ZipFile(path) as z:
        return "Main-Class: org.openjdk.jmh.Main" in z.read("META-INF/MANIFEST.MF").decode(errors="replace")


def java_agent_command(argv: list[str], agent: str, env: dict) -> tuple[list[str], dict]:
    """(argv, env) running `argv` with `agent` loaded where the work runs:
    JMH forks via -jvmArgsAppend, any other JVM via JAVA_TOOL_OPTIONS."""
    jar = argv[argv.index("-jar") + 1] if "-jar" in argv else ""
    if jar and is_jmh_jar(jar):
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
