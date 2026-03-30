"""Lightweight project-wide call graph via tree-sitter queries.

Scalable: uses tree-sitter queries (C-level matching) to extract method
declarations and invocations across all files. No full CFG or dataflow
needed -- just name-based resolution. Handles large projects (1000+ files)
in seconds.

Limitations:
- Name-based resolution (no type inference): overloaded methods with same
  name are merged. Sufficient for PerfOpt where method names are mostly unique.
- Does not resolve dynamic dispatch or reflection.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

from src.analysis._ts_java import LANG as _LANG, parser as _parser, HAS_TS as _HAS_TS, parse as _parse

try:
    from tree_sitter import Query, QueryCursor
    _Q_DECLS = Query(_LANG, """
        (method_declaration name: (identifier) @name) @decl
        (constructor_declaration name: (identifier) @name) @decl
    """)
    _Q_INVOCATIONS = Query(_LANG, "(method_invocation name: (identifier) @call_name) @call")
except Exception:
    pass


@dataclass
class MethodInfo:
    name: str
    qualified: str  # class.method
    file: str
    start_line: int
    end_line: int
    callees: set[str] = field(default_factory=set)
    callers: set[str] = field(default_factory=set)


@dataclass
class CallGraph:
    methods: dict[str, MethodInfo] = field(default_factory=dict)  # qualified_name -> info
    _by_short_name: dict[str, list[str]] = field(default_factory=dict)  # short_name -> [qualified]

    def add_method(self, info: MethodInfo):
        self.methods[info.qualified] = info
        self._by_short_name.setdefault(info.name, []).append(info.qualified)

    def resolve(self, short_name: str) -> list[str]:
        return self._by_short_name.get(short_name, [])

    def callers_of(self, qualified: str) -> set[str]:
        m = self.methods.get(qualified)
        return m.callers if m else set()

    def callees_of(self, qualified: str) -> set[str]:
        m = self.methods.get(qualified)
        return m.callees if m else set()

    def methods_in_file(self, file_path: str) -> list[MethodInfo]:
        return [m for m in self.methods.values() if m.file == file_path]

    def methods_at_lines(self, file_path: str, start: int, end: int) -> list[MethodInfo]:
        return [m for m in self.methods.values()
                if m.file == file_path and m.start_line <= end and m.end_line >= start]


def _extract_class_name(node) -> str:
    p = node.parent
    while p is not None:
        if p.type == "class_declaration":
            name_node = p.child_by_field_name("name")
            if name_node:
                return name_node.text.decode("utf8")
        p = p.parent
    return ""


def build_call_graph(files: dict[str, str]) -> CallGraph:
    """Build call graph from multiple Java files.

    Args:
        files: {file_path: source_code} mapping

    Returns:
        CallGraph with methods and caller/callee edges resolved by name.
    """
    cg = CallGraph()

    for file_path, code in files.items():
        tree = _parse(code)
        root = tree.root_node

        for _, captures in QueryCursor(_Q_DECLS).matches(root):
            decl_nodes = captures.get("decl", [])
            name_nodes = captures.get("name", [])
            if not decl_nodes or not name_nodes:
                continue
            decl = decl_nodes[0]
            name = name_nodes[0].text.decode("utf8")
            cls = _extract_class_name(decl)
            qualified = f"{cls}.{name}" if cls else name

            callees: set[str] = set()
            for _, call_caps in QueryCursor(_Q_INVOCATIONS).matches(decl):
                call_names = call_caps.get("call_name", [])
                for cn in call_names:
                    callees.add(cn.text.decode("utf8"))

            cg.add_method(MethodInfo(
                name=name, qualified=qualified, file=file_path,
                start_line=decl.start_point[0] + 1,
                end_line=decl.end_point[0] + 1,
                callees=callees,
            ))

    for qname, info in cg.methods.items():
        resolved_callees: set[str] = set()
        for callee_short in info.callees:
            targets = cg.resolve(callee_short)
            for target_q in targets:
                if target_q != qname:
                    resolved_callees.add(target_q)
                    cg.methods[target_q].callers.add(qname)
            if not targets:
                resolved_callees.add(callee_short)
        info.callees = resolved_callees

    return cg


def build_call_graph_from_dir(root_dir: str | Path, glob: str = "**/*.java") -> CallGraph:
    """Build call graph from all Java files under a directory."""
    root = Path(root_dir)
    files = {}
    for f in root.glob(glob):
        try:
            files[str(f.relative_to(root))] = f.read_text()
        except Exception:
            continue
    return build_call_graph(files)


def diff_affected_methods(cg: CallGraph, changed_files: dict[str, list[tuple[int, int]]]) -> list[MethodInfo]:
    """Find methods affected by diff line ranges across files.

    Args:
        cg: call graph
        changed_files: {file_path: [(start_line, end_line), ...]}

    Returns:
        List of MethodInfo for directly changed methods.
    """
    affected = []
    for file_path, ranges in changed_files.items():
        for start, end in ranges:
            affected.extend(cg.methods_at_lines(file_path, start, end))
    return affected


def cross_file_call_counts(cg: CallGraph, changed_methods: list[MethodInfo]) -> tuple[int, int]:
    """Count cross-file caller/callee edges among changed methods.

    Returns:
        (callee_in_diff, caller_in_diff) -- how many cross-file call edges
        connect changed methods to other changed methods.
    """
    changed_set = {m.qualified for m in changed_methods}
    changed_files = {m.file for m in changed_methods}

    callee_in_diff = 0
    caller_in_diff = 0
    for m in changed_methods:
        for callee_q in m.callees:
            target = cg.methods.get(callee_q)
            if target and target.qualified in changed_set and target.file != m.file:
                callee_in_diff += 1
        for caller_q in m.callers:
            caller = cg.methods.get(caller_q)
            if caller and caller.qualified in changed_set and caller.file != m.file:
                caller_in_diff += 1

    return callee_in_diff, caller_in_diff
