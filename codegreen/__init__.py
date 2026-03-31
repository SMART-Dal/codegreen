"""
CodeGreen: Energy-aware software development tool

A comprehensive energy measurement and code optimization tool for developers
and researchers who need precise, fine-grained energy consumption analysis.
"""

__version__ = "0.3.12"
__author__ = "Saurabhsingh Rajput"
__email__ = "saurabh@dal.ca"
__description__ = "Energy-aware software development tool"

# Ensure package root is on sys.path for imports
import sys as _sys
from pathlib import Path as _Path

_install_dir = str(_Path(__file__).resolve().parent.parent)
if _install_dir not in _sys.path:
    _sys.path.insert(0, _install_dir)

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "__description__",
]