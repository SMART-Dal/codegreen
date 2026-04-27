"""Run identical GPT-2 workload through CodeGreen access modes and compare totals.

  Mode A: `codegreen run`   -- whole-program energy via the CLI
  Mode B: `codegreen.Session` (manual span around the entire script body)

Both bracket the same wall-clock span, so the readings should agree within
small noise (no instrumentation overhead from extra checkpoints).

A third reference is bare wall-clock (no codegreen) to check timing parity."""
import json, os, statistics, subprocess, sys, time

REPEAT = int(os.environ.get("CG_REPEAT", "3"))
HERE = os.path.dirname(os.path.abspath(__file__))
WORKLOAD = os.path.join(HERE, "_workload_gpt2.py")
WORKLOAD_SESSION = os.path.join(HERE, "_workload_gpt2_session.py")


def _parse_json_blob(stdout: str) -> dict:
    """codegreen --json prints multi-line JSON; find the outermost {...} block."""
    s = stdout
    start = s.find("{")
    end = s.rfind("}")
    if start < 0 or end < 0 or end <= start:
        raise RuntimeError(f"no JSON block found in stdout (last 300 chars):\n{s[-300:]}")
    return json.loads(s[start:end + 1])


def mode_cli_run():
    cmd = ["codegreen", "run", "python", WORKLOAD, "--repeat", "1", "--warmup", "0", "--json"]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if res.returncode != 0:
        raise RuntimeError(f"codegreen run failed:\n{res.stderr[-400:]}")
    d = _parse_json_blob(res.stdout)
    e = d.get("energy_joules", {})
    t = d.get("time_seconds", {})
    energy = e.get("mean") if isinstance(e, dict) else e
    secs = t.get("mean") if isinstance(t, dict) else t
    return {"energy_j": energy, "power_w": d.get("power_watts"), "wall_s": secs,
            "domains": d.get("domains") or {}}


def mode_session():
    out = f"/tmp/_session_{os.getpid()}_{time.time()}.json"
    env = dict(os.environ); env["CG_OUT"] = out
    res = subprocess.run([sys.executable, WORKLOAD_SESSION], env=env, capture_output=True, text=True, timeout=600)
    if res.returncode != 0:
        raise RuntimeError(f"session script failed:\n{res.stderr[-400:]}")
    rep = json.load(open(out))
    task = rep["tasks"][0]
    return {"energy_j": task["energy_j"], "power_w": task["avg_power_w"],
            "wall_s": task["duration_s"], "domains": task["domains"]}


def mode_bare():
    t0 = time.perf_counter()
    res = subprocess.run([sys.executable, WORKLOAD], capture_output=True, text=True, timeout=600)
    dt = time.perf_counter() - t0
    if res.returncode != 0:
        raise RuntimeError(f"bare run failed:\n{res.stderr[-400:]}")
    return {"energy_j": None, "power_w": None, "wall_s": dt, "domains": {}}


def repeat_run(label, fn):
    rows = []
    for _ in range(REPEAT):
        try: rows.append(fn())
        except Exception as e: rows.append({"error": str(e)})
    return label, rows


def stat(rows, key):
    vs = [r[key] for r in rows if "error" not in r and r.get(key) is not None]
    if not vs: return None
    return statistics.mean(vs), (statistics.stdev(vs) if len(vs) > 1 else 0.0)


def main():
    print(f"GPT-2 workload, {REPEAT} repeats per mode\n")
    rs = []
    for label, fn in [("Bare (timing only)", mode_bare),
                      ("CLI: codegreen run", mode_cli_run),
                      ("Session (manual)",   mode_session)]:
        print(f"-- running {label}")
        rs.append(repeat_run(label, fn))

    print(f"\n{'mode':<22} {'energy_j (mean +/- std)':<28} {'power_w':<10} {'wall_s':<14} runs")
    print("-" * 92)
    base_e = base_w = None
    for label, rows in rs:
        ok = [r for r in rows if "error" not in r]
        e = stat(rows, "energy_j"); p = stat(rows, "power_w"); w = stat(rows, "wall_s")
        if not ok:
            print(f"{label:<22} ERROR")
            continue
        if e and base_e is None and "Session" not in label and "CLI" in label:
            base_e = e[0]
        if w and base_w is None: base_w = w[0]
        e_str = f"{e[0]:>9.2f} +/- {e[1]:<6.2f}" if e else "      n/a            "
        e_pct = f"({100*(e[0]-base_e)/base_e:+5.2f}%)" if (e and base_e) else "        "
        p_str = f"{p[0]:>5.1f} W" if p else "  n/a "
        w_str = f"{w[0]:>4.2f} s ({100*(w[0]-base_w)/base_w:+4.1f}%)" if (w and base_w) else f"{w[0]:>4.2f} s"
        print(f"{label:<22} {e_str} J {e_pct}  {p_str:<10} {w_str:<14} {len(ok)}/{REPEAT}")

    json.dump({"repeat": REPEAT, "results": rs}, open("/tmp/cg_modes_compare.json", "w"), indent=2, default=str)
    print(f"\nraw JSON: /tmp/cg_modes_compare.json")


if __name__ == "__main__":
    main()
