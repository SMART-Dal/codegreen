# 05 - GPT-2 staged inference

Multi-task `codegreen.Session` over a small GPT-2 inference pipeline:
tokenise, generate, decode. Demonstrates per-domain attribution
(`package-0`, `core`, `gpu0`, `dram-0`) and time-series export.

## What you learn

- One Session bracketing multiple `with s.task(...):` regions.
- `record_time_series=True` for power-vs-time plots.
- `domains` and `domains_power_w` fields on each task.
- Why `generate` dominates total Joules while `decode` runs hot per watt.

## Prerequisites

- `pip install -r examples/05_gpt2_staged/requirements.txt` (pulls `torch`
  and `transformers`).
- This example is **skipped by the harness** -- it's heavy.

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

## Expected output

A `pipeline.html` time-series plot lands in the example directory plus:

```
OK: gpt2_staged; tasks=3; total_energy_j=84.7800; gen_s=12.41
```

## Why it matters

Real ML workloads have **wildly different per-stage power profiles**.
Tokenisation is CPU-bound at idle power; `generate()` lights up the GPU at
sustained 120-200W; `decode()` is short but hot. Bracketing each stage
shows you which knob (batch size, model size, hardware) moves the needle.

See also: [Python deep dive: GPT-2 with per-domain attribution](python.md#real-world-example-text-generation-with-per-domain-attribution),
[03 - Session API](03_session_api.md).
