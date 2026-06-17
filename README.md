# JiraGuard
### Agent Execution Tracer & Deterministic Replay Engine
**AINS Hackathon 2026 — Use Case 2**

> A transparent proxy that records every LLM call and Jira action
> of an AI agent, then lets you replay it deterministically
> and test corrections safely — without touching production.

---

## The Problem

When a Jira triage agent fails silently in production
(wrong team assigned, wrong priority set), you cannot simply
re-run it to debug:
- The LLM responds differently every time
- Re-running triggers real side effects on real tickets
- Simple logs don't capture LLM reasoning or tool call context

## The Solution — 3 Modes

| Mode | What it does |
|------|-------------|
| RECORD | Transparently intercepts and logs every LLM call + Jira action |
| REPLAY | Re-executes the exact run from cache — zero real API calls |
| WHAT-IF | Injects a correction at step N, observes trajectory divergence |

## Live Demo Results

Run `531ff000` (buggy prompt) vs `08ebda4e` (what-if fixed):

| Ticket | Buggy decision | Fixed decision | Result |
|--------|---------------|----------------|--------|
| JSM-001 `/api/payments` | frontend / high | backend / critical | FIXED |
| JSM-002 Safari button | frontend / medium | frontend / medium | unchanged |
| JSM-003 DB disk 95% | infra / critical | infra / critical | unchanged |
| JSM-004 CSS broken | frontend / medium | frontend / medium | unchanged |
| JSM-005 `/api/users` data | frontend / medium | frontend / medium | unchanged |

**The bug:** prompt rule said "anything mentioning API → frontend"
**The fix:** injected corrected rule "/api/* routes → backend"
**Validated without deploying a single line of code.**

## Evaluation Metrics

| Metric | Result |
|--------|--------|
| Replay Determinism Rate | 100% (3/3 replays identical) |
| Side-Effect Prevention | 100% (5 LLM calls RECORD, 0 in REPLAY) |
| What-If Accuracy Gain | +20% overall (0.40 → 0.60) |
| Test Coverage | 19/19 tests passing |

## Architecture
Agent → [JiraGuard Proxy] → Groq API (LLM)

↓                    ↓

Trace Store          Jira API (mock)

(SQLite)

↓

Replay / What-If Engine

↓

Debug UI

/ui/runs  /ui/runs/{id}  /ui/diff/{a}/{b}

## Project Structure
core/

trace_store.py   # SQLite ORM — stores every step

proxy.py         # FastAPI proxy — RECORD/REPLAY/WHATIF

agent/

jira_agent.py    # Triage agent (buggy + fixed prompts)

mock_jira.py     # Realistic Jira API mock

api/

routes.py        # Debug UI — 3 screens

data/

tickets.json     # 10 synthetic Jira tickets

evaluation_report.md

tests/

test_core.py     # 6/6

test_proxy.py    # 8/8

test_agent.py    # 5/5

main.py            # End-to-end demo script

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Set API key (Groq — free at console.groq.com)
$env:GROQ_API_KEY = "gsk_..."

# Terminal 1 — start proxy
uvicorn core.proxy:app --port 8000

# Terminal 2 — run demo
python main.py

# Open UI
http://localhost:8000/ui/runs
```

## Acceptance Criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Record functionality | DONE | run 531ff000 — 10 steps captured |
| Deterministic replay | DONE | 3/3 replays byte-identical |
| State inspection | DONE | /ui/runs/531ff000 — full timeline |
| Divergence editing | DONE | run 08ebda4e — JSM-001 FIXED badge |

---
*Built for AINS Hackathon 2026 — Use Case 2*
*Stack: Python, FastAPI, SQLite, Groq (llama-3.1-8b-instant)*
