"""Back-compat shim. The EFG moved to `codegreen.analysis.efg`.

Kept so existing imports of `codegreen.analysis.cfg.energy_flow` keep working.
Attribute lookup is forwarded live rather than bound at import, because
`configure_heuristics` mutates the Ball & Larus constants at runtime and
callers read them back through whichever module they imported.

New code should import from `codegreen.analysis.efg`.
"""

from codegreen.analysis import efg as _efg
from codegreen.analysis.efg import adapter as _adapter
from codegreen.analysis.efg import graph as _graph
from codegreen.analysis.efg import heuristics as _heuristics
from codegreen.analysis.efg import paths as _paths
from codegreen.analysis.efg import serialize as _serialize
from codegreen.analysis.efg import types as _types

_SOURCES = (_efg, _types, _heuristics, _graph, _paths, _serialize, _adapter)


def __getattr__(name: str):
    for mod in _SOURCES:
        try:
            return getattr(mod, name)
        except AttributeError:
            continue
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list:
    return sorted({n for mod in _SOURCES for n in dir(mod) if not n.startswith("__")})
