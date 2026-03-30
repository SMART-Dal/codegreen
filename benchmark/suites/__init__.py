"""Benchmark suite implementations."""
from benchmark.suites.base import Suite, Task
from benchmark.suites.benchmarksgame import BenchmarksgameSuite
from benchmark.suites.perfopt import PerfOptSuite

SUITES = {
    "benchmarksgame": BenchmarksgameSuite,
    "perfopt": PerfOptSuite,
}

def get_suite(name: str, **kwargs) -> Suite:
    if name not in SUITES:
        raise ValueError(f"Unknown suite: {name}. Available: {list(SUITES.keys())}")
    return SUITES[name](**kwargs)
