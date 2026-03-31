"""DaCapo benchmark suite for Java workloads.
Requires: DaCapo jar downloaded from https://dacapobench.org/
Usage: codegreen benchmark --suite dacapo --dataset-dir /path/to/dacapo.jar
"""
from pathlib import Path
from typing import List, Optional
from benchmark.suites.base import Suite, Task

DACAPO_BENCHMARKS = [
    "avrora", "batik", "biojava", "cassandra", "eclipse", "fop",
    "graphchi", "h2", "h2o", "jme", "jython", "kafka",
    "luindex", "lusearch", "pmd", "spring", "sunflow",
    "tomcat", "tradebeans", "tradesoap", "xalan", "zxing",
]


class DaCapoSuite(Suite):
    def __init__(self, dataset_dir: str = "", benchmarks: List[str] = None):
        self.jar_path = Path(dataset_dir) if dataset_dir else None
        self.benchmarks = benchmarks or DACAPO_BENCHMARKS

    @property
    def name(self) -> str:
        return "dacapo"

    def discover(self, filters: Optional[dict] = None) -> List[Task]:
        if not self.jar_path or not self.jar_path.exists():
            raise FileNotFoundError(f"DaCapo jar not found at {self.jar_path}. "
                                    "Download from https://dacapobench.org/")
        selected = self.benchmarks
        if filters and "benchmarks" in filters:
            selected = [b for b in selected if b in filters["benchmarks"]]
        return [Task(
            name=b, language="java",
            run_command=["java", "-jar", str(self.jar_path), b],
            variant="default",
            metadata={"suite": "dacapo", "benchmark": b}
        ) for b in selected]

    def build(self, task: Task) -> Task:
        return task  # DaCapo is pre-built

    @property
    def default_timeout(self) -> int:
        return 600
