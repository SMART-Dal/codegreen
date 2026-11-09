# 11 - Monitor socket (standalone)

Run `codegreen monitor` as its own process and let an already-running web
application send per-request annotations over the Unix-domain socket. The
monitor and the application share no imports and restart independently.
This is the production shape of [example 08](08_monitor_socket.md), which
embeds the Monitor in the application process.

## Source

[`examples/11_monitor_socket_standalone/main.py`](https://github.com/SMART-Dal/codegreen/blob/main/examples/11_monitor_socket_standalone/main.py)

```python
--8<-- "examples/11_monitor_socket_standalone/main.py"
```

## Run

```bash
python examples/11_monitor_socket_standalone/main.py
```

The script:

1. Starts `codegreen monitor --listen-on-socket <sock> -o energy.jsonl
   --quiet --json -i 150` as a subprocess and waits for the socket.
2. Starts a stdlib `ThreadingHTTPServer` whose handler sends `op=start`
   before and `op=end` after each request.
3. Sends 7 requests to `/light`, `/medium` and `/heavy`.
4. Sends SIGTERM to the monitor, reads the summary from its stdout and
   counts the records in the JSONL file.

## Output

Last line from a run on an AMD EPYC host:

```text
OK: monitor_socket_standalone; labels=3; samples=8; annotation_starts=7; annotation_ends=7; total_j=101.963
```

## Wiring a framework

The handler in the script speaks the socket protocol directly. In a
framework, use `codegreen.annotate_request`, which connects to the same
default path as `--listen-on-socket default`.

Flask: see the middleware in
[Per-request attribution](../user-guide/continuous-monitoring.md#per-request-attribution).

Generic WSGI (the span ends when the application returns its iterable,
before a streamed body is sent):

```python
from codegreen import annotate_request

def cg_middleware(app):
    def wrapped(environ, start_response):
        with annotate_request(f"{environ['REQUEST_METHOD']} {environ['PATH_INFO']}"):
            return app(environ, start_response)
    return wrapped
```

Map `PATH_INFO` to a route template before using it as a label if paths
contain IDs.

## Running it unattended

Run the monitor with `--quiet` or under a supervisor: a terminal hangup is
a configuration reload, and without `--quiet` the monitor exits on the
closed terminal without writing its summary. A user systemd unit:

```ini
# ~/.config/systemd/user/codegreen-monitor.service
[Unit]
Description=CodeGreen monitor (annotation socket)

[Service]
ExecStart=/usr/local/bin/codegreen monitor --listen-on-socket default \
    -o %h/.local/share/codegreen/energy.jsonl \
    --rotate-mb 100 --max-labels 1000 --quiet
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable --now codegreen-monitor
systemctl --user stop codegreen-monitor    # SIGTERM: summary written, file closed
```

The directory of the `-o` file must exist. [Example 12](12_monitor_systemd_sidecar.md)
covers boot persistence and a system-wide unit.

## Caveats

- A request shorter than the interval can receive 0 J; see
  [Per-request attribution](../user-guide/continuous-monitoring.md#per-request-attribution).
- The socket has mode 0600: the application must run as the same user as
  the monitor (with `default`, both also resolve the same per-user path).
- Run one monitor per socket path: a second monitor started on the same path
  by the same user replaces the socket and the first stops receiving
  annotations without an error.
- Energy is host-wide; two monitors on one host count the same joules.
