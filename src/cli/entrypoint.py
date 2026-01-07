"""
CodeGreen entry point with path independence.

This ensures codegreen can run from any directory and with sudo.
"""

import sys
import os
from pathlib import Path

_entry_file = Path(__file__).resolve()
_install_dir = _entry_file.parent.parent.parent
_install_str = str(_install_dir)

if _install_str not in sys.path:
    sys.path.insert(0, _install_str)

if os.getcwd() != _install_str:
    os.chdir(_install_str)

from src.cli.cli import main_cli

def main_cli_wrapper():
    """Entry point wrapper."""
    if sys.argv[0].endswith('.exe'):
        sys.argv[0] = sys.argv[0][:-4]
    return main_cli()

if __name__ == '__main__':
    sys.exit(main_cli_wrapper())
