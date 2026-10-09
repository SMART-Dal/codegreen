# Changelog

For the latest release notes, see [GitHub Releases](https://github.com/SMART-Dal/codegreen/releases).

## v0.4.9 (Current)

### Per-function attribution: frames close on every exit path

- Work inside `return <expr>` and in functions without a trailing return is now attributed to the function. Each language closes the frame after the value exists, through `instrumentation_config.exit_strategy`:
    - Python, Java, JavaScript: `try`/`finally` wraps the body (one atomic edit), so early returns, exceptions and fall-through all close the frame.
    - C++: an RAII `CodeGreen::Frame` guard whose destructor emits the exit.
    - C: each `return v;` is rewritten to `{ T tmp = v; exit; return tmp; }` using the declared return type, which also works on unbraced bodies.
- Function names are qualified in all languages (`Class.method`, `Outer.Inner.method`, namespaces), for enter and exit probes alike. Python methods without a trailing return and Java void methods and constructors previously exited under an unqualified name.
- Java and JavaScript lambdas and arrow functions no longer emit the enclosing method's exit.
- Refused constructs are reported, not instrumented: async functions, generators and coroutines (frames would interleave), C++ `constexpr`/`consteval` functions, and C functions with an unspellable return type (inline struct/enum, function pointer) or that call a same-file macro containing `return`. They appear in `skipped_functions` (`AnalysisResult.metadata` and `codegreen project --json`).
- New `BraceNormaliser` pre-pass gives every unbraced `if`/`else`/loop body in brace languages a block (configured per language by `non_braced_body_parents`), so every probe site sits inside a braced scope. The normalised source is what gets instrumented.
- One-line function bodies (`def f(n): return f(n - 1) if n > 0 else 0`, `a; b` suites, `int f() { return 1; }`, JavaScript and C++ one-line methods) are framed like any other function: the normalisation pre-pass moves the body's statements, and a brace body's closing brace, onto their own lines before analysis (whitespace, `;` separators and line breaks only). `instrument_code` derives the normalised source itself when `pre_normalised_source` is omitted. A function that still cannot hold a frame is listed in `skipped_functions` instead of being dropped, and so are named JavaScript arrow functions, function expressions and generator declarations, which no query instruments.
- Fixed probes misplaced in non-ASCII sources (byte offsets were used as string indexes), JavaScript enter probes placed before the signature, the runtime import placed above `from __future__` imports (left the whole file uninstrumented), and orphan exits for single-line Java and C methods.
- Call graph (`codegreen.analysis.cfg.callgraph`) now supports Python in addition to Java, with typed edges and confidence scores. A mixed-language file set is refused.

### `codegreen project`

- `--source-glob` is repeatable (multi-package projects). The `**/` prefix was stripped as a character set, so `**/*.java` became `.java` and only worked through a silent instrument-everything fallback; it now uses `removeprefix`. Absolute patterns inside the project are taken relative to it.
- `--sync-device cuda` (Python): drains the device before every probe timestamp so a frame owns the GPU work it launched. Kernel launches are asynchronous, so without it GPU energy lands outside every function. Costs one device drain per probe (no CPU/GPU overlap), fails if no synchronisation ran, and is off by default.
- `--min-attribution-pct` (default 25.0): floor for `attribution_pct`. Below it the output carries `attribution_warning` (`code: LOW_ATTRIBUTION`, `attribution_pct`, `floor_pct`, `sync_device`, `message`).
- New output fields: `attribution_pct`, `attribution_warning`, `sync_device`, `skipped_functions`; per-run `checkpoints_run<N>.sum` aggregates are saved next to the checkpoint files under `--output`.
- Instrumented sources are backed up to `.codegreen_backup/` and restored at the start of the next run if an earlier run was interrupted. SIGTERM and SIGHUP restore the originals before exiting.
- Java runtime: one daemon poller thread publishes the RAPL counter (`codegreen.rapl.poll_us`, default 1000) instead of a sysfs read on every enter/exit (about 80 ns per instrumented call pair). Per-JVM aggregates go to a per-run file instead of `System.err`, which JMH forks can close before the shutdown hook runs.
- Python and C/C++ projects now measure energy through the NEMB backend (previously 0 J and no checkpoints on every NEMB-backed language; only Java worked).

### `codegreen run`

- `--validate/--no-validate` and `--validate-timeout` (default 300 s) control the unmeasured validation run. `--timeout` sets a per-run limit.
- `--stdin <file>` binds a file as the subprocess stdin on every repeat (cat, hash, ETL workloads) while keeping N-run statistics and `--budget` gating.

### `codegreen measure`

- New `instrumentation_audit` block in `--json` output (`prospects_detected`, `fine_runtime_checkpoints`, `fallback_to_coarse`, optional `warning`).
- A fine-granularity run that captures fewer than two checkpoints (work at module level or in child processes) is re-measured at coarse granularity so the report carries whole-program energy instead of 0 J. A crashed run is not re-run and reports its error.
- Failed or checkpoint-less runs set `error` in the JSON, naming the traceback or error line.

### Continuous monitor and telemetry export

- New `codegreen.Monitor` Python class and `codegreen monitor` CLI sample host energy without launching a workload. JSONL output, file rotation (`--rotate-mb`), in-memory cap (`--max-in-memory`), distinct-label cap (`--max-labels`, overflow collapses into `__other__`), SIGHUP hot-reload of `monitor.*` config. Sampling intervals below 50 ms raise `ValueError` (RAPL noise floor). In run-forever mode (no `--duration`), intervals below 100 ms emit a `RuntimeWarning` about sampling overhead.
- Per-PID attribution via `--pid` with `cgroup_v2` (preferred), `cgroup_v1` and `cpu_percent` (last resort) backends. `--attribution-mode` selects one, `auto` picks the most accurate available. `attribution_backend` appears on every sample header and the summary record.
- Per-request attribution: `codegreen.annotate_request` context manager and `codegreen monitor --listen-on-socket /path/to.sock`. Each label becomes a `per_label` bucket in the summary (count, total_joules, p50_ms, p95_ms). Events are dropped when the socket is unreachable so middleware never blocks a request.
- OTLP and Prometheus exporters: `--exporter otlp|prometheus` (repeatable), `--otlp-endpoint`, `--prometheus-port`, `--prometheus-listen-addr`. Install with `pip install codegreen[otlp]` or `codegreen[prometheus]`; a missing dependency fails at start. Prometheus binds to loopback by default (non-loopback emits a warning) and supports an optional bearer token. Label cardinality for both is bounded by `monitor.annotation.max_labels`. See [Continuous Monitoring](../user-guide/continuous-monitoring.md).

### `codegreen timeline`

- New command that places power (NEMB time series), CPU stacks, GC and allocation (JFR), and GPU kernels (`torch.profiler` Chrome trace) on one monotonic-clock axis. It writes a Perfetto/Chrome trace (`--out`, open at ui.perfetto.dev) and prints a phase and bottleneck summary (`--rel-change`, `--confirm`, `--gap-min-us`, `--launch-bound-frac`). At least one of `--nemb`, `--jfr`, `--torch` is required.
- New `codegreen.analysis.sampling` library module (no CLI flag yet): async-profiler stack sampling for Java (JMH jars load the agent through `-jvmArgsAppend`) and per-method energy from sampled stacks, as a low-overhead second hotspot signal. Python stack sampling is not included.

### Examples directory and test harness

- `examples/` ships 14 numbered end-to-end scripts, `01_quickstart_measure` through `14_monitor_prometheus_scrape`. Each prints `OK: <feature>; <metric>=<value>` on success or `SKIP: <reason>` on missing dependencies. Harness: `pytest tests/test_examples.py -q`.
- The docs site mirrors the layout under `/examples/`, with a use-case landing page, per-example pages, a Continuous Monitoring guide and a Project Profiling guide.

### Changed behaviour and compatibility

- **`attribution_pct` is now exclusive.** It was inclusive energy over total run energy, which double-counts nested calls and could exceed 100%. `attributed_energy_j` equals `exclusive_energy_j`. Compare old and new runs only on `exclusive_energy_j`.
- **Qualified function names appear in all output** (`Class.method` instead of `method`), in `project --json` hotspots, `measure --json` checkpoints and the runtime reports. Scripts that match on bare names must be updated.
- **`codegreen project` exits 1** when no checkpoint records are captured (it used to report success with 0 J) and when an explicit `--source-glob` matches no files (it used to widen to every source file).
- **`codegreen run` no longer limits a run to about 300 s.** The per-run default is unlimited; pass `--timeout` for a limit. The project run lost its hardcoded 3600 s limit as well. The unmeasured validation run still happens by default (`--no-validate` skips it).
- **Failures that used to be skipped now raise**: a failing tree-sitter query, instrumentation-point creation errors and AST-based instrumentation errors raise `RuntimeError` instead of logging a fallback and continuing, and a missing tree-sitter raises instead of falling back to legacy line-based instrumentation.
- **`measure --json` has new fields** (`instrumentation_audit`, `error`), and a fine-granularity run with too few checkpoints may be re-run at coarse granularity, so `granularity` in the output can differ from the one requested.
- **`measure -o` output** now includes `normalised_source` and `brace_normaliser_applied` in the saved metadata. Instrumented files that contained one-line function bodies have those bodies expanded over several lines, so line numbers after them shift.
- **`install_info.json`** is written to `$XDG_CONFIG_HOME/codegreen/` (default `~/.config/codegreen/`) on first run, to cache the detected clock source.
- `measure-workload` reports an error when the backend returns no energy instead of printing stderr.
- **Annotation socket.** `annotate_request` no longer defaults to `/tmp/codegreen.sock`. Pass a path, or start the monitor with `--listen-on-socket default`, which uses `$XDG_RUNTIME_DIR/codegreen.sock` (else `/tmp/codegreen-<uid>/codegreen.sock`, created 0700). The listener now refuses to remove a path that is not a socket owned by the current user.
- **Java runtime fails loudly without RAPL.** The standalone Java runtime raises at startup when no package RAPL domain is readable (it used to report 0 J per function), sums every package domain, and handles counter wraparound.
- **Timeseries clock label** is `clock_monotonic`, matching the clock NEMB stamps with (0.4.8 reported `clock_monotonic_raw`); cached `install_info.json` files are regenerated.
- **Packaging.** The sdist now contains the native NEMB sources and language runtimes, so source installs build the measurement backend; wheels built from the sdist are correctly platform-tagged. `tree-sitter-java` is now a declared dependency, and `cmake` is a build requirement so isolated source builds compile NEMB. `codegreen project` now fails up front with a clear message when the native library is missing, instead of reporting no checkpoint records after the run (after restoring any sources an interrupted run left instrumented).

### Known limitations

- `--sync-device` supports torch/CUDA on a single device. Other accelerators and multi-device runs are not synchronised.
- C `longjmp` and `exit` skip the frame exit, so the frame stays open. Macros from headers that contain `return` are invisible to the C return rewrite.
- C and C++ functions returning pointers or references are not matched by the definitions query and are not instrumented.
- Project-mode hotspot percentages that feed the verdict thresholds (`Excl%`/`Incl%` and `_classify_hotspot_verdict`) still use the inclusive sum as denominator, which double-counts nested calls. Changing it needs threshold recalibration against the benchmark harness (todo A10). `attribution_pct` itself is exclusive.
- Without `CODEGREEN_INSTALL_DIR`, NEMB falls back to a 1 ms, 2000-sample ring buffer (a 2 s window). Checkpoints older than the window clamp to the first reading, so long runs lose per-function energy until the buffer is sized from the run length (todo A14).
- NEMB total system energy includes idle GPU draw; CPU-code attribution spreads it by time (todo A11).

## v0.4.8

### Local-timezone display companions (additive — UTC contract unchanged)

Adds three meta fields so users can read timestamps in their host's local timezone without losing the cross-machine UTC contract:

- `meta.started_at_local` — same instant as `started_at`, rendered in the host's local timezone with explicit offset (e.g. `2026-05-10T11:16:56.209074-07:00`).
- `meta.ended_at_local` — same instant as `ended_at`, local TZ.
- `meta.host_timezone` — local TZ label at measurement time (e.g. `PDT`, `ADT`, `+05:30` for non-DST regions).

Canonical `started_at` / `ended_at` are still UTC `+00:00`; the contract field `meta.iso_timestamp_format = "rfc3339_utc"` is unchanged. Both pairs are captured at the same wall-clock instant; UTC ↔ local round-trip is verified to ≤ 1 ms in the test battery.

Why both: UTC stays the wire format for joins/sorts (avoids DST ambiguity, server-migration breakage, mixed-TZ aggregation bugs); local is purely for display when reviewing a single run on your own host. Pick what fits the use case.

Test coverage: 52 audit-battery checks (45 v0.4.7 + 7 new local-field checks, all green on AMD EPYC). The 45 v0.4.7 checks still pass unchanged — proves the canonical fields are not perturbed by the new ones.

## v0.4.7

### JSON-schema + correctness overhaul (32 fixes from 5-track audit)

**Breaking field renames** (CLI JSON only — Session API was already on the short forms):
- `energy_joules.{...}` → `energy_j.{...}`
- `time_seconds.{...}` → `duration_s.{...}`
- `domains_power_watts.{...}` → `domains_power_w.{...}`
- `runs: int` → `runs: {attempted, energy_valid, iqr_outliers_removed, zero_energy_dropped, warmup_runs, measurement_runs, ...}` (structured record)
- `backend: "NEMB (...)"` → `backend: {name, driver, domains_seen}` (structured record)
- `cv_percent` (across runs) → `cv_percent_across_runs`; `worst_power_cv_percent` (within-task) → `worst_within_task_power_cv_percent`
- Session: `session_name`/`abi_version`/`providers` at root → moved into `meta` (`meta.session_name`, `meta.nemb_abi_version`); `providers: []` placeholder removed.

**`meta` block expanded** with reproducibility metadata: `schema_version`, `cpu_model`, `kernel`, `cwd`, `argv`, `codegreen_env`, `measurement_quality`, `domain_support`, `outlier_method`, `iso_timestamp_format`, `domain_topology`, `timeseries.{enabled,schema_version,sample_keys,t_ns_clock,inclusive_of_children}`. Failure-path JSONs now also include `meta` for log correlation.

**`totals` block split into time-window-aware fields**: `wall_duration_s` (s.start → s.stop, monotonic), `task_duration_s` (sum of depth-0 instrumented work — matches `energy_j`'s window), `gap_duration_s = wall − union(task intervals)` (uninstrumented work between/around tasks), `concurrent_overlap_s` (positive when tasks ran in parallel threads). `duration_s` retained as alias for `task_duration_s`.

**Math correctness fixes**:
- CLI `power_w` now computed as `mean(per-run e/t)` with full CI95, not the broken `e_mean/t_mean` over disjoint sample sets. Energy and time arrays are pair-filtered by run index; zero-energy runs drop both members. Surfaces `runs.zero_energy_dropped` so users see the funnel.
- Session totals aggregate per-domain power as `Σenergy / Σduration_over_tasks_where_domain_was_reported` so a domain present on only some tasks is not diluted.
- Empty session emits `meta.measurement_quality = "no_tasks"`; TimeOnly backend emits `"no_backend"`; energy=0 emits `"energy_zero"`. No silent zero-J reports.

**Time/clock robustness**:
- `wall_duration_s` and `duration_total_s` now use `time.monotonic()` end-to-end (NTP-immune).
- `_dur` fallback in `_close_by_sid` uses monotonic delta (was wall-clock).
- `TaskResult.started_at_mono_ns` / `ended_at_mono_ns` persisted so consumers can align task windows with `timeseries[].t_ns` exactly.
- Naive `datetime.now()` calls migrated to `datetime.now(timezone.utc)`; ISO format documented in `meta.iso_timestamp_format = "rfc3339_utc"`.

**Timeseries-mode fixes** (`record_time_series=True`):
- Per-task timeseries slices are sorted by `t_ns` and de-duplicated before assignment.
- `_compute_task_noise` distinguishes "timeseries disabled" (returns `None`) from "timeseries enabled but task too short" (returns `drop_ratio=1.0`); uses sample stdev (not population); computes `samples_expected` from observed median interval when n ≥ 3.
- Buffer-saturation warning reworded to make clear that `buffer_samples` cannot be resized mid-run.
- `meta.timeseries.inclusive_of_children = true` documents that nested-task timeseries DO contain their children's samples (consumers summing across all tasks would double-count).

**Reliability**:
- `_write_json` is now atomic (temp + `os.replace`) — concurrent / crash-safe.
- `_build_report` is wrapped in try/except; an exception in the noise calculation no longer prevents the report from being emitted (`meta.error` carries the failure reason).
- SIGTERM/SIGINT handlers installed alongside `atexit` so graceful termination still flushes the report; SIGKILL remains unrecoverable by definition.
- `_auto_finalize` closes open tasks in LIFO order (deepest first) and re-derives `parent` linkage from the remaining open set — eliminates `depth=N, parent=null` inconsistency on forgot-to-stop.

**Open/Closed compliance**: All meta-block construction goes through a single shared `build_meta_block()` (used by both Session API and CLI). Every magic-number threshold (CV%, drop%, run-id length, quality cutoffs) lives in `config.json` under `measurement.report` — open for extension via config edits, closed for modification via callers. Domain-naming patterns are in a `_DOMAIN_PATTERNS` table; new hardware families add a tuple, not an `if`. Hardware-specific resolvers (CPU model, domain topology) sit in a thin adapter layer separate from the core builder.

**Test coverage**: 42 Session-API checks + 26 CLI checks + 39 logical-correctness assertions on real workloads (GPT-2 inference, multi-task pipelines, concurrent threads, nested tasks, empty sessions). All green on AMD EPYC 9554P.

## v0.4.6

### Fix: DRAM excluded from total energy on Skylake-SP+ Xeons
- On Linux 5.x+ kernels, DRAM is exposed as a sub-zone of the package zone (`intel-rapl:0/intel-rapl:0:0/name=dram`). The RAPL provider previously treated all sub-zones as nested-in-package and excluded them from `total_energy` — but per Intel SDM Vol 4 §14.9, MSR_PKG_ENERGY_STATUS (0x611) and MSR_DRAM_ENERGY_STATUS (0x619) are physically disjoint counters.
- Result was a 10–15 % undercount of `energy_j` on memory-bound workloads on Skylake-SP+ Xeons (verified on Intel Xeon Gold: `perf stat` reported pkg=1118 J + ram=146 J, codegreen reported energy_j=1121 J = pkg+gpu only).
- Fix: promote any sub-zone whose name starts with `dram` to top-level domain. Idempotent across all platforms — AMD EPYC (no dram exposed), Sandy/Ivy/Haswell-EP (dram already zone-level), and PSYS-present chips are all unchanged.
- Other sub-zones (`core`/`pp0`, `uncore`/`pp1`) remain excluded — they ARE genuine subsets of package energy.

## v0.4.5

### Per-task domains_power_w in Session JSON
- `TaskResult` now carries `domains_power_w: Dict[str, float]` (W per domain = `domains[d] / duration_s`), parallel to the existing per-task `domains` energy split. Same time-base as `avg_power_w`.
- `totals.domains` and `totals.domains_power_w` aggregate across depth-0 tasks.
- CSV writer adds `domains_power_w_json` column.
- Dataclass docstring + API docs explain the RAPL nesting semantics (`sum(domains) ≠ energy_j` by design).

## v0.4.4

### Per-domain power split in `codegreen run --json`
- New `domains_power_watts: Dict[str, float]` field in CLI JSON output, parallel to the existing `domains` (joules-per-domain). Computed as `joules / mean wall time`.

## v0.4.3

### Sample interval default + totals
- Fixed `sample_interval_ms` default not propagating into recorded sessions.
- `totals.sample_interval_ms` now surfaces the effective rate that produced the time-series.

## v0.4.2

### Self-describing time-series schema
- Each timeseries sample now uses unit-suffixed keys: `t_ns` (ns), `energy_j` (J cumulative system total), `power_w` (W system total), `domain_j` (per-domain cumulative joules), `domain_w` (per-domain average watts since previous sample). Replaces the older `t/j/w/d` shorthand which was ambiguous about units and granularity.
- New `domain_w` field exposes per-domain instantaneous power directly. Previously users had to derive GPU/CPU power manually from successive `d[t]` joule deltas; now `s["domain_w"]["gpu0"]` is reported per sample. Domains whose provider does not expose per-domain wattage (Darwin IOReport, Windows EMI, AMD RAPL) are absent rather than zero, so callers can distinguish "0 W" from "not measured".
- Verified across 1 ms / 5 ms / 20 ms sampling intervals: `∫ domain_w · dt` recovers `domain_j` to within 0.05 % for CPU package and GPU domains; computation is independent of polling rate (each domain's watts is itself an interval-average from the underlying counter).
- `Session.export_plot()`, the plot.py renderer, and noise computation updated; `t_ns` confirmed to be `CLOCK_MONOTONIC` nanoseconds on Linux, `mach_continuous_time` on macOS, `QueryPerformanceCounter` on Windows -- all explicitly converted to nanoseconds.

## v0.4.1

### Noise / quality reporting in `Session` JSON
- Each task carries a `noise` dict when `record_time_series=True`: `samples_captured`, `samples_expected`, `drop_ratio`, `power_mean_w`, `power_std_w`, `power_cv_percent`, `sample_interval_ms`, `quality` (`excellent` <2 %, `good` <5 %, `moderate` <10 %, `high-noise` >=10 %).
- `totals.worst_power_cv_percent` and `totals.noise_warnings` roll up across tasks.
- `RuntimeWarning` emitted at `stop()` for any task with CV >=10 % or sample drop >=20 %, so unreliable readings are never silent.
- Computation runs once at finalize on already-captured samples; bias-checked at -0.05 % vs `record_time_series=False` on identical workloads (3 fresh subprocesses each, GPT-2 generation).
- CSV export gains `power_cv_percent`, `samples_captured`, `samples_expected`, `drop_ratio`, `quality` columns.

### Documentation
- API reference now documents `record_time_series=True` overhead: mean unchanged (<=0.3 %), run-to-run spread slightly widens because the drain thread competes briefly with the workload for CPU.

## v0.4.0

### Manual span-based measurement (`codegreen.Session`)
- New `codegreen.Session` class -- import directly, bracket code regions as named tasks; reads RAPL/NVML hardware counters in-process.
- Three forms: context manager (`with s.task(...)`), explicit `start_task("X")` / `stop_task("X")`, decorator (`@codegreen.task("name")`).
- Per-task energy + per-RAPL/NVML domain breakdown (`package-0`, `core`, `gpu0`, etc.) computed atomically in NEMB ABI v2.
- Nested tasks supported; per-thread task stacks for concurrent use.
- Single-Session-per-process guard; cross-process pidfile detection (RAPL is system-wide).
- Atexit cleanup -- file written and drain thread joined even if user forgets `.stop()`.
- JSON output by default (`codegreen_<pid>.json`); CSV opt-in via `.csv` extension or `output_format="csv"`.

### Time-series sampling + plotting (ABI v3)
- New C ABI: `nemb_get_time_series_json(buf, size, since_ts_ns)` returns sampled (timestamp, energy, power, per-domain) tuples since a timestamp.
- New C ABI: `nemb_set_buffer_size(n)`, `nemb_set_measurement_interval_ms(ms)` -- runtime mutators on existing coordinator state (no parallel config).
- `Session(record_time_series=True)` captures samples per-task (CLOCK_MONOTONIC ns timestamps) using an adaptive Python drain thread (50 ms floor / 2 s ceiling, auto-tunes from observed buffer saturation).
- Verified: 30-second task with defaults only -- 28,460 samples, full span, zero gaps >50 ms.
- `Session.export_plot(path)` renders power-vs-time charts; format chosen from extension (`.html` Plotly / `.png` `.svg` `.pdf` matplotlib).
- Trapezoidal integration of `w(t)` recovers task `energy_j` to within ~0.2% (verified on a 5 s task with ~4,800 samples).

### Multi-language distribution
- Java runtime JAR (`codegreen-runtime.jar`) auto-built via `javac`/`jar` in `setup.py` and bundled into the wheel under `codegreen/lib/runtime/java/`.
- C/C++ runtime headers (`codegreen_runtime.h`, `runtime.hpp`) bundled under `codegreen/lib/runtime/{c,cpp}/`.
- CI: manylinux + macOS images install JDK 17 so the JAR ships with every published wheel.

### Backward compatibility
- `nemb_stop_session(id, e, p)` retained as a thin shim over `nemb_stop_session_v2`.
- Auto-instrumenter checkpoints + manual Session output emit into the same JSON envelope.
- `config.json -> coordinator.measurement_interval_ms` unchanged; `Session(sample_interval_ms=N)` is an opt-in per-session runtime override on the same field.

### Documentation
- Updated README, Quickstart, Examples → Python, and API → Python pages with verified code samples for every form. See [Quickstart](../getting-started/quickstart.md) → [Python examples](../examples/python.md) → [Python API](../api/python.md).

## v0.3.16 (previous)

### NVML Runtime Loading
- NVML loaded via dlopen/LoadLibrary instead of link-time dependency (fixes `libnvidia-ml.so.1: cannot open shared object file`)
- Works on all platforms without NVIDIA drivers installed (no hard .so dependency)
- `CODEGREEN_NVML_PATH` env var for non-standard NVML locations
- Detailed error messages listing all searched paths when NVML not found
- Eliminates `HAVE_NVML` compile flag entirely -- provider always compiles, decides at runtime

## v0.3.15

### Crash Fixes
- Fix core dump when RAPL permission denied (C++ exception no longer crosses ctypes boundary)
- Fix `os.geteuid()` crash on Windows (AttributeError)
- Fix NEMB session leak on subprocess timeout (always calls `nemb_stop_session`)
- Fix random crash from unhandled `TimeoutExpired` in all measurement backends

### NVML / GPU
- Fix NVML never working: `HAVE_NVML` compile definition now passed to `codegreen-nemb` target
- Add Windows NVML search paths (`C:/Windows/System32`, CUDA toolkit)
- NVIDIA GPU detected and reported in `codegreen doctor`

### Measurement Accuracy
- Consistent `capture_output=True` across JSON and human modes (was 22% energy difference)
- RAPL provider skips inaccessible domains instead of failing entirely (partial access works)
- JSON output budget exit code fixed (was exit 0 even when exceeded)

### CLI Improvements
- `codegreen doctor` now checks NEMB library, energy backend, RAPL permissions, GPU
- `--include-warmup` flag: measure energy during warmup and include in results
- `--repeat` validation (must be >= 1)
- Permission check before measurement runs (fail fast with fix instructions)
- No silent fallbacks: refuses to run without real energy backend
- JSON output includes `backend`, `domains`, `cv_percent`, `power_watts`, `outliers_removed`
- JSON `command` field is now a list (preserves argument boundaries)
- Command grouping: Measurement / Setup / Diagnostics / Validation panels
- Shutdown message suppressed in non-debug mode

### Build & Packaging
- cmake errors now visible under pip install (stderr with captured build output)
- Python 3.14 classifier added
- Version single source of truth via `importlib.metadata`
- Config path alignment between Python CLI and NEMB C++ backend
- Production defaults: `debug_mode: false`, `verbose_logging: false`

### Documentation
- 57 documentation issues fixed across README, INSTALL, CITATION, config, help text
- License classifier corrected (MIT -> MPL-2.0)
- All broken `benchmark cpu_stress` references replaced with working commands
- JavaScript added to Language enum (analysis works; instrumented measurement WIP)

## v0.3.14

### Build
- Remove dead tree-sitter from CMake (fixes sdist build on Python 3.14+)
- Better build error messages in setup.py

## v0.3.13

### Diagnostics
- `--verbose` shows full NEMB init log, provider detection, load errors, alternate paths

## v0.3.12

### Fixes
- Verbose shows exact NEMB load error and searches alternate paths

## v0.3.11

### Diagnostics
- `--verbose`/`--debug` flag shows CPU model, cores, RAM, dependency versions, NEMB status, backend detection

## v0.3.10

### Energy Domain Accuracy
- Correct PSYS-aware domain summation: uses PSYS alone when present (was 82-91% overcount on Skylake+ laptops)
- Multi-socket support: all package-* and dram-* domains summed (was missing socket 1 on dual-socket)
- macOS power calculation uses only top-level domain deltas (was 67% overcount)
- Per-domain breakdown in `codegreen run` output: energy (J) + power (W) per hardware domain
- Structural hierarchy detection: sysfs path depth determines top-level vs sub-domain
- Dynamic channel normalization on macOS (no hardcoded if-else chain)
- Unknown future domains default to top-level (safe overcount, never silent drop)
- Negative energy delta clamping (handles counter reset/sleep)

### Output Quality
- CV (coefficient of variation) and quality rating (excellent/good/moderate/high noise)
- Per-domain energy and power breakdown with relative bar chart
- Noise warning with recommendation to increase repeats
- Domain values averaged across all runs (consistent with total energy)

### Windows 11 Support
- WindowsEMIProvider: RAPL energy via inbox `intelpep.sys` driver (PKG, PP0/cores, PP1/iGPU, DRAM)
- Zero driver install, HVCI-compatible, pre-built Windows x64 wheels on PyPI
- Verified on i7-1165G7 and i7-12700H

### Build & CI
- Pre-built wheels: Linux x64, Linux ARM64, macOS ARM64, Windows x64
- Legacy codegreen-core removed (2,565 lines, jsoncpp/curl/sqlite deps gone)
- Auto GitHub Release on tag push
- Python 3.9+ compatibility
- CodeCarbon and JoularJX profiler wrappers
- DaCapo and Renaissance benchmark suites

## v0.3.1

### Windows 11 Energy Measurement
- WindowsEMIProvider: RAPL energy via inbox `intelpep.sys` driver (PKG, PP0/cores, PP1/iGPU, DRAM)
- Zero driver install, HVCI-compatible, cumulative picowatt-hours via PDH Performance Counters
- Verified on i7-1165G7: idle 47W, load 80W, 4 RAPL domains
- PrecisionTimer: QueryPerformanceCounter path for Windows timestamps

### Fixes
- Python 3.9 compatibility: `from __future__ import annotations` in setup.py
- Removed legacy codegreen-core C++ code (2,565 lines deleted, moved to archive/)
- Removed jsoncpp, curl, sqlite build dependencies (only NEMB remains)
- CMakeLists.txt simplified: single `codegreen-nemb` target
- Version display reads from `__version__` (was hardcoded 0.1.0 in CLI)

## v0.3.0

### Cross-Platform Energy Measurement
- **macOS**: DarwinIOReportProvider via `libIOReport.dylib` (CPU, GPU, ANE, DRAM), DarwinKPCProvider via `kperf.framework` (~200ns exact hardware counters), per-channel unit handling (mJ/nJ via `IOReportChannelGetUnitLabel`), `mach_continuous_time` precision timer (~42ns)
- **Windows 11**: WindowsEMIProvider via PDH Energy Meter counters (RAPL via inbox `intelpep.sys`)
- **Linux**: IntelRAPLProvider, AMDRAPLProvider, NvidiaGPUProvider, AMDGPUProvider
- Pre-built macOS ARM64 wheels on PyPI

### Platform-Aware Energy Backends
- NEMB-first backend selection: NEMB (in-process, zero file I/O) > perf (Linux) > powermetrics (macOS) > time-only
- Extensible backend registry via `_EnergyBackend` subclassing
- `codegreen run` and `codegreen project` auto-detect best backend per platform

## v0.1.0

### Features

- Multi-language energy measurement: Python, C, C++, Java, JavaScript
- Tree-sitter based code instrumentation with config-driven language support
- NEMB C++ backend with Intel RAPL, NVIDIA NVML, AMD ROCm drivers
- `codegreen run` command: measure energy of any shell command with `--repeat`, `--warmup`, `--json`, and `--budget` flags
- CI/CD energy budget gating via `codegreen run --budget`
- Granularity control: coarse (main only) and fine (all functions) modes
- Multiple output formats: JSON, CSV, Markdown, text
- Interactive energy timeline visualization via `--export-plot` (Plotly HTML)
- Hotspot detection (>90th percentile functions)
- Benchmark suite: 0.03% error vs perf RAPL (binarytrees/18)
- 13 CLI commands
- Fork safety for multiprocessing programs (pthread_atfork)

### Architecture

- Signal-generator model: ~100-200ns checkpoint overhead (25-100x lower than synchronous reads)
- Background polling at 1ms with binary search + linear interpolation correlation
- Config-driven language extension via JSON (no core code changes needed)
