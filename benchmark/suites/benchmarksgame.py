"""Benchmarksgame suite: classic single-file compile-and-run benchmarks."""
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from benchmark.suites.base import Suite, Task
from benchmark.config import BenchmarkConfig, LanguageEnv


DEFAULT_DIR = Path(__file__).parent.parent / "benchmarksgame"

PROBLEMS = [
    {"name": "nbody", "sizes": ["1000", "5000", "50000"]},
    {"name": "spectralnorm", "sizes": ["100", "500", "1000"]},
    {"name": "binarytrees", "sizes": ["10", "14", "18"]},
    {"name": "fannkuchredux", "sizes": ["7", "10", "11"]},
]

LANGUAGES = {
    "python": LanguageEnv(".python3", "python3 {source}"),
    "c": LanguageEnv(".gcc", "{binary}", compiler="gcc",
                     flags=["-O3", "-march=native", "-lm", "-lpthread"]),
    "cpp": LanguageEnv(".gpp", "{binary}", compiler="g++",
                       flags=["-O3", "-march=native", "-lpthread"]),
    "java": LanguageEnv(".java", "java -cp {build_dir} {class_name}",
                        compiler="javac", flags=[]),
}


class BenchmarksgameSuite(Suite):
    def __init__(self, benchmarks_dir: Optional[Path] = None,
                 languages: Optional[List[str]] = None,
                 problems: Optional[List[str]] = None,
                 sizes: Optional[List[str]] = None):
        self.benchmarks_dir = benchmarks_dir or DEFAULT_DIR
        self._lang_filter = languages
        self._problem_filter = problems
        self._size_filter = sizes
        self._build_dir = Path(tempfile.mkdtemp(prefix="cg_bench_"))
        self._build_dir.mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        return "benchmarksgame"

    def discover(self, filters: Optional[dict] = None) -> List[Task]:
        tasks = []
        lang_filter = (filters or {}).get("languages", self._lang_filter) or list(LANGUAGES.keys())
        prob_filter = (filters or {}).get("problems", self._problem_filter)

        for prob_cfg in PROBLEMS:
            prob_name = prob_cfg["name"]
            if prob_filter and prob_name not in prob_filter:
                continue
            sizes = self._size_filter or prob_cfg["sizes"]

            for lang_name in lang_filter:
                env = LANGUAGES.get(lang_name)
                if not env:
                    continue
                source = self._find_source(prob_name, env)
                if not source:
                    continue

                for size in sizes:
                    validation = self._load_validation(prob_name, size)
                    tasks.append(Task(
                        name=f"{prob_name}/{lang_name}/{size}",
                        run_command=[],  # filled by build()
                        variant="default",
                        language=lang_name,
                        source_file=source,
                        working_dir=self.benchmarks_dir / prob_name,
                        validation_output=validation,
                        metadata={"problem": prob_name, "size": size,
                                  "env": env},
                    ))
        return tasks

    def build(self, task: Task) -> Task:
        env: LanguageEnv = task.metadata["env"]
        size = task.metadata["size"]
        source = task.source_file

        if env.compiler:
            binary = self._compile(source, env)
        else:
            binary = source

        cmd = self._get_run_command(source, binary, env, [size])
        task.run_command = cmd
        return task

    def _find_source(self, problem: str, env: LanguageEnv) -> Optional[Path]:
        problem_dir = self.benchmarks_dir / problem
        if not problem_dir.exists():
            return None
        pattern = f"{problem}*{env.extension}*"
        files = sorted(problem_dir.glob(pattern))
        clean = [f for f in files if '_coarse' not in f.name
                 and '_instrumented' not in f.name]
        return (clean or files)[0] if (clean or files) else None

    def _load_validation(self, problem: str, size: str) -> Optional[str]:
        out_file = self.benchmarks_dir / problem / f"{size}_out"
        if out_file.exists():
            return out_file.read_text()
        return None

    def _compile(self, source: Path, env: LanguageEnv) -> Path:
        if env.compiler == "javac":
            cmd = [env.compiler] + env.flags + ["-d", str(self._build_dir), str(source)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                raise RuntimeError(f"Java compilation failed: {result.stderr}")
            return self._build_dir / f"{source.stem}.class"

        binary = self._build_dir / source.stem
        lang = "c++" if env.compiler in ("g++", "clang++") else "c"
        extra = []
        if source.suffix in (".gpp", ".gcc") or ".gpp" in source.name:
            extra = ["-x", lang]
        compiler_flags = [f for f in env.flags if not f.startswith('-l')]
        linker_flags = [f for f in env.flags if f.startswith('-l')]
        cmd = [env.compiler] + extra + compiler_flags + [str(source), "-o", str(binary)] + linker_flags
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"Compilation failed: {result.stderr}")
        return binary

    def _get_run_command(self, source: Path, binary: Path,
                         env: LanguageEnv, args: List[str]) -> List[str]:
        if not env.compiler:
            return env.run_cmd.format(source=str(source)).split() + args
        if env.compiler == "javac":
            return env.run_cmd.format(
                build_dir=str(self._build_dir),
                class_name=source.stem).split() + args
        return env.run_cmd.format(binary=str(binary)).split() + args

    def cleanup(self):
        import shutil
        if self._build_dir.exists():
            shutil.rmtree(self._build_dir, ignore_errors=True)
