#!/usr/bin/env python3
"""CodeGreen setup with C++ backend compilation for wheel builds."""

from __future__ import annotations  # Required for Path | None on 3.10

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from setuptools import setup, Distribution
from setuptools.command.build_py import build_py

_EXCLUDE_DIRS = {"ide", "measurement", "optimizer"}
_NATIVE_LIB = {
    "Darwin": "libcodegreen-nemb.dylib",
    "Linux": "libcodegreen-nemb.so",
    "Windows": "codegreen-nemb.dll",
}


def _find_native_lib(source_dir: Path) -> Path | None:
    """Find the NEMB shared library for the current platform."""
    name = _NATIVE_LIB.get(platform.system())
    if not name:
        return None
    path = source_dir / "lib" / name
    return path if path.exists() else None


def _try_java_build(java_dir: Path) -> Path | None:
    """Best-effort Java JAR build. Skip silently if no JDK."""
    jar_path = java_dir / "codegreen-runtime.jar"
    if jar_path.exists():
        return jar_path
    if not shutil.which("javac") or not shutil.which("jar"):
        return None
    try:
        srcs = list(java_dir.rglob("*.java"))
        if not srcs:
            return None
        subprocess.run(["javac", *map(str, srcs)], cwd=str(java_dir),
                       capture_output=True, check=True)
        classes = [str(p.relative_to(java_dir)) for p in java_dir.rglob("*.class")]
        if not classes:
            return None
        subprocess.run(["jar", "cf", "codegreen-runtime.jar", *classes],
                       cwd=str(java_dir), capture_output=True, check=True)
        return jar_path if jar_path.exists() else None
    except (subprocess.CalledProcessError, OSError):
        return None


class BuildWithCMake(build_py):
    """Build C++ backend via cmake + Java JAR via javac, then run normal build_py."""

    def run(self):
        source_dir = Path(__file__).resolve().parent
        native_lib = _find_native_lib(source_dir)

        if not native_lib:
            self._try_cmake_build(source_dir)
            native_lib = _find_native_lib(source_dir)

        java_dir = source_dir / "codegreen" / "instrumentation" / "language_runtimes" / "java"
        java_jar = _try_java_build(java_dir)

        super().run()
        if self.build_lib:
            self._install_native_artifacts(source_dir, native_lib, java_jar)

    def _try_cmake_build(self, source_dir: Path) -> None:
        try:
            build_dir = source_dir / "build"
            build_dir.mkdir(exist_ok=True)
            r = subprocess.run(
                ["cmake", str(source_dir), "-DCMAKE_BUILD_TYPE=Release",
                 f"-DPython3_EXECUTABLE={sys.executable}"],
                cwd=build_dir, capture_output=True, text=True)
            if r.returncode != 0:
                raise subprocess.CalledProcessError(r.returncode, r.args, r.stdout, r.stderr)
            r = subprocess.run(
                ["cmake", "--build", ".", "--config", "Release",
                 "-j", str(os.cpu_count() or 2)],
                cwd=build_dir, capture_output=True, text=True)
            if r.returncode != 0:
                raise subprocess.CalledProcessError(r.returncode, r.args, r.stdout, r.stderr)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            msg = [f"\n{'='*60}",
                   "NEMB C++ build failed: " + str(e),
                   "Energy measurement will not be available.",
                   "Installing Python-only (CLI, instrumentation, analysis work)."]
            if isinstance(e, subprocess.CalledProcessError):
                if e.stderr:
                    msg.append(f"\ncmake stderr:\n{e.stderr.strip()[-800:]}")
                if e.stdout:
                    msg.append(f"\ncmake stdout:\n{e.stdout.strip()[-400:]}")
                msg.append("\nCommon fixes:")
                msg.append("  macOS: xcode-select --install  (for C++ compiler)")
                msg.append("  Linux: apt install build-essential cmake")
                msg.append("  Windows: install Visual Studio Build Tools + cmake")
            elif isinstance(e, FileNotFoundError):
                msg.append("cmake not found. Install: brew install cmake / apt install cmake")
            msg.append("To retry: pip install --force-reinstall --no-cache-dir codegreen")
            msg.append(f"{'='*60}\n")
            sys.stderr.write("\n".join(msg) + "\n")

    def _install_native_artifacts(self, source_dir: Path, native_lib: Path | None,
                                   java_jar: Path | None = None) -> None:
        build_src = Path(self.build_lib) / "codegreen"
        for d in _EXCLUDE_DIRS:
            bad = build_src / d
            if bad.exists():
                shutil.rmtree(bad)

        if not native_lib and not java_jar:
            return

        dest_lib = build_src / "lib"
        dest_lib.mkdir(parents=True, exist_ok=True)
        if native_lib:
            self.copy_file(str(native_lib), str(dest_lib / native_lib.name))

        bin_file = source_dir / "build" / "bin" / "codegreen"
        if not bin_file.exists():
            bin_file = source_dir / "bin" / "codegreen"
        if bin_file.exists():
            dest_bin = build_src / "bin"
            dest_bin.mkdir(parents=True, exist_ok=True)
            self.copy_file(str(bin_file), str(dest_bin / "codegreen"))
            os.chmod(str(dest_bin / "codegreen"), 0o755)

        rt_base = source_dir / "codegreen" / "instrumentation" / "language_runtimes"
        for lang in ("c",):
            header = rt_base / lang / "codegreen_runtime.h"
            if header.exists():
                dest_rt = dest_lib / "runtime" / lang
                dest_rt.mkdir(parents=True, exist_ok=True)
                self.copy_file(str(header), str(dest_rt / "codegreen_runtime.h"))
        cpp_header = rt_base / "cpp" / "codegreen" / "runtime.hpp"
        if cpp_header.exists():
            dest_rt = dest_lib / "runtime" / "cpp" / "codegreen"
            dest_rt.mkdir(parents=True, exist_ok=True)
            self.copy_file(str(cpp_header), str(dest_rt / "runtime.hpp"))

        if java_jar and java_jar.exists():
            dest_java = dest_lib / "runtime" / "java"
            dest_java.mkdir(parents=True, exist_ok=True)
            self.copy_file(str(java_jar), str(dest_java / java_jar.name))


class BinaryDistribution(Distribution):
    def has_ext_modules(self):
        return _find_native_lib(Path(__file__).resolve().parent) is not None


PACKAGES = [
    "codegreen", "codegreen.cli", "codegreen.analyzer", "codegreen.instrumentation", "codegreen.utils",
    "codegreen.analysis", "codegreen.analysis.cfg",
    "benchmark", "benchmark.validation", "benchmark.suites",
]

setup(
    distclass=BinaryDistribution,
    packages=PACKAGES,
    cmdclass={"build_py": BuildWithCMake},
    package_data={
        "codegreen.instrumentation": [
            "configs/*.json",
            "language_runtimes/python/*.py",
            "language_runtimes/c/*.h",
            "language_runtimes/cpp/*.h",
            "language_runtimes/cpp/*.hpp",
            "language_runtimes/java/**/*.java",
        ],
        "codegreen": [
            "lib/*.so",
            "lib/*.dylib",
            "lib/*.dll",
            "lib/runtime/**/*.h",
            "lib/runtime/**/*.hpp",
            "lib/runtime/**/*.jar",
            "bin/codegreen",
            "bin/codegreen.exe",
            "config.json",
        ],
    },
    zip_safe=False,
)
