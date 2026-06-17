"""
JiraGuard — Proxy Intercepteur
Intercepte tous les appels LLM et Jira de l'agent.
3 modes : RECORD (log tout), REPLAY (cache), WHATIF (injection)
"""

import time
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from groq import Groq

from core.trace_store import TraceStore, Step, db
from agent.mock_jira import MockJiraAPI

app = FastAPI(title="JiraGuard Proxy", version="1.0")
groq_client = Groq()
GROQ_MODEL = "llama-3.1-8b-instant"
jira = MockJiraAPI()


# ── ÉTAT GLOBAL DU PROXY ────────────────────────────────────────────────────

class ProxyState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.mode: str = "RECORD"
        self.current_run_id: Optional[str] = None
        self.replay_steps: list = []
        self.replay_cursor: int = 0
        self.whatif_injection_step: Optional[int] = None
        self.whatif_injection: Optional[dict] = None
        self.whatif_passed_injection: bool = False
        self.step_counter: int = 0

state = ProxyState()


# ── SCHÉMAS PYDANTIC ────────────────────────────────────────────────────────

class LLMRequest(BaseModel):
    model: str = "claude-haiku-4-5-20251001"
    system: str
    messages: list
    max_tokens: int = 300
    ticket_id: Optional[str] = None

class JiraAssignRequest(BaseModel):
    ticket_id: str
    team: str
    priority: str

class SetModeRequest(BaseModel):
    mode: str
    run_id: Optional[str] = None
    injection_step: Optional[int] = None
    injection: Optional[dict] = None


# ── HELPER : sauvegarder un step ────────────────────────────────────────────

def save_step(step_type: str, input_payload: dict, output_payload: dict,
              latency_ms: int = 0, injected: bool = False):
    if not state.current_run_id:
        return
    state.step_counter += 1
    step = Step(
        run_id=state.current_run_id,
        step_number=state.step_counter,
        step_type=step_type,
        input_payload=input_payload,
        output_payload=output_payload,
        latency_ms=latency_ms,
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        injected=injected,
    )
    db.save_step(step)


# ── ENDPOINTS DE CONTRÔLE ────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "mode": state.mode,
        "run_id": state.current_run_id,
        "step_counter": state.step_counter,
    }

@app.get("/mode")
def get_mode():
    return {
        "mode": state.mode,
        "run_id": state.current_run_id,
        "replay_cursor": state.replay_cursor,
        "injection_step": state.whatif_injection_step,
    }

@app.post("/mode")
def set_mode(req: SetModeRequest):
    state.reset()

    if req.mode == "RECORD":
        run = db.create_run(mode="RECORD", agent_version="1.0-buggy")
        state.mode = "RECORD"
        state.current_run_id = run.id
        print(f"[PROXY] Mode RECORD — run_id={run.id}")
        return {"mode": "RECORD", "run_id": run.id}

    elif req.mode == "REPLAY":
        if not req.run_id:
            raise HTTPException(400, "run_id requis pour REPLAY")
        steps = db.get_steps(req.run_id)
        if not steps:
            raise HTTPException(404, f"Aucun step pour run {req.run_id}")
        state.mode = "REPLAY"
        state.replay_steps = steps
        state.current_run_id = req.run_id
        print(f"[PROXY] Mode REPLAY — run_id={req.run_id} ({len(steps)} steps chargés)")
        return {"mode": "REPLAY", "run_id": req.run_id, "steps_loaded": len(steps)}

    elif req.mode == "WHATIF":
        if not req.run_id or req.injection_step is None or not req.injection:
            raise HTTPException(400, "run_id, injection_step et injection requis pour WHATIF")
        steps = db.get_steps(req.run_id)
        if not steps:
            raise HTTPException(404, f"Aucun step pour run {req.run_id}")
        whatif_run = db.create_run(
            mode="WHATIF",
            agent_version="1.0-whatif",
            parent_run_id=req.run_id,
            injection_step=req.injection_step,
        )
        state.mode = "WHATIF"
        state.replay_steps = steps
        state.current_run_id = whatif_run.id
        state.whatif_injection_step = req.injection_step
        state.whatif_injection = req.injection
        print(f"[PROXY] Mode WHATIF — original={req.run_id} whatif={whatif_run.id} inject@step={req.injection_step}")
        return {
            "mode": "WHATIF",
            "original_run_id": req.run_id,
            "whatif_run_id": whatif_run.id,
            "injection_at_step": req.injection_step,
        }

    raise HTTPException(400, f"Mode inconnu: {req.mode}")


@app.post("/run/complete")
def complete_run(status: str = "completed"):
    if state.current_run_id:
        db.complete_run(state.current_run_id, status)
        print(f"[PROXY] Run {state.current_run_id} — {status} ({state.step_counter} steps)")
    return {"completed": state.current_run_id, "total_steps": state.step_counter}


# ── PROXY LLM ────────────────────────────────────────────────────────────────

@app.post("/proxy/llm")
def proxy_llm(req: LLMRequest):
    state.step_counter += 1
    current_step = state.step_counter

    # ── MODE REPLAY ──────────────────────────────────────────────────────────
    if state.mode == "REPLAY":
        idx = state.replay_cursor
        if idx < len(state.replay_steps):
            cached = state.replay_steps[idx]
            state.replay_cursor += 1
            print(f"  [PROXY REPLAY] step {current_step} llm_call → depuis cache")
            return cached.output_payload
        else:
            print(f"  [PROXY REPLAY] step {current_step} — plus de cache, appel réel")

    # ── MODE WHATIF ──────────────────────────────────────────────────────────
    if state.mode == "WHATIF":
        if not state.whatif_passed_injection:
            if current_step == state.whatif_injection_step and state.whatif_injection.get("type") == "prompt":
                # Injection : utiliser le nouveau prompt
                injected_system = state.whatif_injection["value"]
                state.whatif_passed_injection = True
                print(f"  [PROXY WHATIF] step {current_step} — INJECTION prompt")
                output = _call_groq(injected_system, req.messages, req.model, req.max_tokens)
                save_step("llm_call",
                    {"system": injected_system[:100] + "...", "messages": req.messages, "injected": True},
                    output, injected=True)
                return output
            else:
                # Avant injection : replay depuis cache
                idx = state.replay_cursor
                if idx < len(state.replay_steps):
                    cached = state.replay_steps[idx]
                    state.replay_cursor += 1
                    print(f"  [PROXY WHATIF] step {current_step} llm_call → cache (avant injection)")
                    save_step("llm_call",
                        {"system": req.system[:100] + "...", "messages": req.messages},
                        cached.output_payload)
                    return cached.output_payload

    # ── MODE RECORD (ou WHATIF après injection) ──────────────────────────────
    start = time.time()
    output = _call_groq(req.system, req.messages, req.model, req.max_tokens)
    latency = int((time.time() - start) * 1000)
    print(f"  [PROXY RECORD] step {current_step} llm_call → API réelle ({latency}ms)")
    save_step("llm_call",
        {"system": req.system[:100] + "...", "messages": req.messages, "model": req.model},
        output, latency_ms=latency)
    return output


def _call_groq(system: str, messages: list,
               model: str = None, max_tokens: int = 200) -> dict:
    """Appel réel à Groq API."""
    response = groq_client.chat.completions.create(
        model=model or GROQ_MODEL,
        messages=[
            {"role": "system", "content": system},
            *messages,
        ],
        max_tokens=max_tokens,
        temperature=0,
    )
    return {"content": response.choices[0].message.content}


# ── PROXY JIRA ────────────────────────────────────────────────────────────────

@app.post("/proxy/jira/assign")
def proxy_jira_assign(req: JiraAssignRequest):
    state.step_counter += 1
    current_step = state.step_counter

    # ── MODE REPLAY (avant injection pour WHATIF) ─────────────────────────────
    if state.mode == "REPLAY" or (state.mode == "WHATIF" and not state.whatif_passed_injection):
        idx = state.replay_cursor
        if idx < len(state.replay_steps):
            cached = state.replay_steps[idx]
            state.replay_cursor += 1
            print(f"  [PROXY REPLAY] step {current_step} jira/assign {req.ticket_id} → cache (pas de vrai appel)")
            if state.mode == "WHATIF":
                save_step("tool_call", req.model_dump(), cached.output_payload)
            return cached.output_payload

    # ── MODE RECORD ou WHATIF après injection ─────────────────────────────────
    result = jira.assign_ticket(req.ticket_id, req.team, req.priority)
    print(f"  [PROXY RECORD] step {current_step} jira/assign {req.ticket_id} → {req.team}/{req.priority}")
    save_step("tool_call", req.model_dump(), result)
    return result


# ── ENDPOINTS INFO ────────────────────────────────────────────────────────────

@app.get("/runs")
def list_runs():
    runs = db.list_runs(limit=20)
    return {"runs": [vars(r) for r in runs]}

@app.get("/runs/{run_id}")
def get_run(run_id: str):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} introuvable")
    steps = db.get_steps(run_id)
    return {"run": vars(run), "steps": [vars(s) for s in steps]}

@app.get("/runs/{run_id}/diff/{whatif_run_id}")
def get_diff(run_id: str, whatif_run_id: str):
    return db.compute_diff(run_id, whatif_run_id)

@app.get("/stats")
def get_stats():
    return db.get_stats()


# ── UI ROUTER ────────────────────────────────────────────────────────────────
from api.routes import router as ui_router
app.include_router(ui_router)


@app.get("/")
def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/ui/runs")
