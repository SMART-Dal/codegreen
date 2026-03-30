"""PerfOpt suite: Java performance optimization benchmarks with JMH.
Dataset: 65 tasks across kafka, netty, presto, RoaringBitmap.
Each task has original and developer-patched variants measured via JMH."""
import csv
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from benchmark.suites.base import Suite, Task


def _find_java_home() -> str:
    """Auto-detect JAVA_HOME from common locations."""
    import os
    if os.environ.get("JAVA_HOME"):
        return os.environ["JAVA_HOME"]
    for path in ["/usr/lib/jvm/java-11-openjdk-amd64",
                 "/usr/lib/jvm/java-11-openjdk",
                 "/usr/lib/jvm/java-17-openjdk-amd64"]:
        if Path(path).exists():
            return path
    return "java"


class PerfOptSuite(Suite):
    """PerfOpt benchmark suite.

    Requires:
        dataset_dir: Path to PerfOpt dataset (contains PerfOpt.csv)
        jars_dir: Path to pre-built JMH JARs ({project}/{commit}_{variant}/*.jar)
    """
    def __init__(self, dataset_dir: Optional[Path] = None,
                 jars_dir: Optional[Path] = None,
                 java_home: Optional[str] = None,
                 projects: Optional[List[str]] = None,
                 tasks: Optional[List[str]] = None,
                 jmh_wi: int = 5, jmh_i: int = 10):
        if not dataset_dir:
            raise ValueError("PerfOpt suite requires --dataset-dir pointing to PerfOpt dataset "
                             "(directory containing PerfOpt.csv)")
        self.dataset_dir = Path(dataset_dir)
        if not jars_dir:
            raise ValueError("PerfOpt suite requires --jars-dir pointing to pre-built JMH JARs")
        self.jars_dir = Path(jars_dir)
        self.java_home = java_home or _find_java_home()
        self._project_filter = projects
        self._task_filter = tasks
        self.jmh_wi = jmh_wi
        self.jmh_i = jmh_i

    @property
    def name(self) -> str:
        return "perfopt"

    @property
    def default_timeout(self) -> int:
        return 900  # JMH with @Param combos can take 10+ minutes

    def discover(self, filters: Optional[dict] = None) -> List[Task]:
        csv_path = self.dataset_dir / "PerfOpt.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"PerfOpt.csv not found at {csv_path}")

        proj_filter = (filters or {}).get("projects", self._project_filter)
        task_filter = (filters or {}).get("tasks", self._task_filter)
        tasks = []

        with open(csv_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                project = row.get("repository", "")
                commit = row.get("id", "")
                source = row.get("source_code", "")
                jmh_case = row.get("jmh_case", "")

                if proj_filter and project not in proj_filter:
                    continue
                if task_filter and commit not in task_filter:
                    continue
                if not source.endswith(".java"):
                    continue

                # Check if pre-built JARs exist for both variants
                for variant in ("org", "dev"):
                    jar_dir = self.jars_dir / project / f"{commit}_{variant}"
                    if not jar_dir.exists():
                        continue
                    jars = list(jar_dir.glob("*.jar"))
                    if not jars:
                        continue

                    variant_name = "original" if variant == "org" else "patched"
                    tasks.append(Task(
                        name=f"{project}/{commit}/{variant_name}",
                        run_command=[],  # filled by build()
                        variant=variant_name,
                        language="java",
                        source_file=Path(source),
                        working_dir=jar_dir,
                        metadata={
                            "project": project,
                            "commit": commit,
                            "jmh_case": jmh_case,
                            "jar_path": str(jars[0]),
                            "source_code": source,
                        },
                    ))
        return tasks

    def build(self, task: Task) -> Task:
        """PerfOpt uses pre-built JARs, so build is just constructing the JMH command."""
        jar = task.metadata["jar_path"]
        jmh_case = task.metadata["jmh_case"]
        java_bin = f"{self.java_home}/bin/java"

        task.run_command = [
            "taskset", "-c", "0-7",
            java_bin, "-Djmh.ignoreLock=true",
            "-jar", jar,
            f".*{jmh_case}.*",
            "-f", "1",
            "-wi", str(self.jmh_wi),
            "-i", str(self.jmh_i),
            "-r", "1",
        ]
        return task

    def validate_output(self, output: str, task: Task) -> bool:
        # JMH always produces valid output if it completes without error
        return True

    def get_task_pairs(self) -> List[tuple]:
        """Return (original_task, patched_task) pairs for comparison."""
        tasks = self.discover()
        by_commit = {}
        for t in tasks:
            key = f"{t.metadata['project']}/{t.metadata['commit']}"
            by_commit.setdefault(key, {})[t.variant] = t
        pairs = []
        for key, variants in by_commit.items():
            if "original" in variants and "patched" in variants:
                pairs.append((variants["original"], variants["patched"]))
        return pairs
