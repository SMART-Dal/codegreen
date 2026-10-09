# 11 — Monitor socket (standalone sidecar)

**Who this is for.** You have an already-running web app (Apache + mod_wsgi
+ Flask, gunicorn, uWSGI, ASGI server) and want per-request energy
attribution **without restarting the app** and **without embedding the
Monitor in the application process**. The Monitor runs as an independent
sidecar; the app talks to it over a Unix-domain socket.

This is the deployment shape that motivated
[GitHub Discussion #5](https://github.com/SMART-Dal/codegreen/discussions/5):
codegreen attaches to the long-running process boundary, not to a
single Python entry point.

For comparison: [example 08](08_monitor_socket.md) runs the Monitor
inside the same Python process as the app — fine for tests and
single-binary deployments, but not what production looks like.

## Quick run

The example uses stdlib `http.server` so it has zero extra dependencies:

```bash
cd codegreen
python examples/11_monitor_socket_standalone/main.py
```

Expected last line:

```text
OK: monitor_socket_standalone; labels=3; samples=8; annotation_starts=7; annotation_ends=7; total_j=...
```

## What the example does

1. Spawns `codegreen monitor --listen-on-socket <sock> -o energy.jsonl
   --quiet --json` as a **separate subprocess** (the sidecar).
2. Waits until the monitor has bound the UDS.
3. Starts a tiny `ThreadingHTTPServer` with a middleware that wraps every
   `do_GET` in an annotation span (`op=start` before work, `op=end` after).
4. Drives 7 requests against 3 routes: `/light`, `/medium`, `/heavy`.
5. SIGTERMs the monitor; it flushes the final summary to stdout and
   closes the JSONL file.

Two processes; one socket; no shared imports. That's the production
shape.

## Will the monitor keep running if I close the terminal?

The Monitor is a normal Unix process. Closing the terminal sends SIGHUP
to its process group. **By default the Monitor will exit cleanly on
SIGHUP** (good for interactive smoke tests, bad for production). Four
ways to keep it alive:

| Mode                              | Survives terminal close? | Survives reboot? | Use for                              |
|-----------------------------------|--------------------------|------------------|---------------------------------------|
| `codegreen monitor ...`           | No                       | No               | Interactive debugging                 |
| `nohup codegreen monitor ... &`   | Yes (ignores SIGHUP)     | No               | One-off long capture                  |
| `tmux new -d 'codegreen monitor ...'` | Yes (tmux owns it)   | No               | Personal dev box                      |
| `systemctl --user start codegreen-monitor.service` | Yes | **Yes** (auto-restart on crash) | **Production webapps (XaBerr's case)** |

### Example systemd unit

`~/.config/systemd/user/codegreen-monitor.service`:

```ini
[Unit]
Description=CodeGreen continuous monitor (annotation socket sidecar)
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/codegreen monitor \
    --listen-on-socket %t/cg.sock \
    -o %h/.local/share/codegreen/energy.jsonl \
    --rotate-mb 100 \
    --max-in-memory 10000 \
    --interval-ms 500 \
    --quiet --json
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

Start: `systemctl --user enable --now codegreen-monitor`.
Stop:  `systemctl --user stop codegreen-monitor` (clean SIGTERM →
summary flushed → JSONL closed). The unit auto-restarts on crash.

### Example `nohup` (quickest)

```bash
nohup codegreen monitor \
    --listen-on-socket /tmp/cg.sock \
    -o /var/log/codegreen/energy.jsonl \
    --rotate-mb 100 --quiet --json \
    > /var/log/codegreen/monitor.out 2>&1 &
```

To stop: `kill -TERM <pid>` (where `<pid>` is in `~/codegreen-monitor.pid`
if you wrote it there; otherwise `pgrep -f 'codegreen monitor'`).

## Wiring the annotation middleware

The example uses a stdlib `BaseHTTPRequestHandler`. For real frameworks:

### Flask

```python
from flask import g, request
from codegreen import annotate_request

@app.before_request
def _cg_start():
    g._cg = annotate_request(f"{request.method} {request.path}",
                             socket_path="/tmp/cg.sock").__enter__()

@app.teardown_request
def _cg_end(exc):
    g._cg.__exit__(type(exc) if exc else None, exc, None)
```

### Generic WSGI

```python
from codegreen import annotate_request

def cg_middleware(app, socket_path="/tmp/cg.sock"):
    def wrapped(environ, start_response):
        label = f"{environ['REQUEST_METHOD']} {environ['PATH_INFO']}"
        with annotate_request(label, socket_path=socket_path):
            return app(environ, start_response)
    return wrapped
```

## What you get out

Two streams:

1. **`energy.jsonl`** — durable record. One JSON per line:
   - `{"type":"sample","t":...,"joules_total":...,"watts":...}` — every interval
   - `{"type":"annotation_start","name":"GET /heavy","token":...}` — per request
   - `{"type":"annotation_end","token":...,"joules":...,"duration_s":...,"status":"ok"}`
2. **Monitor summary** (on stop) — `per_label` dict with count, total
   joules, joules/call, p50/p95 latency for each label.

## Caveats (read these)

- **Sample interval bounds attribution granularity.** Requests shorter
  than `interval_ms` (default 500 ms; minimum 50 ms) may attribute 0 J
  to that label because no sample tick falls inside the span. Aggregate
  across many hits OR drop to a smaller interval. The lower bound is
  noise-floor, not arbitrary.
- **Per-PID accuracy depends on the attribution backend.** On Linux
  with cgroup v2 (most modern distros), `--attribution-mode auto` picks
  `cgroup_v2`, which is the accurate path. Older systems fall back to
  `cpu_percent` — fine as a relative signal, not absolute. See
  [example 07](07_monitor_pid.md) for the comparison.
- **One monitor per host.** The socket path is the only namespace; two
  monitors on the same socket → second one fails fast.

## Next steps

- [Continuous monitoring guide](../user-guide/continuous-monitoring.md)
  — full Monitor / annotation reference.
- [Example 08](08_monitor_socket.md) — same flow inside one process
  (useful for tests).
- [Example 07](07_monitor_pid.md) — per-PID attribution mode comparison.
