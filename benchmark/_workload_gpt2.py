"""GPT-2 generation workload. Same script is used unchanged across modes."""
import os, time
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

import torch
from transformers import GPT2LMHeadModel, GPT2Tokenizer

PROMPTS = [
    "Energy-aware computing is",
    "The cheapest way to train a model is",
    "Hardware energy counters report",
    "Modern transformers can be optimized by",
] * 8  # 32 prompts -> dominates total runtime over import cost


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tok = GPT2Tokenizer.from_pretrained("gpt2")
    tok.pad_token = tok.eos_token
    tok.padding_side = "left"
    model = GPT2LMHeadModel.from_pretrained("gpt2").to(device).eval()
    batch = tok(PROMPTS, padding=True, return_tensors="pt").to(device)
    t0 = time.perf_counter()
    with torch.no_grad():
        out = model.generate(**batch, max_new_tokens=128, do_sample=False)
    dt = time.perf_counter() - t0
    print(f"workload done: device={device} prompts={len(PROMPTS)} gen_s={dt:.2f}")


if __name__ == "__main__":
    main()
