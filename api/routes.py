import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from core.trace_store import db

router = APIRouter(prefix="/ui")

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #F8FAFC;
  color: #1E293B;
  min-height: 100vh;
}
.topbar {
  background: #FFFFFF;
  border-bottom: 1px solid #E2E8F0;
  padding: 0 32px;
  height: 56px;
  display: flex;
  align-items: center;
  gap: 16px;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.logo {
  font-size: 18px;
  font-weight: 700;
  color: #1E40AF;
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: 8px;
}
.logo-dot {
  width: 8px; height: 8px;
  background: #3B82F6;
  border-radius: 50%;
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.3); }
}
.topbar-sep { color: #CBD5E1; font-size: 18px; }
.topbar-sub { color: #64748B; font-size: 13px; }
.topbar-right { margin-left: auto; display: flex; align-items: center; gap: 12px; }
.live-badge {
  background: #DCFCE7;
  color: #15803D;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 99px;
  border: 1px solid #86EFAC;
}
.live-badge.offline {
  background: #FEF2F2;
  color: #DC2626;
  border-color: #FCA5A5;
}
.container { max-width: 1200px; margin: 0 auto; padding: 28px 24px; }
.page-title {
  font-size: 22px;
  font-weight: 600;
  color: #0F172A;
  margin-bottom: 4px;
}
.page-sub { font-size: 14px; color: #64748B; margin-bottom: 24px; }
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-bottom: 28px;
}
.stat {
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 12px;
  padding: 18px 20px;
  transition: box-shadow .15s;
}
.stat:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
.stat-val {
  font-size: 28px;
  font-weight: 700;
  color: #1E40AF;
  margin-bottom: 4px;
}
.stat-lbl { font-size: 13px; color: #64748B; }
.stat-icon {
  font-size: 18px;
  margin-bottom: 8px;
  opacity: .6;
}
.card {
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 12px;
  margin-bottom: 12px;
  transition: box-shadow .15s, border-color .15s;
  overflow: hidden;
}
.card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  border-color: #BFDBFE;
}
.card-header {
  padding: 16px 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid #F1F5F9;
}
.card-body { padding: 16px 20px; }
.run-id {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 14px;
  font-weight: 600;
  color: #1E40AF;
  text-decoration: none;
}
.run-id:hover { color: #1D4ED8; text-decoration: underline; }
.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 99px;
}
.badge-record { background: #DBEAFE; color: #1D4ED8; border: 1px solid #BFDBFE; }
.badge-replay { background: #DCFCE7; color: #15803D; border: 1px solid #86EFAC; }
.badge-whatif { background: #FEF3C7; color: #B45309; border: 1px solid #FCD34D; }
.badge-completed { background: #F0FDF4; color: #15803D; border: 1px solid #86EFAC; }
.badge-running { background: #FEF3C7; color: #B45309; border: 1px solid #FCD34D; }
.badge-failed { background: #FEF2F2; color: #DC2626; border: 1px solid #FCA5A5; }
.steps-pill {
  background: #F1F5F9;
  color: #475569;
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 99px;
  border: 1px solid #E2E8F0;
}
.meta { font-size: 12px; color: #94A3B8; }
.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #1E40AF;
  color: #FFFFFF;
  padding: 7px 16px;
  border-radius: 8px;
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
  transition: background .15s;
}
.btn:hover { background: #1D4ED8; }
.btn-sm { padding: 4px 12px; font-size: 12px; }
.btn-outline {
  background: transparent;
  color: #1E40AF;
  border: 1px solid #BFDBFE;
}
.btn-outline:hover { background: #EFF6FF; }
.btn-green { background: #15803D; }
.btn-green:hover { background: #166534; }
.empty {
  text-align: center;
  padding: 60px 20px;
  color: #94A3B8;
  font-size: 15px;
}
.empty-icon { font-size: 32px; margin-bottom: 12px; opacity: .4; }
.step-row {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  padding: 14px 20px;
  border-bottom: 1px solid #F1F5F9;
  transition: background .1s;
}
.step-row:last-child { border-bottom: none; }
.step-row:hover { background: #F8FAFC; }
.step-num {
  background: #F1F5F9;
  color: #64748B;
  font-family: monospace;
  font-size: 12px;
  padding: 3px 8px;
  border-radius: 6px;
  flex-shrink: 0;
  margin-top: 2px;
  border: 1px solid #E2E8F0;
}
.step-type-llm {
  background: #EEF2FF;
  color: #4338CA;
  border: 1px solid #C7D2FE;
}
.step-type-tool {
  background: #FEF3C7;
  color: #B45309;
  border: 1px solid #FCD34D;
}
.injected-badge {
  background: #FFF7ED;
  color: #C2410C;
  border: 1px solid #FED7AA;
  font-size: 10px;
  font-weight: 700;
  padding: 1px 7px;
  border-radius: 99px;
  margin-left: 6px;
  letter-spacing: .05em;
}
.step-preview {
  font-size: 13px;
  color: #475569;
  margin-top: 4px;
  font-style: italic;
}
details { margin-top: 10px; }
summary {
  cursor: pointer;
  font-size: 12px;
  color: #94A3B8;
  padding: 4px 0;
  user-select: none;
  display: flex;
  align-items: center;
  gap: 6px;
}
summary:hover { color: #64748B; }
.payload-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 8px;
}
.payload-label {
  font-size: 10px;
  font-weight: 600;
  color: #94A3B8;
  letter-spacing: .08em;
  text-transform: uppercase;
  margin-bottom: 4px;
}
pre {
  background: #F8FAFC;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 12px;
  color: #334155;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 280px;
  overflow-y: auto;
  font-family: 'SF Mono', 'Fira Code', monospace;
}
.diff-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #E2E8F0;
}
.diff-table th {
  background: #F8FAFC;
  padding: 10px 16px;
  font-size: 12px;
  font-weight: 600;
  color: #64748B;
  text-align: left;
  border-bottom: 1px solid #E2E8F0;
}
.diff-table td {
  padding: 12px 16px;
  font-size: 13px;
  border-bottom: 1px solid #F1F5F9;
  color: #334155;
}
.diff-table tr:last-child td { border-bottom: none; }
.diff-table tr.changed { background: #FFFBEB; }
.val-bad { color: #DC2626; font-weight: 600; }
.val-good { color: #15803D; font-weight: 600; }
.fixed-badge {
  background: #ECFDF5;
  color: #059669;
  border: 1px solid #6EE7B7;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 9px;
  border-radius: 99px;
}
.rca-card {
  background: #F0F9FF;
  border: 1px solid #BAE6FD;
  border-radius: 12px;
  padding: 20px;
  margin-top: 24px;
}
.rca-title {
  font-size: 15px;
  font-weight: 600;
  color: #0369A1;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.rca-model { font-size: 11px; color: #7DD3FC; font-weight: 400; }
.rca-root {
  font-size: 15px;
  font-weight: 500;
  color: #0F172A;
  margin: 14px 0;
  padding: 12px 16px;
  background: #FFFFFF;
  border-radius: 8px;
  border: 1px solid #E0F2FE;
}
.rca-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 12px;
}
.rca-field { }
.rca-field-label {
  font-size: 10px;
  font-weight: 700;
  color: #7DD3FC;
  text-transform: uppercase;
  letter-spacing: .08em;
  margin-bottom: 4px;
}
.rca-field-val {
  background: #FFFFFF;
  border: 1px solid #E0F2FE;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
  color: #0369A1;
  font-weight: 500;
}
.rca-evidence {
  background: #FFFFFF;
  border: 1px solid #E0F2FE;
  border-left: 3px solid #0EA5E9;
  border-radius: 0 8px 8px 0;
  padding: 10px 14px;
  font-size: 12px;
  color: #334155;
  font-family: monospace;
  white-space: pre-wrap;
  margin-bottom: 10px;
}
.rca-fix {
  background: #F0FDF4;
  border: 1px solid #86EFAC;
  border-left: 3px solid #22C55E;
  border-radius: 0 8px 8px 0;
  padding: 10px 14px;
  font-size: 13px;
  color: #15803D;
}
.rca-loading { color: #94A3B8; font-size: 13px; font-style: italic; }
.rca-error { color: #DC2626; font-size: 13px; }
.alert-info {
  background: #EFF6FF;
  border: 1px solid #BFDBFE;
  border-radius: 10px;
  padding: 14px 18px;
  font-size: 14px;
  color: #1D4ED8;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.breadcrumb {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #94A3B8;
  margin-bottom: 20px;
}
.breadcrumb a {
  color: #64748B;
  text-decoration: none;
}
.breadcrumb a:hover { color: #1E40AF; }
.breadcrumb-sep { color: #CBD5E1; }
.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #334155;
  margin: 24px 0 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.graph-container {
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 24px;
}
.graph-toolbar {
  padding: 12px 20px;
  border-bottom: 1px solid #F1F5F9;
  display: flex;
  align-items: center;
  gap: 10px;
  background: #F8FAFC;
}
.graph-svg { width: 100%; display: block; }
.live-container {
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 24px;
}
.live-toolbar {
  padding: 12px 20px;
  border-bottom: 1px solid #F1F5F9;
  display: flex;
  align-items: center;
  gap: 10px;
  background: #F8FAFC;
}
.live-steps { padding: 0; max-height: 400px; overflow-y: auto; }
.live-step {
  display: flex;
  gap: 12px;
  padding: 12px 20px;
  border-bottom: 1px solid #F1F5F9;
  align-items: center;
  animation: fadeIn .3s ease;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}
.live-step:last-child { border-bottom: none; }
.live-indicator {
  width: 8px; height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.ind-llm { background: #4338CA; }
.ind-tool { background: #B45309; }
"""

def _page(title: str, body: str, extra_js: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — JiraGuard</title>
<style>{CSS}</style>
</head>
<body>
<nav class="topbar">
  <a href="/ui/runs" class="logo">
    <div class="logo-dot"></div>
    JiraGuard
  </a>
  <span class="topbar-sep">|</span>
  <span class="topbar-sub">Flight Recorder for AI Agents</span>
  <div class="topbar-right">
    <span class="live-badge offline" id="ws-badge">Connecting...</span>
    <a href="/ui/live" class="btn btn-sm" style="background:#7C3AED;margin-right:4px">Live</a>
    <a href="/ui/runs" class="btn btn-sm btn-outline">All Runs</a>
  </div>
</nav>
<div class="container">
{body}
</div>
<script>
(function() {{
  const badge = document.getElementById('ws-badge');
  let ws;
  function connect() {{
    try {{
      ws = new WebSocket('ws://' + location.host + '/ws/live');
      ws.onopen = function() {{
        badge.textContent = 'Live';
        badge.classList.remove('offline');
      }};
      ws.onclose = function() {{
        badge.textContent = 'Offline';
        badge.classList.add('offline');
        setTimeout(connect, 3000);
      }};
      ws.onerror = function() {{
        badge.textContent = 'Offline';
        badge.classList.add('offline');
      }};
      {extra_js}
    }} catch(e) {{
      badge.textContent = 'Offline';
      badge.classList.add('offline');
    }}
  }}
  connect();
}})();
</script>
</body>
</html>"""


def _badge_mode(mode):
    cls = {"RECORD": "badge-record", "REPLAY": "badge-replay", "WHATIF": "badge-whatif"}.get(mode, "badge-record")
    icons = {"RECORD": "●", "REPLAY": "▶", "WHATIF": "◆"}
    return f'<span class="badge {cls}">{icons.get(mode, "")} {mode}</span>'

def _badge_status(status):
    cls = {"completed": "badge-completed", "running": "badge-running", "failed": "badge-failed"}.get(status, "")
    return f'<span class="badge {cls}">{status}</span>'

def _badge_type(t):
    cls = "step-type-llm" if t == "llm_call" else "step-type-tool"
    label = "LLM call" if t == "llm_call" else "Tool call"
    return f'<span class="badge {cls}">{label}</span>'


@router.get("/runs", response_class=HTMLResponse)
def ui_runs():
    runs  = db.list_runs(limit=30)
    stats = db.get_stats()

    stats_html = f"""
    <div class="stats-grid">
      <div class="stat">
        <div class="stat-icon">📊</div>
        <div class="stat-val">{stats['total_runs']}</div>
        <div class="stat-lbl">Total runs</div>
      </div>
      <div class="stat">
        <div class="stat-icon">⏺</div>
        <div class="stat-val">{stats['record_runs']}</div>
        <div class="stat-lbl">Record runs</div>
      </div>
      <div class="stat">
        <div class="stat-icon">◆</div>
        <div class="stat-val">{stats['whatif_runs']}</div>
        <div class="stat-lbl">What-If runs</div>
      </div>
      <div class="stat">
        <div class="stat-icon">⚡</div>
        <div class="stat-val">{stats['total_steps']}</div>
        <div class="stat-lbl">Total steps</div>
      </div>
    </div>"""

    if not runs:
        body = stats_html + """
        <div class="empty">
          <div class="empty-icon">📭</div>
          <div>No runs yet. Launch the proxy and run main.py to start.</div>
        </div>"""
    else:
        cards = ""
        for run in runs:
            diff_btn = ""
            if run.mode == "WHATIF" and run.parent_run_id:
                diff_btn = f'&nbsp;&nbsp;<a href="/ui/diff/{run.parent_run_id}/{run.id}" class="btn btn-sm btn-green">View diff</a>'
            parent_info = ""
            if run.parent_run_id:
                parent_info = f'&nbsp;&nbsp;<span class="meta">parent: <a href="/ui/runs/{run.parent_run_id}" style="color:#94A3B8;font-size:12px">{run.parent_run_id}</a></span>'

            cards += f"""
            <div class="card">
              <div class="card-header">
                <a href="/ui/runs/{run.id}" class="run-id">{run.id}</a>
                {_badge_mode(run.mode)}
                {_badge_status(run.status)}
                <span class="steps-pill">{run.total_steps} steps</span>
                {diff_btn}
                <span style="margin-left:auto" class="meta">{run.started_at[:16].replace('T',' ')}</span>
              </div>
              <div class="card-body" style="padding:10px 20px;display:flex;gap:12px;align-items:center">
                <span class="meta">v{run.agent_version}</span>
                {parent_info}
              </div>
            </div>"""

        body = f"""
        <div class="page-title">Runs</div>
        <div class="page-sub">All recorded agent executions</div>
        {stats_html}
        <div class="section-title">Recent runs</div>
        {cards}"""

    live_js = """
      ws.onmessage = function(e) {
        const d = JSON.parse(e.data);
        if (d.type === 'step' || d.type === 'mode_change') {
          setTimeout(() => location.reload(), 800);
        }
      };
    """
    return HTMLResponse(_page("Runs", body, live_js))


@router.get("/runs/{run_id}", response_class=HTMLResponse)
def ui_run_detail(run_id: str):
    run = db.get_run(run_id)
    if not run:
        body = f'<div class="alert-info">Run <code>{run_id}</code> not found.</div>'
        return HTMLResponse(_page("Error", body))

    steps = db.get_steps(run_id)

    # Graphe d'exécution SVG
    graph_html = _build_execution_graph(steps, run.mode)

    # Timeline steps
    if not steps:
        timeline = '<div class="empty"><div class="empty-icon">⏳</div><div>No steps yet. The run may still be executing.</div></div>'
    else:
        timeline = ""
        for step in steps:
            injected = f'<span class="injected-badge">INJECTED</span>' if step.injected else ""
            inp  = json.dumps(step.input_payload,  ensure_ascii=False, indent=2)
            out  = json.dumps(step.output_payload, ensure_ascii=False, indent=2)
            if step.latency_ms and step.latency_ms > 0:
                latency = f"{step.latency_ms}ms"
            elif step.step_type == "tool_call":
                latency = "mock API"
            else:
                latency = "cached"

            preview = ""
            if step.step_type == "llm_call":
                c = step.output_payload.get("content", "")
                if c:
                    preview = f'<div class="step-preview">{c[:120]}{"..." if len(c)>120 else ""}</div>'
            elif step.step_type == "tool_call":
                team = step.output_payload.get("team","")
                prio = step.output_payload.get("priority","")
                tid  = step.input_payload.get("ticket_id","")
                if team:
                    color = "#15803D" if step.output_payload.get("success") else "#DC2626"
                    preview = f'<div class="step-preview" style="color:{color}">{tid} → {team} / {prio}</div>'

            timeline += f"""
            <div class="step-row">
              <div class="step-num">#{step.step_number}</div>
              <div style="flex:1">
                <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
                  {_badge_type(step.step_type)}
                  {injected}
                  <span style="font-size:12px;color:#94A3B8">{latency}</span>
                  <span style="font-size:12px;color:#CBD5E1">{step.timestamp[:19].replace('T',' ')}</span>
                </div>
                {preview}
                <details>
                  <summary>▸ Show full input / output</summary>
                  <div class="payload-grid">
                    <div>
                      <div class="payload-label">Input</div>
                      <pre>{inp}</pre>
                    </div>
                    <div>
                      <div class="payload-label">Output</div>
                      <pre>{out}</pre>
                    </div>
                  </div>
                </details>
              </div>
            </div>"""

    alert = ""
    if run.mode == "RECORD" and steps:
        alert = f"""
        <div class="alert-info">
          ✦ What-If available — inject a correction on this run to test how the trajectory
          would have changed. Use run_id <code style="background:#DBEAFE;padding:1px 5px;border-radius:4px">{run_id}</code>
          with the proxy in WHATIF mode.
        </div>"""

    body = f"""
    <div class="breadcrumb">
      <a href="/ui/runs">All runs</a>
      <span class="breadcrumb-sep">›</span>
      <span style="font-family:monospace;color:#1E40AF">{run_id}</span>
    </div>
    <div style="display:flex;gap:12px;align-items:center;margin-bottom:6px">
      <div class="page-title">Run {run_id}</div>
      {_badge_mode(run.mode)}
      {_badge_status(run.status)}
    </div>
    <div class="page-sub">
      {run.started_at[:19].replace('T',' ')} &nbsp;·&nbsp;
      v{run.agent_version} &nbsp;·&nbsp;
      {run.total_steps} steps
    </div>
    {alert}
    <div class="section-title">⬡ Execution graph</div>
    {graph_html}
    <div class="section-title">⚡ Step timeline</div>
    <div class="card" style="padding:0">
      {timeline}
    </div>"""

    live_js = f"""
      ws.onmessage = function(e) {{
        const d = JSON.parse(e.data);
        if (d.type === 'step' && d.run_id === '{run_id}') {{
          setTimeout(() => location.reload(), 400);
        }}
      }};
    """
    return HTMLResponse(_page(f"Run {run_id}", body, live_js))


def _build_execution_graph(steps, mode) -> str:
    if not steps:
        return '<div style="padding:20px;text-align:center;color:#94A3B8;font-size:13px">No steps to display.</div>'

    n = len(steps)
    node_w, node_h = 160, 48
    gap_x, gap_y = 40, 60
    cols = min(n, 4)

    total_w = cols * node_w + (cols - 1) * gap_x + 60
    rows = (n + cols - 1) // cols
    total_h = rows * node_h + (rows - 1) * gap_y + 60

    nodes_svg = ""
    edges_svg = ""
    node_centers = []

    for i, step in enumerate(steps):
        col = i % cols
        row = i // cols
        x = 30 + col * (node_w + gap_x)
        y = 30 + row * (node_h + gap_y)
        cx, cy = x + node_w // 2, y + node_h // 2
        node_centers.append((cx, cy))

        is_llm  = step.step_type == "llm_call"
        fill    = "#EEF2FF" if is_llm else "#FEF3C7"
        stroke  = "#6366F1" if is_llm else "#F59E0B"
        tcol    = "#4338CA" if is_llm else "#B45309"
        icon    = "🤖" if is_llm else "🔧"
        label   = "LLM call" if is_llm else "Tool call"

        inj_mark = ""
        if step.injected:
            inj_mark = f'<rect x="{x+node_w-22}" y="{y-8}" width="30" height="16" rx="4" fill="#F97316"/><text x="{x+node_w-7}" y="{y+1}" text-anchor="middle" font-size="9" font-weight="700" fill="white">INJ</text>'

        preview = ""
        if is_llm:
            c = step.output_payload.get("content","")[:30]
            preview = c
        else:
            team = step.output_payload.get("team","")
            prio = step.output_payload.get("priority","")
            preview = f"{team}/{prio}" if team else ""

        nodes_svg += f"""
        <g style="cursor:pointer" onclick="window.location.href='/ui/runs/{steps[0].run_id}#step{step.step_number}'">
          <rect x="{x}" y="{y}" width="{node_w}" height="{node_h}" rx="8"
                fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>
          <text x="{x+14}" y="{y+17}" font-size="10" fill="{tcol}" font-weight="600" font-family="sans-serif">#{step.step_number} {label}</text>
          <text x="{x+14}" y="{y+34}" font-size="10" fill="#64748B" font-family="sans-serif">{preview[:24]}{"..." if len(preview)>24 else ""}</text>
          {inj_mark}
        </g>"""

        if i > 0:
            px, py = node_centers[i-1]
            prev_col = (i-1) % cols
            prev_row = (i-1) // cols
            cur_col  = i % cols
            cur_row  = i // cols

            if cur_row == prev_row:
                x1 = 30 + prev_col*(node_w+gap_x) + node_w
                y1 = 30 + prev_row*(node_h+gap_y) + node_h//2
                x2 = 30 + cur_col*(node_w+gap_x)
                y2 = y1
            else:
                x1 = 30 + prev_col*(node_w+gap_x) + node_w//2
                y1 = 30 + prev_row*(node_h+gap_y) + node_h
                x2 = 30 + cur_col*(node_w+gap_x) + node_w//2
                y2 = 30 + cur_row*(node_h+gap_y)

            edge_col = "#6366F1" if is_llm else "#F59E0B"
            edges_svg += f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{edge_col}" stroke-width="1.5" stroke-dasharray="4 3" opacity="0.5" marker-end="url(#arr)"/>'

    legend = f"""
    <rect x="10" y="{total_h-30}" width="12" height="12" rx="3" fill="#EEF2FF" stroke="#6366F1" stroke-width="1.5"/>
    <text x="27" y="{total_h-22}" font-size="11" fill="#64748B" font-family="sans-serif">LLM call</text>
    <rect x="90" y="{total_h-30}" width="12" height="12" rx="3" fill="#FEF3C7" stroke="#F59E0B" stroke-width="1.5"/>
    <text x="107" y="{total_h-22}" font-size="11" fill="#64748B" font-family="sans-serif">Tool call</text>
    <rect x="170" y="{total_h-30}" width="12" height="12" rx="3" fill="#F97316"/>
    <text x="187" y="{total_h-22}" font-size="11" fill="#64748B" font-family="sans-serif">Injected</text>"""

    svg = f"""
    <div class="graph-container">
      <div class="graph-toolbar">
        <span style="font-size:13px;font-weight:600;color:#334155">Execution graph</span>
        <span style="font-size:12px;color:#94A3B8">{n} nodes · click a node to inspect</span>
      </div>
      <div style="overflow-x:auto">
        <svg width="{max(total_w, 600)}" height="{total_h+40}"
             viewBox="0 0 {max(total_w, 600)} {total_h+40}"
             style="display:block;padding:10px">
          <defs>
            <marker id="arr" viewBox="0 0 10 10" refX="8" refY="5"
                    markerWidth="5" markerHeight="5" orient="auto-start-reverse">
              <path d="M2 1L8 5L2 9" fill="none" stroke="#94A3B8"
                    stroke-width="1.5" stroke-linecap="round"/>
            </marker>
          </defs>
          {edges_svg}
          {nodes_svg}
          {legend}
        </svg>
      </div>
    </div>"""
    return svg


@router.get("/live", response_class=HTMLResponse)
def ui_live():
    """Page temps réel — voit les steps arriver en direct pendant un run."""
    body = """
    <div class="page-title">Live monitor</div>
    <div class="page-sub">Steps appear in real time as the agent runs</div>

    <div class="stats-grid" style="grid-template-columns:repeat(3,1fr)">
      <div class="stat">
        <div class="stat-lbl">Current mode</div>
        <div class="stat-val" id="live-mode" style="font-size:20px">—</div>
      </div>
      <div class="stat">
        <div class="stat-lbl">Run ID</div>
        <div class="stat-val" id="live-runid" style="font-size:14px;font-family:monospace">—</div>
      </div>
      <div class="stat">
        <div class="stat-lbl">Steps captured</div>
        <div class="stat-val" id="live-count">0</div>
      </div>
    </div>

    <div class="live-container">
      <div class="live-toolbar">
        <span style="font-size:13px;font-weight:600;color:#334155">Live steps</span>
        <span class="badge badge-running" id="live-status">Waiting for agent...</span>
        <button onclick="clearSteps()"
                style="margin-left:auto;padding:4px 12px;border-radius:6px;
                       border:1px solid #E2E8F0;background:white;font-size:12px;cursor:pointer">
          Clear
        </button>
      </div>
      <div class="live-steps" id="live-steps">
        <div style="padding:40px;text-align:center;color:#94A3B8;font-size:13px">
          Waiting for the agent to start...
          <br><br>
          <code style="font-size:12px;background:#F1F5F9;padding:4px 8px;border-radius:4px">
            python main.py
          </code>
        </div>
      </div>
    </div>"""

    live_js = """
      let count = 0;
      ws.onmessage = function(e) {
        const d = JSON.parse(e.data);
        if (d.type === 'mode_change') {
          document.getElementById('live-mode').textContent = d.mode;
          document.getElementById('live-runid').textContent = d.run_id || '—';
          document.getElementById('live-status').textContent = 'Active — ' + d.mode;
          document.getElementById('live-status').className = 'badge badge-running';
        }
        if (d.type === 'step') {
          count++;
          document.getElementById('live-count').textContent = count;
          document.getElementById('live-mode').textContent = d.mode;
          document.getElementById('live-runid').textContent = d.run_id || '—';
          const container = document.getElementById('live-steps');
          if (container.querySelector('div[style*="text-align:center"]')) {
            container.innerHTML = '';
          }
          const isLLM = d.step.step_type === 'llm_call';
          const div = document.createElement('div');
          div.className = 'live-step';
          div.innerHTML = `
            <div class="live-indicator ${isLLM ? 'ind-llm' : 'ind-tool'}"></div>
            <div style="flex:1">
              <div style="display:flex;align-items:center;gap:8px">
                <span class="badge ${isLLM ? 'step-type-llm' : 'step-type-tool'}">
                  ${isLLM ? 'LLM call' : 'Tool call'}
                </span>
                <span style="font-family:monospace;font-size:12px;color:#94A3B8">#${d.step.step_number}</span>
                ${d.step.injected ? '<span class="injected-badge">INJECTED</span>' : ''}
                <span style="font-size:12px;color:#CBD5E1">${d.step.latency_ms ? d.step.latency_ms+'ms' : 'cache'}</span>
              </div>
              <div style="font-size:13px;color:#475569;margin-top:4px;font-style:italic">
                ${d.step.output_preview || ''}
              </div>
            </div>
            <span style="font-size:11px;color:#CBD5E1">${d.step.timestamp.substring(11,19)}</span>`;
          container.insertBefore(div, container.firstChild);
        }
      };
      window.clearSteps = function() {
        document.getElementById('live-steps').innerHTML = '';
        count = 0;
        document.getElementById('live-count').textContent = '0';
      };
    """
    return HTMLResponse(_page("Live", body, live_js))


@router.get("/diff/{original_id}/{whatif_id}", response_class=HTMLResponse)
def ui_diff(original_id: str, whatif_id: str):
    diff = db.compute_diff(original_id, whatif_id)
    orig_steps = db.get_steps(original_id)
    wi_steps   = db.get_steps(whatif_id)

    orig_tool = [s for s in orig_steps if s.step_type == "tool_call"]
    wi_tool   = [s for s in wi_steps   if s.step_type == "tool_call"]

    changed = diff.get("decision_changed", False)
    n_fixed = diff.get("tickets_corrected", 0)

    rows = ""
    for i, (os_, ws) in enumerate(zip(orig_tool, wi_tool)):
        op = os_.output_payload
        wp = ws.output_payload
        ot = op.get("team","?");   op2 = op.get("priority","?")
        wt = wp.get("team","?");   wp2 = wp.get("priority","?")
        tid = op.get("ticket_id", f"ticket-{i+1}")
        ch  = (ot != wt) or (op2 != wp2)

        team_html = f'<span class="val-bad">{ot}</span> → <span class="val-good">{wt}</span>' if ot != wt else f'<span style="color:#64748B">{ot}</span>'
        prio_html = f'<span class="val-bad">{op2}</span> → <span class="val-good">{wp2}</span>' if op2 != wp2 else f'<span style="color:#64748B">{op2}</span>'
        badge_html = '<span class="fixed-badge">✓ FIXED</span>' if ch else '<span style="color:#94A3B8;font-size:12px">unchanged</span>'

        rows += f"""
        <tr class="{'changed' if ch else ''}">
          <td><code style="font-size:12px;background:#F1F5F9;padding:2px 6px;border-radius:4px">{tid}</code></td>
          <td>{team_html}</td>
          <td>{prio_html}</td>
          <td>{badge_html}</td>
        </tr>"""

    banner_bg = "#ECFDF5" if changed else "#F8FAFC"
    banner_bo = "#86EFAC" if changed else "#E2E8F0"
    banner_co = "#15803D" if changed else "#64748B"
    banner_tx = f"✓ Trajectory diverged — {n_fixed} ticket(s) corrected by What-If injection" if changed else "No decisions changed between original and What-If run."

    body = f"""
    <div class="breadcrumb">
      <a href="/ui/runs">All runs</a>
      <span class="breadcrumb-sep">›</span>
      <a href="/ui/runs/{original_id}">{original_id}</a>
      <span class="breadcrumb-sep">›</span>
      <span>Diff</span>
    </div>
    <div class="page-title">Diff — Original vs What-If</div>
    <div class="page-sub">Comparing buggy prompt trajectory vs corrected prompt trajectory</div>

    <div style="background:{banner_bg};border:1px solid {banner_bo};border-radius:10px;
                padding:14px 18px;color:{banner_co};font-size:14px;font-weight:500;
                margin-bottom:24px;display:flex;align-items:center;gap:10px">
      {banner_tx}
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px">
      <div class="card" style="border-left:3px solid #DC2626">
        <div class="card-header">
          <span style="font-size:13px;font-weight:600;color:#DC2626">Original run</span>
          <code style="font-size:12px;color:#94A3B8">{original_id}</code>
        </div>
        <div class="card-body">
          <div style="font-size:12px;color:#64748B">Buggy system prompt · /api/* → frontend</div>
        </div>
      </div>
      <div class="card" style="border-left:3px solid #15803D">
        <div class="card-header">
          <span style="font-size:13px;font-weight:600;color:#15803D">What-If run</span>
          <code style="font-size:12px;color:#94A3B8">{whatif_id}</code>
        </div>
        <div class="card-body">
          <div style="font-size:12px;color:#64748B">Fixed prompt injected at step {db.get_run(whatif_id).injection_step or '?'}</div>
        </div>
      </div>
    </div>

    <div class="section-title">Decisions per ticket</div>
    <table class="diff-table">
      <thead>
        <tr>
          <th>Ticket</th>
          <th>Team</th>
          <th>Priority</th>
          <th>Result</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>

    <div class="rca-card" id="rca-section">
      <div class="rca-title">
        Root Cause Analysis
        <span class="rca-model">powered by Groq llama-3.1-8b-instant</span>
      </div>
      <div id="rca-body"><div class="rca-loading">Analyzing root cause...</div></div>
    </div>

    <div style="margin-top:20px;display:flex;gap:10px">
      <a href="/ui/runs/{original_id}" class="btn btn-outline">View original run</a>
      <a href="/ui/runs/{whatif_id}" class="btn btn-green">View What-If run</a>
    </div>

    <script>
    fetch('/analyze/diff/{original_id}/{whatif_id}')
      .then(r => r.json())
      .then(data => {{
        const body = document.getElementById('rca-body');
        if (!data.analyses || data.analyses.length === 0) {{
          body.innerHTML = '<div class="rca-error">' + (data.message || 'No analysis available.') + '</div>';
          return;
        }}
        const a = data.analyses[0];
        body.innerHTML = `
          <div class="rca-root">${{a.root_cause}}</div>
          <div class="rca-grid">
            <div class="rca-field">
              <div class="rca-field-label">Failure type</div>
              <div class="rca-field-val">${{a.failure_type}}</div>
            </div>
            <div class="rca-field">
              <div class="rca-field-label">Confidence</div>
              <div class="rca-field-val">${{Math.round(a.confidence * 100)}}%</div>
            </div>
          </div>
          <div class="rca-field-label" style="color:#7DD3FC;margin-bottom:4px">Evidence</div>
          <div class="rca-evidence">${{a.evidence}}</div>
          <div class="rca-field-label" style="color:#7DD3FC;margin-bottom:4px">Fix recommendation</div>
          <div class="rca-fix">${{a.fix_recommendation}}</div>`;
      }})
      .catch(e => {{
        document.getElementById('rca-body').innerHTML =
          '<div class="rca-error">RCA unavailable (no API key?) — run with GROQ_API_KEY set.</div>';
      }});
    </script>"""

    return HTMLResponse(_page("Diff", body))
