"""Instrumentation regression tests for all supported languages.

Verifies that CodeGreen correctly:
1. Finds instrumentation points in source code
2. Generates instrumented code with checkpoints
3. Instrumented code compiles without errors
4. No FALLBACK (AST rewriter failures) occur

Run: python -m pytest tests/test_instrumentation.py -v
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

PYTHON_SAMPLE = '''
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr

def main():
    fibonacci(10)
    bubble_sort([5, 3, 8, 1, 2])

if __name__ == "__main__":
    main()
'''

JAVA_SAMPLE = '''
public class TestInstr {
    public static int fibonacci(int n) {
        if (n <= 1) return n;
        return fibonacci(n - 1) + fibonacci(n - 2);
    }

    public static void bubbleSort(int[] arr) {
        int n = arr.length;
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n - i - 1; j++) {
                if (arr[j] > arr[j + 1]) {
                    int tmp = arr[j];
                    arr[j] = arr[j + 1];
                    arr[j + 1] = tmp;
                }
            }
        }
    }

    public static void main(String[] args) {
        fibonacci(10);
        bubbleSort(new int[]{5, 3, 8, 1, 2});
    }
}
'''

C_SAMPLE = '''
#include <stdio.h>

int fibonacci(int n) {
    if (n <= 1) return n;
    return fibonacci(n - 1) + fibonacci(n - 2);
}

void bubble_sort(int arr[], int n) {
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n - i - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                int tmp = arr[j];
                arr[j] = arr[j + 1];
                arr[j + 1] = tmp;
            }
        }
    }
}

int main() {
    printf("%d\\n", fibonacci(10));
    int arr[] = {5, 3, 8, 1, 2};
    bubble_sort(arr, 5);
    return 0;
}
'''

CPP_SAMPLE = '''
#include <iostream>
#include <vector>
#include <algorithm>

int fibonacci(int n) {
    if (n <= 1) return n;
    return fibonacci(n - 1) + fibonacci(n - 2);
}

void bubble_sort(std::vector<int>& arr) {
    int n = arr.size();
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n - i - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                std::swap(arr[j], arr[j + 1]);
            }
        }
    }
}

int main() {
    std::cout << fibonacci(10) << std::endl;
    std::vector<int> arr = {5, 3, 8, 1, 2};
    bubble_sort(arr);
    return 0;
}
'''

JS_SAMPLE = '''
function fibonacci(n) {
    if (n <= 1) return n;
    return fibonacci(n - 1) + fibonacci(n - 2);
}

function bubbleSort(arr) {
    const n = arr.length;
    for (let i = 0; i < n; i++) {
        for (let j = 0; j < n - i - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                [arr[j], arr[j + 1]] = [arr[j + 1], arr[j]];
            }
        }
    }
    return arr;
}

console.log(fibonacci(10));
bubbleSort([5, 3, 8, 1, 2]);
'''

JAVA_COMPLEX = '''
public class TestComplex {
    public static int search(int[] arr, int target) {
        for (int i = 0; i < arr.length; i++) {
            if (arr[i] == target) return i;
        }
        return -1;  // not found
    }

    public static String classify(Object obj) {
        if (obj == null) return "null";
        if (obj instanceof String) return "string";
        if (obj instanceof Integer) return "int";
        return "other";
    }

    public static void process(int[] data) {
        try {
            for (int val : data) {
                if (val < 0) throw new IllegalArgumentException("negative");
            }
        } catch (IllegalArgumentException e) {
            System.err.println(e.getMessage());
        } finally {
            System.out.println("done");
        }
    }

    public static void main(String[] args) {
        search(new int[]{1, 2, 3}, 2);
        classify("hello");
        process(new int[]{1, -1, 3});
    }
}
'''

SAMPLES = {
    "python": (".py", PYTHON_SAMPLE, 3),
    "java": (".java", JAVA_SAMPLE, 3),
    "c": (".c", C_SAMPLE, 3),
    "cpp": (".cpp", CPP_SAMPLE, 3),
    "javascript": (".js", JS_SAMPLE, 4),
}


def _write_sample(lang: str, code: str, ext: str) -> Path:
    if lang == "java":
        # Java requires filename = class name
        class_name = "TestInstr"
        for line in code.splitlines():
            if "public class" in line:
                class_name = line.split("class")[1].split("{")[0].strip()
                break
        path = Path(tempfile.mkdtemp()) / f"{class_name}{ext}"
    else:
        path = Path(tempfile.mkdtemp()) / f"test_sample{ext}"
    path.write_text(code)
    return path


def _run_codegreen(cmd: list, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


class TestInstrumentationPoints:
    """Verify instrumentation point discovery for each language."""

    @pytest.mark.parametrize("lang,ext,code,min_points", [
        ("python", ".py", PYTHON_SAMPLE, 3),
        ("java", ".java", JAVA_SAMPLE, 3),
        ("c", ".c", C_SAMPLE, 3),
        ("cpp", ".cpp", CPP_SAMPLE, 3),
        pytest.param("javascript", ".js", JS_SAMPLE, 4),
    ])
    def test_finds_instrumentation_points(self, lang, ext, code, min_points):
        path = _write_sample(lang, code, ext)
        result = _run_codegreen(["codegreen", "analyze", lang, str(path), "--json"])
        assert result.returncode == 0, f"analyze failed: {result.stderr}"
        data = json.loads(result.stdout)
        points = data.get("instrumentation_points", [])
        assert len(points) >= min_points, (
            f"{lang}: expected >= {min_points} points, got {len(points)}")

    @pytest.mark.parametrize("lang,ext,code,min_points", [
        ("python", ".py", PYTHON_SAMPLE, 3),
        ("java", ".java", JAVA_SAMPLE, 3),
        ("c", ".c", C_SAMPLE, 3),
        ("cpp", ".cpp", CPP_SAMPLE, 3),
    ])
    def test_instrumented_code_has_checkpoints(self, lang, ext, code, min_points):
        path = _write_sample(lang, code, ext)
        result = _run_codegreen(["codegreen", "analyze", lang, str(path), "--save-instrumented"])
        assert "FALLBACK" not in result.stdout, (
            f"{lang}: AST rewriter fallback occurred:\n{result.stdout}")
        inst_path = str(path).replace(ext, f"_instrumented{ext}")
        assert Path(inst_path).exists(), f"Instrumented file not created: {inst_path}"
        inst_code = Path(inst_path).read_text()
        assert "checkpoint" in inst_code.lower() or "codegreen" in inst_code.lower(), (
            f"{lang}: no checkpoint calls in instrumented code")

    def test_point_types_correct(self):
        path = _write_sample("python", PYTHON_SAMPLE, ".py")
        result = _run_codegreen(["codegreen", "analyze", "python", str(path), "--json"])
        data = json.loads(result.stdout)
        points = data["instrumentation_points"]
        types = {p["type"] for p in points}
        assert "function_enter" in types, "Missing function_enter points"
        assert "function_exit" in types or any("exit" in p["type"] for p in points), (
            "Missing function_exit points")


class TestInstrumentedCompilation:
    """Verify instrumented code compiles without errors."""

    def test_java_compiles(self):
        path = _write_sample("java", JAVA_SAMPLE, ".java")
        _run_codegreen(["codegreen", "analyze", "java", str(path), "--save-instrumented"])
        inst = str(path).replace(".java", "_instrumented.java")
        if not Path(inst).exists():
            pytest.skip("Instrumented file not created")
        # Just verify no FALLBACK errors -- actual compilation requires classpath
        code = Path(inst).read_text()
        assert "CodeGreenRuntime" in code or "checkpoint" in code.lower()

    def test_java_complex_patterns(self):
        """Test try/catch, null checks, early returns, multi-return methods."""
        path = _write_sample("java", JAVA_COMPLEX, ".java")
        result = _run_codegreen(["codegreen", "analyze", "java", str(path), "--save-instrumented"])
        assert "FALLBACK" not in result.stdout, (
            f"Complex Java patterns caused FALLBACK:\n{result.stdout}")


class TestNoRegressions:
    """Verify specific bugs that were fixed don't recur."""

    def test_java_comment_types(self):
        """Regression: java.json had 'comment' instead of 'line_comment'/'block_comment'."""
        code = '''
public class TestComments {
    // This is a line comment
    public static int add(int a, int b) {
        return a + b; // trailing comment
    }
    /* block comment */
    public static void main(String[] args) {
        add(1, 2);
    }
}
'''
        path = _write_sample("java", code, ".java")
        result = _run_codegreen(["codegreen", "analyze", "java", str(path), "--save-instrumented"])
        assert "FALLBACK" not in result.stdout
        assert "missing return" not in result.stdout.lower()

    def test_python_indentation(self):
        """Regression: checkpoints must respect Python indentation."""
        path = _write_sample("python", PYTHON_SAMPLE, ".py")
        _run_codegreen(["codegreen", "analyze", "python", str(path), "--save-instrumented"])
        inst = str(path).replace(".py", "_instrumented.py")
        if Path(inst).exists():
            # Verify it's valid Python by compiling
            result = subprocess.run(["python3", "-m", "py_compile", inst],
                                    capture_output=True, text=True, timeout=10)
            assert result.returncode == 0, f"Instrumented Python doesn't compile: {result.stderr}"

    @pytest.mark.parametrize("name,code", [
        ("nested_fn", "def outer(n):\n    def inner(x):\n        return x * 2\n    return inner(n)\nouter(5)\n"),
        ("inline_one_liner", "def one(): return 42\none()\n"),
        ("multiple_one_liners", "def a(): return 1\ndef b(): return 2\nc = a() + b()\n"),
        ("ends_in_for", "def f(n):\n    t = 0\n    for i in range(n):\n        t += i\nf(7)\n"),
        ("deeply_nested", "def d(n):\n    p = list(range(n))\n    for v in range(n):\n        for w in range(v):\n            p[w] = w\n    return p\nd(5)\n"),
        ("generator_yield", "def g(n):\n    for i in range(n):\n        if i % 2:\n            yield i\n    yield n\nlist(g(8))\n"),
        ("tab_indented", "def t(n):\n\ts = 0\n\tfor i in range(n):\n\t\ts += i\n\treturn s\nt(4)\n"),
    ])
    def test_instrumented_python_always_valid_syntax(self, name, code):
        """Regression (fannkuch/one-liner class): instrumenting diverse function
        shapes -- inline bodies, deep nesting, generators, tabs, functions ending in
        compound statements -- must always yield syntactically VALID Python.

        These shipped broken before because bad indentation slips past tree-sitter's
        has_error (it does not flag Python 'unexpected indent'), producing a program
        that dies with IndentationError and is silently reported as 0 J.
        """
        import ast
        from codegreen.instrumentation.language_engine import LanguageEngine
        engine = LanguageEngine()
        analysis = engine.analyze_code(code, "python")
        instrumented = engine.instrument_code(code, analysis.instrumentation_points, "python")
        ast.parse(instrumented)  # raises SyntaxError if instrumentation broke the code


def test_python_same_named_methods_get_distinct_checkpoint_names():
    """A PyTorch file with Model/CausalSelfAttention/NewGELU `forward`s was
    profiled as ONE function `forward` (calls summed, energy double-counted);
    checkpoints carry the class-qualified name, as Java's already do."""
    from codegreen.instrumentation.language_engine import LanguageEngine
    code = ("class A:\n    def forward(self, x):\n        return x + 1\n\n"
            "class B:\n    def forward(self, x):\n        return x * 2\n\n"
            "def forward(x):\n    return x\n")
    engine = LanguageEngine()
    out = engine.instrument_code(code, engine.analyze_code(code, "python").instrumentation_points, "python")
    for name in ("A.forward", "B.forward"):
        assert f"'{name}', 'enter'" in out
    assert "'forward', 'enter'" in out


JAVA_OVERLOADS = """\
class Util {
    static int highbits(int x) {
        return x >>> 16;
    }

    static int highbits(long x) {
        return (int) (x >>> 48);
    }

    static int solo(int x) {
        return x;
    }

    static void many(java.util.List<String> a, int... xs) {
        a.size();
    }

    void recv(Util this, /* c */ final int y[], @Deprecated long... zs) {
        y[0] = 1;
    }
}
"""

JAVA_OVERLOADS_ONE_LINE = """\
class V {
    static int hb(int x) { return x >>> 16; }
    static int hb(long x) { return (int) (x >>> 48); }
    static int one(int x) { return x; }
}
"""


def _enter_points(code, lang):
    from codegreen.instrumentation.language_engine import LanguageEngine
    engine = LanguageEngine()
    result = engine.analyze_code(code, lang)
    assert result.success, result.error
    return engine, result, {p.metadata["record_name"]: p for p in result.instrumentation_points if p.type == "function_enter"}


def test_java_overloads_are_separate_records_with_line_and_signature():
    """`Util.highbits(int)` and `(long)` were one record `Util.highbits`; the runtime aggregates by emitted name."""
    engine, result, enters = _enter_points(JAVA_OVERLOADS, "java")
    def line(text):
        return next(i for i, ln in enumerate(JAVA_OVERLOADS.splitlines(), 1) if text in ln)

    l_int, l_long = line("highbits(int"), line("highbits(long")
    assert set(enters) == {f"Util.highbits@{l_int}", f"Util.highbits@{l_long}", "Util.solo", "Util.many", "Util.recv"}
    assert [enters[f"Util.highbits@{n}"].metadata["decl_line"] for n in (l_int, l_long)] == [l_int, l_long]
    assert enters[f"Util.highbits@{l_int}"].metadata["signature"] == "(int)"
    assert enters[f"Util.highbits@{l_long}"].metadata["signature"] == "(long)"
    assert enters["Util.solo"].metadata["decl_line"] == line("solo(int") and enters["Util.solo"].metadata["signature"] == "(int)"
    assert enters["Util.many"].metadata["signature"] == "(java.util.List<String>, int...)"
    assert enters["Util.recv"].metadata["signature"] == "(int[], long...)"
    out = engine.instrument_code(JAVA_OVERLOADS, result.instrumentation_points, "java",
                                 pre_normalised_source=result.metadata["normalised_source"])
    for name in enters:
        assert f'"{name}", "enter"' in out and f'"{name}", "exit"' in out
    assert '"Util.highbits", ' not in out


def test_java_overload_lines_refer_to_the_original_source_after_normalisation():
    """One-line bodies are split onto several lines before analysis; reported lines must still be the file's."""
    _, result, enters = _enter_points(JAVA_OVERLOADS_ONE_LINE, "java")
    assert result.metadata["normalised_source"] != JAVA_OVERLOADS_ONE_LINE
    assert {n: p.metadata["decl_line"] for n, p in enters.items()} == {"V.hb@2": 2, "V.hb@3": 3, "V.one": 4}


def test_python_same_named_nested_functions_get_line_suffix_and_no_signature():
    code = ("def a():\n    def helper():\n        return 1\n    return helper()\n\n"
            "def b():\n    def helper():\n        return 2\n    return helper()\n")
    _, _, enters = _enter_points(code, "python")
    assert set(enters) == {"a", "b", "helper@2", "helper@7"}
    assert all("signature" not in p.metadata for p in enters.values())


JAVA_OVERLOAD_BODIES = """\
class K {
    static int side(String t, int v) { return v; }
    int x;
    K(int a) {
        x = side("ctor-int", a);
    }
    K(long a) {
        x = side("ctor-long", (int) a);
    }
    int m(int a) {
        int t = side("m-int", a);
        return side("m-int-ret", t + 1);
    }
    int m(long a) {
        int t = side("m-long", (int) a);
        return side("m-long-ret", t + 2);
    }
}
"""


def test_java_overload_probes_inside_each_function_share_its_renamed_frame_name():
    import re
    engine, result, enters = _enter_points(JAVA_OVERLOAD_BODIES, "java")
    out = engine.instrument_code(JAVA_OVERLOAD_BODIES, result.instrumentation_points, "java",
                                 pre_normalised_source=result.metadata["normalised_source"])
    def at(text):
        return next(i for i, ln in enumerate(JAVA_OVERLOAD_BODIES.splitlines(), 1) if text in ln)

    names = {"ctor-int": f"K.K@{at('K(int a)')}", "ctor-long": f"K.K@{at('K(long a)')}",
             "m-int": f"K.m@{at('m(int a)')}", "m-long": f"K.m@{at('m(long a)')}"}
    names |= {"m-int-ret": names["m-int"], "m-long-ret": names["m-long"]}
    assert len(set(names.values())) == 4 and set(enters) == set(names.values()) | {"K.side"}
    rec = {p.metadata["function_start"]: p.metadata["record_name"] for p in enters.values()}
    assert all(p.metadata["qualified_name"] == rec[p.metadata["function_start"]] for p in result.instrumentation_points)
    stack, entered = [], []
    for m in re.finditer(r'checkpoint\("[^"]*", "([^"]+)", "(enter|exit)"\)|\bside\("([a-z-]+)"', out):
        if m.group(3):
            assert stack and stack[-1] == names[m.group(3)], f"{m.group(3)} outside its frame, stack {stack}"
        elif m.group(2) == "enter":
            stack.append(m.group(1))
            entered.append(m.group(1))
        else:
            assert stack and stack.pop() == m.group(1), f"unbalanced exit {m.group(1)}"
    assert not stack and sorted(entered) == sorted(set(names.values()) | {"K.side"})


def test_signature_only_where_the_language_configures_parameter_signature():
    _, _, java = _enter_points("class Z {\n    static int z() {\n        return 1;\n    }\n}\n", "java")
    assert java["Z.z"].metadata["signature"] == "()"
    _, _, py = _enter_points("def z():\n    return 1\n\ndef y(a):\n    return a\n", "python")
    assert all("signature" not in p.metadata for p in py.values())


def test_unlocated_overloads_stay_one_flagged_record(caplog):
    """Without declaration lines (normalisation changed the function count) overloads keep the shared name and are
    flagged with their count instead of taking a line from the normalised source."""
    from codegreen.instrumentation.language_engine import LanguageEngine
    engine = LanguageEngine()
    normalise = engine._normalise
    engine._normalise = lambda src, lang: normalise(src, lang).replace("class Util {\n", "class Util {\n    void extra() {\n    }\n", 1)
    result = engine.analyze_code(JAVA_OVERLOADS, "java")
    enters = {p.metadata["record_name"]: p for p in result.instrumentation_points if p.type == "function_enter"}
    assert {n: (p.metadata["decl_line"], p.metadata.get("merged_declarations"), "signature" in p.metadata)
            for n, p in enters.items() if n.startswith("Util.highbits")} == {"Util.highbits": (None, 2, False)}
    assert "2 functions share the record Util.highbits" in caplog.text
    from codegreen.cli.cli import _function_meta
    assert _function_meta([result.instrumentation_points])["Util.highbits"] == {"line": None, "merged_declarations": 2}


def test_bare_name_records_are_flagged_and_emitted_unchanged():
    code = "int f(int x) {\n    return x;\n}\n\nint f(long x) {\n    return 1;\n}\n"
    engine, result, _ = _enter_points(code, "cpp")
    enters = [p for p in result.instrumentation_points if p.type == "function_enter"]
    assert [(p.metadata["record_name"], p.metadata["merged_declarations"]) for p in enters] == [("f", 2), ("f", 2)]
    assert all("signature" not in p.metadata for p in enters)
    out = engine.instrument_code(code, result.instrumentation_points, "cpp",
                                 pre_normalised_source=result.metadata["normalised_source"])
    assert out.count('"f");') == 2 and "@" not in out


def test_function_meta_keeps_plain_names_and_marks_ambiguous_ones():
    from codegreen.cli.cli import _function_meta
    _, _, enters = _enter_points(JAVA_OVERLOADS, "java")
    points = [p for p in enters.values()]
    meta = _function_meta([points])
    assert meta["Util.solo"] == {"line": 10, "signature": "(int)"}
    assert sorted(m["line"] for n, m in meta.items() if n.startswith("Util.highbits@")) == [2, 6]
    assert _function_meta([points, points]) == meta
    _, _, other = _enter_points(JAVA_OVERLOADS.replace("class Util {\n", "class Util {\n\n"), "java")
    assert _function_meta([points, list(other.values())])["Util.solo"] == {"line": None}


def test_overload_records_are_separate_and_totals_unchanged(tmp_path):
    """Replay is keyed by emitted name, so '@line' names give one record each and the sums match the merged ones."""
    from codegreen.cli.cli import _stderr_checkpoint_events, _replay_checkpoint_events
    f = tmp_path / "cp.txt"
    f.write_text("CG_CP_SUM|1|Util.highbits@2|3|30|20|300\nCG_CP_SUM|1|Util.highbits@6|1|10|10|100\n"
                 "CG_CP_SUM|1|Util.solo|2|8|8|80\n")
    func = {}
    _replay_checkpoint_events(_stderr_checkpoint_events(str(f), func), func)
    assert func["Util.highbits@2"]["calls"] == 3 and func["Util.highbits@6"]["calls"] == 1
    assert sum(d["inclusive_uj"] for d in func.values()) == 48 and sum(d["exclusive_uj"] for d in func.values()) == 38


# --- Function frames: every exit path closes the frame with the qualified name, after the return value ---

def _instrument(lang, code):
    from codegreen.instrumentation.language_engine import LanguageEngine
    engine = LanguageEngine()
    result = engine.analyze_code(code, lang)
    assert result.success, result.error
    out = engine.instrument_code(code, result.instrumentation_points, lang,
                                 pre_normalised_source=result.metadata["normalised_source"])
    return out, {s["function"] for s in result.metadata["skipped_functions"]}


HELPER_FRAMES = ("side", "sided", "Prog.side")


def _drop_helpers(lines):
    """The programs' one-line `side` helpers are framed like any function; their frames are not under test."""
    return [ln for ln in lines if ln.partition(" ")[2] not in HELPER_FRAMES]


def _base(name):
    """Overloads are emitted as `Cls.m@<line>`; the programs' own `eval` tags name the function without the suffix."""
    return name.partition("@")[0]


def _verify_trace(lines):
    """`enter F`/`exit F` frames nest; `eval F` (work inside F's return expression) runs while F is innermost."""
    stack, seen = [], []
    for ln in _drop_helpers(lines):
        kind, _, name = ln.partition(" ")
        if kind == "enter":
            stack.append(name)
            seen.append(name)
        elif kind == "exit":
            assert stack and stack.pop() == name, f"unbalanced exit: {ln} with stack {stack}"
        elif kind == "eval":
            assert stack and _base(stack[-1]) == name, f"{ln} ran outside its frame, stack {stack}"
    assert not stack, f"frames left open: {stack}"
    return seen


def _run(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, f"{cmd}\n{r.stdout}\n{r.stderr}"
    return r.stdout.splitlines()


def _check_program(tmp_path, lang, files, main_file, build, run, expect_frames, expect_skipped=()):
    """Build and run the original and the instrumented program: identical program output, balanced frames with
    return-expression work inside them, every expected function framed, refused constructs reported."""
    out, skipped = _instrument(lang, files[main_file])
    stdout = {}
    for tag, main_src in (("plain", files[main_file]), ("inst", out)):
        d = tmp_path / tag
        for name, text in {**files, main_file: main_src}.items():
            (d / name).parent.mkdir(parents=True, exist_ok=True)
            (d / name).write_text(text)
        for cmd in build:
            _run(cmd, d)
        stdout[tag] = _run(run, d)
    assert [ln for ln in stdout["inst"] if not ln.startswith(("enter ", "exit "))] == stdout["plain"], "instrumentation changed program output"
    frames = [_base(f) for f in _verify_trace(stdout["inst"])]
    assert set(expect_frames) <= set(frames), f"missing frames: {set(expect_frames) - set(frames)}"
    assert skipped == set(expect_skipped)
    assert not (set(expect_skipped) & set(frames))


PY_PROGRAM = '''\
LOG = []
def side(tag, v=None): LOG.append("eval " + tag); return v

class W:
    def __init__(self, n):
        self.n = n
        side("W.__init__")

    def run(self):
        for i in range(self.n):
            side("W.run")

    def total(self):
        return side("W.total", 5), side("W.total", 6)

    def early(self, k):
        if k:
            return side("W.early", 1)
        self.n += 1

    def raises(self):
        side("W.raises")
        raise ValueError("x")

    def text(self):
        """doc"""
        s = """a
  b
c"""
        return s

    def outer(self):
        def inner():
            return side("W.inner", 2)
        return inner() + side("W.outer", 3)

    def gen(self):
        yield 1

    async def co(self):
        return 1

    def fin(self):
        try:
            return side("W.fin", 1)
        finally:
            side("W.fin", 2)

def tabbed(n):
\ts = 0
\tfor i in range(n):
\t\ts += i
\treturn side("tabbed", s)
'''


def test_python_frames_cover_every_exit_path(monkeypatch):
    import ast
    import sys
    import types
    out, skipped = _instrument("python", PY_PROGRAM)
    ast.parse(out)
    assert skipped == {"W.gen", "W.co"}
    log: list = []
    rt = types.ModuleType("codegreen_runtime")
    rt.checkpoint = lambda cid, name, kind: log.append(f"{kind} {name}")
    monkeypatch.setitem(sys.modules, "codegreen_runtime", rt)
    ns: dict = {}
    exec(out, ns)
    ns["LOG"] = log
    w = ns["W"](2)
    w.run()
    assert w.total() == (5, 6) and w.early(1) == 1 and w.early(0) is None
    with pytest.raises(ValueError):
        w.raises()
    assert w.text() == "a\n  b\nc" and w.outer() == 5 and w.fin() == 1 and ns["tabbed"](4) == 6
    assert list(w.gen()) == [1]
    frames = _verify_trace(log)
    log = _drop_helpers(log)
    assert log[:5] == ["enter W.__init__", "eval W.__init__", "exit W.__init__", "enter W.run", "eval W.run"]
    i = log.index("enter W.total")
    assert log[i:i + 5] == ["enter W.total", "eval W.total", "eval W.total", "exit W.total", "enter W.early"]
    assert log[log.index("eval W.raises") + 1] == "exit W.raises"
    assert "W.gen" not in frames and "W.co" not in frames and frames.count("W.run") == 1


def test_python_unicode_and_inline_bodies_stay_valid():
    import ast
    code = "def a(): return 1\n\ndef b(x):\n    s = 'caf\u00e9 \u2713'\n    return s + str(x)\n\nclass C:\n    def m(self):\n        pass\n"
    out, skipped = _instrument("python", code)
    ast.parse(out)
    assert not skipped and "def a(): return 1" not in out
    assert all(f"'{n}', 'enter'" in out and f"'{n}', 'exit'" in out for n in ("a", "b", "C.m"))


PY_ONE_LINERS = "\n".join([
    "def rec(n): return rec(n - 1) if n > 0 else 0",
    "def semi(a): x = a + 1; y = x * 2; return y",
    "def trailing(a): return a;",
    'def doc(): """d"""; return 5',
    "def cont(a): \\",
    "    return a + 1",
    "def noop(): pass",
    "def err(): raise ValueError('x')",
    "def commented(): return 1  # c",
    "def multi(a,",
    "          b): return a + b",
    "class K:",
    "    def m(self): return 1",
    "    def n(self, v): self.v = v; return self.v",
    "    @staticmethod",
    "    def s(): return 3",
    "class T:",
    "\tdef m(self): return 4",
    "def outer():",
    "    def inner(): return 2",
    "    return inner() + 1",
    ""])


def test_python_one_line_functions_are_framed_and_keep_their_semantics(monkeypatch):
    """`def f(n): return f(n-1) if n > 0 else 0` got no frame and no skipped_functions entry. Every one-line suite
    (`;`-separated, continued, decorated, tab-indented, inside a class) must be framed with identical results."""
    import ast
    import sys
    import types
    out, skipped = _instrument("python", PY_ONE_LINERS)
    ast.parse(out)
    assert not skipped
    log: list = []
    rt = types.ModuleType("codegreen_runtime")
    rt.checkpoint = lambda cid, name, kind: log.append(f"{kind} {name}")
    monkeypatch.setitem(sys.modules, "codegreen_runtime", rt)
    plain: dict = {}
    inst: dict = {}
    exec(PY_ONE_LINERS, plain)
    exec(out, inst)

    def results(ns):
        with pytest.raises(ValueError):
            ns["err"]()
        k = ns["K"]()
        return (ns["rec"](3), ns["semi"](1), ns["trailing"](2), ns["doc"](), ns["doc"].__doc__, ns["cont"](1), ns["noop"](),
                ns["commented"](), ns["multi"](1, 2), k.m(), k.n(5), ns["K"].s(), ns["T"]().m(), ns["outer"]())

    assert results(inst) == results(plain)
    frames = _verify_trace(log)
    names = ("rec", "semi", "trailing", "doc", "cont", "noop", "err", "commented", "multi", "K.m", "K.n", "K.s", "T.m", "outer")
    assert set(names) <= set(frames) and frames.count("rec") == 4


JAVA_RUNTIME = """\
package codegreen.runtime;
public class CodeGreenRuntime {
    public static void checkpoint(String id, String name, String type) { System.out.println(type + " " + name); }
}
"""

JAVA_PROGRAM = """\
import java.util.*;
import java.util.function.*;
public class Prog {
    static <T> T side(String tag, T v) { System.out.println("eval " + tag); return v; }
    // café ✓ non-ASCII text before every later method shifts byte offsets from character offsets
    final int x;
    Prog(int a) { this(a, 1); }
    Prog(int a, int b) {
        this.x = a + b;
        side("Prog.Prog", 0);
    }
    static byte b() {
        return 1;
    }
    static char c() {
        return 'a' + 1;
    }
    static Byte boxed() {
        return 1;
    }
    static long widen(int i) {
        return side("Prog.widen", i);
    }
    static <T> List<T> gen(T t) {
        List<T> l = new ArrayList<>();
        l.add(t);
        return side("Prog.gen", l);
    }
    static int tern(boolean f) {
        return f ? side("Prog.tern", 1) : side("Prog.tern", 2);
    }
    static Supplier<Integer> lam(int k) {
        Supplier<Integer> s = () -> { return side("Prog.main", k); };
        return () -> { return s.get() + 1; };
    }
    static void vd(int c) {
        if (c > 0) return;
        side("Prog.vd", 0);
    }
    static int early(int c) {
        for (int i = 0; i < 3; i++) { if (i == c) return side("Prog.early", i); }
        return -1;
    }
    static int thrower(boolean t) throws Exception {
        if (t) throw new Exception("boom");
        return side("Prog.thrower", 1);
    }
    static int tryFinal() {
        try {
            return side("Prog.tryFinal", 1);
        } finally {
            side("Prog.tryFinal", 2);
        }
    }
    static Object anon() {
        return new Object() {
            int m() {
                return side("Prog.m", 7);
            }
            public String toString() {
                return "anon" + m();
            }
        };
    }
    static int sw(int k) {
        switch (k) {
            case 0: return side("Prog.sw", 10);
            default: return side("Prog.sw", 20);
        }
    }
    interface I { default int d() {
        return side("Prog.I.d", 3);
    } }
    static class Inner implements I {
        int v() {
            return d() + side("Prog.Inner.v", 1);
        }
    }
    public static void main(String[] a) throws Exception {
        System.out.println(new Prog(2).x + " " + b() + " " + c() + " " + boxed() + " " + widen(3) + " " + gen("g"));
        System.out.println(tern(true) + " " + lam(4).get() + " " + early(1) + " " + tryFinal() + " " + sw(0) + sw(5));
        vd(1);
        vd(0);
        try { thrower(true); } catch (Exception e) { System.out.println(e.getMessage()); }
        System.out.println(thrower(false) + " " + anon() + " " + new Inner().v());
    }
}
"""


@pytest.mark.skipif(not shutil.which("javac"), reason="javac missing")
def test_java_frames_cover_every_construct(tmp_path):
    _check_program(
        tmp_path, "java", {"Prog.java": JAVA_PROGRAM, "codegreen/runtime/CodeGreenRuntime.java": JAVA_RUNTIME}, "Prog.java",
        [["javac", "--release", "11", "-Xlint:-options", "-d", ".", "Prog.java", "codegreen/runtime/CodeGreenRuntime.java"]],
        ["java", "-cp", ".", "Prog"],
        ["Prog.Prog", "Prog.b", "Prog.c", "Prog.boxed", "Prog.widen", "Prog.gen", "Prog.tern", "Prog.lam", "Prog.vd",
         "Prog.early", "Prog.thrower", "Prog.tryFinal", "Prog.anon", "Prog.m", "Prog.toString", "Prog.sw", "Prog.I.d", "Prog.Inner.v", "Prog.main"])


C_STUB = """\
#include <stdio.h>
#include <string.h>
void nemb_mark_checkpoint(const char* name) {
    char kind[16], rest[256];
    sscanf(name, "%15[^:]:%255s", kind, rest);
    char* id = strrchr(rest, ':');
    if (id) *id = 0;
    if (!strcmp(kind, "enter") || !strcmp(kind, "exit")) printf("%s %s\\n", kind, rest);
}
"""

C_PROGRAM = """\
#include <stdio.h>
struct S { int a; double b; };
static int side(const char *tag, int v) { printf("eval %s\\n", tag); return v; }
static double sided(const char *tag, double v) { printf("eval %s\\n", tag); return v; }
struct S mk(int a) {
    struct S s = {a, 1.5};
    return s;
}
static const char *name(int i) {
    if (i) return "x";
    return "y";
}
unsigned long big(void) {
    return 1UL << 40;
}
double dbl(int i) {
    return sided("dbl", i * 0.5);
}
int fib(int n) {
    if (n <= 1) return side("fib", n);
    else return fib(n - 1) + fib(n - 2);
}
void v(int *a) {
    if (!a) return;
    *a = side("v", 1);
}
void w(int *a) {
    for (int i = 0; i < 3; i++)
        for (int j = 0; j < 3; j++)
            if (i + j == 3) return;
    *a = 2;
}
int tern(int k) {
    return k ? side("tern", 1) : side("tern", 2);
}
void *nul(void) {
    return (void *)0;
}
enum { RA, RB } pick(void) {
    return RB;
}
void fall(int *a) {
    *a = side("fall", 4);
}
#define BAIL(x) if (!(x)) return -1
int guarded(int v) {
    BAIL(v > 0);
    return side("main", v);
}
int main(void) {
    int z = 0;
    struct S s = mk(2);
    printf("%d %s %lu %f %d %d %d %p\\n", s.a, name(0), big(), dbl(3), fib(5), tern(0), tern(1), nul());
    v(&z);
    v(0);
    w(&z);
    fall(&z);
    printf("%d %d %d\\n", z, pick() == RB, guarded(2));
}
"""


@pytest.mark.skipif(not shutil.which("gcc"), reason="gcc missing")
def test_c_frames_cover_every_construct(tmp_path):
    rt = Path(__file__).parent.parent / "codegreen" / "instrumentation" / "language_runtimes" / "c"
    _check_program(
        tmp_path, "c", {"prog.c": C_PROGRAM, "stub.c": C_STUB}, "prog.c",
        [["gcc", "-std=c11", "-Wall", "-Werror=return-type", "-I", str(rt), "-o", "prog", "prog.c", "stub.c"]],
        ["./prog"],
        ["mk", "big", "dbl", "fib", "v", "w", "tern", "fall", "main"], expect_skipped={"pick", "guarded"})


CPP_STUB = """\
#include <cstdio>
#include <cstring>
extern "C" void nemb_mark_checkpoint(const char* name) {
    char kind[16], rest[256];
    std::sscanf(name, "%15[^:]:%255s", kind, rest);
    char* id = std::strrchr(rest, ':');
    if (id) *id = 0;
    if (!std::strcmp(kind, "enter") || !std::strcmp(kind, "exit")) std::printf("%s %s\\n", kind, rest);
}
"""

CPP_PROGRAM = """\
#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>
template <typename T> T side(const char* tag, T v) { std::printf("eval %s\\n", tag); return v; }
// café ✓ non-ASCII text before every later function
struct Big { std::vector<int> v; Big() : v(10, 1) {} Big(const Big&) = delete; Big(Big&&) = default; };
Big make() {
    return side("make", Big());
}
std::string str(int i) {
    if (i) return side("str", std::string("x"));
    return std::string("y");
}
void thrower(int i) {
    if (i) throw std::runtime_error("e");
    std::puts("ok");
}
void caught() {
    try { thrower(1); } catch (const std::exception&) { std::puts("caught"); }
}
template <typename T>
T twice(T x) {
    return side("twice", x + x);
}
constexpr int cx(int x) {
    return x * 2;
}
int lam() {
    auto f = [](int a) { return a + 1; };
    return side("lam", f(2));
}
void bare(int* p) {
    if (!p) return;
    *p = side("bare", 1);
}
int main() {
    int z = 0;
    bare(&z);
    bare(nullptr);
    caught();
    std::printf("%zu %s %d %d %d\\n", make().v.size(), str(0).c_str(), twice(3), lam(), cx(2));
}
"""


@pytest.mark.skipif(not shutil.which("g++"), reason="g++ missing")
def test_cpp_frames_cover_every_construct(tmp_path):
    rt = Path(__file__).parent.parent / "codegreen" / "instrumentation" / "language_runtimes" / "cpp"
    _check_program(
        tmp_path, "cpp", {"prog.cpp": CPP_PROGRAM, "stub.cpp": CPP_STUB}, "prog.cpp",
        [["g++", "-std=c++17", "-Wall", "-I", str(rt), "-o", "prog", "prog.cpp", "stub.cpp"]],
        ["./prog"],
        ["make", "str", "thrower", "caught", "twice", "lam", "bare", "main"], expect_skipped={"cx"})


def test_cpp_coroutines_are_refused():
    code = "#include <coroutine>\nstruct T {};\nT co() {\n    co_return;\n}\nint ok() {\n    return 1;\n}\n"
    out, skipped = _instrument("cpp", code)
    assert skipped == {"co"} and "Frame cg_frame" in out and out.count("Frame cg_frame") == 1


JS_RUNTIME = "export const CodeGreen = { checkpoint(id, name, type) { console.log(type + ' ' + name); } };\n"

JS_PROGRAM = """\
function side(tag, v) { console.log('eval ' + tag); return v; }
function plain(n) {
    if (n < 2) return side('plain', n);
    return plain(n - 1) + plain(n - 2);
}
class K {
    constructor(a) {
        this.a = a;
        side('constructor', 0);
    }
    m() {
        const f = (x) => { return x + 1; };
        const g = (x) => x * 2;
        return side('m', f(this.a) + g(1));
    }
    static s() {
        return side('s', 1);
    }
    async am() {
        return 2;
    }
    *g() {
        yield 3;
    }
}
function thrower(t) {
    if (t) throw new Error('x');
    return side('thrower', 1);
}
function comma() {
    return side('comma', 1), side('comma', 2);
}
function nested() {
    function inner() {
        return side('inner', 5);
    }
    return inner() + side('nested', 1);
}
function tern(t) {
    return t ? side('tern', 1) : side('tern', 2);
}
async function af() {
    return await Promise.resolve(1);
}
function* gen() {
    yield 1;
}
console.log(plain(4), new K(1).m(), K.s(), comma(), nested(), tern(false), [...gen()]);
try { thrower(true); } catch (e) { console.log(e.message); }
console.log(thrower(false));
af().then((v) => console.log('af', v));
new K(2).am().then((v) => console.log('am', v));
console.log([...new K(3).g()]);
"""


@pytest.mark.skipif(not shutil.which("node"), reason="node missing")
def test_javascript_frames_cover_every_construct(tmp_path):
    _check_program(
        tmp_path, "javascript",
        {"prog.mjs": JS_PROGRAM, "node_modules/codegreen-runtime/index.mjs": JS_RUNTIME,
         "node_modules/codegreen-runtime/package.json": '{"name": "codegreen-runtime", "type": "module", "main": "index.mjs"}'},
        "prog.mjs", [], ["node", "prog.mjs"],
        ["plain", "constructor", "m", "s", "thrower", "comma", "nested", "inner", "tern"], expect_skipped={"af", "K.am", "K.g", "f", "g", "gen"})


JAVA_ONE_LINERS = """\
public class P {
    int f;
    static int sq(int n) { return n * n; }
    static int two(int n) { int a = n + 1; return a * 2; }
    static void inc(int[] a) { a[0]++; }
    static int cm(int n) { // trailing comment
        return n + 1;
    }
    P(int a) { this(a, 1); }
    P(int a, int b) { f = a + b; }
    interface I { int d(); }
    static class Inner implements I { public int d() { return 9; } }
    public static void main(String[] x) { int[] a = {1}; inc(a); System.out.println(sq(3) + " " + two(1) + " " + a[0] + " " + new P(2).f + " " + cm(1) + " " + new Inner().d()); }
}
"""


@pytest.mark.skipif(not shutil.which("javac"), reason="javac missing")
def test_java_one_line_bodies_are_framed(tmp_path):
    _check_program(
        tmp_path, "java", {"P.java": JAVA_ONE_LINERS, "codegreen/runtime/CodeGreenRuntime.java": JAVA_RUNTIME}, "P.java",
        [["javac", "--release", "11", "-Xlint:-options", "-d", ".", "P.java", "codegreen/runtime/CodeGreenRuntime.java"]],
        ["java", "-cp", ".", "P"], ["P.sq", "P.two", "P.inc", "P.cm", "P.P", "P.Inner.d", "P.main"])


C_ONE_LINERS = """\
#include <stdio.h>
static int sq(int n) { return n * n; }
static int two(int n) { int a = n + 1; return a * 2; }
static void pr(int n) { printf("%d\\n", n); }
int main(void) { pr(sq(3) + two(1)); return 0; }
"""


@pytest.mark.skipif(not shutil.which("gcc"), reason="gcc missing")
def test_c_one_line_bodies_are_framed(tmp_path):
    rt = Path(__file__).parent.parent / "codegreen" / "instrumentation" / "language_runtimes" / "c"
    _check_program(
        tmp_path, "c", {"prog.c": C_ONE_LINERS, "stub.c": C_STUB}, "prog.c",
        [["gcc", "-std=c11", "-Wall", "-Werror=return-type", "-I", str(rt), "-o", "prog", "prog.c", "stub.c"]],
        ["./prog"], ["sq", "two", "pr", "main"])


CPP_ONE_LINERS = """\
#include <cstdio>
struct A {
    int v;
    int get() const { return v; }
    void set(int x) { v = x; }
};
int sq(int n) { return n * n; }
int main() { A a{1}; a.set(sq(3)); std::printf("%d\\n", a.get()); return 0; }
"""


@pytest.mark.skipif(not shutil.which("g++"), reason="g++ missing")
def test_cpp_one_line_bodies_are_framed(tmp_path):
    rt = Path(__file__).parent.parent / "codegreen" / "instrumentation" / "language_runtimes" / "cpp"
    _check_program(
        tmp_path, "cpp", {"prog.cpp": CPP_ONE_LINERS, "stub.cpp": CPP_STUB}, "prog.cpp",
        [["g++", "-std=c++17", "-Wall", "-I", str(rt), "-o", "prog", "prog.cpp", "stub.cpp"]],
        ["./prog"], ["sq", "main"])


JS_ONE_LINERS = """\
function sq(n) { return n * n; }
function two(n) { const a = n + 1; return a * 2; }
const arrow = (n) => n * 2;
const block = (n) => { return n + 1; };
class K {
    constructor(a) { this.a = a; }
    m() { return this.a; }
    static s() { return 3; }
}
console.log(sq(3), two(1), arrow(2), block(1), new K(4).m(), K.s());
"""


@pytest.mark.skipif(not shutil.which("node"), reason="node missing")
def test_javascript_one_line_bodies_are_framed_and_arrow_functions_refused(tmp_path):
    _check_program(
        tmp_path, "javascript",
        {"prog.mjs": JS_ONE_LINERS, "node_modules/codegreen-runtime/index.mjs": JS_RUNTIME,
         "node_modules/codegreen-runtime/package.json": '{"name": "codegreen-runtime", "type": "module", "main": "index.mjs"}'},
        "prog.mjs", [], ["node", "prog.mjs"], ["sq", "two", "constructor", "m", "s"], expect_skipped={"arrow", "block"})


class TestConfigDriven:
    """Verify instrumentation is config-driven, not hardcoded."""

    def test_all_configs_loadable(self):
        """All language configs must load without errors and have required keys."""
        configs_dir = Path(__file__).parent.parent / "codegreen" / "instrumentation" / "configs"
        for config_file in configs_dir.glob("*.json"):
            if config_file.name == "TEMPLATE.json":
                continue
            data = json.loads(config_file.read_text())
            assert "ast_config" in data, f"{config_file.name}: missing ast_config"
            assert "instrumentation_config" in data, f"{config_file.name}: missing instrumentation_config"
            assert "node_types" in data, f"{config_file.name}: missing node_types"
            node_types = data["node_types"]
            assert "comment_types" in node_types, f"{config_file.name}: missing comment_types"
            assert "return_types" in node_types or "return_statements" in node_types, (
                f"{config_file.name}: missing return_types/return_statements in node_types")

    def test_no_hardcoded_language_checks_in_engine(self):
        """Engine code must not have if language == 'X' patterns."""
        engine_path = Path(__file__).parent.parent / "codegreen" / "instrumentation" / "language_engine.py"
        if not engine_path.exists():
            pytest.skip("language_engine.py not found")
        code = engine_path.read_text()
        for lang in ["python", "java", "javascript", "cpp"]:
            # Allow in comments and strings, but not in if-conditions
            lines = code.splitlines()
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith("//"):
                    continue
                if f'== "{lang}"' in line or f"== '{lang}'" in line:
                    if "if " in line or "elif " in line:
                        pytest.fail(f"Hardcoded language check at line {i+1}: {stripped}")


JAVA_RAPL_PROG = """\
import codegreen.runtime.CodeGreenStandaloneRuntime;
import java.io.RandomAccessFile;
public class Prog {
    public static void main(String[] a) throws Exception {
        CodeGreenStandaloneRuntime.checkpoint("1", "m", "enter");
        for (int i = 0; i + 1 < a.length; i += 2)
            try (RandomAccessFile f = new RandomAccessFile(a[i], "rw")) { f.write(a[i + 1].getBytes()); }
        Thread.sleep(150);
        CodeGreenStandaloneRuntime.checkpoint("2", "m", "exit");
    }
}
"""


@pytest.fixture(scope="module")
def java_rapl_prog(tmp_path_factory):
    if not (shutil.which("javac") and shutil.which("java")):
        pytest.skip("javac/java missing")
    rt = Path(__file__).parent.parent / "codegreen" / "instrumentation" / "language_runtimes" / "java"
    d = tmp_path_factory.mktemp("java_rapl")
    (d / "Prog.java").write_text(JAVA_RAPL_PROG)
    r = subprocess.run(["javac", "-cp", str(rt), "-d", str(d), str(d / "Prog.java")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return d


def _fake_rapl(root, packages):
    """packages: list of (name, energy_uj, max_range_uj); energy files are fixed-width so in-place rewrites never expose a short read."""
    for i, (name, energy, rng) in enumerate(packages):
        dom = root / f"intel-rapl:{i}"
        dom.mkdir(parents=True)
        (dom / "name").write_text(name + "\n")
        (dom / "energy_uj").write_text(f"{energy:012d}\n")
        (dom / "max_energy_range_uj").write_text(f"{rng}\n")


def _java_rapl_env():
    """The poller settings `codegreen project` exports from java.json project_config.runtime_injection.env."""
    cfg = json.loads((Path(__file__).parent.parent / "codegreen/instrumentation/configs/java.json").read_text())
    return cfg["project_config"]["runtime_injection"]["env"]


def _run_java_rapl(prog, root, *writes, env=None):
    ck = prog / "cp.txt"
    ck.unlink(missing_ok=True)
    r = subprocess.run(
        ["java", f"-Dcodegreen.rapl.root={root}", "-cp", str(prog), "Prog", *writes], capture_output=True, text=True,
        env={**os.environ, **(_java_rapl_env() if env is None else env), "CG_CP_CHECKPOINT_FILE": str(ck)}, timeout=60)
    return r, (ck.read_text() if ck.exists() else "")


def test_java_runtime_fails_loudly_without_rapl(java_rapl_prog, tmp_path):
    r, out = _run_java_rapl(java_rapl_prog, tmp_path / "missing")
    assert r.returncode != 0 and "no zone matching" in r.stderr and out == ""
    r, _ = _run_java_rapl(java_rapl_prog, tmp_path / "missing", env={})
    assert r.returncode != 0 and "CODEGREEN_RAPL_ZONE" in r.stderr and "is unset" in r.stderr


def test_java_runtime_rejects_unreadable_package_domain(java_rapl_prog, tmp_path):
    _fake_rapl(tmp_path, [("package-0", 5, 1000)])
    (tmp_path / "intel-rapl:0" / "max_energy_range_uj").unlink()
    r, _ = _run_java_rapl(java_rapl_prog, tmp_path)
    assert r.returncode != 0 and "cannot read RAPL domain" in r.stderr


def test_java_runtime_sums_packages_and_handles_counter_wrap(java_rapl_prog, tmp_path):
    _fake_rapl(tmp_path, [("package-0", 900, 1000), ("package-1", 100, 5000), ("psys", 1, 10)])
    d0, d1 = (tmp_path / f"intel-rapl:{i}" / "energy_uj" for i in (0, 1))
    r, out = _run_java_rapl(java_rapl_prog, tmp_path, str(d0), f"{100:012d}\n", str(d1), f"{400:012d}\n")
    assert r.returncode == 0, r.stderr
    meta, sums = [ln for ln in out.splitlines() if ln.startswith("CG_CP_META|")], \
        [ln for ln in out.splitlines() if ln.startswith("CG_CP_SUM|")]
    assert len(meta) == 1 and len(sums) == 1
    m = json.loads(meta[0].split("|", 1)[1])
    assert m["marker_reads"] == "last_poll" and m["failed_reads"] == 0 and m["readings"] >= 1
    assert [p["name"] for p in m["providers"]] == ["intel_rapl"] and m["providers"][0]["energy_source"] == "counter"
    row = sums[0].split("|")
    assert row[:3] == ["CG_CP_SUM", row[1], "m"] and row[3] == "1"
    assert int(row[4]) == (100 + 1000 - 900) + (400 - 100)
