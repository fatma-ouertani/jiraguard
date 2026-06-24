# JiraGuard — Dataset Description
## AINS Hackathon 2026

---

## Overview

JiraGuard uses a synthetic dataset of Jira-style
incident tickets for agent evaluation. The dataset
is designed to test AI triage accuracy across 3
engineering teams and 4 priority levels.

---

## Source

**Type:** 100% synthetic — no real data, no PII.

**Creation method:** Manually crafted to represent
realistic enterprise IT incidents based on common
patterns documented in:
- ITIL v4 incident classification guidelines
- Common software engineering incident categories
  (backend API errors, frontend UI bugs,
  infrastructure failures)
- Real-world Jira ticket patterns from public
  engineering post-mortems

**Sensitivity:** None. All emails use the fictional
`@acme.com` domain. All names, ticket IDs, and
descriptions are invented. GDPR-compliant by
construction.

---

## Format

**File:** `data/tickets.json`
**Format:** JSON array
**Size:** 10 tickets
**Encoding:** UTF-8

---

## Schema

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | string | Local ticket identifier | `JSM-001` |
| `title` | string | Short incident summary | `Erreur 500 sur /api/payments` |
| `description` | string | Detailed incident description | Full text |
| `reporter` | string | Fictional reporter email | `alice@acme.com` |
| `expected_team` | string | Ground truth team label | `backend` |
| `expected_priority` | string | Ground truth priority label | `critical` |

---

## Labels (Ground Truth)

### Teams (3 categories)
| Label | Description | Ticket count |
|-------|-------------|--------------|
| `backend` | Server-side errors, API failures, data corruption | 3 |
| `frontend` | UI bugs, CSS issues, browser compatibility | 4 |
| `infra` | Infrastructure, deployment, certificates, monitoring | 3 |

### Priorities (4 levels)
| Label | Description | Ticket count |
|-------|-------------|--------------|
| `critical` | Production down, data loss, security breach | 4 |
| `high` | Major feature broken, significant impact | 3 |
| `medium` | Degraded functionality, workaround exists | 2 |
| `low` | Feature request, cosmetic issue | 1 |

---

## Distribution

The dataset reflects a realistic incident mix:
- **Critical incidents are over-represented** (4/10 = 40%)
  because they expose the most dangerous agent errors —
  a misrouted critical ticket is the worst failure mode.
- **Frontend is the largest team class** (4 tickets;
  backend and infra have 3 each). The buggy prompt's rule
  "anything mentioning API → frontend" causes it to
  over-assign frontend, so backend API tickets
  (e.g. JSM-001 `/api/payments`) are precisely where the
  bug surfaces and the What-If correction is validated.

---

## Atlassian Integration

When `USE_REAL_JIRA=true`, each local ticket is
mapped to a real Jira Cloud issue via
`data/jira_ticket_map.json` (gitignored).

The mapping links:
- `JSM-001` → `JG-1` (https://[site].atlassian.net/browse/JG-1)
- `JSM-002` → `JG-2`
- ...

After each RECORD run, JiraGuard writes real labels
to the Jira Cloud tickets:
- `team:backend` (or frontend/infra)
- `priority-assessed:critical` (or high/medium/low)
- `jiraguard-processed`

---

## Quality Notes

| Aspect | Status |
|--------|--------|
| PII | None — all data fictional |
| Bias | Intentional class imbalance (see Distribution) |
| Coverage | 3 teams × 4 priorities = 12 combinations, 10 tickets |
| Limitations | Small dataset (10 tickets) — sufficient for demo, not production evaluation |
| Extension | Can be extended to 50+ tickets by adding entries to `tickets.json` following the same schema |

---

## Usage in Evaluation

```python
# Load tickets
import json
with open("data/tickets.json") as f:
    tickets = json.load(f)

# Ground truth labels used by:
# - M1 (Triage Accuracy)
# - M3 (What-If Improvement)
# - M4 (AI Step Quality — expected_team/priority passed to evaluator)
```
