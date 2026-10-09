"""Auto-discovery test harness for examples/NN_*/main.py.

Each example is spawned as a fresh `python main.py` subprocess with a
per-example timeout from `PER_EXAMPLE_TIMEOUT_S` (default `DEFAULT_TIMEOUT_S`). A run passes iff exit-0 AND the
last line of stdout matches `OK: <name>; ...` OR `SKIP: ...`.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = ROOT / "examples"
DEFAULT_TIMEOUT_S = 90
PER_EXAMPLE_TIMEOUT_S = {
    "06_monitor_host": 30,
    "07_monitor_pid": 30,
    "08_monitor_socket": 30,
    "11_monitor_socket_standalone": 60,
    "12_monitor_systemd_sidecar": 90,
    "13_monitor_otlp_export": 60,
    "14_monitor_prometheus_scrape": 60,
    "04_project_hotspots_java": 180,
    "05_gpt2_staged": 600,
    "10_codegreen_vs_perf": 120,
}
HEAVY_EXAMPLES = {"05_gpt2_staged"}
# Heavy examples are always skipped in CI (they download multi-GB ML models
# and take >5 min). Run manually with: python examples/05_gpt2_staged/main.py
# or force-enable via `CODEGREEN_RUN_HEAVY_EXAMPLES=1 pytest tests/test_examples.py`.
RUN_HEAVY = os.environ.get("CODEGREEN_RUN_HEAVY_EXAMPLES") == "1"


def _discover():
    if not EXAMPLES_DIR.exists():
        return []
    out = []
    for d in sorted(EXAMPLES_DIR.iterdir()):
        if not d.is_dir():
            continue
        if not d.name[0].isdigit():
            continue
        main = d / "main.py"
        if main.exists():
            out.append(d)
    return out


def _has_torch():
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        return True
    except ImportError:
        return False


_EXAMPLES = _discover()


@pytest.mark.parametrize("example_dir", _EXAMPLES, ids=lambda d: d.name)
def test_example_runs(example_dir: Path) -> None:
    if example_dir.name in HEAVY_EXAMPLES and not RUN_HEAVY:
        pytest.skip(f"{example_dir.name} is heavy; set CODEGREEN_RUN_HEAVY_EXAMPLES=1 to run")
    if example_dir.name in HEAVY_EXAMPLES and not _has_torch():
        pytest.skip(f"{example_dir.name} requires torch + transformers")
    timeout = PER_EXAMPLE_TIMEOUT_S.get(example_dir.name, DEFAULT_TIMEOUT_S)
    main = example_dir / "main.py"
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    p = subprocess.run([sys.executable, str(main)], cwd=str(example_dir),
                       capture_output=True, text=True, timeout=timeout, env=env)
    assert p.returncode == 0, f"{example_dir.name} exited {p.returncode}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
    last = next((ln for ln in reversed(p.stdout.splitlines()) if ln.strip()), "")
    assert last.startswith(("OK:", "SKIP:")), (
        f"{example_dir.name}: last line must start with OK:/SKIP:; got {last!r}\nFull stdout:\n{p.stdout}"
    )


def test_examples_dir_exists():
    assert EXAMPLES_DIR.is_dir(), "examples/ directory missing"
    assert (EXAMPLES_DIR / "README.md").is_file(), "examples/README.md missing"


def test_codegreen_cli_available():
    assert shutil.which("codegreen"), "codegreen CLI must be on PATH for examples"
