"""
CodeGreen: Know the true energy cost of your code.

Precise, hardware-level energy measurement for any program. Reads directly
from CPU and GPU energy counters (Intel/AMD RAPL, NVIDIA NVML, Apple
IOReport, Windows EMI). No estimation, no modeling -- just what the
hardware reports. Per-domain attribution, function-level profiling,
statistical analysis, and CI/CD-ready JSON output.
"""

try:
    from importlib.metadata import version as _pkg_version
    __version__ = _pkg_version("codegreen")
except Exception:
    __version__ = "0.3.15"  # fallback for dev/editable installs
__author__ = "Saurabhsingh Rajput"
__email__ = "saurabh@dal.ca"
__description__ = "Know the true energy cost of your code -- hardware-level measurement via RAPL, NVML, IOReport, EMI"

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