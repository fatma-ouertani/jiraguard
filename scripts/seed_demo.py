"""
JiraGuard — Seed de démo synthétique
Recrée un run RECORD (prompt bugué) + un run WHAT-IF (prompt corrigé)
SANS aucun appel LLM, directement dans le Trace Store.

But : peupler la DB pour les captures d'écran / la démo offline,
de façon reproductible et déterministe.

Usage :
    python scripts/seed_demo.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json
from datetime import datetime, timezone

from core.trace_store import db, Step

# ── Décisions synthétiques (identiques au vrai run de démo) ──────────────────
# (ticket, titre, buggy_team, buggy_prio, buggy_reason,
#                  fixed_team, fixed_prio, fixed_reason)
DEMO = [
    ("JSM-001", "Erreur 500 sur /api/payments en production",
     "frontend", "high",     "Error 500 on payment API endpoint, likely related to frontend",
     "backend",  "critical", "Production down, security breach possible due to unhandled error on /api/payments"),
    ("JSM-002", "Bouton de connexion ne répond pas sur mobile Safari",
     "frontend", "medium",   "Mention of mobile and Safari indicates frontend routing rule",
     "frontend", "medium",   "Mention of mobile and Safari indicates frontend routing rule"),
    ("JSM-003", "Base de données principale saturée à 95%",
     "infra",    "critical", "Disk space issue with primary database, service will be stopped",
     "infra",    "critical", "Disk space issue with primary database, service will be stopped"),
    ("JSM-004", "CSS cassé sur la page de profil utilisateur",
     "frontend", "medium",   "Mention of CSS indicates frontend team responsibility",
     "frontend", "medium",   "Mention of CSS indicates frontend team responsibility"),
    ("JSM-005", "API /api/users retourne des données corrompues",
     "frontend", "medium",   "Mention of API and users indicates frontend routing",
     "frontend", "medium",   "Mention of API and users indicates frontend routing"),
]

MODEL = "llama-3.1-8b-instant"


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def _decision_json(team, prio, reason):
    return json.dumps({"team": team, "priority": prio, "reasoning": reason}, ensure_ascii=False)


def _add_ticket_steps(run_id, n_start, ticket, title, team, prio, reason,
                      injected=False, latency=250):
    """Ajoute un llm_call + un tool_call pour un ticket. Renvoie le prochain step_number."""
    user_msg = (f"Ticket ID: {ticket}\nTitle: {title}\n"
                f"Description: ...\n\nReturn your decision as JSON.")

    # llm_call
    db.save_step(Step(
        run_id=run_id, step_number=n_start, step_type="llm_call",
        input_payload={"system": "(system prompt)...", "messages": [{"role": "user", "content": user_msg}], "model": MODEL},
        output_payload={"content": _decision_json(team, prio, reason)},
        latency_ms=(0 if not latency else latency), timestamp=_now(), injected=injected,
    ))
    # tool_call (assignation Jira)
    db.save_step(Step(
        run_id=run_id, step_number=n_start + 1, step_type="tool_call",
        input_payload={"ticket_id": ticket, "team": team, "priority": prio},
        output_payload={"ticket_id": ticket, "team": team, "priority": prio,
                        "timestamp": _now(), "success": True,
                        "jira_response": "Issue updated successfully", "mock": True},
        latency_ms=0, timestamp=_now(), injected=injected,
    ))
    return n_start + 2


def seed():
    # ── Run RECORD (prompt bugué) ────────────────────────────────────────────
    record = db.create_run(mode="RECORD", agent_version="1.0-buggy")
    n = 1
    for (tid, title, bt, bp, br, _ft, _fp, _fr) in DEMO:
        n = _add_ticket_steps(record.id, n, tid, title, bt, bp, br, latency=250)
    db.complete_run(record.id)

    # ── Run WHAT-IF (prompt corrigé injecté au step 1) ───────────────────────
    whatif = db.create_run(mode="WHATIF", agent_version="1.0-whatif",
                           parent_run_id=record.id, injection_step=1)
    n = 1
    for i, (tid, title, _bt, _bp, _br, ft, fp, fr) in enumerate(DEMO):
        # le premier ticket porte le step injecté
        injected = (i == 0)
        n = _add_ticket_steps(whatif.id, n, tid, title, ft, fp, fr,
                              injected=injected, latency=260 if injected else 0)
    db.complete_run(whatif.id)

    return record.id, whatif.id


if __name__ == "__main__":
    rec_id, wi_id = seed()
    print("JiraGuard — seed de démo terminé (aucun appel LLM)")
    print(f"  RECORD run : {rec_id}  (10 steps)")
    print(f"  WHATIF run : {wi_id}  (10 steps)")
    print()
    print("URLs pour les captures :")
    print(f"  /ui/runs")
    print(f"  /ui/runs/{rec_id}")
    print(f"  /ui/diff/{rec_id}/{wi_id}")
