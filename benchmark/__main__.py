"""Entry point for `python3 -m benchmark`."""
import argparse
import sys
from pathlib import Path
from benchmark.config import BenchmarkConfig
from benchmark.harness import BenchmarkHarness

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
    harness = BenchmarkHarness(config)

    try:
        collector = harness.run_suite(
            problems=args.problems,
            languages=args.languages,
            sizes=args.sizes,
            profilers=args.profilers,
            repetitions=args.repetitions,
        )
        summaries = collector.summarize_all()
        print(f"\n{'='*60}")
        print(f"Results: {len(collector.results)} runs")
        print(f"{'='*60}")
        for key, data in sorted(summaries.items()):
            e = data.get("energy")
            t = data.get("time")
            valid = data.get("valid_runs", 0)
            total = data.get("total_runs", 0)
            energy_str = f"{e.mean:.4f} +/- {e.std:.4f} J" if e else "N/A"
            print(f"  {key}: energy={energy_str}  time={t.mean:.3f}s  valid={valid}/{total}")

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
