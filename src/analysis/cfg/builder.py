"""Java CFG builder using tree-sitter 0.25 visitor pattern.

Adapted from tree-climber (submodules/tree-climber), ported to tree-sitter 0.25
with added synchronized, try/catch, try-with-resources, lambda body support.
"""

from __future__ import annotations

from src.analysis._ts_java import LANG as _LANG, parser as _parser, HAS_TS as _HAS_TS, parse as _parse

from src.analysis.cfg.types import CFG, NType


def _text(n, max_bytes: int = 0) -> str:
    if not n.text:
        return ""
    raw = n.text[:max_bytes] if max_bytes > 0 else n.text
    return raw.decode("utf8", errors="replace")


def _field(n, name: str):
    return n.child_by_field_name(name)


def _field_req(n, name: str):
    c = n.child_by_field_name(name)
    if c is None:
        raise ValueError(f"Missing field '{name}' in {n.type}")
    return c


_USE_SKIP = {"method_declaration", "class_declaration", "formal_parameter",
             "type_identifier", "catch_formal_parameter"}


def _collect_defs(root) -> list[str]:
    defs = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type == "variable_declarator":
            for c in node.children:
                if c.type == "identifier":
                    defs.append(_text(c))
        elif node.type == "assignment_expression" and node.children:
            left = node.children[0]
            if left.type == "identifier":
                defs.append(_text(left))
        elif node.type == "update_expression":
            for c in node.children:
                if c.type == "identifier":
                    defs.append(_text(c))
        for c in reversed(node.children):
            stack.append(c)
    return defs


def _has_object_creation(root) -> bool:
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type == "object_creation_expression":
            return True
        for c in node.children:
            stack.append(c)
    return False


def _collect_uses(root) -> list[str]:
    uses = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type == "identifier" and node.parent:
            if node.parent.type in _USE_SKIP:
                continue
            if node.parent.type == "variable_declarator":
                name_node = node.parent.child_by_field_name("name")
                if name_node and name_node.start_byte == node.start_byte:
                    continue
            if node.parent.type == "assignment_expression":
                left = node.parent.children[0] if node.parent.children else None
                if left and left.start_byte == node.start_byte:
                    op = node.parent.children[1] if len(node.parent.children) > 1 else None
                    if op and _text(op) == "=":
                        continue
            if node.parent.type in ("method_invocation", "field_access"):
                arg_list = node.parent.child_by_field_name("arguments")
                if arg_list is None or node.start_byte < (arg_list.start_byte if arg_list else node.end_byte):
                    continue
            uses.append(_text(node))
            continue
        for c in reversed(node.children):
            stack.append(c)
    return uses


def _collect_calls(root) -> list[str]:
    calls = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type == "method_invocation":
            ids = [c for c in node.children if c.type == "identifier"]
            if ids:
                calls.append(_text(ids[-1]))
        for c in reversed(node.children):
            stack.append(c)
    return calls


class _Builder:
    def __init__(self):
        self.cfg = CFG()
        self._break_targets: list[int] = []
        self._cont_targets: list[int] = []
        self._exit_stack: list[int] = []

    def _push_loop(self, brk: int, cont: int):
        self._break_targets.append(brk)
        self._cont_targets.append(cont)

    def _pop_loop(self):
        self._break_targets.pop()
        self._cont_targets.pop()

    def build(self, root) -> CFG:
        entry, exits = self._visit(root)
        self.cfg.entry = entry
        self.cfg.exits = exits
        return self.cfg

    def _visit(self, n) -> tuple[int, list[int]]:
        m = getattr(self, f"_v_{n.type}", None)
        if m:
            return m(n)
        return self._v_generic(n)

    def _v_generic(self, n) -> tuple[int, list[int]]:
        nid = self.cfg.node(NType.STMT, _text(n, 120), n.type)
        self.cfg.nodes[nid].defs = _collect_defs(n)
        self.cfg.nodes[nid].uses = _collect_uses(n)
        self.cfg.nodes[nid].has_alloc = _has_object_creation(n)
        self.cfg.nodes[nid].calls = _collect_calls(n)
        return nid, [nid]

    def _v_seq(self, n) -> tuple[int, list[int]]:
        entry = -1; cur_exits: list[int] = []
        for c in n.children:
            if not c.is_named:
                continue
            ce, cx = self._visit(c)
            if entry == -1:
                entry, cur_exits = ce, cx
            else:
                for e in cur_exits:
                    self.cfg.edge(e, ce)
                cur_exits = cx
        if entry == -1:
            nid = self.cfg.node(NType.STMT, "empty")
            return nid, [nid]
        return entry, cur_exits

    def _v_program(self, n): return self._v_seq(n)
    def _v_class_declaration(self, n): return self._visit(_field_req(n, "body"))
    def _v_class_body(self, n): return self._v_seq(n)
    def _v_block(self, n): return self._v_seq(n)
    def _v_expression_statement(self, n): return self._v_generic(n)
    def _v_local_variable_declaration(self, n): return self._v_generic(n)

    def _v_method_declaration(self, n) -> tuple[int, list[int]]:
        name = _text(_field_req(n, "name"))
        body = _field(n, "body")
        if body is None:
            nid = self.cfg.node(NType.STMT, f"abstract:{name}", "abstract_method")
            return nid, [nid]
        eid = self.cfg.node(NType.ENTRY, name)
        xid = self.cfg.node(NType.EXIT, name)
        self._exit_stack.append(xid)
        be, bx = self._visit(body)
        self.cfg.edge(eid, be)
        for x in bx:
            self.cfg.edge(x, xid)
        self._exit_stack.pop()
        return eid, [xid]

    def _v_constructor_declaration(self, n):
        return self._v_method_declaration(n)

    def _v_if_statement(self, n) -> tuple[int, list[int]]:
        cond = _field_req(n, "condition")
        then = _field_req(n, "consequence")
        els = _field(n, "alternative")
        cid = self.cfg.node(NType.COND, _text(cond)[:80], "if")
        self.cfg.nodes[cid].uses = _collect_uses(cond)
        te, tx = self._visit(then)
        self.cfg.edge(cid, te, "true")
        exits = list(tx)
        if els:
            ee, ex = self._visit(els)
            self.cfg.edge(cid, ee, "false")
            exits.extend(ex)
        else:
            exits.append(cid)
        return cid, exits

    def _v_while_statement(self, n) -> tuple[int, list[int]]:
        cond = _field_req(n, "condition")
        body = _field_req(n, "body")
        hid = self.cfg.node(NType.LOOP, _text(cond)[:80], "while")
        self.cfg.nodes[hid].uses = _collect_uses(cond)
        xid = self.cfg.node(NType.EXIT, "while_exit")
        self._push_loop(xid, hid)
        be, bx = self._visit(body)
        self.cfg.edge(hid, be, "true")
        for x in bx:
            self.cfg.edge(x, hid)
        self.cfg.edge(hid, xid, "false")
        self._pop_loop()
        return hid, [xid]

    def _v_for_statement(self, n) -> tuple[int, list[int]]:
        init = _field(n, "init")
        cond = _field(n, "condition")
        upd = _field(n, "update")
        body = _field_req(n, "body")
        init_id = -1
        if init:
            init_id, _ = self._visit(init)
        cond_text = _text(cond)[:80] if cond else "true"
        hid = self.cfg.node(NType.LOOP, cond_text, "for")
        if cond:
            self.cfg.nodes[hid].uses = _collect_uses(cond)
        if init_id != -1:
            self.cfg.edge(init_id, hid)
        upd_id = hid
        if upd:
            upd_id = self.cfg.node(NType.STMT, _text(upd)[:80], "for_update")
            self.cfg.nodes[upd_id].defs = _collect_defs(upd)
            self.cfg.edge(upd_id, hid)
        xid = self.cfg.node(NType.EXIT, "for_exit")
        self._push_loop(xid, upd_id)
        be, bx = self._visit(body)
        self.cfg.edge(hid, be, "true")
        for x in bx:
            self.cfg.edge(x, upd_id if upd else hid)
        self.cfg.edge(hid, xid, "false")
        self._pop_loop()
        return (init_id if init_id != -1 else hid), [xid]

    def _v_enhanced_for_statement(self, n) -> tuple[int, list[int]]:
        body = _field_req(n, "body")
        hid = self.cfg.node(NType.LOOP, _text(n, 80), "for_each")
        xid = self.cfg.node(NType.EXIT, "foreach_exit")
        self._push_loop(xid, hid)
        be, bx = self._visit(body)
        self.cfg.edge(hid, be, "true")
        for x in bx:
            self.cfg.edge(x, hid)
        self.cfg.edge(hid, xid, "false")
        self._pop_loop()
        return hid, [xid]

    def _v_do_statement(self, n) -> tuple[int, list[int]]:
        cond = _field_req(n, "condition")
        body = _field_req(n, "body")
        hid = self.cfg.node(NType.LOOP, _text(cond)[:80], "do_while")
        self.cfg.nodes[hid].uses = _collect_uses(cond)
        xid = self.cfg.node(NType.EXIT, "dowhile_exit")
        self._push_loop(xid, hid)
        be, bx = self._visit(body)
        for x in bx:
            self.cfg.edge(x, hid)
        self.cfg.edge(hid, be, "true")
        self.cfg.edge(hid, xid, "false")
        self._pop_loop()
        return be, [xid]

    def _v_break_statement(self, n) -> tuple[int, list[int]]:
        nid = self.cfg.node(NType.BREAK, "break")
        if self._break_targets:
            self.cfg.edge(nid, self._break_targets[-1])
        return nid, []

    def _v_continue_statement(self, n) -> tuple[int, list[int]]:
        nid = self.cfg.node(NType.CONTINUE, "continue")
        if self._cont_targets:
            self.cfg.edge(nid, self._cont_targets[-1])
        return nid, []

    def _v_return_statement(self, n) -> tuple[int, list[int]]:
        nid = self.cfg.node(NType.RETURN, _text(n, 80))
        self.cfg.nodes[nid].uses = _collect_uses(n)
        if self._exit_stack:
            self.cfg.edge(nid, self._exit_stack[-1])
        return nid, []

    def _v_try_statement(self, n) -> tuple[int, list[int]]:
        body = _field_req(n, "body")
        be, bx = self._visit(body)
        exits = list(bx)
        for c in n.children:
            if c.type == "catch_clause":
                ce, cx = self._visit(c)
                self.cfg.edge(be, ce, "exception")
                exits.extend(cx)
            elif c.type == "finally_clause":
                fe, fx = self._visit(c)
                old_exits = exits
                exits = list(fx)
                for e in old_exits:
                    self.cfg.edge(e, fe)
        return be, exits

    def _v_try_with_resources_statement(self, n):
        return self._v_try_statement(n)

    def _v_catch_clause(self, n):
        return self._visit(_field_req(n, "body"))

    def _v_finally_clause(self, n):
        return self._v_seq(n)

    def _v_synchronized_statement(self, n) -> tuple[int, list[int]]:
        body = _field_req(n, "body")
        sid = self.cfg.node(NType.STMT, "synchronized", "synchronized")
        be, bx = self._visit(body)
        self.cfg.edge(sid, be)
        return sid, bx

    def _v_lambda_expression(self, n) -> tuple[int, list[int]]:
        body = _field(n, "body")
        if body:
            return self._visit(body)
        return self._v_generic(n)


def build_cfg(code: str) -> CFG:
    tree = _parse(code)
    return _Builder().build(tree.root_node)


def _find_methods(node, out: list):
    if node.type in ("method_declaration", "constructor_declaration"):
        name_node = node.child_by_field_name("name")
        name = _text(name_node) if name_node else "constructor"
        body = node.child_by_field_name("body")
        if body is not None:
            out.append((name, node))
        return
    for c in node.children:
        _find_methods(c, out)


def build_per_method_cfgs(code: str) -> list[tuple[str, CFG]]:
    """Build independent CFGs per method. No cross-method dataflow leakage."""
    tree = _parse(code)
    methods: list = []
    _find_methods(tree.root_node, methods)
    result = []
    for name, node in methods:
        b = _Builder()
        entry, exits = b._v_method_declaration(node)
        b.cfg.entry = entry
        b.cfg.exits = exits
        result.append((name, b.cfg))
    return result
