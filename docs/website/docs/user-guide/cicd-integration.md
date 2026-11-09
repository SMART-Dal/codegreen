# CI/CD Integration

CodeGreen can fail a pipeline when a workload uses more energy than a budget,
or more than the base branch. This page shows the gate, a regression check,
per-function budgets, and what the runner must provide.

## Runner requirements

Energy is read from hardware counters, so the job must run where they are
readable:

- **Bare metal or a VM that exposes RAPL.** Hosted cloud runners usually do
  not expose energy counters; use a self-hosted runner on a physical machine.
- **Counter access.** Run `sudo codegreen init-sensors` once on the runner
  host (it adds the runner's user to the `codegreen` group and installs a udev
  rule), then restart the runner service so it picks up the group. Check with
  `codegreen doctor`.
- **Containers** need read access to `/sys/class/powercap` (and the NVIDIA
  driver for GPU energy), for example by running privileged.
- **A quiet machine.** RAPL counts the whole package, including other jobs on
  the same host. Run energy jobs one at a time on dedicated, identical
  hardware, ideally with a fixed CPU frequency governor
  (`sudo cpupower frequency-set --governor performance`).

Install with `pip install codegreen` in the job (wheels for Linux x86_64 and
aarch64).

## Exit codes

| Exit | Meaning | Pipeline action |
|---|---|---|
| 0 | Valid measurement, within budget | pass |
| 1 | Mean energy above `--budget`, the command failed, or no energy could be read | fail |
| 3 | Invalid measurement (see `validity.reasons`), checked before the budget | fail, or retry: the number is not a measurement |

A gate that treats any non-zero exit as failure is correct; distinguish 3
when you want to retry instead of reporting a regression. Setting
`measurement.report.validity.fail_on_invalid` to `false` turns exit 3 into 0,
which lets invalid numbers pass silently, so keep the default in CI.

## Energy budget gate

```bash
codegreen run --repeat 10 --warmup 1 --sensors rapl --budget 60 -- python3 sums.py
```

```bash
set +e
codegreen run --repeat 10 --sensors rapl --budget 60 --json -- python3 sums.py > energy.json
status=$?
set -e
case $status in
  0) echo "within budget" ;;
  1) echo "over budget or command failed"; exit 1 ;;
  3) echo "invalid measurement: $(python3 -c 'import json; print(json.load(open("energy.json"))["validity"]["reasons"])')"; exit 1 ;;
esac
```

`--sensors rapl` keeps GPU energy out of a CPU workload's total; omit it (or
list `rapl nvidia`) when the GPU is part of the workload. Set the budget from
several runs on the same runner: look at `energy_j.mean`,
`energy_j.cv_percent_across_runs` and the 95 % interval in the JSON.

## Regression check against the base branch

Measure the base and the head on the same runner in the same job, then
compare the means. This script fails only when the head is more than the
given percentage above the base and the two 95 % intervals do not overlap:

```python
# compare_energy.py BASE.json HEAD.json MAX_INCREASE_PCT
import json, sys

def mean_energy(path):
    r = json.load(open(path))
    if r["validity"]["status"] != "valid":
        sys.exit(f"{path}: invalid measurement: {r['validity']['reasons']}")
    return r["energy_j"]["mean"], r["energy_j"]["ci95_upper"] - r["energy_j"]["mean"]

base, base_ci = mean_energy(sys.argv[1])
head, head_ci = mean_energy(sys.argv[2])
limit = float(sys.argv[3])
change = (head - base) / base * 100
print(f"base {base:.2f} J (+/-{base_ci:.2f}), head {head:.2f} J (+/-{head_ci:.2f}), change {change:+.1f}%")
sys.exit(1 if change > limit and head - head_ci > base + base_ci else 0)
```

```bash
git worktree add ../base "origin/$BASE_BRANCH"
(cd ../base && codegreen run --repeat 10 --sensors rapl --json -- python3 bench.py) > base.json
codegreen run --repeat 10 --sensors rapl --json -- python3 bench.py > head.json
python3 compare_energy.py base.json head.json 5
```

Two back-to-back measurements of the same program on an AMD EPYC 9554P:

```console
$ python3 compare_energy.py base.json head.json 5
base 59.08 J (+/-0.61), head 60.27 J (+/-1.93), change +2.0%
```

## Per-function budgets

`codegreen measure -g fine --json` reports each function's exclusive energy.
A budget file maps function names to joules:

```python
# check_functions.py REPORT.json BUDGETS.json
import json, sys

report, budgets = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
if report["validity"]["status"] != "valid":
    sys.exit(f"invalid measurement: {report['validity']['reasons']}")
over = {f: report["per_function_energy"][f]["exclusive_j"] for f, limit in budgets.items()
        if report["per_function_energy"][f]["exclusive_j"] > limit}
for f, j in over.items():
    print(f"{f}: {j:.2f} J exclusive > budget {budgets[f]} J")
sys.exit(1 if over else 0)
```

```console
$ codegreen measure python sums.py -g fine --sensors rapl --json > report.json
$ echo '{"square_sum": 30.0, "cube_sum": 25.0}' > budgets.json
$ python3 check_functions.py report.json budgets.json
square_sum: 35.82 J exclusive > budget 30.0 J
```

Only budget functions whose `quality` is `measured` (or at least
`aggregate_only`); `measure` exits 3 on an invalid run, so check its exit
code before running the script. For multi-file projects use
`codegreen project --json` and its `exclusive_energy_j` field.

## GitHub Actions

```yaml
name: energy
on: [pull_request]

jobs:
  energy:
    runs-on: [self-hosted, energy]      # bare-metal runner with init-sensors applied
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - run: pip install codegreen
      - name: Measure base and head
        run: |
          git worktree add ../base "origin/${{ github.base_ref }}"
          (cd ../base && codegreen run --repeat 10 --sensors rapl --json -- python3 bench.py) > base.json
          codegreen run --repeat 10 --sensors rapl --json -- python3 bench.py > head.json
      - name: Compare
        run: python3 compare_energy.py base.json head.json 5
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: energy
          path: "*.json"
```

## GitLab CI

```yaml
energy:
  tags: [energy]                        # bare-metal runner with init-sensors applied
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  script:
    - pip install codegreen
    - git fetch origin "$CI_MERGE_REQUEST_TARGET_BRANCH_NAME"
    - git worktree add ../base "origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME"
    - (cd ../base && codegreen run --repeat 10 --sensors rapl --json -- python3 bench.py) > base.json
    - codegreen run --repeat 10 --sensors rapl --json -- python3 bench.py > head.json
    - python3 compare_energy.py base.json head.json 5
  artifacts:
    when: always
    paths: ["*.json"]
```

Other CI systems follow the same pattern: install, run the measurement on a
dedicated runner, and act on the exit code.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `No energy data collected` (exit 1) | The counters are not readable: run `sudo codegreen init-sensors` on the host and restart the runner; in a container, expose `/sys/class/powercap` |
| Exit 3 with `RUN_BELOW_RESOLUTION` | The command finishes in a few milliseconds; measure a larger input or loop the work |
| Warning `GPU_IN_TOTAL` | The total includes GPU energy; pass `--sensors rapl` for CPU-only workloads |
| High `cv_percent_across_runs` | Other load on the host, frequency scaling or too few runs: use a dedicated runner, the `performance` governor and more `--repeat` |
