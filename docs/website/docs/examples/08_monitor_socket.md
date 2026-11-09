# 08 - Monitor socket (in-process)

Run a Monitor with an annotation socket inside the same Python process as a
small HTTP server, wrap each request in a `start`/`end` annotation, and
read per-route energy and latency from the summary. No Flask required.

## What you learn

- The Monitor's Unix-domain-socket annotation channel (`listen_socket_path`).
- The line-delimited JSON protocol (`op: start` / `op: end`).
- The `per_label` summary: `count`, `joules_total`, `duration_total_s`,
  `joules_per_call_avg`, `latency_ms_p50`, `latency_ms_p95`.

## Prerequisites

- `pip install codegreen`
- Linux or macOS (Unix-domain sockets) with a working energy provider.

## Source

[`examples/08_monitor_socket/main.py`](https://github.com/SMART-Dal/codegreen/blob/main/examples/08_monitor_socket/main.py)

```python
--8<-- "examples/08_monitor_socket/main.py"
```

## Run

```bash
python examples/08_monitor_socket/main.py
```

## Output

From a run on an AMD EPYC host (interval 150 ms):

```text
{
  "labels": {
    "GET /heavy": {
      "count": 2,
      "joules_total": 14.458636,
      "duration_total_s": 0.193379,
      "joules_per_call_avg": 7.229318,
      "latency_ms_p50": 96.994,
      "latency_ms_p95": 96.385
    },
    "GET /light": {
      "count": 1,
      "joules_total": 0.0,
      "duration_total_s": 0.000855,
      "joules_per_call_avg": 0.0,
      "latency_ms_p50": 0.855,
      "latency_ms_p95": 0.855
    },
    "GET /medium": {
      "count": 2,
      "joules_total": 0.0,
      "duration_total_s": 0.020084,
      "joules_per_call_avg": 0.0,
      "latency_ms_p50": 10.105,
      "latency_ms_p95": 9.979
    }
  }
}
OK: monitor_socket; labels=3; total_j=86.469; requests=5
```

`/light` and `/medium` finish well inside one 150 ms interval, so no sample
was taken while they were open and they received 0 J. A span receives the
whole energy of each sample taken while it is open; see
[Per-request attribution](../user-guide/continuous-monitoring.md#per-request-attribution)
for the rules and the Flask middleware.

This example embeds the Monitor in the application process, which suits
tests. For a running server, run the monitor as a separate process:
[11 - Monitor socket (standalone)](11_monitor_socket_standalone.md).

See also: [Python API: annotate_request](../api/python.md#annotate_request).
