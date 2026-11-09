# Configuration

CodeGreen works without any configuration. Its defaults live in the bundled
`codegreen/config.json`; to change one, put only the keys you change in
`~/.codegreen/config.json`. The [Configuration Reference](../user-guide/configuration-reference.md)
lists every key, and [Configuration API](../api/config.md) covers file
resolution and environment variables.

## Which file is used

The first of:

1. `codegreen --config PATH ...` or `CODEGREEN_CONFIG=PATH` (a missing file is an error)
2. `~/.codegreen/config.json`
3. the bundled `codegreen/config.json`

A user file only needs the keys it changes: the bundled defaults fill in the
rest.

## Common settings

Measure the CPU package only, unless `--sensors` says otherwise:

```json
{"measurement": {"default_sensors": ["rapl"]}}
```

The sensor names are `rapl`, `amd_cpu`, `nvidia` and `amd_gpu`
(`measurement.sensor_providers`). The default, `"all"`, sums every provider
that initializes, GPUs included.

Sample the counters every 5 ms instead of 10 ms (finer per-function
resolution, more sampler overhead):

```json
{"measurement": {"nemb": {"coordinator": {"measurement_interval_ms": 5}}}}
```

Report invalid measurements without failing the command (exit 0 instead of 3):

```json
{"measurement": {"report": {"validity": {"fail_on_invalid": false}}}}
```

## Commands

```bash
codegreen config            # summary of the active settings
codegreen config --show     # full JSON of the active file
codegreen config --edit     # open ~/.codegreen/config.json in $EDITOR (a full copy of the active file if missing)
codegreen config --reset    # delete ~/.codegreen/config.json
codegreen init              # detect providers and write them to the user config
```

A file that is not valid JSON raises an error naming it; there is no silent
fallback to defaults.
