# 05 - GPT-2 staged inference

One `codegreen.Session` with three tasks over a GPT-2 pipeline:
`preprocess` (load the tokenizer), `load_model` and `generate` (16 prompts,
64 new tokens each, on CUDA when available). It records the power time
series and exports a plot.

What it shows:

- Per-task `domains`: CPU package (`package-0`, with the nested `core`) and
  GPU (`gpu0`) energy for each stage.
- `record_time_series=True`: per-task samples, the `noise` summary and
  `Session.export_plot`.

## Prerequisites

- `pip install -r examples/05_gpt2_staged/requirements.txt` (`torch`,
  `transformers`, `sentencepiece`). The first run downloads the `gpt2` model.
- `plotly` for the HTML plot. Without it `export_plot` writes nothing.
- The test harness skips this example unless
  `CODEGREEN_RUN_HEAVY_EXAMPLES=1` is set.

## Source

[`examples/05_gpt2_staged/main.py`](https://github.com/SMART-Dal/codegreen/blob/main/examples/05_gpt2_staged/main.py)

```python
--8<-- "examples/05_gpt2_staged/main.py"
```

## Run

```bash
pip install -r examples/05_gpt2_staged/requirements.txt
python examples/05_gpt2_staged/main.py
```

`pipeline.html` is written next to `main.py` (override the path with
`CG_PLOT`). The last line on the host used for these pages:

```text
OK: gpt2_staged; tasks=3; total_energy_j=131.7195; gen_s=0.67
```

The script does not check validity, and this run was not valid. Read the
`validity` block of `codegreen_<pid>.json` before using the numbers. That
run's report:

| Task | `energy_j` | `duration_s` | `package-0` (J) | `gpu0` (J) |
|---|---:|---:|---:|---:|
| `preprocess` | 5.68 | 0.073 | 5.68 | 0 |
| `load_model` | 22.75 | 0.210 | 17.36 | 5.39 |
| `generate` | 103.29 | 0.677 | 53.93 | 49.36 |

- `validity.status` was `invalid` with `COUNTER_INTEGRAL_DIVERGED`
  (`counter 54.748 J, integral 31.075 J over 0.962 s` for `gpu0`): the GPU
  energy counter and the integral of its sampled power disagreed beyond
  `measurement.report.validity.counter_check.tolerance`. This check is fatal
  by default; its usual cause is another process reading the counter or the
  instantaneous power (`nvidia-smi`, DCGM).
- `TASK_BELOW_RESOLUTION` (warning) named all three tasks. The NVIDIA
  provider reported an update interval of about 100 ms, so a stage needs
  about 1 s to be resolved on the GPU side.
- `GPU_IN_TOTAL` (warning): each task's `energy_j` sums CPU and GPU
  providers. Select sensors to measure one side only.

On a CPU-only host the `gpu0` domain is absent and the same code reports CPU
energy only.

See also: [Python deep dive](python.md),
[03 - Session API](03_session_api.md),
[Python API: TaskResult fields](../api/python.md#taskresult-fields).
