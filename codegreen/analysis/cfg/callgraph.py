"""Lightweight project-wide call graph via tree-sitter, for Java and Python
(language inferred from the file suffixes; a mixed set is refused).

Scalable: tree-sitter queries (C-level matching) extract method and
constructor declarations and their call sites across all files, resolved by
name. Handles large projects (1000+ files) in seconds.

Methods are keyed by package-qualified name (`pkg.Outer.Inner.method`), with
`@L<line>` added only to tell overloads in one type apart, so same-named types
in different packages and overloads never overwrite each other.

Edges: method invocations, method references (`X::m`, `X::new`), object
creation (`new X(...)` -> X's constructors) and `this(...)` delegation.

Two edge sets:
- `callees`/`callers`: name-based, every same-named method is a candidate.
  This over-approximates, the safe direction for "what can reach this method"
  (reflection and `super(...)` targets excepted).
- `typed_callees`/`typed_callers`: {target: confidence}, resolved from the
  receiver's declared type (parameter, local, field, `this`, a type name for
  static calls, `new T`) through imports and the same package, widened to the
  type's supertypes (inherited declarations) and subtypes (overrides reached
  by dynamic dispatch). A call on a type outside the project (java.util.List)
  gets no typed edge. Confidence follows Codebase-Memory (arXiv 2603.27277,
  s3.4): 0.95 import/same-package type, 0.85 simple-name type match, 0.75 a
  receiver of unknown type whose method name is unique, 0.5 otherwise.

Python keys are module-qualified (`pkg.mod.Class.method`). Typed edges follow
the same cascade on names: 0.95 through the file's imports (including
relative ones) or a `self.`/`cls.`/`super()` call resolved on the enclosing
class, its bases and its subclasses; 0.90 a name defined in the same module;
0.75 a unique project-wide name; 0.5 otherwise. A call on a name bound to a
module or class outside the project gets no typed edge.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

from codegreen.analysis._ts_java import LANG as _LANG, HAS_TS as _HAS_TS, parse as _parse

if _HAS_TS:
    from tree_sitter import Query, QueryCursor
    _Q_DECLS = Query(_LANG, """
        (method_declaration name: (identifier) @name) @decl
        (constructor_declaration name: (identifier) @name) @decl
    """)
    _Q_CALLS = Query(_LANG, """
        (method_invocation name: (identifier) @call)
        (method_reference (identifier) @call .)
        (object_creation_expression type: (type_identifier) @call)
        (object_creation_expression type: (generic_type (type_identifier) @call))
        (method_reference (type_identifier) @call "::" "new")
    """)
    _Q_THIS = Query(_LANG, '(explicit_constructor_invocation constructor: (this) @this)')
    _Q_PKG = Query(_LANG, "(package_declaration (_) @pkg)")
    _Q_IMPORT = Query(_LANG, "(import_declaration (scoped_identifier) @imp)")

_TYPES = ("class_declaration", "interface_declaration", "enum_declaration",
          "record_declaration", "annotation_type_declaration")


@dataclass
class MethodInfo:
    name: str
    qualified: str  # class.method
    file: str
    start_line: int
    end_line: int
    callees: set[str] = field(default_factory=set)
    callers: set[str] = field(default_factory=set)
    typed_callees: dict[str, float] = field(default_factory=dict)
    typed_callers: dict[str, float] = field(default_factory=dict)


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
    """Enclosing type chain of `node`, outermost first (`Outer.Inner`)."""
    names, p = [], node.parent
    while p is not None:
        if p.type in _TYPES and p.child_by_field_name("name") is not None:
            names.append(p.child_by_field_name("name").text.decode("utf8"))
        p = p.parent
    return ".".join(reversed(names))


def _simple_type(text: str) -> str:
    """`java.util.Map<K, V>[]` -> `Map`; `var` and primitives stay as written."""
    return text.split("<")[0].split("[")[0].replace("...", "").strip().split(".")[-1]


def _bindings(decl) -> dict[str, str]:
    """name -> declared simple type for parameters and locals of `decl`
    (`var` and lambda parameters are left out: their type is not written)."""
    out: dict[str, str] = {}
    stack = [decl]
    while stack:
        n = stack.pop()
        t = n.child_by_field_name("type")
        if n.type in ("formal_parameter", "spread_parameter", "enhanced_for_statement",
                      "catch_formal_parameter") and t is not None:
            nm = n.child_by_field_name("name")
            if nm is None:
                nm = next((c for c in n.children if c.type in ("identifier", "variable_declarator")), None)
            if nm is not None:
                out[(nm.child_by_field_name("name") or nm).text.decode()] = _simple_type(t.text.decode())
        elif n.type == "local_variable_declaration" and t is not None:
            for d in n.children:
                if d.type == "variable_declarator":
                    out[d.child_by_field_name("name").text.decode()] = _simple_type(t.text.decode())
        stack.extend(n.children)
    return {k: v for k, v in out.items() if v != "var"}


def build_call_graph(files: dict[str, str]) -> CallGraph:
    """Call graph over {file_path: source} for one language (.java or .py):
    name-based edges plus typed edges with confidence (module docstring)."""
    suffixes = {Path(f).suffix for f in files}
    if suffixes == {".py"}:
        return _build_python(files)
    if suffixes - {".java"}:
        raise ValueError(f"call graph needs one language (.java or .py), got {sorted(suffixes)}")
    cg = CallGraph()
    decls = []
    types: dict[str, dict] = {}        # qualified type -> {simple, supers, fields}
    for file_path, code in files.items():
        root = _parse(code).root_node
        pkg = next((n.text.decode("utf8") for _, c in QueryCursor(_Q_PKG).matches(root)
                    for n in c.get("pkg", [])), "")
        imports = {n.text.decode().split(".")[-1]: n.text.decode()
                   for _, c in QueryCursor(_Q_IMPORT).matches(root) for n in c.get("imp", [])}
        stack = [root]
        while stack:
            n = stack.pop()
            stack.extend(n.children)
            if n.type not in _TYPES or n.child_by_field_name("name") is None:
                continue
            chain = ".".join(x for x in (_extract_class_name(n), n.child_by_field_name("name").text.decode()) if x)
            supers = [_simple_type(t.text.decode()) for f in ("superclass", "interfaces") if n.child_by_field_name(f)
                      for t in _nodes_of(n.child_by_field_name(f), ("type_identifier", "scoped_type_identifier",
                                                                     "generic_type"))]
            supers += [_simple_type(t.text.decode()) for c in n.children if c.type == "extends_interfaces"
                       for t in _nodes_of(c, ("type_identifier", "scoped_type_identifier", "generic_type"))]
            body = n.child_by_field_name("body")
            fields = {d.child_by_field_name("name").text.decode(): _simple_type(f.child_by_field_name("type").text.decode())
                      for f in (body.children if body else []) if f.type == "field_declaration"
                      for d in f.children if d.type == "variable_declarator"}
            types[".".join(x for x in (pkg, chain) if x)] = {"simple": chain.split(".")[-1], "supers": supers,
                                                             "fields": fields, "pkg": pkg, "imports": imports}
        for _, captures in QueryCursor(_Q_DECLS).matches(root):
            decl, name = captures["decl"][0], captures["name"][0].text.decode("utf8")
            owner = ".".join(x for x in (pkg, _extract_class_name(decl)) if x)
            base = ".".join(x for x in (owner, name) if x)
            callees = {n.text.decode("utf8") for _, c in QueryCursor(_Q_CALLS).matches(decl)
                       for n in c.get("call", [])}
            if decl.type == "constructor_declaration" and any(QueryCursor(_Q_THIS).matches(decl)):
                callees.add(name)
            decls.append((base, owner, decl, MethodInfo(name=name, qualified=base, file=file_path,
                                                        start_line=decl.start_point[0] + 1,
                                                        end_line=decl.end_point[0] + 1, callees=callees)))
    counts: dict[str, int] = {}
    for base, *_ in decls:
        counts[base] = counts.get(base, 0) + 1
    for base, _, _, info in decls:
        if counts[base] > 1:
            info.qualified = f"{base}@L{info.start_line}"
        cg.add_method(info)

    _link_by_name(cg)
    _resolve_typed(cg, decls, types)
    return cg


def _all_of(node, kinds: tuple) -> list:
    """Every descendant of `node` whose type is in `kinds`."""
    out, stack = [], list(node.children)
    while stack:
        n = stack.pop()
        if n.type in kinds:
            out.append(n)
        stack.extend(n.children)
    return out


def _nodes_of(node, kinds: tuple) -> list:
    """Outermost descendants of `node` whose type is in `kinds`."""
    out, stack = [], list(node.children)
    while stack:
        n = stack.pop()
        if n.type in kinds:
            out.append(n)
        else:
            stack.extend(n.children)
    return out


def _resolve_typed(cg: CallGraph, decls: list, types: dict) -> None:
    by_simple: dict[str, list[str]] = {}
    subs: dict[str, set[str]] = {}
    for q, t in types.items():
        by_simple.setdefault(t["simple"], []).append(q)
    for q, t in types.items():
        for sup in t["supers"]:
            for sq in by_simple.get(sup, []):
                subs.setdefault(sq, set()).add(q)
    owner_methods: dict[tuple[str, str], list[str]] = {}
    for base, owner, _, info in decls:
        owner_methods.setdefault((owner, info.name), []).append(info.qualified)

    def type_qs(simple: str, ctx: dict) -> tuple[list[str], float]:
        if simple in ctx["imports"] and ctx["imports"][simple] in types:
            return [ctx["imports"][simple]], 0.95
        same = f"{ctx['pkg']}.{simple}" if ctx["pkg"] else simple
        if same in types:
            return [same], 0.95
        nested = [q for q in by_simple.get(simple, []) if q.startswith(ctx["owner"] + ".")]
        if nested:
            return nested, 0.95
        return by_simple.get(simple, []), 0.85

    def walk(q: str, step) -> set[str]:
        seen, stack = {q}, [q]
        while stack:
            for x in step(stack.pop()) - seen:
                seen.add(x)
                stack.append(x)
        return seen

    def closure(q: str) -> set[str]:
        """Declarations a call on static type q can dispatch to: q's subtypes
        (overrides) and supertypes (inherited declarations), never a sibling
        reached by going up to a shared interface and back down."""
        up = walk(q, lambda c: {x for s in types.get(c, {}).get("supers", []) for x in by_simple.get(s, [])})
        return up | walk(q, lambda c: set(subs.get(c, ())))

    for _, owner, decl, info in decls:
        t = types.get(owner, {"imports": {}, "pkg": "", "fields": {}, "supers": []})
        ctx = {"imports": t["imports"], "pkg": t["pkg"], "owner": owner}
        local = _bindings(decl)
        edges: dict[str, float] = {}

        def add(type_list: list[str], conf: float, method: str) -> int:
            found = 0
            for tq in {x for q in type_list for x in closure(q)}:
                for target in owner_methods.get((tq, method), []):
                    if target != info.qualified:
                        edges[target] = max(edges.get(target, 0.0), conf)
                        found += 1
            return found

        for call in _all_of(decl, ("method_invocation", "object_creation_expression")):
            if call.type == "object_creation_expression":
                tn = call.child_by_field_name("type")
                simple = _simple_type(tn.text.decode())
                tq, conf = type_qs(simple, ctx)
                for q in tq:
                    for target in owner_methods.get((q, simple), []):
                        edges[target] = max(edges.get(target, 0.0), conf)
                continue
            method = call.child_by_field_name("name").text.decode()
            obj = call.child_by_field_name("object")
            if obj is None or obj.type == "this":
                # Not declared in the type hierarchy: a static import or an
                # enclosing type's method; fall back to the name.
                if not add([owner] if owner in types else [], 0.95, method):
                    _fallback(cg, edges, info.qualified, method)
                continue
            if obj.type == "super":
                add([q for s in t["supers"] for q in type_qs(s, ctx)[0]], 0.95, method)
                continue
            text = obj.text.decode()
            if obj.type == "field_access" and text.startswith("this."):
                text = text[5:]
            simple = local.get(text) or t["fields"].get(text)
            if simple is None and obj.type == "identifier" and text[:1].isupper():
                simple = text
            if simple is None:
                _fallback(cg, edges, info.qualified, method)
                continue
            tq, conf = type_qs(simple, ctx)
            add(tq, conf, method)
        info.typed_callees = edges
    for q, info in cg.methods.items():
        for target, conf in info.typed_callees.items():
            cg.methods[target].typed_callers[q] = conf


def _fallback(cg: CallGraph, edges: dict, self_q: str, method: str) -> None:
    """Receiver type unknown: every same-named project method, 0.75 when the
    name is unique project-wide, else 0.5."""
    targets = [t for t in cg.resolve(method) if t != self_q]
    for target in targets:
        edges[target] = max(edges.get(target, 0.0), 0.75 if len(targets) == 1 else 0.5)


def _link_by_name(cg: CallGraph) -> None:
    """Resolve each method's called simple names to every same-named method."""
    for qname, info in cg.methods.items():
        resolved: set[str] = set()
        for short in info.callees:
            targets = cg.resolve(short)
            for target_q in targets:
                if target_q != qname:
                    resolved.add(target_q)
                    cg.methods[target_q].callers.add(qname)
            if not targets:
                resolved.add(short)
        info.callees = resolved


def _py_module(path: str) -> str:
    parts = list(Path(path).with_suffix("").parts)
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _py_scope(node) -> list:
    """Enclosing class/function definition nodes, outermost first."""
    out, p = [], node.parent
    while p is not None:
        if p.type in ("class_definition", "function_definition"):
            out.append(p)
        p = p.parent
    return out[::-1]


def _py_imports(root, module: str, is_pkg: bool) -> dict[str, str]:
    """Local name -> fully qualified target for every import in the file;
    relative imports resolved against the file's package."""
    pkg = module if is_pkg else module.rpartition(".")[0]
    out: dict[str, str] = {}
    for n in _all_of(root, ("import_statement", "import_from_statement")):
        if n.type == "import_statement":
            for c in n.named_children:
                if c.type == "aliased_import":
                    out[c.child_by_field_name("alias").text.decode()] = c.child_by_field_name("name").text.decode()
                elif c.type == "dotted_name":
                    out[c.text.decode().split(".")[0]] = c.text.decode().split(".")[0]
            continue
        mod = n.child_by_field_name("module_name")
        text = mod.text.decode()
        if mod.type == "relative_import":
            dots = len(text) - len(text.lstrip("."))
            base = pkg.split(".")[:len(pkg.split(".")) - dots + 1] if pkg else []
            text = ".".join([*base, text.lstrip(".")] if text.lstrip(".") else base)
        for c in n.children_by_field_name("name"):
            name = (c.child_by_field_name("name") or c).text.decode()
            alias = c.child_by_field_name("alias")
            out[(alias or c).text.decode() if alias else name.split(".")[-1]] = f"{text}.{name}" if text else name
    return out


def _build_python(files: dict[str, str]) -> CallGraph:
    from tree_sitter_language_pack import get_parser
    parser = get_parser("python")
    cg, decls, classes, modules = CallGraph(), [], {}, {}
    for file_path, code in files.items():
        root = parser.parse(code.encode()).root_node
        module = _py_module(file_path)
        ctx = {"module": module, "imports": _py_imports(root, module, Path(file_path).stem == "__init__")}
        modules[module] = ctx
        for n in _all_of(root, ("class_definition", "function_definition")):
            chain = [x.child_by_field_name("name").text.decode() for x in _py_scope(n)]
            q = ".".join([module, *chain, n.child_by_field_name("name").text.decode()])
            if n.type == "class_definition":
                sup = n.child_by_field_name("superclasses")
                classes[q] = {"ctx": ctx, "bases": [b.text.decode() for b in (sup.named_children if sup else [])
                                                     if b.type in ("identifier", "attribute")]}
                continue
            scope = _py_scope(n)
            owner = ".".join([module, *chain]) if scope and scope[-1].type == "class_definition" else ""
            calls = _all_of(n, ("call",))
            callees = {(f.child_by_field_name("attribute") if f.type == "attribute" else f).text.decode()
                       for c in calls for f in [c.child_by_field_name("function")]
                       if f.type in ("identifier", "attribute")}
            decls.append((q, owner, n, ctx, MethodInfo(name=n.child_by_field_name("name").text.decode(),
                                                       qualified=q, file=file_path,
                                                       start_line=n.start_point[0] + 1,
                                                       end_line=n.end_point[0] + 1, callees=callees)))
    counts: dict[str, int] = {}
    for q, *_ in decls:
        counts[q] = counts.get(q, 0) + 1
    for q, *_, info in decls:
        if counts[q] > 1:
            info.qualified = f"{q}@L{info.start_line}"
        cg.add_method(info)
    _link_by_name(cg)
    _resolve_typed_python(cg, decls, classes, modules)
    return cg


def _resolve_typed_python(cg: CallGraph, decls: list, classes: dict, modules: dict) -> None:
    funcs: dict[str, list[str]] = {}
    for q, *_, info in decls:
        funcs.setdefault(q, []).append(info.qualified)

    def lookup(text: str, ctx: dict) -> tuple[str, float]:
        """Qualified project name `text` denotes in ctx, with its confidence."""
        head, _, rest = text.partition(".")
        if head in ctx["imports"]:
            return ".".join(x for x in (ctx["imports"][head], rest) if x), 0.95
        return f"{ctx['module']}.{text}", 0.90

    bases = {q: {b for b in (lookup(t, c["ctx"])[0] for t in c["bases"]) if b in classes} for q, c in classes.items()}
    subs: dict[str, set[str]] = {}
    for q, bs in bases.items():
        for b in bs:
            subs.setdefault(b, set()).add(q)

    def walk(q: str, step) -> set[str]:
        seen, stack = {q}, [q]
        while stack:
            for x in step(stack.pop()) - seen:
                seen.add(x)
                stack.append(x)
        return seen

    def closure(q: str, down: bool = True) -> set[str]:
        up = walk(q, lambda c: set(bases.get(c, ())))
        return up | walk(q, lambda c: set(subs.get(c, ()))) if down else up

    for _, owner, node, ctx, info in decls:
        edges: dict[str, float] = {}

        def on_classes(cls: set[str], method: str, conf: float) -> int:
            hits = [k for c in cls for k in funcs.get(f"{c}.{method}", ())]
            for k in hits:
                if k != info.qualified:
                    edges[k] = max(edges.get(k, 0.0), conf)
            return len(hits)

        for call in _all_of(node, ("call",)):
            f = call.child_by_field_name("function")
            if f.type == "identifier":
                target, conf = lookup(f.text.decode(), ctx)
                if target in classes:
                    on_classes(closure(target, down=False), "__init__", conf)
                elif target in funcs:
                    on_classes({target.rpartition(".")[0]}, target.rpartition(".")[2], conf)
                elif f.text.decode() not in ctx["imports"]:
                    _fallback(cg, edges, info.qualified, f.text.decode())
                continue
            if f.type != "attribute":
                continue
            obj, method = f.child_by_field_name("object"), f.child_by_field_name("attribute").text.decode()
            if obj.type == "identifier" and obj.text.decode() in ("self", "cls") and owner in classes:
                if not on_classes(closure(owner), method, 0.95):
                    _fallback(cg, edges, info.qualified, method)
                continue
            if obj.type == "call" and obj.child_by_field_name("function").text.decode() == "super" \
                    and owner in classes:
                on_classes(closure(owner, down=False) - {owner}, method, 0.95)
                continue
            if obj.type not in ("identifier", "attribute"):
                _fallback(cg, edges, info.qualified, method)
                continue
            target, conf = lookup(obj.text.decode(), ctx)
            if target in classes:
                on_classes(closure(target), method, conf)
            elif target in modules or f"{target}.{method}" in funcs:
                on_classes({target}, method, conf)
            elif obj.text.decode().partition(".")[0] not in ctx["imports"]:
                _fallback(cg, edges, info.qualified, method)
        info.typed_callees = edges
    for q, info in cg.methods.items():
        for target, conf in info.typed_callees.items():
            cg.methods[target].typed_callers[q] = conf


def build_call_graph_from_dir(root_dir: str | Path, glob: str = "**/*.java") -> CallGraph:
    """Build call graph from every file matching `glob` under a directory
    (one language: **/*.java or **/*.py)."""
    root = Path(root_dir)
    return build_call_graph({str(f.relative_to(root)): f.read_text(encoding="utf-8", errors="replace")
                             for f in root.glob(glob) if f.is_file()})


def transitive_callers(cg: CallGraph, seeds: set[str]) -> set[str]:
    """Every method that can reach one of `seeds` (qualified keys), seeds
    included. Name resolution over-approximates edges, so this is a superset
    of the true callers (reflection excepted)."""
    seen, stack = set(seeds), list(seeds)
    while stack:
        for caller in cg.callers_of(stack.pop()) - seen:
            seen.add(caller)
            stack.append(caller)
    return seen


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
