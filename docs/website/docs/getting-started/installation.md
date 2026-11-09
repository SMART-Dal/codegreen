# Installation

## From PyPI (recommended)

```bash
pip install codegreen
```

Wheels include the native backend (`libcodegreen-nemb`), so nothing is compiled:

| Platform | Python |
|---|---|
| Linux x86_64 (manylinux_2_28) | 3.9-3.13 |
| Linux aarch64 (manylinux_2_28) | 3.10-3.13 |
| macOS arm64 (Apple Silicon) | 3.10-3.13 |
| Windows x86_64 | 3.10-3.13 |

Other platforms install from source.

On Linux, give your user read access to the RAPL counters once:

```bash
sudo codegreen init-sensors
# log out and back in for the group change to take effect
```

macOS needs no setup.

### Optional extras

| Extra | Installs | Needed for |
|---|---|---|
| `codegreen[viz]` | matplotlib, pandas, plotly | `--export-plot` (HTML needs plotly, PNG/PDF need matplotlib) |
| `codegreen[otlp]` | OpenTelemetry SDK and OTLP/gRPC exporter | `codegreen monitor --exporter otlp` |
| `codegreen[prometheus]` | prometheus-client | `codegreen monitor --exporter prometheus` |
| `codegreen[all]` | the `otlp` and `prometheus` extras | both exporters |

## From source

```bash
git clone https://github.com/SMART-Dal/codegreen.git
cd codegreen
sudo ./install.sh        # or ./install.sh --skip-rapl, then: sudo codegreen init-sensors
```

`install.sh` checks for `python3`, `cmake`, `make` and a C++ compiler,
initializes the git submodules (Tree-sitter grammars), installs the Python
dependencies, builds `lib/libcodegreen-nemb.so` with CMake, installs the
package in editable mode (`pip install -e .`, `--user` outside a virtual
environment) and, unless `--skip-rapl` is given, sets up RAPL permissions (a
`codegreen` group and a udev rule). Run as root it also copies the library to
`/usr/local/lib`. `./install.sh --upgrade` rebuilds and reinstalls.

For a manual build, see [Building from Source](../development/building.md).

## Hardware sensors

NEMB detects the available energy providers at startup. `codegreen doctor`
and `codegreen capabilities energy` report which ones initialize on your host.

### Linux

| Provider | Hardware | Source |
|---|---|---|
| `intel_rapl` | Intel and AMD CPUs | powercap (`/sys/class/powercap/intel-rapl*`): package, core, uncore, DRAM and psys zones where the CPU exposes them |
| `amd_rapl` | AMD CPUs | RAPL MSRs (`/dev/cpu/0/msr`; needs the `msr` module, read access and `CAP_SYS_RAWIO`). AMD has no separate DRAM counter |
| `nvidia_gpu` | NVIDIA GPUs | NVML (`libnvidia-ml.so.1`; set `CODEGREEN_NVML_PATH` if it is not found) |
| `amd_gpu` | AMD GPUs | ROCm SMI |
| `arm_eas` | ARM SoCs | hwmon SoC energy counter (`scmi_energy` or `arm_energy`, `energy1_input`). It has no `--sensors` name, so only the default `"all"` includes it |

On AMD CPUs `intel_rapl` and `amd_rapl` read the same package counter; NEMB
uses one of them and skips the other (`codegreen doctor` shows which).

### macOS

| Source | Hardware | Notes |
|---|---|---|
| IOReport | Apple Silicon or Intel | CPU, GPU, ANE and DRAM energy |
| kpc | Apple Silicon | Hardware performance counters (cycles, instructions, cache misses) |

### Windows

| Source | Hardware | Notes |
|---|---|---|
| EMI (Energy Metering Interface) | Windows 11, Intel CPU | RAPL energy from the inbox `intelpep.sys` driver: package, cores (PP0), integrated GPU (PP1) and DRAM. No driver install or admin rights |
| NVML | NVIDIA GPU | GPU energy via `nvml.dll` |

AMD CPUs on Windows and Windows 10 do not expose RAPL through EMI.

## Troubleshooting

**`codegreen: command not found`.** The script directory of your Python
environment is not on `PATH` (for `pip install --user`: `~/.local/bin`).

**Permission denied reading RAPL.** Run `sudo codegreen init-sensors`, log
out and back in, and check `groups | grep codegreen`.

**Anything else.** `codegreen doctor` checks the installation and lists every
provider with the reason it did or did not initialize; `codegreen doctor
--test-sensors` also takes a live reading. Open an issue on
[GitHub](https://github.com/SMART-Dal/codegreen/issues) if that does not help.
