"""
JiraGuard — Script de démonstration complet
Démontre les 3 modes : RECORD → REPLAY → WHAT-IF
Lance le proxy d'abord : uvicorn core.proxy:app --reload
"""

import json
import time
import sys
import os
import requests

# Fix encodage Windows : force UTF-8 sur stdout (cp1252 ne gère pas → ═ ✓)
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.jira_agent import JiraAgent, load_tickets
from agent.mock_jira  import MockJiraAPI

from dotenv import load_dotenv
load_dotenv()

PROXY_URL = "http://localhost:8000"


def wait_for_proxy(timeout: int = 8) -> bool:
    for i in range(timeout):
        try:
            r = requests.get(f"{PROXY_URL}/health", timeout=2)
            if r.status_code == 200:
                print(f"[OK] Proxy actif — mode={r.json()['mode']}")
                return True
        except Exception:
            pass
        print(f"  Attente proxy... ({i+1}/{timeout})")
        time.sleep(1)
    return False


def print_separator(title: str):
    print("\n" + "═" * 60)
    print(f"  {title}")
    print("═" * 60)


def demo_record(tickets: list) -> str:
    print_separator("PHASE 1 — MODE RECORD (agent bugué)")

    r = requests.post(f"{PROXY_URL}/mode", json={"mode": "RECORD"})
    run_id = r.json()["run_id"]
    print(f"Run ID : {run_id}\n")

    agent = JiraAgent(use_fixed_prompt=False)
    results = agent.run_batch(tickets, proxy_url=PROXY_URL)

    requests.post(f"{PROXY_URL}/run/complete")

    # Évaluer les résultats
    jira_eval = MockJiraAPI()
    for result in results:
        if result.get("decision") and result["decision"].get("team") != "unknown":
            jira_eval.assign_ticket(
                result["ticket_id"],
                result["decision"].get("team","unknown"),
                result["decision"].get("priority","unknown")
            )
    metrics = jira_eval.evaluate_assignments(tickets)
    print(f"\nAccuracy agent bugué : {metrics['accuracy']} ({metrics['correct']}/{metrics['total']})")

    return run_id


def demo_replay(run_id: str, tickets: list):
    print_separator("PHASE 2 — MODE REPLAY (déterministe, zéro appel LLM)")

    r = requests.post(f"{PROXY_URL}/mode", json={"mode": "REPLAY", "run_id": run_id})
    print(f"Steps chargés : {r.json()['steps_loaded']}\n")

    agent = JiraAgent(use_fixed_prompt=False)
    agent.run_batch(tickets, proxy_url=PROXY_URL)
    requests.post(f"{PROXY_URL}/run/complete")
    print("\nReplay terminé — aucun appel LLM réel effectué ✓")


def demo_whatif(run_id: str, tickets: list) -> str:
    print_separator("PHASE 3 — MODE WHAT-IF (injection prompt corrigé au step 1)")

    from agent.jira_agent import SYSTEM_PROMPT_FIXED

    r = requests.post(f"{PROXY_URL}/mode", json={
        "mode": "WHATIF",
        "run_id": run_id,
        "injection_step": 1,
        "injection": {"type": "prompt", "value": SYSTEM_PROMPT_FIXED},
    })
    data = r.json()
    whatif_run_id = data["whatif_run_id"]
    print(f"Run original  : {run_id}")
    print(f"Run What-If   : {whatif_run_id}")
    print(f"Injection au step : {data['injection_at_step']}\n")

    agent = JiraAgent(use_fixed_prompt=False)
    results = agent.run_batch(tickets, proxy_url=PROXY_URL)
    requests.post(f"{PROXY_URL}/run/complete")

    # Évaluer le what-if
    jira_eval = MockJiraAPI()
    for result in results:
        if result.get("decision") and result["decision"].get("team") != "unknown":
            jira_eval.assign_ticket(
                result["ticket_id"],
                result["decision"].get("team","unknown"),
                result["decision"].get("priority","unknown")
            )
    metrics = jira_eval.evaluate_assignments(tickets)
    print(f"\nAccuracy What-If (prompt corrigé) : {metrics['accuracy']} ({metrics['correct']}/{metrics['total']})")

    # Afficher le diff
    diff = requests.get(f"{PROXY_URL}/runs/{run_id}/diff/{whatif_run_id}").json()
    print(f"\nDIFF original vs What-If :")
    print(f"  Divergence au step    : {diff.get('divergence_at_step')}")
    print(f"  Tickets corrigés      : {diff.get('tickets_corrected')}/{len(diff.get('original_decisions', []))}")
    for ch in diff.get("decisions_changed", []):
        o = ch["original"]; w = ch["whatif"]
        print(f"    - step {ch['step']}: "
              f"{o['team']}/{o['priority']}  ->  {w['team']}/{w['priority']}")
    print(f"  Décision changée      : {diff.get('decision_changed')}")

    return whatif_run_id


def main():
    print("JiraGuard — Démonstration complète")
    print("Use Case 2 — AINS Hackathon 2026\n")

    if not wait_for_proxy():
        print("\nERREUR : Proxy inaccessible sur http://localhost:8000")
        print("Lance d'abord : uvicorn core.proxy:app --reload")
        sys.exit(1)

    tickets = load_tickets(5)
    print(f"Tickets chargés : {len(tickets)}\n")

    run_id       = demo_record(tickets)
    demo_replay(run_id, tickets)
    whatif_run_id = demo_whatif(run_id, tickets)

    print_separator("RÉSUMÉ")
    print(f"Run original  : {run_id}")
    print(f"Run What-If   : {whatif_run_id}")

    stats = requests.get(f"{PROXY_URL}/stats").json()
    print(f"\nStats DB :")
    print(f"  Total runs  : {stats['total_runs']}")
    print(f"  Total steps : {stats['total_steps']}")
    print(f"\nUI disponible (prochaine étape) : http://localhost:8000/ui/runs")
    print("\nDémonstration terminée ✓")


if __name__ == "__main__":
    main()
