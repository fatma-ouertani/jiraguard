"""
JiraGuard — Jira Triage Agent (Groq backend)
Utilise Groq API (gratuit) à la place d'Anthropic.
Le modèle llama-3.1-8b-instant est rapide et gratuit.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json
import time
import requests as req
from pathlib import Path
from groq import Groq

TICKETS_PATH = Path(__file__).parent.parent / "data" / "tickets.json"
GROQ_MODEL   = "llama-3.1-8b-instant"

# ── PROMPT BUGUÉ ────────────────────────────────────────────────────────────
SYSTEM_PROMPT_BUGGY = """You are a Jira ticket triage expert.

Routing rules:
- Anything mentioning payments, users, API, data -> frontend
- Anything mentioning CSS, buttons, Safari, mobile -> frontend
- Anything mentioning disk, kubernetes, certificates -> infra
- Everything else -> backend

Priority rules:
- Always assign "medium" unless the word "down" appears explicitly
- Feature requests -> low

Reply ONLY with valid JSON, no text before or after:
{
  "team": "backend|frontend|infra",
  "priority": "critical|high|medium|low",
  "reasoning": "short explanation"
}"""

# ── PROMPT CORRIGÉ ───────────────────────────────────────────────────────────
SYSTEM_PROMPT_FIXED = """You are a Jira ticket triage expert.

Routing rules:
- Routes /api/*, REST endpoints, server-side logic -> backend
- CSS, HTML, JavaScript, UI components, Safari, mobile -> frontend
- Kubernetes, disk, certificates, monitoring, CI/CD -> infra
- Security vulnerabilities -> backend, priority: critical
- Data corruption, race conditions -> backend, priority: critical

Priority rules:
- Production down, data loss, security breach -> critical
- Major feature broken, no workaround -> high
- Degraded feature, workaround exists -> medium
- Feature request, cosmetic -> low

Reply ONLY with valid JSON, no text before or after:
{
  "team": "backend|frontend|infra",
  "priority": "critical|high|medium|low",
  "reasoning": "short explanation"
}"""


class JiraAgent:
    def __init__(self, use_fixed_prompt: bool = False):
        self.client  = Groq()
        self.prompt  = SYSTEM_PROMPT_FIXED if use_fixed_prompt else SYSTEM_PROMPT_BUGGY
        self.version = "1.1-fixed" if use_fixed_prompt else "1.0-buggy"
        self.model   = GROQ_MODEL

    def _parse_decision(self, raw: str) -> dict:
        raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{[^}]+\}', raw, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except Exception:
                    pass
            return {"team": "unknown", "priority": "unknown", "reasoning": raw[:100]}

    def process_ticket(self, ticket: dict) -> dict:
        """Appel direct Groq — pour tests unitaires."""
        user_message = (
            f"Ticket ID: {ticket['id']}\n"
            f"Title: {ticket['title']}\n"
            f"Description: {ticket['description']}\n\n"
            f"Return your decision as JSON."
        )
        start = time.time()
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.prompt},
                {"role": "user",   "content": user_message},
            ],
            max_tokens=200,
            temperature=0,
        )
        latency_ms = int((time.time() - start) * 1000)
        raw = response.choices[0].message.content
        return {
            "ticket_id":  ticket["id"],
            "decision":   self._parse_decision(raw),
            "latency_ms": latency_ms,
            "raw":        raw,
        }

    def process_ticket_via_proxy(self, ticket: dict,
                                  proxy_url: str = "http://localhost:8000") -> dict:
        """Appel via le proxy JiraGuard — utilisé pour RECORD/REPLAY/WHATIF."""
        user_message = (
            f"Ticket ID: {ticket['id']}\n"
            f"Title: {ticket['title']}\n"
            f"Description: {ticket['description']}\n\n"
            f"Return your decision as JSON."
        )
        start = time.time()

        # Appel LLM via proxy
        llm_resp = req.post(
            f"{proxy_url}/proxy/llm",
            json={
                "model":      self.model,
                "system":     self.prompt,
                "messages":   [{"role": "user", "content": user_message}],
                "max_tokens": 200,
                "ticket_id":  ticket["id"],
            },
            timeout=30,
        )
        llm_resp.raise_for_status()
        raw = llm_resp.json().get("content", "")
        latency_ms = int((time.time() - start) * 1000)

        decision = self._parse_decision(raw)

        # Appel Jira via proxy
        jira_resp = req.post(
            f"{proxy_url}/proxy/jira/assign",
            json={
                "ticket_id": ticket["id"],
                "team":      decision.get("team", "unknown"),
                "priority":  decision.get("priority", "unknown"),
            },
            timeout=10,
        )
        jira_result = jira_resp.json() if jira_resp.ok else {"success": False}

        return {
            "ticket_id":    ticket["id"],
            "decision":     decision,
            "jira_updated": jira_result.get("success", False),
            "latency_ms":   latency_ms,
        }

    def run_batch(self, tickets: list, proxy_url: str = None) -> list:
        results = []
        for ticket in tickets:
            try:
                if proxy_url:
                    result = self.process_ticket_via_proxy(ticket, proxy_url)
                else:
                    result = self.process_ticket(ticket)
                d = result["decision"]
                print(
                    f"  [{ticket['id']}] "
                    f"{d.get('team','?'):10s} / {d.get('priority','?'):8s} | "
                    f"{d.get('reasoning','')[:60]}"
                )
                results.append(result)
            except Exception as e:
                print(f"  [{ticket['id']}] ERREUR: {e}")
                results.append({"ticket_id": ticket["id"],
                                 "error": str(e), "decision": {}})
        return results


def load_tickets(n: int = None) -> list:
    with open(TICKETS_PATH) as f:
        tickets = json.load(f)
    return tickets[:n] if n else tickets
