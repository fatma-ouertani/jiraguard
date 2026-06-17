"""
JiraGuard — Routes UI
Interface web pour visualiser les runs et faire le What-If.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from core.trace_store import db
import json

router = APIRouter(prefix="/ui")


def _badge_mode(mode: str) -> str:
    colors = {"RECORD": "#3B82F6", "REPLAY": "#10B981", "WHATIF": "#F59E0B"}
    c = colors.get(mode, "#6B7280")
    return f'<span style="background:{c};color:#fff;padding:2px 10px;border-radius:99px;font-size:12px;font-weight:600">{mode}</span>'

def _badge_status(status: str) -> str:
    colors = {"completed": "#10B981", "running": "#F59E0B", "failed": "#EF4444"}
    c = colors.get(status, "#6B7280")
    return f'<span style="background:{c};color:#fff;padding:2px 10px;border-radius:99px;font-size:12px">{status}</span>'

def _badge_type(step_type: str) -> str:
    colors = {"llm_call": "#6366F1", "tool_call": "#F59E0B", "memory_snapshot": "#6B7280"}
    c = colors.get(step_type, "#6B7280")
    return f'<span style="background:{c};color:#fff;padding:2px 8px;border-radius:6px;font-size:11px">{step_type}</span>'

def _html_page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — JiraGuard</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0F172A; color: #E2E8F0; min-height: 100vh; }}
  .topbar {{ background: #1E3A5F; padding: 14px 32px; display: flex;
             align-items: center; gap: 16px; border-bottom: 1px solid #2D4A6F; }}
  .topbar a {{ color: #38BDF8; text-decoration: none; font-size: 20px; font-weight: 700; }}
  .topbar a:hover {{ color: #7DD3FC; }}
  .topbar .sep {{ color: #475569; }}
  .topbar .sub {{ color: #94A3B8; font-size: 14px; }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 32px 24px; }}
  h1 {{ font-size: 24px; font-weight: 600; color: #F1F5F9; margin-bottom: 8px; }}
  .subtitle {{ color: #94A3B8; font-size: 14px; margin-bottom: 28px; }}
  .card {{ background: #1E293B; border: 1px solid #334155;
           border-radius: 12px; padding: 20px; margin-bottom: 16px; }}
  .card:hover {{ border-color: #3B82F6; transition: border-color .2s; }}
  .run-header {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
  .run-id {{ font-family: monospace; font-size: 15px; font-weight: 600;
             color: #38BDF8; text-decoration: none; }}
  .run-id:hover {{ color: #7DD3FC; text-decoration: underline; }}
  .meta {{ color: #64748B; font-size: 13px; margin-top: 8px; }}
  .steps-count {{ background: #0F172A; border: 1px solid #334155;
                  border-radius: 8px; padding: 4px 12px; font-size: 13px; color: #94A3B8; }}
  .step-row {{ display: flex; gap: 14px; align-items: flex-start;
               padding: 14px 0; border-bottom: 1px solid #1E293B; }}
  .step-row:last-child {{ border-bottom: none; }}
  .step-num {{ background: #0F172A; border: 1px solid #334155; border-radius: 8px;
               padding: 4px 10px; font-size: 13px; color: #64748B;
               font-family: monospace; flex-shrink: 0; }}
  .step-content {{ flex: 1; }}
  .step-title {{ font-size: 14px; font-weight: 500; color: #E2E8F0; margin-bottom: 6px; }}
  .injected-label {{ background: #F59E0B; color: #000; padding: 1px 8px;
                     border-radius: 6px; font-size: 11px; font-weight: 600;
                     margin-left: 8px; }}
  details {{ margin-top: 8px; }}
  summary {{ cursor: pointer; font-size: 12px; color: #64748B;
             padding: 4px 0; user-select: none; }}
  summary:hover {{ color: #94A3B8; }}
  pre {{ background: #0F172A; border: 1px solid #1E293B; border-radius: 8px;
         padding: 12px; font-size: 12px; overflow-x: auto; color: #94A3B8;
         white-space: pre-wrap; word-break: break-word; margin-top: 6px;
         max-height: 300px; overflow-y: auto; }}
  .diff-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
                margin-top: 16px; }}
  .diff-box {{ background: #0F172A; border-radius: 10px; padding: 16px; }}
  .diff-box h3 {{ font-size: 14px; margin-bottom: 10px; }}
  .diff-orig {{ border: 1px solid #EF4444; }}
  .diff-orig h3 {{ color: #EF4444; }}
  .diff-fixed {{ border: 1px solid #10B981; }}
  .diff-fixed h3 {{ color: #10B981; }}
  .diff-field {{ display: flex; justify-content: space-between; padding: 5px 0;
                 border-bottom: 1px solid #1E293B; font-size: 13px; }}
  .diff-field:last-child {{ border-bottom: none; }}
  .label {{ color: #64748B; }}
  .val-bad {{ color: #EF4444; font-weight: 600; }}
  .val-good {{ color: #10B981; font-weight: 600; }}
  .alert {{ background: #1E3A5F; border: 1px solid #2563EB; border-radius: 10px;
            padding: 16px; margin-bottom: 20px; font-size: 14px; color: #93C5FD; }}
  .alert strong {{ color: #38BDF8; }}
  .btn {{ display: inline-block; background: #2563EB; color: #fff;
          padding: 8px 18px; border-radius: 8px; text-decoration: none;
          font-size: 13px; font-weight: 500; }}
  .btn:hover {{ background: #1D4ED8; }}
  .btn-sm {{ padding: 4px 12px; font-size: 12px; }}
  .empty {{ color: #475569; font-size: 15px; text-align: center; padding: 40px; }}
  .stats-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;
                margin-bottom: 28px; }}
  .stat-card {{ background: #1E293B; border: 1px solid #334155; border-radius: 10px;
                padding: 16px; text-align: center; }}
  .stat-val {{ font-size: 28px; font-weight: 700; color: #38BDF8; }}
  .stat-lbl {{ font-size: 12px; color: #64748B; margin-top: 4px; }}
</style>
</head>
<body>
<div class="topbar">
  <a href="/ui/runs">JiraGuard</a>
  <span class="sep">|</span>
  <span class="sub">Flight Recorder for AI Agents</span>
</div>
<div class="container">
{body}
</div>
</body>
</html>"""


@router.get("/runs", response_class=HTMLResponse)
def ui_runs():
    runs  = db.list_runs(limit=30)
    stats = db.get_stats()

    stats_html = f"""
    <div class="stats-row">
      <div class="stat-card"><div class="stat-val">{stats['total_runs']}</div><div class="stat-lbl">Total runs</div></div>
      <div class="stat-card"><div class="stat-val">{stats['record_runs']}</div><div class="stat-lbl">Record runs</div></div>
      <div class="stat-card"><div class="stat-val">{stats['whatif_runs']}</div><div class="stat-lbl">What-If runs</div></div>
      <div class="stat-card"><div class="stat-val">{stats['total_steps']}</div><div class="stat-lbl">Total steps</div></div>
    </div>"""

    if not runs:
        body = stats_html + '<div class="empty">Aucun run enregistre. Lance main.py pour commencer.</div>'
    else:
        cards = ""
        for run in runs:
            parent_info = ""
            if run.parent_run_id:
                parent_info = f' &nbsp;|&nbsp; parent: <a href="/ui/runs/{run.parent_run_id}" style="color:#64748B;font-size:12px">{run.parent_run_id}</a>'
            diff_btn = ""
            if run.mode == "WHATIF" and run.parent_run_id:
                diff_btn = f'&nbsp;<a href="/ui/diff/{run.parent_run_id}/{run.id}" class="btn btn-sm">Voir diff</a>'
            cards += f"""
            <div class="card">
              <div class="run-header">
                <a href="/ui/runs/{run.id}" class="run-id">{run.id}</a>
                {_badge_mode(run.mode)}
                {_badge_status(run.status)}
                <span class="steps-count">{run.total_steps} steps</span>
                {diff_btn}
              </div>
              <div class="meta">
                {run.started_at[:19].replace('T',' ')} &nbsp;|&nbsp;
                v{run.agent_version}
                {parent_info}
              </div>
            </div>"""
        body = f"<h1>Runs enregistres</h1><p class='subtitle'>Tous les runs de l'agent JiraGuard</p>" + stats_html + cards

    return HTMLResponse(_html_page("Runs", body))


@router.get("/runs/{run_id}", response_class=HTMLResponse)
def ui_run_detail(run_id: str):
    run = db.get_run(run_id)
    if not run:
        body = f'<div class="alert">Run <code>{run_id}</code> introuvable.</div><a href="/ui/runs" class="btn">Retour</a>'
        return HTMLResponse(_html_page("Erreur", body))

    steps = db.get_steps(run_id)

    # Alerte What-If dispo
    whatif_alert = ""
    if run.mode == "RECORD" and steps:
        whatif_alert = f"""
        <div class="alert">
          <strong>Mode What-If disponible</strong> — Tu peux injecter une correction
          sur ce run et observer comment la trajectoire aurait change.
          Lance le proxy en mode WHATIF avec run_id=<code>{run_id}</code>
        </div>"""

    # Timeline
    if not steps:
        timeline = '<div class="empty">Aucun step enregistre pour ce run.</div>'
    else:
        timeline = ""
        for step in steps:
            injected_label = '<span class="injected-label">INJECTED</span>' if step.injected else ""
            inp  = json.dumps(step.input_payload,  ensure_ascii=False, indent=2)
            out  = json.dumps(step.output_payload, ensure_ascii=False, indent=2)
            latency = f"{step.latency_ms}ms" if step.latency_ms else "cache"

            # Extrait lisible de l'output
            preview = ""
            if step.step_type == "llm_call":
                content = step.output_payload.get("content", "")
                preview = content[:120] + "..." if len(content) > 120 else content
            elif step.step_type == "tool_call":
                team = step.output_payload.get("team") or step.output_payload.get("updated_fields", {}).get("team", "")
                prio = step.output_payload.get("priority") or step.output_payload.get("updated_fields", {}).get("priority", "")
                if team:
                    preview = f"team={team}  priority={prio}"

            timeline += f"""
            <div class="step-row">
              <div class="step-num">#{step.step_number}</div>
              <div class="step-content">
                <div class="step-title">
                  {_badge_type(step.step_type)} {injected_label}
                  &nbsp;<span style="color:#94A3B8;font-size:12px">{latency}</span>
                </div>
                <div style="font-size:13px;color:#64748B;margin:4px 0">{step.timestamp[:19].replace('T',' ')}</div>
                {"<div style='font-size:13px;color:#94A3B8;margin-top:4px'>"+preview+"</div>" if preview else ""}
                <details>
                  <summary>Voir input / output complets</summary>
                  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:6px">
                    <div>
                      <div style="font-size:11px;color:#475569;margin-bottom:3px">INPUT</div>
                      <pre>{inp}</pre>
                    </div>
                    <div>
                      <div style="font-size:11px;color:#475569;margin-bottom:3px">OUTPUT</div>
                      <pre>{out}</pre>
                    </div>
                  </div>
                </details>
              </div>
            </div>"""

    body = f"""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px">
      <a href="/ui/runs" style="color:#64748B;text-decoration:none;font-size:13px">Tous les runs</a>
      <span style="color:#334155">/</span>
      <span style="font-family:monospace;color:#38BDF8">{run_id}</span>
    </div>
    <div style="display:flex;gap:10px;align-items:center;margin-bottom:8px">
      <h1>Run {run_id}</h1>
      {_badge_mode(run.mode)}
      {_badge_status(run.status)}
    </div>
    <p class="subtitle">
      {run.started_at[:19].replace('T',' ')} &nbsp;|&nbsp;
      v{run.agent_version} &nbsp;|&nbsp;
      {run.total_steps} steps
    </p>
    {whatif_alert}
    <div class="card">
      {timeline}
    </div>"""

    return HTMLResponse(_html_page(f"Run {run_id}", body))


@router.get("/diff/{original_id}/{whatif_id}", response_class=HTMLResponse)
def ui_diff(original_id: str, whatif_id: str):
    diff = db.compute_diff(original_id, whatif_id)

    orig_run   = db.get_run(original_id)
    whatif_run = db.get_run(whatif_id)
    orig_steps = db.get_steps(original_id)
    wi_steps   = db.get_steps(whatif_id)

    def _decision_from_steps(steps):
        for s in reversed(steps):
            if s.step_type == "tool_call":
                p = s.output_payload
                team = p.get("team") or p.get("updated_fields", {}).get("team", "?")
                prio = p.get("priority") or p.get("updated_fields", {}).get("priority", "?")
                return team, prio
        return "?", "?"

    orig_team, orig_prio = _decision_from_steps(orig_steps)
    wi_team,   wi_prio   = _decision_from_steps(wi_steps)

    changed = diff.get("decision_changed", False)
    div_step = diff.get("divergence_at_step", "N/A")

    status_html = f"""
    <div class="alert" style="{'border-color:#10B981;background:#0D2E20' if changed else ''}">
      <strong>{'Trajectoire divergente' if changed else 'Aucune divergence'}</strong>
      &nbsp;—&nbsp;
      {'La correction What-If a change la decision de l\'agent.' if changed else 'Les deux runs ont produit la meme decision.'}
      &nbsp;|&nbsp; Divergence au step <strong>{div_step}</strong>
    </div>"""

    # Récupère toutes les décisions ticket par ticket
    orig_tool_steps = [s for s in orig_steps if s.step_type == "tool_call"]
    wi_tool_steps   = [s for s in wi_steps   if s.step_type == "tool_call"]

    tickets_rows = ""
    for i, (os_, ws) in enumerate(zip(orig_tool_steps, wi_tool_steps)):
        op = os_.output_payload
        wp = ws.output_payload
        orig_team = op.get("team", "?")
        orig_prio = op.get("priority", "?")
        wi_team   = wp.get("team", "?")
        wi_prio   = wp.get("priority", "?")
        tid       = op.get("ticket_id", f"ticket-{i+1}")
        changed   = (orig_team != wi_team) or (orig_prio != wi_prio)
        row_bg    = "#1A0A00" if changed else "#0F172A"
        row_border= "#F59E0B" if changed else "#1E293B"

        team_html = (
            f'<span class="val-bad">{orig_team}</span> &rarr; '
            f'<span class="val-good">{wi_team}</span>'
        ) if orig_team != wi_team else f'<span style="color:#94A3B8">{orig_team}</span>'

        prio_html = (
            f'<span class="val-bad">{orig_prio}</span> &rarr; '
            f'<span class="val-good">{wi_prio}</span>'
        ) if orig_prio != wi_prio else f'<span style="color:#94A3B8">{orig_prio}</span>'

        changed_badge = (
            '<span style="background:#F59E0B;color:#000;padding:1px 8px;'
            'border-radius:6px;font-size:11px;font-weight:600">FIXED</span>'
        ) if changed else (
            '<span style="color:#475569;font-size:12px">unchanged</span>'
        )

        tickets_rows += f"""
        <div style="background:{row_bg};border:1px solid {row_border};
                    border-radius:8px;padding:12px 16px;margin-bottom:8px;
                    display:grid;grid-template-columns:100px 1fr 1fr 80px;
                    align-items:center;gap:12px">
          <span style="font-family:monospace;color:#64748B;font-size:13px">{tid}</span>
          <div style="font-size:13px">Team: {team_html}</div>
          <div style="font-size:13px">Priority: {prio_html}</div>
          {changed_badge}
        </div>"""

    tickets_corrected = diff.get("tickets_corrected", 0)
    total_tickets     = len(orig_tool_steps)

    diff_grid = f"""
    <div style="background:#0F172A;border:1px solid #334155;border-radius:10px;
                padding:16px;margin-top:16px">
      <div style="display:flex;justify-content:space-between;
                  align-items:center;margin-bottom:14px">
        <h2 style="font-size:16px;color:#F1F5F9">
          Decisions par ticket
        </h2>
        <span style="color:#F59E0B;font-size:14px;font-weight:600">
          {tickets_corrected}/{total_tickets} tickets corriges
        </span>
      </div>
      {tickets_rows}
    </div>"""

    # Comparaison step par step
    step_compare = ""
    for i, (os_, ws) in enumerate(zip(orig_steps, wi_steps)):
        same = os_.output_payload == ws.output_payload
        bg   = "#0F172A" if same else "#1A0A00"
        border = "#334155" if same else "#F59E0B"
        step_compare += f"""
        <div style="background:{bg};border:1px solid {border};border-radius:8px;padding:10px 14px;margin-bottom:8px">
          <div style="display:flex;gap:8px;align-items:center;margin-bottom:4px">
            <span style="font-family:monospace;color:#64748B;font-size:12px">Step {i+1}</span>
            {_badge_type(os_.step_type)}
            {"<span style='color:#F59E0B;font-size:12px;font-weight:600'>DIVERGENCE</span>" if not same else "<span style='color:#10B981;font-size:12px'>identique</span>"}
          </div>
        </div>"""

    # Section Root Cause Analysis
    rca_section = f"""
    <div style="margin-top:28px">
      <h2 style="font-size:16px;color:#94A3B8;margin-bottom:12px">
        Root Cause Analysis
        <span style="font-size:12px;color:#475569;font-weight:400;margin-left:8px">
          powered by Groq llama-3.1-8b-instant
        </span>
      </h2>
      <div style="background:#0F172A;border:1px solid #2563EB;border-radius:10px;
                  padding:16px;font-size:13px">
        <div id="rca-loading" style="color:#64748B">
          Chargement de l'analyse...
        </div>
        <div id="rca-content" style="display:none">
          <div id="rca-root-cause"
               style="color:#F1F5F9;font-size:14px;font-weight:500;margin-bottom:12px">
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:10px">
            <div>
              <div style="font-size:11px;color:#475569;margin-bottom:4px">FAILURE TYPE</div>
              <div id="rca-type"
                   style="background:#1E293B;border-radius:6px;
                          padding:6px 10px;color:#F59E0B;font-size:12px">
              </div>
            </div>
            <div>
              <div style="font-size:11px;color:#475569;margin-bottom:4px">CONFIDENCE</div>
              <div id="rca-confidence"
                   style="background:#1E293B;border-radius:6px;
                          padding:6px 10px;color:#10B981;font-size:12px">
              </div>
            </div>
          </div>
          <div style="margin-top:12px">
            <div style="font-size:11px;color:#475569;margin-bottom:4px">EVIDENCE</div>
            <div id="rca-evidence"
                 style="background:#1E293B;border:1px solid #334155;border-radius:6px;
                        padding:8px 10px;color:#94A3B8;font-size:12px;
                        font-family:monospace;white-space:pre-wrap">
            </div>
          </div>
          <div style="margin-top:12px">
            <div style="font-size:11px;color:#475569;margin-bottom:4px">
              FIX RECOMMENDATION
            </div>
            <div id="rca-fix"
                 style="background:#0D2E20;border:1px solid #10B981;border-radius:6px;
                        padding:8px 10px;color:#10B981;font-size:13px">
            </div>
          </div>
        </div>
        <div id="rca-error" style="display:none;color:#EF4444;font-size:13px"></div>
      </div>
    </div>
    <script>
    fetch('/analyze/diff/{original_id}/{whatif_id}')
      .then(r => r.json())
      .then(data => {{
        document.getElementById('rca-loading').style.display = 'none';
        if (data.error || !data.analyses || data.analyses.length === 0) {{
          document.getElementById('rca-error').style.display = 'block';
          document.getElementById('rca-error').textContent =
            data.message || data.error || 'No analysis available.';
          return;
        }}
        const a = data.analyses[0];
        document.getElementById('rca-content').style.display = 'block';
        document.getElementById('rca-root-cause').textContent =
          'Root cause: ' + a.root_cause;
        document.getElementById('rca-type').textContent     = a.failure_type;
        document.getElementById('rca-confidence').textContent =
          Math.round(a.confidence * 100) + '% confidence';
        document.getElementById('rca-evidence').textContent  = a.evidence;
        document.getElementById('rca-fix').textContent       = a.fix_recommendation;
      }})
      .catch(e => {{
        document.getElementById('rca-loading').style.display = 'none';
        document.getElementById('rca-error').style.display   = 'block';
        document.getElementById('rca-error').textContent     = 'Analysis failed: ' + e;
      }});
    </script>"""

    body = f"""
    <div style="margin-bottom:20px">
      <a href="/ui/runs" style="color:#64748B;text-decoration:none;font-size:13px">Tous les runs</a>
      <span style="color:#334155"> / </span>
      <span style="color:#94A3B8;font-size:13px">Diff</span>
    </div>
    <h1>Diff — Original vs What-If</h1>
    <p class="subtitle">Comparaison des trajectoires : prompt bugue vs prompt corrige</p>
    {status_html}
    {diff_grid}
    <h2 style="font-size:16px;color:#94A3B8;margin:24px 0 12px">Comparaison step par step</h2>
    {step_compare}
    <div style="margin-top:20px;display:flex;gap:10px">
      <a href="/ui/runs/{original_id}" class="btn">Voir run original</a>
      <a href="/ui/runs/{whatif_id}" class="btn" style="background:#10B981">Voir run What-If</a>
    </div>
    {rca_section}"""

    return HTMLResponse(_html_page("Diff", body))
