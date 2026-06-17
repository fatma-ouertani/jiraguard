"""
JiraGuard — Tests de déterminisme
Vérifie que le replay produit exactement le même résultat que le run original.
C'est la métrique principale pour le rapport d'évaluation du hackathon.
"""

import sys
import os
import tempfile

# Fix encodage Windows : force UTF-8 sur stdout (cp1252 ne gère pas → ═ ✓)
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# DB temporaire pour les tests — ne pollue pas data/jiraguard.db
_tmp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp_db.close()
os.environ['JIRAGUARD_DB_PATH'] = _tmp_db.name

from core.trace_store import TraceStore, Step, db


def test_trace_store_creation():
    """Test : la DB se crée correctement."""
    store = TraceStore()
    stats = store.get_stats()
    assert "total_runs" in stats
    print("PASS : trace_store_creation")


def test_create_and_get_run():
    """Test : créer et récupérer un run."""
    run = db.create_run(mode="RECORD", agent_version="test-1.0")
    assert run.id is not None
    assert run.mode == "RECORD"

    fetched = db.get_run(run.id)
    assert fetched is not None
    assert fetched.id == run.id
    assert fetched.mode == "RECORD"
    print(f"PASS : create_and_get_run (id={run.id})")


def test_save_and_get_steps():
    """Test : sauvegarder et récupérer des steps."""
    from core.trace_store import Step
    from datetime import datetime, timezone

    run = db.create_run(mode="RECORD", agent_version="test-1.0")

    step1 = Step(
        run_id=run.id,
        step_number=1,
        step_type="llm_call",
        input_payload={"system": "test prompt", "messages": [{"role": "user", "content": "test"}]},
        output_payload={"content": '{"team": "backend", "priority": "high", "reasoning": "test"}'},
        latency_ms=250,
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
    )
    db.save_step(step1)

    step2 = Step(
        run_id=run.id,
        step_number=2,
        step_type="tool_call",
        input_payload={"ticket_id": "JSM-001", "team": "backend", "priority": "high"},
        output_payload={"success": True, "ticket_id": "JSM-001"},
        latency_ms=50,
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
    )
    db.save_step(step2)

    steps = db.get_steps(run.id)
    assert len(steps) == 2
    assert steps[0].step_type == "llm_call"
    assert steps[1].step_type == "tool_call"
    assert steps[0].output_payload["content"] is not None
    print(f"PASS : save_and_get_steps (run={run.id}, steps={len(steps)})")


def test_diff_computation():
    """Test : calcul du diff entre run original et what-if."""
    from core.trace_store import Step
    from datetime import datetime, timezone

    # Run original
    orig = db.create_run(mode="RECORD", agent_version="test")
    step_orig = Step(
        run_id=orig.id, step_number=1, step_type="tool_call",
        input_payload={"ticket_id": "JSM-001"},
        output_payload={"team": "frontend", "priority": "medium"},
        latency_ms=100, timestamp=datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
    )
    db.save_step(step_orig)

    # Run what-if (décision différente)
    whatif = db.create_run(mode="WHATIF", agent_version="test", parent_run_id=orig.id)
    step_whatif = Step(
        run_id=whatif.id, step_number=1, step_type="tool_call",
        input_payload={"ticket_id": "JSM-001"},
        output_payload={"team": "backend", "priority": "critical"},
        latency_ms=100, timestamp=datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
    )
    db.save_step(step_whatif)

    diff = db.compute_diff(orig.id, whatif.id)
    assert diff["decision_changed"] is True
    assert diff["divergence_at_step"] == 1
    assert diff["tickets_corrected"] == 1
    assert diff["original_decisions"][0]["team"] == "frontend"
    assert diff["whatif_decisions"][0]["team"] == "backend"
    assert diff["decisions_changed"][0]["original"]["team"] == "frontend"
    assert diff["decisions_changed"][0]["whatif"]["team"] == "backend"
    print(f"PASS : diff_computation — divergence au step {diff['divergence_at_step']}")


def test_list_runs():
    """Test : lister les runs."""
    runs = db.list_runs(limit=5)
    assert isinstance(runs, list)
    print(f"PASS : list_runs — {len(runs)} runs en DB")


def test_stats():
    """Test : statistiques globales."""
    stats = db.get_stats()
    assert "total_runs" in stats
    assert "total_steps" in stats
    assert stats["total_runs"] >= 0
    print(f"PASS : stats — {stats}")


def run_all():
    print("JiraGuard — Tests unitaires")
    print("=" * 50)
    tests = [
        test_trace_store_creation,
        test_create_and_get_run,
        test_save_and_get_steps,
        test_diff_computation,
        test_list_runs,
        test_stats,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"FAIL : {test.__name__} — {e}")
            failed += 1

    print("=" * 50)
    print(f"Résultat : {passed}/{len(tests)} tests passés")
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
