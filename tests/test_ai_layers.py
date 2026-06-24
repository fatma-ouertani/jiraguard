import sys, os
sys.path.insert(0, os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
))
if sys.stdout.encoding and \
   sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
from core.trace_store import db, Step
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc)\
                   .replace(tzinfo=None).isoformat()


def test_ai_evaluator_import():
    from core.ai_evaluator import AIEvaluator
    ev = AIEvaluator()
    assert ev.model == "llama-3.1-8b-instant"
    print("PASS : ai_evaluator_import")


def test_metrics_import():
    from core.metrics import MetricsDashboard
    d = MetricsDashboard()
    assert d is not None
    print("PASS : metrics_import")


def test_evaluate_step_no_api():
    """Test sans appel API — step avec données synthétiques."""
    from core.ai_evaluator import AIEvaluator
    ev = AIEvaluator()
    run = db.create_run(mode="RECORD",
                        agent_version="test")
    step = Step(
        run_id=run.id, step_number=1,
        step_type="llm_call",
        input_payload={"system": "test", "messages": []},
        output_payload={"content": '{"team":"backend","priority":"critical"}'},
        latency_ms=300,
        timestamp=_now(),
    )
    db.save_step(step)
    if not os.environ.get("GROQ_API_KEY"):
        print("SKIP : evaluate_step (no GROQ_API_KEY)")
        return
    result = ev.evaluate_step(step, "backend", "critical")
    assert "quality" in result
    assert "confidence" in result
    assert 0.0 <= result["confidence"] <= 1.0
    print(f"PASS : evaluate_step → quality={result['quality']}"
          f" confidence={result['confidence']}")


def test_replay_fidelity_identical():
    """Test fidelité avec steps identiques."""
    from core.ai_evaluator import AIEvaluator
    ev = AIEvaluator()
    run = db.create_run(mode="RECORD",
                        agent_version="test")
    steps = []
    for i in range(2):
        s = Step(
            run_id=run.id, step_number=i+1,
            step_type="tool_call",
            input_payload={"ticket_id": f"JSM-00{i+1}",
                           "team": "backend",
                           "priority": "critical"},
            output_payload={"team": "backend",
                            "priority": "critical",
                            "success": True},
            latency_ms=50, timestamp=_now(),
        )
        db.save_step(s)
        steps.append(s)
    result = ev.evaluate_replay_fidelity(steps, steps)
    assert result["replay_fidelity_score"] == 1.0
    assert result["fully_faithful"] is True
    print(f"PASS : replay_fidelity_identical → "
          f"score={result['replay_fidelity_score']}")


def run_all():
    print("JiraGuard — Tests AI Layers")
    print("=" * 50)
    tests = [
        test_ai_evaluator_import,
        test_metrics_import,
        test_evaluate_step_no_api,
        test_replay_fidelity_identical,
    ]
    passed = failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"FAIL : {test.__name__} — {e}")
            failed += 1
    print("=" * 50)
    print(f"Resultat : {passed} passes | {failed} echoues")
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    import sys
    sys.exit(0 if success else 1)
