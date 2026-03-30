"""Shared tree-sitter Java parser and language instance.

All modules should import from here rather than creating their own parsers.
"""

try:
    import tree_sitter_java as tsjava
    from tree_sitter import Language, Parser, Query, QueryCursor
    LANG = Language(tsjava.language())
    parser = Parser(LANG)
    HAS_TS = True
except ImportError:
    LANG = None
    parser = None
    HAS_TS = False
    Query = None
    QueryCursor = None


def parse(code: str):
    if not HAS_TS:
        raise RuntimeError("tree-sitter and tree-sitter-java required")
    return parser.parse(bytes(code, "utf8"))
