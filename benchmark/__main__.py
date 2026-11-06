"""Entry point for `python3 -m benchmark`."""
import argparse
from pathlib import Path
from benchmark.config import BenchmarkConfig
from benchmark.harness import BenchmarkHarness
from benchmark.suites.benchmarksgame import BenchmarksgameSuite

def main():
    parser = argparse.ArgumentParser(description="CodeGreen Energy Benchmark Suite")
    parser.add_argument("--problems", nargs="+", help="Problems to run (default: all)")
    parser.add_argument("--languages", nargs="+", default=["python"], help="Languages (default: python)")
    parser.add_argument("--sizes", nargs="+", help="Input sizes (default: from config)")
    parser.add_argument("--profilers", nargs="+", default=["codegreen"], help="Profilers (default: codegreen)")
    parser.add_argument("--repetitions", type=int, default=5, help="Repetitions per run (default: 5)")
    parser.add_argument("--output", type=Path, help="Output JSON file path")
    parser.add_argument("--csv", type=Path, help="Output CSV file path")
    parser.add_argument("--config", type=Path, help="YAML config file")
    args = parser.parse_args()

    config = BenchmarkConfig.from_yaml(args.config) if args.config else BenchmarkConfig.default()
    suite = BenchmarksgameSuite(Path(config.benchmarks_dir) if config.benchmarks_dir else None,
                                languages=args.languages, problems=args.problems, sizes=args.sizes)
    harness = BenchmarkHarness(suite, repetitions=args.repetitions, warmup_runs=config.warmup_runs,
                               timeout_seconds=config.timeout_seconds, min_runtime_seconds=config.min_runtime_seconds)

    try:
        collector = harness.run_suite(profilers=args.profilers, repetitions=args.repetitions)
        summaries = collector.summarize_all()
        print(f"\n{'='*60}")
        print(f"Results: {len(collector.results)} runs")
        print(f"{'='*60}")
        for key, data in sorted(summaries.items()):
            e, t = data["energy"], data["time"]
            energy_str = f"{e.mean:.4f} +/- {e.std:.4f} J" if e else "N/A"
            time_str = f"{t.mean:.3f}s" if t else "N/A"
            print(f"  {key}: energy={energy_str}  time={time_str}  valid={data['valid_runs']}/{data['total_runs']}"
                  f"  invalid={data['invalid_reasons']}")

        if args.output:
            collector.to_json(args.output)
            print(f"\nJSON saved: {args.output}")
        if args.csv:
            collector.to_csv(args.csv)
            print(f"CSV saved: {args.csv}")
    finally:
        harness.cleanup()

if __name__ == "__main__":
    main()
