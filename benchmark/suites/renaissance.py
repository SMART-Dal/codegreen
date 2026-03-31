"""Renaissance benchmark suite for modern JVM workloads.
Requires: Renaissance jar downloaded from https://renaissance.dev/
Usage: codegreen benchmark --suite renaissance --dataset-dir /path/to/renaissance.jar
"""
from pathlib import Path
from typing import List, Optional
from benchmark.suites.base import Suite, Task

RENAISSANCE_BENCHMARKS = [
    "akka-uct", "als", "chi-square", "db-shootout", "dec-tree",
    "dotty", "finagle-chirper", "finagle-http", "fj-kmeans",
    "future-genetic", "gauss-mix", "log-regression", "mnemonics",
    "movie-lens", "naive-bayes", "neo4j-analytics", "page-rank",
    "par-mnemonics", "philosophers", "reactors", "rx-scrabble",
    "scala-doku", "scala-kmeans", "scala-stm-bench7", "scrabble",
]


class RenaissanceSuite(Suite):
    def __init__(self, dataset_dir: str = "", benchmarks: List[str] = None, repetitions: int = 1):
        self.jar_path = Path(dataset_dir) if dataset_dir else None
        self.benchmarks = benchmarks or RENAISSANCE_BENCHMARKS
        self.repetitions = repetitions

    @property
    def name(self) -> str:
        return "renaissance"

    def discover(self, filters: Optional[dict] = None) -> List[Task]:
        if not self.jar_path or not self.jar_path.exists():
            raise FileNotFoundError(f"Renaissance jar not found at {self.jar_path}. "
                                    "Download from https://renaissance.dev/")
        selected = self.benchmarks
        if filters and "benchmarks" in filters:
            selected = [b for b in selected if b in filters["benchmarks"]]
        return [Task(
            name=b, language="java",
            run_command=["java", "-jar", str(self.jar_path), b, "-r", str(self.repetitions)],
            variant="default",
            metadata={"suite": "renaissance", "benchmark": b, "repetitions": self.repetitions}
        ) for b in selected]

    def build(self, task: Task) -> Task:
        return task

    @property
    def default_timeout(self) -> int:
        return 900
