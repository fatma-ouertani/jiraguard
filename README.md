# JiraGuard
### Agent Execution Tracer & Deterministic Replay Engine

**AINS Hackathon 2026 — Use Case 2**
**Team:** Fatma Ouertani
**Stack:** Python · FastAPI · SQLite · Groq (llama-3.1-8b-instant)

---

## Problem Statement

Enterprise teams deploy AI agents that operate non-deterministically.
When a Jira triage agent silently misroutes a critical ticket —
wrong team, wrong priority — debugging is impossible with
conventional tools:

- Re-running the agent produces different LLM outputs every time
- Re-running also triggers real side effects (emails sent, tickets modified)
- Standard log files capture outputs but not LLM reasoning or context

**JiraGuard solves this** with a transparent proxy that acts as a
"flight recorder" for AI agents — record everything, replay safely,
test corrections before deploying anything.

---

## Proposed Solution

A 3-mode infrastructure layer that wraps any AI agent:

### Mode RECORD — Silent Observer
The proxy transparently intercepts every LLM call and every
Jira API action. The agent doesn't know it's being recorded.
Every prompt, every response, every tool call is stored with
exact payloads in SQLite.

### Mode REPLAY — Deterministic Sandbox
Load any past run and replay it. The proxy returns cached
responses instead of calling real APIs.
**Zero real LLM calls. Zero side effects. 100% deterministic.**

### Mode WHAT-IF — Surgical Correction
Replay up to step N, inject a correction (modified prompt or
tool response), let the agent continue freely.
Observe exactly how the trajectory diverges from the original.

---

## Target Users

| User | Problem JiraGuard solves |
|------|--------------------------|
| AI Engineers | Debug agent failures without re-running in production |
| Platform Teams | Audit every agent decision with full context |
| Compliance Officers | Replay any past run — exact state snapshot |

---

## Core AI Mechanism

JiraGuard cannot function without AI. The proxy is designed
specifically for non-deterministic LLM agents:

- **Trajectory recording** captures the full reasoning chain,
  not just inputs/outputs
- **Deterministic replay** is only meaningful because the
  underlying system (LLM) is non-deterministic — the proxy
  freezes that non-determinism
- **What-If divergence** only makes sense in an agent context
  where prompt changes alter multi-step reasoning chains

Remove the AI component and the system has nothing to record,
nothing to replay, and no divergence to observe.

---

## Technical Architecture
Jira Triage Agent (Python)

|

v

[JiraGuard Proxy — FastAPI]  <-- core of the system

|              |

v              v

Groq LLM API    Jira API (mock)

|

v

Trace Store (SQLite)

runs table + steps table

|

v

Replay / What-If Engine

|

v

Debug UI  (/ui/runs · /ui/runs/{id} · /ui/diff/{a}/{b})

**Data flow:**
- RECORD: Agent → Proxy → Real APIs → Trace Store
- REPLAY: Agent → Proxy → Trace Store (no real API calls)
- WHATIF: Agent → Proxy → Trace Store until step N,
          then inject correction → Proxy → Real APIs

---

## Project Structure
jiraguard/

├── core/

│   ├── trace_store.py    # SQLite ORM — stores every run + step

│   └── proxy.py          # FastAPI proxy — 3 modes

├── agent/

│   ├── jira_agent.py     # Triage agent (buggy + fixed prompts)

│   └── mock_jira.py      # Realistic Jira API mock + evaluator

├── api/

│   └── routes.py         # Debug UI — timeline, diff view

├── data/

│   ├── tickets.json      # 10 synthetic Jira tickets

│   └── evaluation_report.md

├── tests/

│   ├── test_core.py      # 6/6 passing

│   ├── test_proxy.py     # 8/8 passing

│   └── test_agent.py     # 5/5 passing

├── main.py               # End-to-end demo: RECORD→REPLAY→WHATIF

└── requirements.txt

---

## Demo Scenario

**The bug:** Agent system prompt has no rule for `/api/*` routes.
Rule says: *"anything mentioning payments, users, API → frontend"*

**The crime:** JSM-001 ("Erreur 500 sur /api/payments en production")
gets assigned `frontend / high` instead of `backend / critical`.
No error fires. The ticket silently reaches the wrong team.

**The investigation:** Open JiraGuard UI. Find the run.
Inspect Step 1 — see the exact prompt that caused the wrong decision.

**The What-If fix:** Inject corrected prompt at Step 1.
Agent re-routes JSM-001 → `backend / critical`.
**Zero real Jira modifications during the entire debug session.**

---

## Evaluation Metric

**Replay Determinism Rate** — the primary metric:

```python
# Replay the same run 3 times, compare output at every step
results = [replay(run_id) for _ in range(3)]
assert all(r == results[0] for r in results)
# → Determinism Rate = 100%
```

| Metric | Result |
|--------|--------|
| Replay Determinism Rate | **100%** (3/3 replays identical) |
| Side-Effect Prevention | **100%** (5 LLM calls RECORD, 0 in REPLAY) |
| What-If Accuracy Gain | **+20%** (0.40 → 0.60 overall accuracy) |
| JSM-001 correction | frontend/high → backend/critical |
| Test coverage | **19/19** tests passing |

---

## Current Status (First Submission)

### Already implemented and tested
- Trace Store (SQLite) — full schema, 6/6 tests passing
- FastAPI Proxy — RECORD mode capturing LLM + tool calls
- REPLAY mode — deterministic, zero real API calls
- WHAT-IF mode — injection + diff computation
- Jira triage agent — buggy prompt + fixed prompt
- Mock Jira API — realistic responses + accuracy evaluator
- Debug UI — run list, step timeline, diff view
- End-to-end demo script (main.py)
- 19/19 unit tests passing

### Planned for final submission
- Extended test set (20 tickets instead of 5)
- Evaluation report with full statistical analysis
- Demo video walkthrough (5 minutes)
- Architecture diagram (final version)

---

## Setup & Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Get a free Groq API key at console.groq.com
#    Set environment variable (never commit the key)
$env:GROQ_API_KEY = "gsk_..."   # PowerShell
export GROQ_API_KEY="gsk_..."   # bash/zsh

# 3. Terminal 1 — start the proxy
uvicorn core.proxy:app --port 8000

# 4. Terminal 2 — run the full demo
python main.py

# 5. Open the debug UI
# http://localhost:8000/ui/runs
```

---

## Acceptance Criteria Coverage

| Criterion | Priority | Status | Evidence |
|-----------|----------|--------|----------|
| Record functionality | MUST | DONE | 10 steps captured per run |
| Deterministic replay | MUST | DONE | 3/3 replays identical |
| State inspection | MUST | DONE | /ui/runs/{id} full timeline |
| Divergence editing | SHOULD | DONE | JSM-001 FIXED badge in diff UI |

---

## Why This Cannot Exist Without AI

JiraGuard is infrastructure built specifically for the properties
of LLM-based agents: non-determinism, context sensitivity,
and multi-step reasoning chains.

A conventional logging system captures outputs.
JiraGuard captures the mechanism — the exact reasoning state
that produced each decision — and freezes it for safe replay.

The intelligence is not a feature bolted on.
It is the reason the system exists.

---

*AINS Hackathon 2026 — Use Case 2: Agent Execution Tracer
and Deterministic Replay Engine*
