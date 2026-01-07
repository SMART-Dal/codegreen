"""
CodeGreen: Energy-aware software development tool

A comprehensive energy measurement and code optimization tool for developers
and researchers who need precise, fine-grained energy consumption analysis.
"""

__version__ = "0.1.0"
__author__ = "Saurabhsingh Rajput"
__email__ = "saurabh@dal.ca"
__description__ = "Energy-aware software development tool"

# Path independence: Setup paths when src package is first imported
# This runs BEFORE entrypoint.py imports, allowing sudo to work
import sys as _sys
import os as _os
from pathlib import Path as _Path

_init_file = _Path(__file__).resolve()
_install_dir = _init_file.parent.parent
_install_str = str(_install_dir)

if _install_str not in _sys.path:
    _sys.path.insert(0, _install_str)

if _os.getcwd() != _install_str:
    _os.chdir(_install_str)

# Import main components for easy access
try:
    from .cli import main as cli_main
    from .core.engine import MeasurementEngine
    from .core.config import Config
except ImportError:
    # Handle import errors gracefully during installation
    pass

# Package metadata
__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "__description__",
    "cli_main",
    "MeasurementEngine",
    "Config",
]