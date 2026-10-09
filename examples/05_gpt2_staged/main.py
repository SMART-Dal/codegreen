"""05 GPT-2 staged inference with codegreen.Session(record_time_series=True).

Three explicit tasks (preprocess, load, generate) inside one Session.
Useful for ML practitioners to see per-stage energy attribution.

Heavy deps (torch + transformers); skipped by the auto-test harness.
"""
import os
import sys
import time

os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")


def main() -> int:
    try:
        import torch
        from transformers import GPT2LMHeadModel, GPT2Tokenizer
    except ImportError as e:
        print(f"SKIP: missing dep {e.name}; pip install -r requirements.txt")
        return 0

    import codegreen
    PROMPTS = [
        "Energy-aware computing is",
        "The cheapest way to train a model is",
        "Hardware energy counters report",
        "Modern transformers can be optimized by",
    ] * 4
    device = "cuda" if torch.cuda.is_available() else "cpu"

    with codegreen.Session("gpt2_pipeline", record_time_series=True) as s:
        s.start_task("preprocess")
        tok = GPT2Tokenizer.from_pretrained("gpt2")
        tok.pad_token = tok.eos_token
        tok.padding_side = "left"
        s.stop_task("preprocess")

        s.start_task("load_model")
        model = GPT2LMHeadModel.from_pretrained("gpt2").to(device).eval()
        s.stop_task("load_model")

        s.start_task("generate")
        batch = tok(PROMPTS, padding=True, return_tensors="pt").to(device)
        t0 = time.perf_counter()
        with torch.no_grad():
            model.generate(**batch, max_new_tokens=64, do_sample=False)
        dt = time.perf_counter() - t0
        s.stop_task("generate")

    s.export_plot(os.environ.get("CG_PLOT", str(__file__).replace("main.py", "pipeline.html")))
    report = s.stop()
    tasks = report.get("tasks", []) if isinstance(report, dict) else []
    total_j = sum(float(t.get("energy_j", 0.0)) for t in tasks)
    print(f"OK: gpt2_staged; tasks={len(tasks)}; total_energy_j={total_j:.4f}; gen_s={dt:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
