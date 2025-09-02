"""
CodeGreen: Energy-aware software development tool

A comprehensive energy measurement and code optimization tool for developers
and researchers who need precise, fine-grained energy consumption analysis.
"""

__version__ = "0.1.0"
__author__ = "Saurabhsingh Rajput"
__email__ = "saurabh@dal.ca"
__description__ = "Energy-aware software development tool"

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