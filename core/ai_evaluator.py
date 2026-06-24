"""
JiraGuard — AI Step Evaluator
Utilise un LLM pour évaluer chaque step de la trace :
- Détecte les anomalies (latence anormale, décision suspecte)
- Classifie la qualité de chaque décision LLM
- Produit un score de confiance par step
Sans cette couche IA, on ne peut pas détecter les
comportements silencieusement incorrects.
"""

import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from groq import Groq
from core.trace_store import db, Step

GROQ_MODEL = "llama-3.1-8b-instant"

STEP_EVAL_PROMPT = """You are an AI quality evaluator for Jira triage agents.

Analyze this agent execution step and evaluate its quality.

Return ONLY valid JSON:
{
  "quality": "good|suspicious|bad",
  "confidence": 0.0-1.0,
  "anomaly_detected": true|false,
  "anomaly_type": "none|wrong_team|wrong_priority|hallucination|slow_response|inconsistent_reasoning",
  "reasoning": "one sentence explanation",
  "suggested_fix": "one sentence fix if anomaly detected, else null"
}"""

REPLAY_FIDELITY_PROMPT = """You are evaluating whether two AI agent decisions are semantically equivalent.

Original decision: {original}
Replayed decision: {replayed}

Are these decisions semantically equivalent for Jira triage purposes?
Return ONLY valid JSON:
{
  "equivalent": true|false,
  "fidelity_score": 0.0-1.0,
  "difference": "description of difference if any, else null"
}"""


class AIEvaluator:
    def __init__(self):
        self.client = Groq()
        self.model  = GROQ_MODEL

    def evaluate_step(self, step: Step,
                      expected_team: str = None,
                      expected_priority: str = None) -> dict:
        """Évalue un step individuel avec un LLM."""
        context = self._build_step_context(
            step, expected_team, expected_priority
        )
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": STEP_EVAL_PROMPT},
                    {"role": "user",   "content": context},
                ],
                max_tokens=200,
                temperature=0,
            )
            raw = resp.choices[0].message.content.strip()
            result = json.loads(raw)
        except Exception as e:
            result = {
                "quality": "unknown",
                "confidence": 0.0,
                "anomaly_detected": False,
                "anomaly_type": "none",
                "reasoning": f"Evaluation failed: {e}",
                "suggested_fix": None,
            }
        result["step_number"] = step.step_number
        result["step_type"]   = step.step_type
        return result

    def evaluate_replay_fidelity(self,
                                  orig_steps: list,
                                  replay_steps: list) -> dict:
        """
        Évalue la fidélité sémantique du replay vs l'original.
        Va au-delà de la comparaison byte-par-byte.
        """
        if not orig_steps or not replay_steps:
            return {"fidelity_score": 0.0, "error": "No steps"}

        tool_orig   = [s for s in orig_steps
                       if s.step_type == "tool_call"]
        tool_replay = [s for s in replay_steps
                       if s.step_type == "tool_call"]

        scores = []
        details = []
        for o, r in zip(tool_orig, tool_replay):
            orig_dec   = {
                "team":     o.output_payload.get("team",""),
                "priority": o.output_payload.get("priority",""),
            }
            replay_dec = {
                "team":     r.output_payload.get("team",""),
                "priority": r.output_payload.get("priority",""),
            }
            if orig_dec == replay_dec:
                scores.append(1.0)
                details.append({
                    "step": o.step_number,
                    "equivalent": True,
                    "fidelity_score": 1.0,
                })
                continue
            try:
                prompt = REPLAY_FIDELITY_PROMPT.format(
                    original=json.dumps(orig_dec),
                    replayed=json.dumps(replay_dec),
                )
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=150,
                    temperature=0,
                )
                raw    = resp.choices[0].message.content.strip()
                result = json.loads(raw)
                scores.append(result.get("fidelity_score", 0.0))
                details.append({
                    "step": o.step_number,
                    **result,
                })
            except Exception:
                scores.append(0.0)
                details.append({
                    "step": o.step_number,
                    "equivalent": False,
                    "fidelity_score": 0.0,
                })

        avg = round(sum(scores) / len(scores), 3) if scores else 0.0
        return {
            "replay_fidelity_score": avg,
            "steps_compared": len(scores),
            "fully_faithful": avg == 1.0,
            "details": details,
        }

    def evaluate_run(self, run_id: str,
                     tickets: list = None) -> dict:
        """Évalue tous les steps d'un run."""
        steps   = db.get_steps(run_id)
        run     = db.get_run(run_id)
        results = []

        ticket_map = {}
        if tickets:
            ticket_map = {t["id"]: t for t in tickets}

        for step in steps:
            if step.step_type == "llm_call":
                ticket_id = step.input_payload.get(
                    "ticket_id", ""
                )
                t = ticket_map.get(ticket_id, {})
                eval_result = self.evaluate_step(
                    step,
                    expected_team=t.get("expected_team"),
                    expected_priority=t.get("expected_priority"),
                )
                results.append(eval_result)

        anomalies = [r for r in results if r["anomaly_detected"]]
        avg_conf  = (
            round(sum(r["confidence"] for r in results)
                  / len(results), 2)
            if results else 0.0
        )
        return {
            "run_id":           run_id,
            "mode":             run.mode if run else "unknown",
            "total_steps_eval": len(results),
            "anomalies_found":  len(anomalies),
            "avg_confidence":   avg_conf,
            "anomaly_rate":     round(
                len(anomalies)/len(results), 2
            ) if results else 0.0,
            "step_evaluations": results,
            "anomalies":        anomalies,
        }

    def _build_step_context(self, step: Step,
                             expected_team: str,
                             expected_priority: str) -> str:
        if step.step_type == "llm_call":
            content = step.output_payload.get("content", "")
            try:
                decision = json.loads(content)
            except Exception:
                decision = {"raw": content}

            ctx = f"""Step #{step.step_number} — LLM call
Latency: {step.latency_ms}ms
Decision made: {json.dumps(decision)}"""
            if expected_team:
                ctx += f"\nExpected team: {expected_team}"
            if expected_priority:
                ctx += f"\nExpected priority: {expected_priority}"
            return ctx

        elif step.step_type == "tool_call":
            return f"""Step #{step.step_number} — Tool call (jira_assign)
Input:  {json.dumps(step.input_payload)}
Output: {json.dumps(step.output_payload)}
Latency: {step.latency_ms}ms"""
        return f"Step #{step.step_number} — {step.step_type}"


evaluator = AIEvaluator()
