"""Verify codegreen.Session against CodeCarbon EmissionsTracker on a transformers
fine-tune (mirrors https://docs.codecarbon.io/latest/how-to/transformers/).

Trackers run **sequentially** (not concurrent) to avoid double-instrumentation noise:

  Phase 1: CodeCarbon-only  -> 1 fine-tune  (baseline reference)
  Phase 2: CodeGreen-only   -> 3 fine-tunes inside one Session, one per API form:
             explicit start_task / stop_task
             `with sess.task(...)` context manager
             `@codegreen.task(...)` decorator

Each fine-tune trains on the same IMDB slice with the same TrainingArguments,
so per-task CG energy / time / power are directly comparable to the CC baseline.

Run: python -m benchmark.cg_vs_codecarbon_transformers [--n 128] [--epochs 1] [--batch 8]
"""
import argparse, json, os, time

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")


def _build_dataset_and_model_factory(model_name, n):
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    from datasets import load_dataset
    tok = AutoTokenizer.from_pretrained(model_name)
    ds = load_dataset("imdb", split=f"train[:{n}]")
    ds = ds.map(lambda b: tok(b["text"], truncation=True, padding="max_length", max_length=128), batched=True)
    ds = ds.rename_column("label", "labels")
    ds.set_format("torch", columns=["input_ids", "attention_mask", "labels"])
    return ds, lambda: AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=2)


def _train_args(out, epochs, batch):
    from transformers import TrainingArguments
    return TrainingArguments(output_dir=out, num_train_epochs=epochs,
                             per_device_train_batch_size=batch, save_strategy="no",
                             report_to=[], disable_tqdm=True, logging_strategy="no", use_cpu=True)


def _do_train(new_model, ds, out, epochs, batch):
    from transformers import Trainer
    Trainer(model=new_model(), args=_train_args(out, epochs, batch), train_dataset=ds).train()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=128)
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--batch", type=int, default=8)
    p.add_argument("--out", default="/tmp/cg_session.json")
    p.add_argument("--model", default="distilbert-base-uncased")
    args = p.parse_args()

    ds, new_model = _build_dataset_and_model_factory(args.model, args.n)

    # ---- Phase 1: CodeCarbon-only baseline ----
    from codecarbon import EmissionsTracker
    cc = EmissionsTracker(project_name="cg_vs_cc", output_dir="/tmp",
                          log_level="error", save_to_file=False)
    cc.start()
    t0 = time.perf_counter()
    _do_train(new_model, ds, "/tmp/_cc", args.epochs, args.batch)
    cc_wall = time.perf_counter() - t0
    co2 = cc.stop()
    cc_j = (cc.final_emissions_data.energy_consumed or 0.0) * 3.6e6

    # ---- Phase 2: CodeGreen Session (3 forms in one session, sequential) ----
    import codegreen
    sess = codegreen.Session(output_file=args.out, record_time_series=True)
    sess.start()
    t0 = time.perf_counter()

    sess.start_task("explicit_train")
    _do_train(new_model, ds, "/tmp/_t1", args.epochs, args.batch)
    sess.stop_task("explicit_train")

    with sess.task("context_train"):
        _do_train(new_model, ds, "/tmp/_t2", args.epochs, args.batch)

    @codegreen.task("decorator_train")
    def fine_tune():
        _do_train(new_model, ds, "/tmp/_t3", args.epochs, args.batch)
    fine_tune()

    cg_wall = time.perf_counter() - t0
    sess.stop()

    rep = json.load(open(args.out))
    tasks = {t["name"]: t for t in rep["tasks"]}
    cg_total_tasks = sum(t["energy_j"] for t in rep["tasks"])

    # Per-task delta vs CC baseline (CC ran 1 train; each CG task ran 1 train)
    print(f"\n{args.model} | IMDB[:{args.n}] | {args.epochs} ep | batch={args.batch}\n")
    print(f"Phase 1 (CodeCarbon, 1 train)")
    print(f"  wall {cc_wall:.2f} s   energy {cc_j:.2f} J   power {cc_j/cc_wall:.2f} W   CO2 {co2*1000:.4f} g")
    print(f"\nPhase 2 (CodeGreen Session, 3 trains sequential)")
    print(f"  total span energy {rep['total']['energy_j']:.2f} J   power {rep['total']['power_w']:.2f} W   wall {cg_wall:.2f} s")
    print(f"\n  task                 energy(J)  dur(s)  power(W)   ts   delta-vs-CC")
    for name in ("explicit_train", "context_train", "decorator_train"):
        t = tasks[name]
        ts = len(t.get("time_series", []))
        d = 100 * (t["energy_j"] - cc_j) / cc_j if cc_j else float("nan")
        print(f"  {name:<18}  {t['energy_j']:>8.2f}  {t['duration_s']:>6.2f}  {t['power_w']:>7.2f}  {ts:>5}   {d:+7.2f}%")
    print(f"\n  domains captured: {list(tasks['explicit_train'].get('per_domain', {}).keys())}")


if __name__ == "__main__":
    main()
