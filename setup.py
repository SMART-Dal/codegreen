#!/usr/bin/env python3
"""CodeGreen setup with C++ backend compilation for wheel builds."""

from __future__ import annotations

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


class BuildWithCMake(build_py):
    """Build C++ backend via cmake, then run normal build_py."""

    def run(self):
        source_dir = Path(__file__).resolve().parent
        native_lib = _find_native_lib(source_dir)

        if not native_lib:
            self._try_cmake_build(source_dir)
            native_lib = _find_native_lib(source_dir)

        super().run()
        if self.build_lib:
            self._install_native_artifacts(source_dir, native_lib)

    def _try_cmake_build(self, source_dir: Path) -> None:
        try:
            build_dir = source_dir / "build"
            build_dir.mkdir(exist_ok=True)
            subprocess.check_call(
                ["cmake", str(source_dir), "-DCMAKE_BUILD_TYPE=Release",
                 f"-DPython3_EXECUTABLE={sys.executable}"],
                cwd=build_dir)
            subprocess.check_call(
                ["cmake", "--build", ".", "--config", "Release",
                 "-j", str(os.cpu_count() or 2)],
                cwd=build_dir)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"\n{'='*60}")
            print(f"NEMB C++ build failed: {e.__class__.__name__}: {e}")
            print(f"Installing Python-only (CLI, instrumentation, analysis work).")
            print(f"Energy measurement requires the NEMB native library.")
            print(f"To fix: install cmake (brew install cmake / apt install cmake)")
            print(f"then: pip install --force-reinstall --no-cache-dir codegreen")
            print(f"{'='*60}\n")

    def _install_native_artifacts(self, source_dir: Path, native_lib: Path | None) -> None:
        build_src = Path(self.build_lib) / "codegreen"
        for d in _EXCLUDE_DIRS:
            bad = build_src / d
            if bad.exists():
                shutil.rmtree(bad)

        if not native_lib:
            return

        dest_lib = build_src / "lib"
        dest_lib.mkdir(parents=True, exist_ok=True)
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
        for lang in ("c", "cpp"):
            header = rt_base / lang / "codegreen_runtime.h"
            if header.exists():
                dest_rt = dest_lib / "runtime" / lang
                dest_rt.mkdir(parents=True, exist_ok=True)
                self.copy_file(str(header), str(dest_rt / "codegreen_runtime.h"))


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
            "bin/codegreen",
            "bin/codegreen.exe",
            "config.json",
        ],
    },
    zip_safe=False,
)
