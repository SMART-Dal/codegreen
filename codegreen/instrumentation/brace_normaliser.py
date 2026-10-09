"""AST-driven brace-normalisation pre-pass.

After this pass, every node listed in the language's `non_braced_body_parents`
config has its referenced field(s) pointing to a `block` node (or, for
`if_statement.alternative`, another `if_statement` denoting an `else if`).
This makes the downstream insertion-point logic safe: every probe site is
inside a braced block, so inserting before/after a statement cannot escape
its parent's lexical scope.

Design:
- Candidate parent nodes are located via a config-built tree-sitter Query
  (consistent with the rest of the engine, which uses QueryCursor for all
  capture-based traversal). The query is composed from the language's
  `non_braced_body_parents` entries; new languages register patterns by
  adding entries to their JSON — no Python branching per language (OCP).
- The query narrows to O(parents); per-node field lookup
  (`node.child_by_field_name`) handles consequence/alternative/body — fields
  are not first-class capture predicates in tree-sitter, so this is the
  correct primitive once candidates are narrowed.
- Edits are applied descending-offset to a single string buffer, then the
  source is reparsed once. No byte arithmetic on the source text; offsets
  come from `Node.start_byte` / `Node.end_byte` only.

Cache: built queries are memoised on `(language, parents-spec hash)` so
repeated invocations across an analysis batch reuse the compiled Query.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

try:
    from tree_sitter import Tree, Node, Query, QueryCursor
    from tree_sitter_language_pack import get_language, get_parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    Tree = Node = Query = QueryCursor = None

_QUERY_CACHE: Dict[Tuple[str, Tuple[str, ...]], Any] = {}


def _build_query(language: str, parents: List[Dict[str, Any]]):
    """Compose a tree-sitter query capturing every configured parent node.

    Cached on (language, ordered type list). Returns None when no parents
    are configured for the language — caller treats that as a no-op pass.
    """
    if not parents:
        return None
    key = (language, tuple(p['type'] for p in parents))
    cached = _QUERY_CACHE.get(key)
    if cached is not None:
        return cached
    ts_lang = get_language(language)
    pattern = '\n'.join(f"({p['type']}) @brace_parent" for p in parents)
    query = Query(ts_lang, pattern)
    _QUERY_CACHE[key] = query
    return query


class BraceNormaliser:
    """AST-driven brace insertion for braceless control-flow bodies."""

    def __init__(self, source_code: str, tree: "Tree", language: str, config_manager):
        self._source = source_code
        self._tree = tree
        self._language = language
        self._config_manager = config_manager
        node_types = config_manager.get_node_types(language)
        self._parents = node_types.get('non_braced_body_parents', []) or []
        self._fields_by_type: Dict[str, List[str]] = {
            entry['type']: list(entry.get('fields', [])) for entry in self._parents
        }
        self._body_types = set(node_types.get('body_types', []) or [])
        self._planned: List[Tuple[int, str]] = []

    @property
    def planned_edits(self) -> List[Tuple[int, str]]:
        return list(self._planned)

    def _plan(self) -> None:
        self._planned.clear()
        if not self._parents:
            return
        query = _build_query(self._language, self._parents)
        if query is None:
            return
        cursor = QueryCursor(query)
        captures = cursor.captures(self._tree.root_node)
        parent_nodes = captures.get('brace_parent', []) if isinstance(captures, dict) else []
        seen_edges: set = set()
        for node in parent_nodes:
            for field_name in self._fields_by_type.get(node.type, ()):
                child = node.child_by_field_name(field_name)
                if child is None:
                    continue
                if child.type in self._body_types:
                    continue
                # if-else chain: do NOT wrap `else if`
                if node.type == 'if_statement' and field_name == 'alternative' and child.type == 'if_statement':
                    continue
                edge = (child.start_byte, child.end_byte)
                if edge in seen_edges:
                    continue
                seen_edges.add(edge)
                self._planned.append((child.start_byte, '{ '))
                self._planned.append((child.end_byte, ' }'))

    def normalise(self) -> Tuple[str, "Tree"]:
        if not TREE_SITTER_AVAILABLE or self._tree is None:
            raise RuntimeError(f"BraceNormaliser needs tree-sitter and a parsed tree for {self._language}")
        self._plan()
        if not self._planned:
            return self._source, self._tree
        raw = self._source.encode('utf-8')
        for offset, snippet in sorted(self._planned, key=lambda x: x[0], reverse=True):
            raw = raw[:offset] + snippet.encode('utf-8') + raw[offset:]
        new_tree = get_parser(self._language).parse(raw)
        self._planned.clear()
        return raw.decode('utf-8'), new_tree
