"""
JiraGuard — Trace Store
Base de données SQLite qui stocke chaque step de chaque run d'agent.
C'est la mémoire centrale de tout le système.
"""

import os
import sqlite3
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict


DB_PATH = Path(
    os.environ.get('JIRAGUARD_DB_PATH',
    str(Path(__file__).parent.parent / "data" / "jiraguard.db"))
)


@dataclass
class Step:
    run_id: str
    step_number: int
    step_type: str          # "llm_call" | "tool_call" | "memory_snapshot"
    input_payload: dict
    output_payload: dict
    latency_ms: int
    timestamp: str
    injected: bool = False  # True si modifié en mode What-If
    id: Optional[int] = None


@dataclass
class Run:
    id: str
    started_at: str
    mode: str               # "RECORD" | "REPLAY" | "WHATIF"
    agent_version: str
    total_steps: int = 0
    parent_run_id: Optional[str] = None   # pour les runs What-If
    injection_step: Optional[int] = None  # step où l'injection a eu lieu
    ended_at: Optional[str] = None
    status: str = "running"  # "running" | "completed" | "failed"


class TraceStore:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    started_at TIMESTAMP NOT NULL,
                    ended_at TIMESTAMP,
                    mode TEXT NOT NULL,
                    agent_version TEXT NOT NULL,
                    total_steps INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running',
                    parent_run_id TEXT,
                    injection_step INTEGER,
                    FOREIGN KEY (parent_run_id) REFERENCES runs(id)
                );

                CREATE TABLE IF NOT EXISTS steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    step_number INTEGER NOT NULL,
                    step_type TEXT NOT NULL,
                    input_payload TEXT NOT NULL,
                    output_payload TEXT NOT NULL,
                    latency_ms INTEGER DEFAULT 0,
                    injected BOOLEAN DEFAULT FALSE,
                    timestamp TIMESTAMP NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs(id)
                );

                CREATE INDEX IF NOT EXISTS idx_steps_run_id ON steps(run_id);
                CREATE INDEX IF NOT EXISTS idx_runs_parent ON runs(parent_run_id);
            """)

    # ─── RUNS ───────────────────────────────────────────────────────────────

    def create_run(
        self,
        mode: str = "RECORD",
        agent_version: str = "1.0",
        parent_run_id: Optional[str] = None,
        injection_step: Optional[int] = None,
    ) -> Run:
        run = Run(
            id=str(uuid.uuid4())[:8],
            started_at=datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            mode=mode,
            agent_version=agent_version,
            parent_run_id=parent_run_id,
            injection_step=injection_step,
        )
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO runs
                   (id, started_at, mode, agent_version, status, parent_run_id, injection_step)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (run.id, run.started_at, run.mode, run.agent_version,
                 run.status, run.parent_run_id, run.injection_step),
            )
        return run

    def complete_run(self, run_id: str, status: str = "completed"):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE runs SET ended_at=?, status=? WHERE id=?",
                (datetime.now(timezone.utc).replace(tzinfo=None).isoformat(), status, run_id),
            )
            count = conn.execute(
                "SELECT COUNT(*) FROM steps WHERE run_id=?", (run_id,)
            ).fetchone()[0]
            conn.execute(
                "UPDATE runs SET total_steps=? WHERE id=?", (count, run_id)
            )

    def get_run(self, run_id: str) -> Optional[Run]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE id=?", (run_id,)
            ).fetchone()
        if not row:
            return None
        return Run(**dict(row))

    def list_runs(self, limit: int = 20) -> list[Run]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [Run(**dict(r)) for r in rows]

    # ─── STEPS ──────────────────────────────────────────────────────────────

    def save_step(self, step: Step) -> Step:
        with self._get_conn() as conn:
            cursor = conn.execute(
                """INSERT INTO steps
                   (run_id, step_number, step_type, input_payload, output_payload,
                    latency_ms, injected, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    step.run_id,
                    step.step_number,
                    step.step_type,
                    json.dumps(step.input_payload, ensure_ascii=False),
                    json.dumps(step.output_payload, ensure_ascii=False),
                    step.latency_ms,
                    step.injected,
                    step.timestamp,
                ),
            )
            step.id = cursor.lastrowid
        return step

    def get_steps(self, run_id: str) -> list[Step]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM steps WHERE run_id=? ORDER BY step_number ASC",
                (run_id,),
            ).fetchall()
        steps = []
        for row in rows:
            d = dict(row)
            d["input_payload"] = json.loads(d["input_payload"])
            d["output_payload"] = json.loads(d["output_payload"])
            steps.append(Step(**d))
        return steps

    def get_step(self, run_id: str, step_number: int) -> Optional[Step]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM steps WHERE run_id=? AND step_number=?",
                (run_id, step_number),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["input_payload"] = json.loads(d["input_payload"])
        d["output_payload"] = json.loads(d["output_payload"])
        return Step(**d)

    # ─── DIFF (What-If) ─────────────────────────────────────────────────────

    def compute_diff(self, original_run_id: str, whatif_run_id: str) -> dict:
        orig_steps = self.get_steps(original_run_id)
        new_steps  = self.get_steps(whatif_run_id)

        def extract_decision(step):
            """Extrait uniquement team/priority d'un tool_call."""
            if step.step_type != "tool_call":
                return None
            p = step.output_payload
            team = p.get("team") or p.get("updated_fields", {}).get("team")
            prio = p.get("priority") or p.get("updated_fields", {}).get("priority")
            if team and prio:
                return {"team": team, "priority": prio}
            return None

        divergence_at = None
        decisions_changed = []

        for i, (o, n) in enumerate(zip(orig_steps, new_steps)):
            orig_dec = extract_decision(o)
            new_dec  = extract_decision(n)
            if orig_dec and new_dec and orig_dec != new_dec:
                if divergence_at is None:
                    divergence_at = i + 1
                decisions_changed.append({
                    "step": i + 1,
                    "original": orig_dec,
                    "whatif":   new_dec,
                })

        # Décisions finales des tool_calls
        orig_tool_calls = [s for s in orig_steps if s.step_type == "tool_call"]
        new_tool_calls  = [s for s in new_steps  if s.step_type == "tool_call"]

        orig_decisions = [extract_decision(s) for s in orig_tool_calls]
        new_decisions  = [extract_decision(s) for s in new_tool_calls]

        return {
            "original_run_id":      original_run_id,
            "whatif_run_id":        whatif_run_id,
            "divergence_at_step":   divergence_at,
            "total_orig_steps":     len(orig_steps),
            "total_whatif_steps":   len(new_steps),
            "original_decisions":   orig_decisions,
            "whatif_decisions":     new_decisions,
            "decisions_changed":    decisions_changed,
            "decision_changed":     len(decisions_changed) > 0,
            "tickets_corrected":    len(decisions_changed),
        }

    # ─── STATS ──────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        with self._get_conn() as conn:
            total_runs = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            record_runs = conn.execute(
                "SELECT COUNT(*) FROM runs WHERE mode='RECORD'"
            ).fetchone()[0]
            whatif_runs = conn.execute(
                "SELECT COUNT(*) FROM runs WHERE mode='WHATIF'"
            ).fetchone()[0]
            total_steps = conn.execute("SELECT COUNT(*) FROM steps").fetchone()[0]
            injected_steps = conn.execute(
                "SELECT COUNT(*) FROM steps WHERE injected=TRUE"
            ).fetchone()[0]
        return {
            "total_runs": total_runs,
            "record_runs": record_runs,
            "whatif_runs": whatif_runs,
            "total_steps": total_steps,
            "injected_steps": injected_steps,
        }


# ─── INSTANCE GLOBALE ───────────────────────────────────────────────────────
db = TraceStore()
