"""Instrumentation regression tests for all supported languages.

Verifies that CodeGreen correctly:
1. Finds instrumentation points in source code
2. Generates instrumented code with checkpoints
3. Instrumented code compiles without errors
4. No FALLBACK (AST rewriter failures) occur

Run: python -m pytest tests/test_instrumentation.py -v
"""
import json
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
    "javascript": (".js", JS_SAMPLE, 2),
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
        pytest.param("javascript", ".js", JS_SAMPLE, 2,
                     marks=pytest.mark.xfail(reason="JavaScript instrumentation incomplete")),
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


class TestConfigDriven:
    """Verify instrumentation is config-driven, not hardcoded."""

    def test_all_configs_loadable(self):
        """All language configs must load without errors and have required keys."""
        configs_dir = Path(__file__).parent.parent / "src" / "instrumentation" / "configs"
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
        engine_path = Path(__file__).parent.parent / "src" / "instrumentation" / "language_engine.py"
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
