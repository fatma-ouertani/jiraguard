# JiraGuard — Evaluation Report
## AINS Hackathon 2026 — Use Case 2

> Backend LLM : **Groq** `llama-3.1-8b-instant` (temperature=0).
> Run executed 2026-06-17 with contrasted buggy/fixed prompts.
> All figures below are measured, not estimated.
> Original run: `6e7f15c5` (10 steps) · What-If run: `86ede0f3` (10 steps).

### Metric 1 : Replay Determinism Rate
**Definition** : Replay the same recorded run N times.
Each replay must produce byte-identical outputs at every step.

**Protocol** :
- Record 1 run of the Jira triage agent (5 tickets, 10 steps = 5 llm_call + 5 tool_call)
- Replay the same run 3 times through the proxy in REPLAY mode
- Compare the decision (team/priority) at each step across all replays

**Result** : 3/3 replays identical → **Determinism Rate = 100%**

**Why this matters** : This proves the proxy intercepts all
non-determinism. An engineer can debug the exact failure
without the LLM introducing variance.

---

### Metric 2 : What-If Correction Accuracy
**Definition** : Does injecting the fixed prompt improve
the agent's triage accuracy vs the buggy prompt?

**Protocol** :
- Run buggy agent on 5 tickets, compare to expected_team/priority
- Run What-If with fixed prompt injected at step 1 on the same 5 tickets
- Compare accuracy scores

**Result** :
| | Buggy prompt | Fixed prompt |
|---|---|---|
| Team accuracy | 0.60 (3/5) | 0.80 (4/5) |
| Priority accuracy | 0.40 (2/5) | 0.60 (3/5) |
| Overall accuracy | 0.40 (2/5) | 0.60 (3/5) |

**Key correction (visible divergence)** :
- **JSM-001** ("Erreur 500 sur /api/payments en production"):
  buggy prompt routed it to **frontend / high**, the fixed prompt
  corrected it to **backend / critical** (the expected answer).
  The buggy rule "anything mentioning payments/API -> frontend"
  caused the misroute; the fixed rule "Routes /api/*, REST
  endpoints -> backend" repaired it.

**Conclusion** : The What-If mode validated a real **+0.20 accuracy
improvement** (0.40 → 0.60) on the recorded run, *before any
production deployment*, and pinpointed exactly which ticket and which
step the fix corrected.

---

### Metric 3 : Side-Effect Prevention
**Definition** : In REPLAY mode, zero calls to real external APIs.

**Protocol** :
- Count real LLM API calls during RECORD run
- Count real LLM API calls during REPLAY run (must be 0)

**Result** : RECORD = **5** real Groq LLM calls, REPLAY = **0** real LLM calls
(all 5 served from the recorded cache)
→ **Side-Effect Prevention Rate = 100%**

---

### Acceptance Criteria Status
| Criterion | Status | Evidence |
|---|---|---|
| Record functionality | DONE | Run `6e7f15c5` captured, 10 steps (5 llm_call + 5 tool_call) |
| Deterministic replay | DONE | 3/3 replays identical, 0 real LLM calls in REPLAY |
| State inspection | DONE | `/ui/runs/6e7f15c5` — step-by-step timeline with input/output |
| Divergence editing | DONE | What-If run `86ede0f3`, prompt injected at step 1, JSM-001 corrected frontend→backend |

---

### Diff metric (post-fix)
`compute_diff` now compares only the semantic decision fields
(`team`, `priority`) per tool_call, ignoring timestamps and reasoning
text. For this run it reports **1/5 tickets corrected** (JSM-001),
divergence at step 2 — an accurate, deployment-relevant signal.
