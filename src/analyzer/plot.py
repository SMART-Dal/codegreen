"""Post-measurement energy timeline visualization.

Checkpoint format from C++ NEMB backend:
  {"checkpoint_id": "function_enter:main:1", "timestamp": <ns>, "joules": <float>, "watts": <float>}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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


def export_plot(checkpoints: list[dict[str, Any]], path: Path) -> None:
    """Export energy timeline visualization. Format based on file extension."""
    points = parse_checkpoints(checkpoints)
    if not points:
        return
    path = Path(path)
    if not path.suffix:
        path = path.with_suffix(".html")
    if path.suffix == ".html":
        _render_html(points, path)
    elif path.suffix in (".png", ".pdf"):
        _render_matplotlib(points, path)
    else:
        _render_html(points, path.with_suffix(".html"))


def _render_matplotlib(points: list[dict[str, Any]], path: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        raise ValueError("matplotlib required for PNG/PDF export: pip install matplotlib")
    times = [p["time_s"] for p in points]
    joules = [p["joules"] for p in points]
    colors = ["#22c55e" if "enter" in p["type"] else "#ef4444" for p in points]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(times, joules, "-", color="#6366f1", linewidth=1.5)
    ax.scatter(times, joules, c=colors, s=40, zorder=5)
    for p in points:
        if len(points) <= 20:
            ax.annotate(p["func"], (p["time_s"], p["joules"]), fontsize=7,
                        textcoords="offset points", xytext=(4, 6))
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Energy (J)")
    ax.set_title("CodeGreen Energy Timeline")
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _render_html(points: list[dict[str, Any]], path: Path) -> None:
    total_j = points[-1]["joules"] - points[0]["joules"]
    wall_s = points[-1]["time_s"] - points[0]["time_s"]
    avg_w = total_j / wall_s if wall_s > 0 else 0
    peak_w = max(p["watts"] for p in points)
    # per-function energy
    func_energy: dict[str, float] = {}
    for p in points:
        if p["type"] in ("function_exit", "exit"):
            func_energy[p["func"]] = func_energy.get(p["func"], 0) + p["delta_j"]
    func_sorted = sorted(func_energy.items(), key=lambda x: -x[1])
    # peak detection: >90th percentile
    if func_energy:
        vals = sorted(func_energy.values())
        p90 = vals[int(len(vals) * 0.9)] if len(vals) > 1 else vals[0]
        hotspots = [f for f, e in func_energy.items() if e >= p90]
    else:
        hotspots = []

    data_json = json.dumps(points)
    stats_json = json.dumps({
        "total_j": round(total_j, 6), "wall_s": round(wall_s, 6),
        "avg_w": round(avg_w, 3), "peak_w": round(peak_w, 3),
        "func_energy": {f: round(e, 6) for f, e in func_sorted},
        "hotspots": hotspots,
    })

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>CodeGreen Energy Timeline</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:system-ui,-apple-system,sans-serif;background:#0f172a;color:#e2e8f0;padding:20px}}
.grid{{display:grid;grid-template-columns:1fr 280px;gap:20px;max-width:1200px;margin:0 auto}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
h1{{font-size:1.3rem;margin-bottom:12px;color:#a5b4fc}}
.stat{{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #334155}}
.stat-val{{color:#22d3ee;font-weight:600}}
.hotspot{{color:#f87171;font-weight:600}}
svg{{width:100%;height:400px}}
.tooltip{{position:absolute;background:#1e293b;border:1px solid #475569;border-radius:6px;padding:8px 12px;
  font-size:0.8rem;pointer-events:none;display:none;z-index:10}}
#func-table{{width:100%;font-size:0.8rem;margin-top:8px}}
#func-table td{{padding:3px 6px}}
#func-table tr:nth-child(even){{background:#253044}}
.enter{{fill:#22c55e}} .exit{{fill:#ef4444}}
@media(max-width:768px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body>
<h1>CodeGreen Energy Timeline</h1>
<div class="grid">
<div class="card" id="chart-card"><svg id="svg"></svg></div>
<div class="card" id="stats-card"></div>
</div>
<div class="tooltip" id="tip"></div>
<script>
const pts={data_json};
const stats={stats_json};
const svg=document.getElementById("svg");
const tip=document.getElementById("tip");
const sc=document.getElementById("stats-card");
// Stats panel
let sh='<h1>Summary</h1>';
sh+='<div class="stat"><span>Total Energy</span><span class="stat-val">'+stats.total_j.toFixed(4)+' J</span></div>';
sh+='<div class="stat"><span>Wall Time</span><span class="stat-val">'+stats.wall_s.toFixed(4)+' s</span></div>';
sh+='<div class="stat"><span>Avg Power</span><span class="stat-val">'+stats.avg_w.toFixed(3)+' W</span></div>';
sh+='<div class="stat"><span>Peak Power</span><span class="stat-val">'+stats.peak_w.toFixed(3)+' W</span></div>';
if(Object.keys(stats.func_energy).length>0){{
  sh+='<h1 style="margin-top:12px">Functions</h1><table id="func-table">';
  for(const[f,e]of Object.entries(stats.func_energy)){{
    const cls=stats.hotspots.includes(f)?'hotspot':'';
    sh+='<tr><td class="'+cls+'">'+f+'</td><td class="stat-val">'+e.toFixed(6)+' J</td></tr>';
  }}
  sh+='</table>';
}}
sc.innerHTML=sh;
// Chart
const W=svg.clientWidth||800,H=svg.clientHeight||400;
const pad={{t:20,r:20,b:40,l:60}};
const cw=W-pad.l-pad.r,ch=H-pad.t-pad.b;
const xs=pts.map(p=>p.time_s),ys=pts.map(p=>p.joules);
let xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys),ymax=Math.max(...ys);
if(xmax===xmin){{xmin-=0.5;xmax+=0.5}}
if(ymax===ymin){{ymin-=0.1;ymax+=0.1}}
const xr=xmax-xmin,yr=ymax-ymin;
xmin-=xr*0.05;xmax+=xr*0.05;ymin-=yr*0.05;ymax+=yr*0.05;
function sx(v){{return pad.l+(v-xmin)/(xmax-xmin)*cw}}
function sy(v){{return pad.t+(1-(v-ymin)/(ymax-ymin))*ch}}
svg.setAttribute("viewBox","0 0 "+W+" "+H);
// Grid lines
let g='<g stroke="#334155" stroke-width="0.5">';
for(let i=0;i<=5;i++){{
  const y=pad.t+ch*i/5;const v=(ymax-(ymax-ymin)*i/5).toFixed(3);
  g+='<line x1="'+pad.l+'" y1="'+y+'" x2="'+(W-pad.r)+'" y2="'+y+'"/>';
  g+='<text x="'+(pad.l-6)+'" y="'+(y+4)+'" fill="#94a3b8" font-size="11" text-anchor="end">'+v+'</text>';
}}
for(let i=0;i<=5;i++){{
  const x=pad.l+cw*i/5;const v=(xmin+(xmax-xmin)*i/5).toFixed(3);
  g+='<line x1="'+x+'" y1="'+pad.t+'" x2="'+x+'" y2="'+(H-pad.b)+'"/>';
  g+='<text x="'+x+'" y="'+(H-pad.b+16)+'" fill="#94a3b8" font-size="11" text-anchor="middle">'+v+'</text>';
}}
g+='</g>';
// Axes labels
g+='<text x="'+(W/2)+'" y="'+(H-4)+'" fill="#94a3b8" font-size="12" text-anchor="middle">Time (s)</text>';
g+='<text x="14" y="'+(H/2)+'" fill="#94a3b8" font-size="12" text-anchor="middle" transform="rotate(-90,14,'+(H/2)+')">Energy (J)</text>';
// Polyline
const lp=pts.map(p=>sx(p.time_s)+","+sy(p.joules)).join(" ");
g+='<polyline points="'+lp+'" fill="none" stroke="#818cf8" stroke-width="2"/>';
// Markers
pts.forEach((p,i)=>{{
  const cx=sx(p.time_s),cy=sy(p.joules);
  const cls=p.type.includes("enter")?"enter":"exit";
  g+='<circle cx="'+cx+'" cy="'+cy+'" r="5" class="'+cls+'" data-i="'+i+'" style="cursor:pointer"/>';
}});
svg.innerHTML=g;
// Tooltip
svg.addEventListener("mousemove",e=>{{
  const t=e.target;
  if(t.tagName==="circle"){{
    const p=pts[+t.dataset.i];
    tip.innerHTML='<b>'+p.func+'</b> ('+p.type+')<br>Time: '+p.time_s.toFixed(6)+'s<br>Energy: '+p.joules.toFixed(6)+' J<br>Power: '+p.watts.toFixed(3)+' W<br>Delta: '+p.delta_j.toFixed(6)+' J';
    tip.style.display="block";tip.style.left=(e.pageX+12)+"px";tip.style.top=(e.pageY-10)+"px";
  }}else{{tip.style.display="none"}}
}});
// Click to highlight function pair
svg.addEventListener("click",e=>{{
  const t=e.target;
  if(t.tagName!=="circle")return;
  const p=pts[+t.dataset.i];
  document.querySelectorAll("circle").forEach(c=>c.setAttribute("r","5"));
  // Highlight all circles for same function
  pts.forEach((q,j)=>{{if(q.func===p.func)document.querySelectorAll('circle[data-i="'+j+'"]').forEach(c=>c.setAttribute("r","8"))}});
}});
</script></body></html>"""
    path.write_text(html)
