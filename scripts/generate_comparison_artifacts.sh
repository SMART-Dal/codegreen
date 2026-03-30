#!/bin/bash
# Generate comparison artifacts for CodeGreen website.
# Compares CodeGreen vs perf RAPL on benchmarksgame suite.
# Output: JSON results + markdown table for website embedding.
#
# Usage: bash scripts/generate_comparison_artifacts.sh [output_dir]

set -e
cd "$(dirname "$0")/.."

OUT=${1:-docs/website/docs/benchmarks}
mkdir -p "$OUT"

echo "=== Generating CodeGreen vs Perf comparison artifacts ==="
echo "Output: $OUT"

# Run benchmarksgame suite: all problems, Python + C, both profilers, 5 reps
codegreen benchmark \
    --suite benchmarksgame \
    -l python -l c \
    --profiler perf --profiler codegreen \
    --reps 5 \
    -o "$OUT" 2>&1 | tee "$OUT/benchmark_run.log"

# Generate markdown comparison table
python3 -c "
import json
from pathlib import Path

out = Path('$OUT')
json_file = out / 'benchmark_benchmarksgame_latest.json'
if not json_file.exists():
    print('No results found')
    exit(1)

with open(json_file) as f:
    data = json.load(f)

# Build comparison table
runs = data.get('runs', [])
grouped = {}
for r in runs:
    key = (r['problem'], r['language'], r['size'])
    grouped.setdefault(key, {})[r['profiler']] = grouped.get(key, {}).get(r['profiler'], [])
    grouped[key][r['profiler']].append(r['energy_joules'])

md = ['# CodeGreen Energy Measurement Accuracy', '',
      '| Problem | Language | Size | perf RAPL (J) | CodeGreen (J) | Error % |',
      '|---------|----------|------|---------------|---------------|---------|']

for (prob, lang, size), profs in sorted(grouped.items()):
    perf_vals = [v for v in profs.get('perf', []) if v > 0]
    cg_vals = [v for v in profs.get('codegreen', []) if v > 0]
    if not perf_vals or not cg_vals:
        continue
    perf_mean = sum(perf_vals) / len(perf_vals)
    cg_mean = sum(cg_vals) / len(cg_vals)
    error = abs(perf_mean - cg_mean) / perf_mean * 100
    md.append(f'| {prob} | {lang} | {size} | {perf_mean:.2f} | {cg_mean:.2f} | {error:.1f}% |')

md.extend(['', f'*Generated on {data[\"metadata\"][\"timestamp\"][:10]} on {data[\"system_state\"][\"cpu_model\"]}*'])

md_file = out / 'accuracy_comparison.md'
md_file.write_text('\n'.join(md))
print(f'Markdown table saved to {md_file}')
print('\n'.join(md))
"

echo ""
echo "=== Artifacts generated ==="
ls -la "$OUT"/*.json "$OUT"/*.csv "$OUT"/*.md 2>/dev/null
