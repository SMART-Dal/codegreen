"""Regression tests: instrumentation must not break single-line braced
control-flow bodies (e.g. `if (c) { return x; }`, `for (...) if (...) { ... }`).

Repro from fasta CLBG benchmark: in the original codegreen, the instrumentation
inserted the checkpoint at column 0 of the line containing `{ return ...; }`
- BEFORE the opening brace - which made the checkpoint the body of the
non-braced `if`, orphaning the block and breaking variable scope for any
identifiers introduced by an outer non-braced `for`/`while`.

Fix lives in instrumentation/brace_normaliser.py (AST-driven pre-pass that wraps
any non-braced control-flow body in a `block` before instrumentation) plus
ast_processor._find_insertion_point_via_ast mode='immediately_before', which
inserts at the start_byte of the direct block-child containing the probe site.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from codegreen.instrumentation.language_engine import LanguageEngine

# Minimal repro: braceless for + braceless if + single-line braced return block.
# Originally broke: codegreen inserted the checkpoint between the `if (...)`
# header and the `{ return ...; }` block, making the orphaned block reference
# `a[i]` after `i` had gone out of for-scope.
FASTA_SHAPE = """\
public class BraceTest {
    public static int pick(int[] a) {
        int n = a.length;
        for (int i = 0; i < n; i++)
            if (a[i] > 0)
                { return a[i]; }
        return -1;
    }

    public static void main(String[] args) {
        int[] arr = {0, 0, 7, 0};
        System.out.println(pick(arr));
    }
}
"""

# Variant 2: braced if directly (no for wrapper). Inserting checkpoint
# before `{ return ...; }` on its own line used to land before the `{`.
SINGLE_LINE_BRACE = """\
public class SingleLine {
    public static int sign(int x) {
        if (x < 0)
            { return -1; }
        if (x > 0)
            { return 1; }
        return 0;
    }
    public static void main(String[] a) { System.out.println(sign(-3)); }
}
"""

# Variant 3: classic braceless if-return (already worked via wrap_with_braces).
# Kept here to guard against regression of the existing path.
BRACELESS_RETURN = """\
public class Braceless {
    public static int abs(int x) {
        if (x < 0) return -x;
        return x;
    }
    public static void main(String[] a) { System.out.println(abs(-7)); }
}
"""


def _instrument_and_compile(java_src: str, tmpdir: Path, classname: str) -> tuple[bool, str]:
    engine = LanguageEngine()
    result = engine.analyze_code(java_src, "java", filename=f"{classname}.java")
    assert result.success, f"analyze_code failed: {result.error}"
    instrumented = engine.instrument_code(java_src, result.instrumentation_points, "java")
    src_file = tmpdir / f"{classname}.java"
    src_file.write_text(instrumented)
    # Ship a minimal CodeGreenRuntime stub so javac resolves the symbol.
    runtime_dir = tmpdir / "codegreen" / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "CodeGreenRuntime.java").write_text(
        "package codegreen.runtime;\n"
        "public class CodeGreenRuntime {\n"
        "  public static void checkpoint(String id, String name, String phase) {}\n"
        "}\n"
    )
    proc = subprocess.run(
        ["javac", "-d", str(tmpdir), str(src_file),
         str(runtime_dir / "CodeGreenRuntime.java")],
        capture_output=True, text=True, timeout=60,
    )
    return proc.returncode == 0, proc.stderr


@pytest.mark.parametrize("name,src", [
    ("BraceTest", FASTA_SHAPE),
    ("SingleLine", SINGLE_LINE_BRACE),
    ("Braceless", BRACELESS_RETURN),
])
def test_instrumented_java_compiles(name, src, tmp_path):
    ok, stderr = _instrument_and_compile(src, tmp_path, name)
    assert ok, f"javac failed for {name}:\n{stderr}"


# ------------------------------------------------------------------
# TestBraceNormaliserStructural — AST-level invariants per Phase 6.
# ------------------------------------------------------------------

from codegreen.instrumentation.brace_normaliser import BraceNormaliser
from codegreen.instrumentation.language_configs import get_language_config_manager
from tree_sitter_language_pack import get_parser


def _java_body(snippet: str) -> str:
    return f"class T {{ void m() {{ {snippet} }} }}"


CASES = {
    "if_then_bare": _java_body("if (a) f();"),
    "if_else_bare": _java_body("if (a) f(); else g();"),
    "if_else_if_else": _java_body("if (a) f(); else if (b) g(); else h();"),
    "for_bare": _java_body("for (int i=0;i<3;i++) f(i);"),
    "enhanced_for_bare": _java_body("for (int x : arr) f(x);"),
    "while_bare": _java_body("while (c) g();"),
    "do_while_bare": _java_body("do h(); while (d);"),
    "labelled_bare": _java_body("outer: for (int i=0;i<3;i++) f(i);"),
    "empty_while_body": _java_body("while (c) ;"),
    "nested_bare": _java_body("for (int i=0;i<3;i++) if (a) g(); else h();"),
    "if_in_while_bare": _java_body("while (c) if (a) f();"),
}


def _walk(node):
    yield node
    for c in node.children:
        yield from _walk(c)


def _parse_java(src: str):
    return get_parser('java').parse(src.encode())


def _normalise_java(src: str):
    cfg = get_language_config_manager()
    tree = _parse_java(src)
    norm = BraceNormaliser(src, tree, 'java', cfg)
    return norm.normalise()


# Map parent.type -> fields that must point to a `block` after normalisation.
# `if_statement.alternative` is also satisfied by another `if_statement` (else if).
PARENT_FIELDS = {
    "if_statement": ("consequence", "alternative"),
    "for_statement": ("body",),
    "enhanced_for_statement": ("body",),
    "while_statement": ("body",),
    "do_statement": ("body",),
    "labeled_statement": ("statement",),
}


class TestBraceNormaliserStructural:
    @pytest.mark.parametrize("case", list(CASES.keys()))
    def test_every_field_is_block_after_normalisation(self, case):
        new_src, new_tree = _normalise_java(CASES[case])
        offenders = []
        for node in _walk(new_tree.root_node):
            fields = PARENT_FIELDS.get(node.type)
            if not fields:
                continue
            for f in fields:
                child = node.child_by_field_name(f)
                if child is None:
                    continue
                if child.type == 'block':
                    continue
                if node.type == 'if_statement' and f == 'alternative' and child.type == 'if_statement':
                    continue
                offenders.append((case, node.type, f, child.type))
        assert not offenders, f"non-block field-child after normalisation: {offenders}\nsrc={new_src}"

    def test_idempotent(self):
        for src in CASES.values():
            once_src, once_tree = _normalise_java(src)
            twice = BraceNormaliser(once_src, once_tree, 'java', get_language_config_manager())
            twice_src, _ = twice.normalise()
            assert once_src == twice_src

    def test_else_if_chain_preserved(self):
        src = _java_body("if (a) f(); else if (b) g(); else if (c) h(); else k();")
        new_src, new_tree = _normalise_java(src)
        # Walk every if_statement; alternative must be either a block (else { ... })
        # or another if_statement (else if). Never `expression_statement` etc.
        for node in _walk(new_tree.root_node):
            if node.type != 'if_statement':
                continue
            alt = node.child_by_field_name('alternative')
            if alt is None:
                continue
            assert alt.type in ('block', 'if_statement'), f"alternative leaked type {alt.type}; src={new_src}"

    def test_lambda_body_untouched(self):
        src = _java_body("Runnable r = () -> f();")
        new_src, _ = _normalise_java(src)
        # No braces should be injected — lambda body is not in non_braced_body_parents.
        assert new_src == src

    def test_already_braced_is_noop(self):
        src = _java_body("if (a) { f(); } else { g(); } for (int i=0;i<3;i++) { f(i); }")
        new_src, _ = _normalise_java(src)
        assert new_src == src

    def test_query_cache_reused(self):
        from codegreen.instrumentation.brace_normaliser import _QUERY_CACHE
        _normalise_java(CASES["if_then_bare"])
        size_after_first = len(_QUERY_CACHE)
        _normalise_java(CASES["for_bare"])
        # Same language + same parents list -> identical cache key, no new entry.
        assert len(_QUERY_CACHE) == size_after_first


class TestFailuresAreLoud:
    def test_normaliser_without_tree_raises(self):
        with pytest.raises(RuntimeError, match="parsed tree"):
            BraceNormaliser("class A {}", None, 'java', get_language_config_manager()).normalise()

    def test_normaliser_planning_error_propagates(self, monkeypatch):
        monkeypatch.setattr(BraceNormaliser, "_plan", lambda self: (_ for _ in ()).throw(ValueError("boom")))
        with pytest.raises(ValueError, match="boom"):
            _normalise_java(CASES["if_then_bare"])

    def test_engine_reports_failed_analysis_instead_of_proceeding(self, monkeypatch):
        monkeypatch.setattr(BraceNormaliser, "normalise", lambda self: (_ for _ in ()).throw(ValueError("boom")))
        res = LanguageEngine().analyze_code(CASES["if_then_bare"], 'java')
        assert res.success is False and "boom" in res.error

    def test_clamp_counter_is_gone(self):
        from codegreen.instrumentation import ast_processor
        assert not hasattr(ast_processor, "HOTPATCH_CLAMP_COUNTER")
