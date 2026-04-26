"""Post-measurement energy timeline visualization.

Checkpoint format from C++ NEMB backend:
  {"checkpoint_id": "enter:main:1", "timestamp": <ns>, "joules": <float>, "watts": <float>}
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

CG = "#4dae50"
RED = "#e55353"
BG = "#1a1a1a"
CARD = "#242424"
GRID = "#333"
TXT = "#aaa"


def parse_checkpoints(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse raw checkpoint dicts into normalized timeline points."""
    if not raw:
        return []
    t0 = raw[0].get("timestamp", 0)
    points: list[dict[str, Any]] = []
    for i, cp in enumerate(raw):
        cid = cp.get("checkpoint_id", "")
        parts = cid.split(":")
        cp_type = parts[0] if parts else "unknown"
        func = parts[1] if len(parts) > 1 else cid
        ts = cp.get("timestamp", 0)
        joules = cp.get("joules", 0.0)
        watts = cp.get("watts", 0.0)
        prev_j = raw[i - 1].get("joules", 0.0) if i > 0 else 0.0
        points.append({
            "time_s": (ts - t0) / 1e9,
            "joules": joules,
            "watts": watts,
            "delta_j": joules - prev_j,
            "type": cp_type,
            "func": func,
        })
    return points


def _compute_stats(points: list[dict[str, Any]]) -> dict[str, Any]:
    total_j = points[-1]["joules"] - points[0]["joules"]
    wall_s = points[-1]["time_s"] - points[0]["time_s"]
    avg_w = total_j / wall_s if wall_s > 0 else 0
    peak_w = max(p["watts"] for p in points)
    func_energy: dict[str, float] = {}
    for p in points:
        if "exit" in p["type"]:
            func_energy[p["func"]] = func_energy.get(p["func"], 0) + p["delta_j"]
    func_sorted = sorted(func_energy.items(), key=lambda x: -x[1])
    hotspots = []
    if func_energy:
        vals = sorted(func_energy.values())
        p90 = vals[int(len(vals) * 0.9)] if len(vals) > 1 else vals[0]
        hotspots = [f for f, e in func_energy.items() if e >= p90]
    return {
        "total_j": round(total_j, 6), "wall_s": round(wall_s, 6),
        "avg_w": round(avg_w, 3), "peak_w": round(peak_w, 3),
        "func_energy": {f: round(e, 6) for f, e in func_sorted},
        "hotspots": hotspots,
    }


def export_plot(checkpoints: list[dict[str, Any]], path: Path) -> None:
    """Export energy timeline visualization. Format based on file extension."""
    points = parse_checkpoints(checkpoints)
    if not points:
        return
    path = Path(path)
    if not path.suffix:
        path = path.with_suffix(".html")
    if path.suffix == ".html":
        _render_plotly(points, path)
    elif path.suffix in (".png", ".pdf"):
        _render_matplotlib(points, path)
    else:
        _render_plotly(points, path.with_suffix(".html"))


def _render_plotly(points: list[dict[str, Any]], path: Path) -> None:
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        raise ValueError("plotly required for HTML export: pip install plotly")

    stats = _compute_stats(points)
    fe = stats["func_energy"]
    has_funcs = len(fe) > 1

    # For large checkpoint counts: keep hotspot functions + uniform sample of rest
    display_pts = points
    hotspot_set = set(stats["hotspots"])
    if len(points) > 5000:
        hot = [p for p in points if p["func"] in hotspot_set]
        cold = [p for p in points if p["func"] not in hotspot_set]
        # Keep all hotspot points (up to 3000), uniform sample the rest
        if len(hot) > 3000:
            step = len(hot) // 3000
            hot = hot[::step]
        remain = max(500, 5000 - len(hot))
        if len(cold) > remain:
            step = len(cold) // remain
            cold = cold[::step]
        display_pts = sorted(hot + cold, key=lambda p: p["time_s"])
        if display_pts[-1] is not points[-1]:
            display_pts.append(points[-1])

    rows = 2 if has_funcs else 1
    specs = [[{"type": "bar"}], [{"type": "scatter"}]] if has_funcs else [[{"type": "scatter"}]]
    heights = [0.3, 0.7] if has_funcs else [1.0]
    fig = make_subplots(
        rows=rows, cols=1, row_heights=heights, specs=specs,
        subplot_titles=["Function Energy (J)", "Energy Timeline"] if has_funcs else ["Energy Timeline"],
        vertical_spacing=0.12 if has_funcs else 0,
    )

    # Bar chart
    if has_funcs:
        names = list(fe.keys())
        vals = list(fe.values())
        colors = [RED if n in stats["hotspots"] else CG for n in names]
        fig.add_trace(go.Bar(
            y=names, x=vals, orientation="h",
            marker_color=colors, text=[f"{v:.4f} J" for v in vals],
            textposition="outside", textfont_size=11,
            hovertemplate="%{y}: %{x:.6f} J<extra></extra>",
        ), row=1, col=1)
        fig.update_yaxes(autorange="reversed", row=1, col=1)

    # Timeline scatter
    tl_row = rows
    times = [p["time_s"] for p in display_pts]
    joules = [p["joules"] for p in display_pts]
    marker_colors = [CG if "enter" in p["type"] else RED for p in display_pts]
    hover_text = [
        f"<b>{p['func']}</b> ({p['type']})<br>"
        f"Time: {p['time_s']:.6f}s<br>"
        f"Energy: {p['joules']:.6f} J<br>"
        f"Power: {p['watts']:.3f} W<br>"
        f"Delta: {p['delta_j']:.6f} J"
        for p in display_pts
    ]
    fig.add_trace(go.Scatter(
        x=times, y=joules, mode="lines", line=dict(color=GRID, width=1),
        showlegend=False, hoverinfo="skip",
    ), row=tl_row, col=1)
    fig.add_trace(go.Scatter(
        x=times, y=joules, mode="markers",
        marker=dict(color=marker_colors, size=7, line=dict(color=BG, width=1)),
        text=hover_text, hoverinfo="text",
        showlegend=False,
    ), row=tl_row, col=1)
    fig.update_xaxes(title_text="Time (s)", row=tl_row, col=1)
    fig.update_yaxes(title_text="Energy (J)", row=tl_row, col=1)

    # Summary annotation
    wall_fmt = f"{stats['wall_s']*1000:.2f} ms" if stats["wall_s"] < 1 else f"{stats['wall_s']:.4f} s"
    summary = (
        f"Total: {stats['total_j']:.4f} J | Wall: {wall_fmt} | "
        f"Avg: {stats['avg_w']:.2f} W | Peak: {stats['peak_w']:.2f} W | "
        f"Checkpoints: {len(points)}"
    )
    if len(points) != len(display_pts):
        summary += f" (showing {len(display_pts)})"

    fig.update_layout(
        title=dict(text=f"CodeGreen Energy Timeline<br><sub>{summary}</sub>", font_color=CG),
        template="plotly_dark",
        paper_bgcolor=BG, plot_bgcolor=CARD,
        font=dict(family="system-ui, -apple-system, sans-serif", color=TXT),
        height=700 if has_funcs else 450,
        margin=dict(l=60, r=30, t=80, b=40),
        dragmode="zoom",
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID)

    fig.write_html(str(path), include_plotlyjs=True, full_html=True)


def _render_matplotlib(points: list[dict[str, Any]], path: Path) -> None:
    try:
        import matplotlib.pyplot as plt
        import matplotlib
        matplotlib.rcParams.update({
            "figure.facecolor": BG, "axes.facecolor": CARD,
            "axes.edgecolor": GRID, "axes.labelcolor": TXT,
            "xtick.color": TXT, "ytick.color": TXT,
            "text.color": TXT, "grid.color": GRID,
        })
    except ImportError:
        raise ValueError("matplotlib required for PNG/PDF export: pip install matplotlib")
    stats = _compute_stats(points)
    fe = stats["func_energy"]
    has_funcs = len(fe) > 1
    fig, axes = plt.subplots(2 if has_funcs else 1, 1,
                             figsize=(10, 8 if has_funcs else 5),
                             gridspec_kw={"height_ratios": [1, 1.5]} if has_funcs else None)
    if not has_funcs:
        axes = [axes]
    if has_funcs:
        ax = axes[0]
        names = list(fe.keys())
        vals = list(fe.values())
        colors = [(RED if n in stats["hotspots"] else CG) for n in names]
        ax.barh(names, vals, color=colors, height=0.6)
        ax.set_xlabel("Energy (J)")
        ax.set_title("Per-Function Energy", fontsize=11, color=CG)
        ax.invert_yaxis()
        ax.grid(axis="x", alpha=0.2)
    ax2 = axes[-1]
    times = [p["time_s"] for p in points]
    joules = [p["joules"] for p in points]
    cols = [CG if "enter" in p["type"] else RED for p in points]
    ax2.plot(times, joules, "-", color=GRID, linewidth=1, alpha=0.7)
    ax2.scatter(times, joules, c=cols, s=50, zorder=5, edgecolors=BG, linewidths=0.5)
    if len(points) <= 30:
        labeled: set[str] = set()
        idx = 0
        for p in points:
            if p["func"] in labeled:
                continue
            labeled.add(p["func"])
            late = p["time_s"] > (times[-1] * 0.7)
            dx = -80 if late else 15
            dy = -12 * idx if late else 15 + 12 * idx
            ax2.annotate(
                p["func"], (p["time_s"], p["joules"]),
                fontsize=7, textcoords="offset points", xytext=(dx, dy),
                color=CG if "enter" in p["type"] else RED,
                arrowprops=dict(arrowstyle="-", color=GRID, lw=0.5),
            )
            idx += 1
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Energy (J)")
    ax2.set_title("Energy Timeline", fontsize=11, color=CG)
    ax2.grid(alpha=0.15)
    wall_fmt = f"{stats['wall_s']*1000:.1f}ms" if stats["wall_s"] < 1 else f"{stats['wall_s']:.3f}s"
    fig.suptitle(
        f"CodeGreen  |  {stats['total_j']:.2f} J  |  {wall_fmt}  |  "
        f"Peak {stats['peak_w']:.1f} W  |  {len(points)} checkpoints",
        fontsize=10, color=CG, y=0.98,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)


def export_session_plot(report: dict, path: Path) -> None:
    """Render a power-vs-time chart from a codegreen.Session report.
    Expects report["tasks"] with each task having `timeseries` of {t,j,w,d}."""
    tasks = [t for t in report.get("tasks", []) if t.get("timeseries")]
    if not tasks:
        return
    path = Path(path)
    if path.suffix == ".html":
        _render_session_plotly(tasks, path)
    elif path.suffix in (".png", ".svg", ".pdf"):
        _render_session_matplotlib(tasks, path)
    else:
        _render_session_plotly(tasks, path.with_suffix(".html"))


def _render_session_plotly(tasks: list, path: Path) -> None:
    try:
        import plotly.graph_objects as go
    except ImportError:
        return
    fig = go.Figure()
    t0_ns = min(s["t"] for t in tasks for s in t["timeseries"])
    for t in tasks:
        ts = t["timeseries"]
        x = [(s["t"] - t0_ns) / 1e9 for s in ts]
        y = [s["w"] for s in ts]
        fig.add_trace(go.Scatter(
            x=x, y=y, mode="lines", name=t["name"],
            line=dict(width=1),
            hovertemplate="t=%{x:.3f}s  P=%{y:.1f}W<extra>" + t["name"] + "</extra>",
        ))
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG, plot_bgcolor=CARD,
        title=f"CodeGreen Session Power Trace  ({len(tasks)} task(s))",
        xaxis_title="Time (s)", yaxis_title="Power (W)",
        height=420, showlegend=True,
        font=dict(color=TXT),
    )
    fig.write_html(str(path), include_plotlyjs=True, full_html=True)


def _render_session_matplotlib(tasks: list, path: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    fig, ax = plt.subplots(figsize=(10, 4), facecolor=BG)
    ax.set_facecolor(CARD)
    t0_ns = min(s["t"] for t in tasks for s in t["timeseries"])
    for t in tasks:
        ts = t["timeseries"]
        x = [(s["t"] - t0_ns) / 1e9 for s in ts]
        y = [s["w"] for s in ts]
        ax.plot(x, y, lw=0.8, label=t["name"])
    ax.set_xlabel("Time (s)", color=TXT)
    ax.set_ylabel("Power (W)", color=TXT)
    ax.set_title("CodeGreen Session Power Trace", color=CG)
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(alpha=0.15)
    ax.tick_params(colors=TXT)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
