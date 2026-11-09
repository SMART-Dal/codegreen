# Configuration API

How CodeGreen finds its configuration, how it reaches measured processes and
the native library, and the environment variables it reads. The keys
themselves are in the [Configuration Reference](../user-guide/configuration-reference.md).

## File resolution

The CLI, the Python runtime and the native library read one active file, the
first of:

1. `CODEGREEN_CONFIG` (the CLI's global `--config PATH` sets it); a missing
   file is an error
2. `~/.codegreen/config.json`, when it exists
3. the bundled `codegreen/config.json` of the installed package
   (`$CODEGREEN_INSTALL_DIR/codegreen/config.json` when that is set)

The CLI and the Python runtime export the resolved path as `CODEGREEN_CONFIG`
to measured processes and to the library, so every component reads the same
file. Python merges the bundled defaults with the active file key by key, so
a user file needs only the keys it changes; the native library reads the
active file alone and keeps its built-in defaults, which equal the bundled
values, for keys the file lacks. A program linked against the library
without `CODEGREEN_CONFIG` reads the config installed next to the library
(`<libdir>/../config.json`, `../codegreen/config.json` or
`../share/codegreen/config.json`). A file that does not parse raises an
error naming it; there is no fallback to defaults.

## Environment variables

| Variable | Read by | Meaning |
|---|---|---|
| `CODEGREEN_CONFIG` | CLI, runtime, library | Active config file (see above) |
| `CODEGREEN_PROVIDERS` | library | Providers to initialize: comma-separated groups, each a provider name or `a|b` alternatives (`intel_rapl|amd_rapl,nvidia_gpu`). An unknown name or a group with no working provider is an error. The CLI and the runtime set it from `--sensors` or `measurement.default_sensors`; unset (default `"all"`) means every provider that initializes |
| `CODEGREEN_INSTALL_DIR` | runtime | Package location, used to find the bundled config when the runtime is copied into a project |
| `CODEGREEN_LIB_PATH` | runtime | Directory searched first for `libcodegreen-nemb` |
| `CODEGREEN_NVML_PATH` | library | Path to `libnvidia-ml.so.1` when it is not found automatically |
| `CODEGREEN_DEBUG` | library | `1` shows provider initialization messages (set by `--debug`/`--verbose`) |
| `CODEGREEN_CHECKPOINT_THROTTLE_MS` | Python runtime | Drop a checkpoint repeated within this many ms (0, the default, keeps all); see [Checkpoint throttling](../user-guide/energy-measurement.md#checkpoint-throttling) |
| `CODEGREEN_SYNC_DEVICE` | Python runtime | `cuda` synchronizes the device at every checkpoint (set by `project --sync-device`) |
| `CODEGREEN_ASYNC_PROFILER` | profiling | async-profiler release directory for Java line sampling |
| `CC`, `CXX` | `measure` | C and C++ compilers for instrumented code (override `measurement.toolchain`) |
| `XDG_RUNTIME_DIR` | runtime | Location of the annotation socket and of the list of running CodeGreen processes |

## Commands

```bash
codegreen config            # active file, user override and sampler settings
codegreen config --show     # the active file as JSON
codegreen config --edit     # edit ~/.codegreen/config.json (created from the active file)
codegreen config --reset    # delete ~/.codegreen/config.json
```

From Python, `codegreen.instrumentation.language_runtimes.python.codegreen_runtime.load_config()`
returns the merged configuration the runtime uses.
