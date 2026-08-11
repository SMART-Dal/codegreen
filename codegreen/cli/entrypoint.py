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

os.environ.setdefault("CODEGREEN_INSTALL_DIR", _install_str)


def _unshadow() -> None:
    """Recover when the working directory shadows this package.

    An empty entry in PYTHONPATH (which a trailing colon produces) resolves to
    the working directory, so a directory named `codegreen` there is imported as
    a namespace package instead of the installed one. CodeGreen creates such a
    directory while instrumenting a workload, so running it twice in the same
    working directory would otherwise fail with an ImportError on its own
    version string. Load the real package over the namespace stand-in rather
    than purging modules, since this runs while a submodule is still importing.
    """
    mod = sys.modules.get("codegreen")
    if mod is None or getattr(mod, "__file__", None) is not None:
        return                      # resolved to the real package already
    import importlib.util
    pkg_dir = Path(_install_str) / "codegreen"
    init = pkg_dir / "__init__.py"
    if not init.is_file():
        return
    sys.path[:] = [p for p in sys.path if p not in ("", ".", os.getcwd())]
    spec = importlib.util.spec_from_file_location(
        "codegreen", init, submodule_search_locations=[str(pkg_dir)])
    real = importlib.util.module_from_spec(spec)
    sys.modules["codegreen"] = real
    spec.loader.exec_module(real)


_unshadow()

from codegreen.cli.cli import main_cli

def main_cli_wrapper():
    """Entry point wrapper."""
    if sys.argv[0].endswith('.exe'):
        sys.argv[0] = sys.argv[0][:-4]
    return main_cli()

if __name__ == '__main__':
    sys.exit(main_cli_wrapper())
