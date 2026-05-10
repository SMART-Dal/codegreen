"""GPT2 inference broken into three explicit codegreen tasks (preprocess/train/eval),
with record_time_series=True so per-task power traces are captured.

Differs from _workload_gpt2_session.py (which uses a single "everything" task):
this script exercises multi-task aggregation, per-task energy/power/duration,
the inclusive-of-children timeseries semantic, and the noise/quality summary.
Useful as a smoke-test that the v0.4.7 schema reports stay self-consistent on
a real ML workload."""
import os
import time

os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

import codegreen

s = codegreen.Session("pipeline", record_time_series=True).start()

s.start_task("preprocess")
import torch
from transformers import GPT2LMHeadModel, GPT2Tokenizer

PROMPTS = [
    "Energy-aware computing is",
    "The cheapest way to train a model is",
    "Hardware energy counters report",
    "Modern transformers can be optimized by",
] * 8

device = "cuda" if torch.cuda.is_available() else "cpu"
tok = GPT2Tokenizer.from_pretrained("gpt2")
tok.pad_token = tok.eos_token
tok.padding_side = "left"
s.stop_task("preprocess")

s.start_task("train")
model = GPT2LMHeadModel.from_pretrained("gpt2").to(device).eval()
s.stop_task("train")

s.start_task("eval")
batch = tok(PROMPTS, padding=True, return_tensors="pt").to(device)
t0 = time.perf_counter()
with torch.no_grad():
    out = model.generate(**batch, max_new_tokens=128, do_sample=False)
dt = time.perf_counter() - t0
print(f"workload done: device={device} prompts={len(PROMPTS)} gen_s={dt:.2f}")
s.stop_task("eval")

s.export_plot(os.environ.get("CG_PLOT", "pipeline.html"))
report = s.stop()
