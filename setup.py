#!/usr/bin/env python3
"""CodeGreen setup -- delegates to pyproject.toml for metadata.
C++ backend must be built separately via install.sh or cmake."""

from setuptools import setup, find_packages

setup(
    packages=find_packages(where="."),
    package_data={
        "src.instrumentation": ["configs/*.json"],
        "src.instrumentation.language_runtimes.python": ["*.py"],
    },
    zip_safe=False,
)
