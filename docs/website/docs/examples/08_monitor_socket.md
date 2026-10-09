# 08 - Monitor socket (Flask / WSGI request attribution)

Run a Monitor with `--listen-on-socket`, send `start`/`end` events from a
tiny HTTP server, and get **per-request energy + p50/p95 latency**. This is
the recipe for Apache+mod_wsgi+Flask and any other already-running web
server -- exactly the use case from GitHub Discussion #5.

## What you learn

- Monitor's Unix-domain-socket annotation channel.
- The `codegreen.annotate_request("label")` context manager.
- The `per_label` summary in the Monitor's stop record: `count`,
  `total_joules`, `p50_ms`, `p95_ms`.

## Prerequisites

- `pip install codegreen` (stdlib only; no Flask required).
- Linux or macOS with a working backend.

## Source

[`examples/08_monitor_socket/main.py`](https://github.com/SMART-Dal/codegreen/blob/main/examples/08_monitor_socket/main.py)

```python
--8<-- "examples/08_monitor_socket/main.py"
```

## Run

```bash
python examples/08_monitor_socket/main.py
```

## Equivalent CLI

```bash
codegreen monitor --listen-on-socket /tmp/cg.sock -o requests.jsonl
```

## Flask middleware recipe

```python
from flask import Flask, g, request
import codegreen

app = Flask(__name__)

@app.before_request
def _cg_start():
    g._cg = codegreen.annotate_request(
        f"{request.method} {request.path}",
        socket_path="/tmp/cg.sock",
    ).__enter__()

@app.teardown_request
def _cg_end(exc):
    g._cg.__exit__(None, None, None)
```

Start the Monitor separately:

```bash
codegreen monitor --listen-on-socket /tmp/cg.sock -o energy.jsonl &
gunicorn -w 4 'app:app'
```

## Expected output

```
{"labels": {"GET /light": {"count": 1, ...}, "GET /heavy": {"count": 2, ...}}}
OK: monitor_socket; labels=3; total_j=0.321; requests=5
```

## Why it matters

This is the **first per-request energy primitive** that works with the
"server is already running, you can't embed instrumentation" case. The UDS
listener is non-blocking, daemon-thread-local, and racing-safe; a single
Monitor process can serve hundreds of workers via a shared socket.

See also: [User guide: Continuous Monitoring](../user-guide/continuous-monitoring.md#per-request-attribution),
[Python API: annotate_request](../api/python.md#annotate_request).
