"""Benchmark suite implementations."""
from benchmark.suites.base import Suite, Task
from benchmark.suites.benchmarksgame import BenchmarksgameSuite
from benchmark.suites.perfopt import PerfOptSuite
from benchmark.suites.dacapo import DaCapoSuite
from benchmark.suites.renaissance import RenaissanceSuite

SUITES = {
    "benchmarksgame": BenchmarksgameSuite,
    "perfopt": PerfOptSuite,
    "dacapo": DaCapoSuite,
    "renaissance": RenaissanceSuite,
}

def get_suite(name: str, **kwargs) -> Suite:
    if name not in SUITES:
        raise ValueError(f"Unknown suite: {name}. Available: {list(SUITES.keys())}")
    return SUITES[name](**kwargs)
