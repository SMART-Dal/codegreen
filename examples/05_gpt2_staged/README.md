# 05_gpt2_staged

Staged GPT-2 inference (preprocess / load / generate) measured with
`codegreen.Session(record_time_series=True)`. Demonstrates multi-task
aggregation, per-task energy/power/duration, the inclusive-of-children
timeseries semantic, and the noise/quality summary on a real ML workload.

This example is SKIPPED by the auto-test harness because `torch` +
`transformers` are heavy dependencies. To run manually:

```bash
cd examples/05_gpt2_staged
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Expected output (last line):

```
OK: gpt2_staged; tasks=3; total_energy_j=<float>; gen_s=<float>
```

A `pipeline.html` plot is written next to `main.py`.
