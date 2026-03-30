"""Base Suite protocol and Task dataclass."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class Task:
    """A single benchmark task within a suite."""
    name: str
    run_command: List[str]
    variant: str = "default"
    language: str = "python"
    source_file: Optional[Path] = None
    working_dir: Optional[Path] = None
    validation_output: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class Suite(ABC):
    """Protocol for benchmark suites. Each suite knows how to discover,
    build, and produce runnable tasks."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Suite identifier (e.g., 'benchmarksgame', 'perfopt')."""

    @abstractmethod
    def discover(self, filters: Optional[dict] = None) -> List[Task]:
        """Discover available tasks. filters can narrow by language, problem, etc."""

    @abstractmethod
    def build(self, task: Task) -> Task:
        """Build/compile if needed. Returns task with updated run_command."""

    @property
    def default_timeout(self) -> int:
        """Default timeout in seconds for tasks in this suite."""
        return 300

    def validate_output(self, output: str, task: Task) -> bool:
        """Validate program output against expected. Default: always valid."""
        if task.validation_output is None:
            return True
        expected = task.validation_output.strip()
        actual = output.strip()
        if expected == actual:
            return True
        try:
            for exp, act in zip(expected.split('\n'), actual.split('\n')):
                if abs(float(exp.strip()) - float(act.strip())) > 1e-6:
                    return False
            return True
        except (ValueError, TypeError):
            return False

    def cleanup(self):
        """Clean up build artifacts."""
