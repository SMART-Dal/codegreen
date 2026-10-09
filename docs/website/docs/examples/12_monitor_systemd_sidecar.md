# 12 — Monitor systemd sidecar (production-shaped, no root)

**Who this is for.** You ran [example 11](11_monitor_socket_standalone.md)
and want the sidecar to actually behave like a production unit:
auto-restart on crash, auto-start on boot (with linger), clean SIGTERM
shutdown, no orphaned processes when your terminal closes or your SSH
session drops.

This example wires `codegreen monitor` into a **user-mode** systemd unit
under `~/.config/systemd/user/`. No `sudo`, no system-wide install, no
admin assistance. The same unit file (or a near-mirror with `--system`
paths) is what you ship in production.

## Quick run

```bash
cd codegreen
python examples/12_monitor_systemd_sidecar/main.py
```

Expected last line on a Linux host with systemd:

```text
OK: monitor_systemd_sidecar; labels=3; samples=5; annotation_starts=5; annotation_ends=5; total_j=192.4; unit=codegreen-monitor-1559456.service
```

On macOS, BSD, or a Linux host without per-user systemd
(`XDG_RUNTIME_DIR` missing), the script prints
`SKIP: systemd not available` and exits 0. The test harness treats both
as success.

## What the example does

1. Writes a transient `codegreen-monitor-<pid>.service` to
   `~/.config/systemd/user/`. The unit's `ExecStart` points at the local
   `codegreen` binary plus the production flag set: `--listen-on-socket
   <runtime>/cg.sock -o <runtime>/energy.jsonl --rotate-mb 50
   --max-labels 100 --interval 250 --quiet --json`.
2. Runs `systemctl --user daemon-reload` + `systemctl --user start
   codegreen-monitor-<pid>`.
3. Waits for the monitor to bind the UDS, then drives 5 HTTP requests
   against an in-process `ThreadingHTTPServer`. The middleware opens an
   annotation span per request via the socket — same wire as
   [example 11](11_monitor_socket_standalone.md).
4. Stops the unit (`systemctl --user stop`), waits for the JSONL summary
   to land, parses it.
5. Cleans up: `disable`, removes the unit file, `daemon-reload`,
   removes the temporary runtime dir.

## Will the monitor survive terminal close, SSH drop, or reboot?

Yes — **with one caveat**.

| Event                | Survives by default? | How to fix                                  |
|----------------------|----------------------|---------------------------------------------|
| Terminal close       | Yes                  | systemd owns the process, not your shell.   |
| SSH session drop     | Yes                  | Same: detached from your login session.     |
| `systemctl --user stop` | No (by design)    | Clean shutdown path; summary flushed.       |
| Crash inside monitor | Yes (auto-restart)   | `Restart=on-failure` + `RestartSec=2`.      |
| Reboot               | Only with linger     | `sudo loginctl enable-linger $USER` once.   |

Without `enable-linger`, the per-user systemd manager exits when your
last login session ends, taking your monitor with it. With linger,
the manager stays up across reboots and your unit's `WantedBy=default.target`
+ `systemctl --user enable` will auto-start it.

## Reusing the unit in production

Production hosts usually want a **system** unit (under `/etc/systemd/system/`)
running as a dedicated `codegreen` user. The example's unit is the
template; in production you only swap paths and the `User=` line.

```ini
[Unit]
Description=CodeGreen continuous monitor (annotation socket sidecar)
After=network.target

[Service]
Type=simple
User=codegreen
ExecStart=/usr/local/bin/codegreen monitor \
    --listen-on-socket /run/codegreen/cg.sock \
    -o /var/log/codegreen/energy.jsonl \
    --rotate-mb 100 --max-in-memory 0 --max-labels 1000 \
    --interval 500 --quiet --json
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=5
LimitNOFILE=8192

[Install]
WantedBy=multi-user.target
```

Three things to notice:

- **`ExecReload=/bin/kill -HUP $MAINPID`** — wires `systemctl reload` to
  SIGHUP, which the Monitor reads as "re-read config without dropping
  in-flight annotations or the JSONL position". See
  [continuous-monitoring guide → SIGHUP-reload](../user-guide/continuous-monitoring.md#sighup-reload-policy-changes-without-restart).
- **`--max-labels 1000`** — caps annotation cardinality so a label
  source with raw URLs or per-user UUIDs cannot OOM the aggregator.
  Overflow rolls into a single `__other__` bucket carrying a count + total
  joules so you still see it happen.
- **`--rotate-mb 100`** — JSONL rotates at 100 MB; older files keep up to
  `monitor.rotate_max_backups` (default 5) generations.

## What you get out

Identical to [example 11](11_monitor_socket_standalone.md):

- **`/var/log/codegreen/energy.jsonl`** — durable record, one JSON per line
  (`header`, `sample`, `annotation_start`, `annotation_end`, optional
  `reload`, trailing `summary`).
- **summary.per_label** — aggregated `count`, `joules_total`,
  `joules_per_call_avg`, `latency_ms_p50`, `latency_ms_p95` per route,
  plus the `__other__` overflow bucket if the cardinality cap fired.

## Caveats

- **Linux-only.** macOS uses `launchd`, BSDs use `rc.d`. The wire
  protocol (UDS annotation socket) is identical across platforms — the
  example's harness layer is what changes. The test harness `SKIP`s
  cleanly when systemd is absent.
- **User mode vs system mode.** User-mode is convenient (no root) but
  the unit dies when your last login session ends unless linger is
  enabled. For real production, use a system unit + a dedicated service
  account.
- **One monitor per host.** Multiple monitors double-count RAPL. The
  unit's `Restart=on-failure` plus the socket-uniqueness check in the
  Monitor prevent two from coming up on the same socket.

## Next steps

- [Continuous monitoring guide](../user-guide/continuous-monitoring.md)
  — full Monitor / annotation reference + the eight production
  deployment shapes (Apache/Flask, K8s SaaS, MLOps, batch ETL,
  IoT/edge, CI/CD, dashboards, compliance).
- [Example 11](11_monitor_socket_standalone.md) — same sidecar wire,
  unsupervised (Python subprocess for tests).
- [Example 08](08_monitor_socket.md) — same UDS protocol, but with the
  Monitor embedded in the application process.
