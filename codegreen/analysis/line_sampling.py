"""Line-level stack sampling behind registered language adapters.

A language is added by registering a LineAdapter (the `lines` component of its codegreen.analysis.languages adapter):
code for how to run and read its sampler, while its frame, library and irreducible patterns, sampler flags, passes and
features are data in config.json languages.<language>.line_sampler. Nothing in this module branches on a language. Every
result is a codegreen.analysis.metrics.MetricRecord, the schema every CodeGreen metric provider shares: key is
"file:function:line" (parts present), the structured location is in detail (file, function, line).

Samples are taken on a profiled run only, never on a measured one. Shares are time-proportional (a line's share
of the run's CPU samples), not energy.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from codegreen.analysis import languages
from codegreen.analysis.metrics import MetricRecord
from codegreen.instrumentation.language_runtimes.python.codegreen_runtime import load_config

PROVIDER = "line_sampler"


def metric(name: str, unit: str, scope: str, value: Optional[float], *, key: Optional[dict] = None, share: Optional[float] = None,
           lift: Optional[float] = None, available: bool = True, reason: str = "", detail: Optional[dict] = None) -> MetricRecord:
    """A MetricRecord whose location (file, function, line) is in detail and joined into key."""
    loc = key or {}
    return MetricRecord(name, unit, scope, ":".join(str(loc[k]) for k in ("file", "function", "line") if loc.get(k) is not None),
                        value, PROVIDER, share=share, lift=lift, detail={**loc, **(detail or {})}, available=available, reason=reason)


def unavailable(name: str, unit: str, scope: str, reason: str) -> MetricRecord:
    return metric(name, unit, scope, None, available=False, reason=reason)


def settings(language: str, options: Optional[dict] = None) -> dict:
    """config.json languages.<language>.line_sampler, overridden by the caller's options (e.g. binary)."""
    return {**load_config()["languages"][language]["line_sampler"], **(options or {})}


@dataclass(frozen=True)
class LineAdapter:
    """One language's line sampler. record builds the (argv, env) of a profiled run writing to `out` (a file or a
    directory, as the sampler writes); read returns the collapsed stack files ('frame;frame;... count', outermost first)
    of that output; inspect reports the sampler's capability. Each receives the language's settings (with the caller's
    options). alloc builds (argv, env) of an allocation-tracing run, None when the language has none."""
    language: str
    record: Callable[[list[str], Path, int, list[str], dict, dict], tuple[list[str], dict]]   # (argv, out, rate_hz, flags, settings, env)
    read: Callable[[Path, dict], list[Path]]
    inspect: Callable[[dict], dict]          # settings -> {"available", "version", "flags": {feature or pass: bool}, "reason"}
    alloc: Optional[Callable[[list[str], Path, dict], tuple[list[str], dict]]] = None

    def probe(self, options: Optional[dict] = None) -> dict:
        return self.inspect(settings(self.language, options))


def register(adapter: LineAdapter) -> LineAdapter:
    languages.add(adapter.language, lines=adapter)
    return adapter


def adapter(language: str) -> LineAdapter:
    try:
        return languages.component(language, "lines")
    except KeyError as e:
        raise ValueError(str(e)) from e


def command(language: str, argv: list[str], out: Path, rate_hz: Optional[int], options: dict, pass_name: str = "cpu",
            env: Optional[dict] = None) -> tuple[list[str], dict]:
    """(argv, env) of one profiled run: the always-on flags, the in-run features switched on in options and the flags
    of pass_name ('cpu' = none); rate_hz None takes the configured rate."""
    a, s = adapter(language), settings(language, options)
    if pass_name != "cpu" and pass_name not in s["pass_flags"]:
        raise ValueError(f"{language} sampler has no pass {pass_name!r}; known: {sorted(s['pass_flags'])}")
    flags = [*s["flags"], *(f for name, fl in s["feature_flags"].items() if s.get(name) for f in fl), *s["pass_flags"].get(pass_name, [])]
    return a.record(list(argv), Path(out), int(rate_hz or s["rate_hz"]), flags, s, dict(os.environ if env is None else env))


def read(language: str, out: Path, options: Optional[dict] = None) -> list[Path]:
    """The collapsed stack files of a profiled run's output."""
    return adapter(language).read(Path(out), settings(language, options))


def capabilities(language: str, options: dict) -> dict:
    """The adapter's probe plus one unavailability record per requested feature or pass the sampler lacks."""
    s = settings(language, options)
    cap = adapter(language).probe(options)
    wanted = [n for n in s["feature_flags"] if options.get(n)] + [p for p in options.get("passes", []) if p != "cpu"]
    flags = {**s["feature_flags"], **s["pass_flags"]}
    cap["unavailable"] = {n: ("sampler not available: " + cap["reason"]) if not cap["available"] else f"sampler lacks {' '.join(flags.get(n, [n]))}"
                          for n in wanted if not cap["available"] or not cap["flags"].get(n)}
    return cap


def frame_parser(language: str) -> Callable[[str], Optional[tuple[str, str, Optional[int]]]]:
    """Collapsed frame -> (file, function, line) by the language's frame_re (groups file, func, optional line; line 0
    is None), file rewritten by file_replace; None for a frame frame_re does not match (native)."""
    s = settings(language)
    fr, rewrite = re.compile(s["frame_re"]), s.get("file_replace", {})

    def parse_frame(raw: str):
        m = fr.fullmatch(raw)
        if not m:
            return None
        path = m["file"]
        for a, b in rewrite.items():
            path = path.replace(a, b)
        return path, m["func"], int(m["line"] or 0) or None
    return parse_frame


Frame = tuple[str, str, str, Optional[int]]   # (kind project|library|native, file, function, line)


def parse(language: str, text: str, project_root: str) -> list[tuple[list[Frame], int]]:
    """Collapsed stacks ('frame;frame;... count', outermost first) as classified frames."""
    frame, lib = frame_parser(language), re.compile(settings(language)["library_re"])
    root = str(Path(project_root).resolve())
    out = []
    for row in text.splitlines():
        stack, _, count = row.rpartition(" ")
        if not stack:
            continue
        frames: list[Frame] = []
        for raw in stack.split(";"):
            f = frame(raw)
            if f is None:
                frames.append(("native", "", raw, None))
                continue
            inside = str(Path(root, f[0]).resolve()).startswith(root + "/")
            frames.append(("library" if lib.search(f[0]) or not inside else "project", *f))
        out.append((frames, int(count)))
    return out


def line_profile(language: str, paths: list[Path], project_root: str) -> dict:
    """Per-line and per-function CPU samples of the project's frames over every recording, as common-schema records:
    {"samples": N, "lines": [...], "functions": [...], "run": [...], "call_sites": [...]}.
    A line or function record's value is its self samples (leaf frame), detail.total_samples its inclusive samples
    (once per stack). Run records split the samples by leaf kind (project, library, native) and give the irreducible
    share (leaf frame matching the language's irreducible_re; unavailable when it declares none). A call site is a
    project frame whose direct callee is a frame of another function, its samples all those beneath the call."""
    if not paths:
        raise ValueError("no line-sampler recording: the sampler wrote nothing")
    pattern = settings(language).get("irreducible_re")
    irr = re.compile(pattern) if pattern else None
    own, total, fself, ftotal, sites, kinds = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
    irreducible = samples = 0
    for p in paths:
        for frames, n in parse(language, Path(p).read_text(), project_root):
            samples += n
            leaf = frames[-1]
            kinds[leaf[0]] += n
            irreducible += n * bool(irr and leaf[0] != "project" and irr.search(f"{leaf[2]} {leaf[1]}"))
            proj = [f for f in frames if f[0] == "project"]
            if leaf[0] == "project":
                own[leaf[1:]] += n
                fself[leaf[1:3]] += n
            for k in {f[1:] for f in proj}:
                total[k] += n
            for k in {f[1:3] for f in proj}:
                ftotal[k] += n
            for k in {(a[1], a[2], a[3], b[1], b[2]) for a, b in zip(frames, frames[1:]) if a[0] == "project" and a[1:3] != b[1:3]}:
                sites[k] += n
    if samples == 0:
        raise ValueError(f"no samples in {[str(p) for p in paths]}")

    def pct(n: int) -> float:
        return round(100.0 * n / samples, 3)
    return {"samples": samples,
            "lines": [metric("cpu_samples", "samples", "line", own[k], key={"file": k[0], "function": k[1], "line": k[2]}, share=pct(own[k]),
                             detail={"total_samples": total[k]}) for k in sorted(total, key=lambda k: (-own[k], -total[k], k[0], k[1], k[2] or 0))],
            "functions": [metric("cpu_samples", "samples", "function", fself[k], key={"file": k[0], "function": k[1]}, share=pct(fself[k]),
                                 detail={"total_samples": ftotal[k]}) for k in sorted(ftotal, key=lambda k: (-fself[k], k))],
            "run": [*(metric(f"{kind}_leaf_samples", "samples", "run", kinds[kind], share=pct(kinds[kind])) for kind in ("project", "library", "native")),
                    metric("irreducible_leaf_samples", "samples", "run", irreducible, share=pct(irreducible)) if irr else
                    unavailable("irreducible_leaf_samples", "samples", "run", f"no irreducible_re declared for {language}")],
            "call_sites": [{"file": k[0], "function": k[1], "line": k[2], "callee_file": k[3], "callee_function": k[4], "samples": n}
                           for k, n in sorted(sites.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1], kv[0][2] or 0))]}


def pass_ratio(language: str, num: list[Path], num_s: float, den: list[Path], den_s: float, project_root: str, name: str) -> list[MetricRecord]:
    """Per function, the rate of its inclusive samples in a numerator pass over the rate in a denominator pass, each per
    second of that pass's run (two separate profiled runs; e.g. on-CPU over on-stack-including-idle = on-CPU fraction).
    The value is the raw ratio: sampling noise between the runs can put it above 1, which detail.above_one flags (a
    consumer bounding a fraction clips it itself). A function absent from the denominator pass has no record."""
    if num_s <= 0 or den_s <= 0:
        raise ValueError(f"pass durations must be positive, got {num_s}, {den_s}")
    a = {(r.detail["file"], r.detail["function"]): r.detail["total_samples"] for r in line_profile(language, num, project_root)["functions"]}
    b = {(r.detail["file"], r.detail["function"]): r.detail["total_samples"] for r in line_profile(language, den, project_root)["functions"]}
    out = []
    for k, n in sorted(b.items()):
        if n:
            ratio = (a.get(k, 0) / num_s) / (n / den_s)
            out.append(metric(name, "ratio", "function", round(ratio, 4), key={"file": k[0], "function": k[1]},
                              detail={"numerator_samples": a.get(k, 0), "denominator_samples": n, "above_one": ratio > 1.0}))
    return out


def read_alloc(path: Path) -> list[MetricRecord]:
    """Line records of an allocation-tracing run's JSON ({"top": [{file, line, size_b, count}], "total_b"}): value = the line's
    peak live bytes over the run's snapshots, share = its part of the sum of per-line peaks."""
    data = json.loads(Path(path).read_text())
    total = data["total_b"]
    return [metric("alloc_bytes", "bytes", "line", t["size_b"], key={"file": t["file"], "line": t["line"]},
                   share=round(100.0 * t["size_b"] / total, 3) if total else None, detail={"blocks": t["count"]}) for t in data["top"]]


# Python: py-spy (record --format raw: 'func (file:line);... count'). Allocation hot spots come from a tracemalloc run
# (codegreen.analysis.pyalloc) of the same command.
def _pyspy_record(argv: list[str], out: Path, rate_hz: int, flags: list[str], s: dict, env: dict) -> tuple[list[str], dict]:
    return [os.path.expanduser(s["binary"]), *s["record"], "--rate", str(rate_hz), *flags, "-o", str(out), "--", *argv], env


def _pyspy_read(out: Path, s: dict) -> list[Path]:
    if not out.is_file():
        raise FileNotFoundError(f"{out}: py-spy wrote no recording")
    return [out]


def _pyspy_inspect(s: dict) -> dict:
    binary = shutil.which(os.path.expanduser(s["binary"]))
    if not binary:
        return {"available": False, "version": "", "flags": {}, "reason": f"py-spy binary {s['binary']!r} not on PATH"}
    version = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
    help_text = subprocess.run([binary, "record", "--help"], capture_output=True, text=True, timeout=30).stdout
    return {"available": True, "version": version, "reason": "",
            "flags": {n: all(f in help_text for f in fl) for n, fl in {**s["feature_flags"], **s["pass_flags"]}.items()}}


def _pyalloc(argv: list[str], out: Path, options: dict) -> tuple[list[str], dict]:
    """The workload's own interpreter (the first argv word matching interpreter_re, so launchers such as `uv run` or
    `taskset` stay in front) runs the rest under tracemalloc; codegreen is put on its path."""
    s = settings("python", options)
    py = re.compile(s["interpreter_re"])
    i = next((i for i, w in enumerate(argv) if py.fullmatch(Path(w).name)), None)
    if i is None:
        raise ValueError(f"allocation tracing needs a Python interpreter in the workload command (interpreter_re "
                         f"{s['interpreter_re']!r}), got {argv}")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(x for x in (str(Path(__file__).resolve().parents[2]), os.environ.get("PYTHONPATH", "")) if x)}
    return [*argv[:i + 1], "-m", "codegreen.analysis.pyalloc", "--out", str(out), "--frames", str(int(s["alloc_frames"])),
            "--top", str(int(s["alloc_top"])), "--interval", str(float(s["alloc_interval_s"])), "--", *argv[i + 1:]], env


register(LineAdapter("python", _pyspy_record, _pyspy_read, _pyspy_inspect, _pyalloc))


if __name__ == "__main__":   # capability probe: python -m codegreen.analysis.line_sampling <language>
    lang = sys.argv[1] if len(sys.argv) > 1 else "python"
    s = settings(lang)
    print(json.dumps(capabilities(lang, {**dict.fromkeys(s["feature_flags"], True), "passes": list(s["pass_flags"])}), indent=1))
