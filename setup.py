#!/usr/bin/env python3
"""CodeGreen setup with C++ backend compilation for wheel builds."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from setuptools import setup, Distribution
from setuptools.command.build_py import build_py

# Directories that must NOT be in the wheel
_EXCLUDE_DIRS = {"ide", "measurement", "optimizer"}


class BuildWithCMake(build_py):
    """Build C++ backend via cmake, then run normal build_py."""

    def run(self):
        source_dir = Path(__file__).resolve().parent
        lib_dir = source_dir / "lib"
        so_file = lib_dir / "libcodegreen-nemb.so"

        if not so_file.exists():
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

        super().run()

        if not self.build_lib:
            return

        build_src = Path(self.build_lib) / "codegreen"

        # Remove unwanted directories that setuptools auto-included
        for d in _EXCLUDE_DIRS:
            bad = build_src / d
            if bad.exists():
                shutil.rmtree(bad)

        # Copy native files
        if so_file.exists():
            dest_lib = build_src / "lib"
            dest_lib.mkdir(parents=True, exist_ok=True)
            self.copy_file(str(so_file), str(dest_lib / "libcodegreen-nemb.so"))

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
        return True


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
            "lib/runtime/**/*.h",
            "bin/codegreen",
            "config.json",
        ],
    },
    zip_safe=False,
)
