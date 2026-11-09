# 12 - Monitor systemd sidecar

Run the [example 11](11_monitor_socket_standalone.md) sidecar under
user-mode systemd: restart on failure, clean SIGTERM shutdown, and
independence from the terminal and the SSH session. No root is needed.

## Source

[`examples/12_monitor_systemd_sidecar/main.py`](https://github.com/SMART-Dal/codegreen/blob/main/examples/12_monitor_systemd_sidecar/main.py)

```python
--8<-- "examples/12_monitor_systemd_sidecar/main.py"
```

## Run

```bash
python examples/12_monitor_systemd_sidecar/main.py
```

The script:

1. Writes `~/.config/systemd/user/codegreen-monitor-<pid>.service` whose
   `ExecStart` is the `codegreen` on `PATH` with `--listen-on-socket
   <runtime>/cg.sock -o <runtime>/energy.jsonl --rotate-mb 50
   --max-in-memory 0 --max-labels 100 --interval 250 --quiet --json`, where
   `<runtime>` is a directory under `$XDG_RUNTIME_DIR`.
2. Runs `systemctl --user daemon-reload` and `start`, waits for the socket,
   and sends 5 requests through a stdlib HTTP server that annotates each one.
3. Stops the unit, reads the `summary` record from the JSONL file, then
   disables and deletes the unit and the runtime directory.

It prints a line of the form

```text
OK: monitor_systemd_sidecar; labels=<n>; samples=<n>; annotation_starts=5; annotation_ends=5; total_j=<J>; unit=codegreen-monitor-<pid>.service
```

and prints `SKIP: systemd not available ...` and exits 0 when
`systemctl --user` or `XDG_RUNTIME_DIR` is unavailable (macOS, most
containers).

## Lifetime

| Event | Monitor keeps running | Notes |
|---|---|---|
| Terminal close, SSH drop | Yes | systemd owns the process |
| `systemctl --user stop` | No | SIGTERM: summary written, file closed |
| Monitor crash | Yes | `Restart=on-failure` |
| Logout of the last session, reboot | Only with linger | `sudo loginctl enable-linger $USER`, plus `systemctl --user enable` for start at boot |

## System unit

A system unit runs the monitor as a service account. Because the
annotation socket has mode 0600, that account must be the one the
application runs as, and it needs read access to the energy counters
(`sudo codegreen init-sensors` adds the invoking user to the `codegreen`
group; add the service account to that group).

```ini
# /etc/systemd/system/codegreen-monitor.service
[Unit]
Description=CodeGreen monitor (annotation socket)

[Service]
User=www-data
RuntimeDirectory=codegreen
LogsDirectory=codegreen
ExecStart=/usr/local/bin/codegreen monitor \
    --listen-on-socket /run/codegreen/cg.sock \
    -o /var/log/codegreen/energy.jsonl \
    --rotate-mb 100 --max-in-memory 0 --max-labels 1000 --quiet
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

- `RuntimeDirectory` and `LogsDirectory` create `/run/codegreen` and
  `/var/log/codegreen` for the service user; the monitor does not create
  either directory.
- The application passes `socket_path="/run/codegreen/cg.sock"` to
  `codegreen.annotate_request`.
- `ExecReload` maps `systemctl reload` to SIGHUP, which re-reads
  `monitor.interval_ms_default`, `monitor.rotate_mb_default`,
  `monitor.max_samples_in_memory` and `monitor.annotation.max_labels` from
  the configuration. Those values then replace the command-line options;
  see [Reloading configuration](../user-guide/continuous-monitoring.md#reloading-configuration).

## Caveats

- Linux with systemd only; the socket protocol itself is the same
  everywhere.
- One monitor per socket path, and energy is host-wide; see
  [example 11](11_monitor_socket_standalone.md#caveats).
