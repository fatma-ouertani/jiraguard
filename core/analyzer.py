"""
JiraGuard — Root Cause Analyzer
Utilise un LLM pour analyser une trace d'exécution et expliquer
POURQUOI l'agent a pris une mauvaise décision.
C'est la couche d'intelligence qui va au-delà du simple logging.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json
from groq import Groq
from core.trace_store import TraceStore, db

GROQ_MODEL = "llama-3.1-8b-instant"

ANALYZER_PROMPT = """You are an AI debugging expert analyzing why an AI agent
made a wrong decision.

You will receive:
1. The agent's execution trace (LLM prompts + responses + tool calls)
2. The wrong decision the agent made
3. The correct expected decision

Your job: identify the ROOT CAUSE of the failure.

Analyze and return a JSON object with exactly these fields:
{
  "root_cause": "one sentence describing the exact cause",
  "failure_type": "prompt_rule_missing|prompt_ambiguity|hallucination|context_error|tool_error",
  "evidence": "quote the exact part of the prompt or response that caused the failure",
  "fix_recommendation": "one concrete sentence on how to fix the prompt or system",
  "confidence": 0.0-1.0
}

Be specific. Quote exact text from the trace as evidence.
Return ONLY valid JSON, no text before or after."""


class RootCauseAnalyzer:
    def __init__(self):
        self.client = Groq()
        self.model  = GROQ_MODEL

    def analyze_run(self, run_id: str,
                    wrong_decision: dict,
                    expected_decision: dict) -> dict:
        """
        Analyse un run et identifie la cause racine de l'erreur.

        Args:
            run_id: ID du run à analyser
            wrong_decision: {"team": "frontend", "priority": "high"}
            expected_decision: {"team": "backend", "priority": "critical"}

        Returns:
            dict avec root_cause, failure_type, evidence, fix_recommendation, confidence
        """
        steps = db.get_steps(run_id)
        if not steps:
            return {"error": f"No steps found for run {run_id}"}

        # Construire un résumé lisible de la trace
        trace_summary = self._build_trace_summary(steps)

        user_message = f"""EXECUTION TRACE:
{trace_summary}

WRONG DECISION MADE:
team={wrong_decision.get('team')} / priority={wrong_decision.get('priority')}

EXPECTED CORRECT DECISION:
team={expected_decision.get('team')} / priority={expected_decision.get('priority')}

Analyze the root cause of this wrong decision."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": ANALYZER_PROMPT},
                {"role": "user",   "content": user_message},
            ],
            max_tokens=400,
            temperature=0,
        )

        raw = response.choices[0].message.content.strip()

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            result = json.loads(match.group()) if match else {
                "root_cause": raw[:200],
                "failure_type": "unknown",
                "evidence": "",
                "fix_recommendation": "",
                "confidence": 0.0,
            }

        result["run_id"]            = run_id
        result["wrong_decision"]    = wrong_decision
        result["expected_decision"] = expected_decision
        return result

    def analyze_diff(self, original_run_id: str,
                     whatif_run_id: str) -> dict:
        """
        Analyse automatiquement un diff entre run original et what-if.
        Identifie les tickets corrigés et explique pourquoi ils étaient faux.
        """
        from core.trace_store import db as store
        diff = store.compute_diff(original_run_id, whatif_run_id)

        if not diff.get("decisions_changed"):
            return {
                "message": "No decisions changed between original and what-if run.",
                "original_run_id": original_run_id,
                "whatif_run_id":   whatif_run_id,
            }

        analyses = []
        for change in diff["decisions_changed"]:
            analysis = self.analyze_run(
                run_id=original_run_id,
                wrong_decision=change["original"],
                expected_decision=change["whatif"],
            )
            analysis["step"] = change["step"]
            analyses.append(analysis)

        return {
            "original_run_id":  original_run_id,
            "whatif_run_id":    whatif_run_id,
            "tickets_analyzed": len(analyses),
            "analyses":         analyses,
        }

    def _build_trace_summary(self, steps: list) -> str:
        lines = []
        for step in steps:
            if step.step_type == "llm_call":
                system = step.input_payload.get("system", "")[:300]
                messages = step.input_payload.get("messages", [])
                user_content = messages[0].get("content", "")[:200] if messages else ""
                output = step.output_payload.get("content", "")[:200]
                lines.append(
                    f"[Step {step.step_number} — LLM CALL]\n"
                    f"SYSTEM PROMPT (first 300 chars): {system}\n"
                    f"USER MESSAGE: {user_content}\n"
                    f"LLM RESPONSE: {output}\n"
                )
            elif step.step_type == "tool_call":
                inp = step.input_payload
                out = step.output_payload
                lines.append(
                    f"[Step {step.step_number} — TOOL CALL: jira_assign]\n"
                    f"INPUT:  ticket={inp.get('ticket_id')} "
                    f"team={inp.get('team')} priority={inp.get('priority')}\n"
                    f"OUTPUT: success={out.get('success')}\n"
                )
        return "\n".join(lines)
