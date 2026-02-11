"""Compiler management for C/C++/Java benchmarks."""
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional
from benchmark.config import LanguageEnv

class CompilerManager:
    def __init__(self, build_dir: Optional[Path] = None):
        self.build_dir = build_dir or Path(tempfile.mkdtemp(prefix="codegreen_bench_"))
        self.build_dir.mkdir(parents=True, exist_ok=True)

    def compile(self, source: Path, env: LanguageEnv) -> Path:
        if not env.compiler:
            return source
        lang = self._detect_language(source, env)
        if lang == "java":
            return self._compile_java(source, env)
        return self._compile_native(source, env, lang)

    def _detect_language(self, source: Path, env: LanguageEnv) -> str:
        if env.compiler == "javac":
            return "java"
        if env.compiler in ("g++", "clang++"):
            return "cpp"
        return "c"

    def _compile_native(self, source: Path, env: LanguageEnv, lang: str) -> Path:
        binary = self.build_dir / source.stem
        extra_flags = []
        if source.suffix in (".gpp", ".gcc") or ".gpp" in source.name or ".gcc" in source.name:
            extra_flags = ["-x", "c++" if lang == "cpp" else "c"]
        # Separate linker flags (like -lm) from compiler flags - linker flags go at end
        compiler_flags = [f for f in env.flags if not f.startswith('-l')]
        linker_flags = [f for f in env.flags if f.startswith('-l')]
        cmd = [env.compiler] + extra_flags + compiler_flags + [str(source), "-o", str(binary)] + linker_flags
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"Compilation failed: {result.stderr}")
        return binary

    def _compile_java(self, source: Path, env: LanguageEnv) -> Path:
        cmd = [env.compiler] + env.flags + ["-d", str(self.build_dir), str(source)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"Java compilation failed: {result.stderr}")
        class_name = source.stem
        return self.build_dir / f"{class_name}.class"

    def get_run_command(self, source: Path, binary: Path, env: LanguageEnv, args: List[str]) -> List[str]:
        if not env.compiler:
            cmd_str = env.run_cmd.format(source=str(source))
            return cmd_str.split() + args
        if env.compiler == "javac":
            class_name = source.stem
            cmd_str = env.run_cmd.format(build_dir=str(self.build_dir), class_name=class_name)
            return cmd_str.split() + args
        cmd_str = env.run_cmd.format(binary=str(binary))
        return cmd_str.split() + args

    def cleanup(self):
        import shutil
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir, ignore_errors=True)
