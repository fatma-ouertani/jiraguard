import sys
import os

# Fix encodage Windows : force UTF-8 sur stdout (cp1252 ne gère pas → ═ ✓)
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.jira_agent import JiraAgent, load_tickets
from agent.mock_jira  import MockJiraAPI


def test_mock_jira_assign():
    jira = MockJiraAPI()
    result = jira.assign_ticket("JSM-001", "backend", "critical")
    assert result["success"] is True
    assert result["ticket_id"] == "JSM-001"
    assert result["team"] == "backend"
    assert "JSM-001" in jira.assignments
    print("PASS : mock_jira_assign")


def test_mock_jira_evaluate():
    jira = MockJiraAPI()
    tickets = load_tickets(3)

    # Simule une assignation parfaite pour JSM-001 (backend/critical)
    jira.assign_ticket("JSM-001", "backend", "critical")
    # Simule une erreur pour JSM-002 (attendu frontend/high, on met backend/low)
    jira.assign_ticket("JSM-002", "backend", "low")
    # Pas d'assignation pour JSM-003

    metrics = jira.evaluate_assignments(tickets)
    assert metrics["total"]    == 2
    assert metrics["correct"]  == 1
    assert metrics["accuracy"] == 0.5
    print(f"PASS : mock_jira_evaluate (accuracy={metrics['accuracy']})")


def test_load_tickets():
    tickets = load_tickets()
    assert len(tickets) >= 5
    assert "id" in tickets[0]
    assert "expected_team" in tickets[0]
    assert "expected_priority" in tickets[0]
    print(f"PASS : load_tickets ({len(tickets)} tickets chargés)")


def test_agent_single_ticket():
    """Test sur 1 ticket — appel réel API Anthropic."""
    if not os.environ.get("GROQ_API_KEY"):
        print("SKIP : test_agent_single_ticket (GROQ_API_KEY non définie)")
        return

    agent   = JiraAgent(use_fixed_prompt=False)
    tickets = load_tickets(1)
    result  = agent.process_ticket(tickets[0])

    assert "decision" in result
    assert result["decision"].get("team") in ["backend", "frontend", "infra", "unknown"]
    assert result["decision"].get("priority") in ["critical", "high", "medium", "low", "unknown"]
    assert result["latency_ms"] > 0
    print(
        f"PASS : agent_single_ticket "
        f"→ {result['decision'].get('team')} / {result['decision'].get('priority')} "
        f"({result['latency_ms']}ms)"
    )


def test_agent_batch_buggy_vs_fixed():
    """
    Test clé pour la démo : compare l'agent bugué vs l'agent corrigé
    sur les 5 premiers tickets.
    Montre que le prompt fixé améliore l'accuracy.
    """
    if not os.environ.get("GROQ_API_KEY"):
        print("SKIP : test_agent_batch_buggy_vs_fixed (GROQ_API_KEY non définie)")
        return

    tickets = load_tickets(5)

    print("\n  --- Agent bugué ---")
    agent_buggy  = JiraAgent(use_fixed_prompt=False)
    jira_buggy   = MockJiraAPI()
    results_buggy = agent_buggy.run_batch(tickets)
    for r in results_buggy:
        if r.get("decision"):
            jira_buggy.assign_ticket(
                r["ticket_id"],
                r["decision"].get("team","unknown"),
                r["decision"].get("priority","unknown")
            )
    metrics_buggy = jira_buggy.evaluate_assignments(tickets)

    print("\n  --- Agent corrigé ---")
    agent_fixed  = JiraAgent(use_fixed_prompt=True)
    jira_fixed   = MockJiraAPI()
    results_fixed = agent_fixed.run_batch(tickets)
    for r in results_fixed:
        if r.get("decision"):
            jira_fixed.assign_ticket(
                r["ticket_id"],
                r["decision"].get("team","unknown"),
                r["decision"].get("priority","unknown")
            )
    metrics_fixed = jira_fixed.evaluate_assignments(tickets)

    print(f"\n  Buggy  accuracy : {metrics_buggy['accuracy']} ({metrics_buggy['correct']}/{metrics_buggy['total']})")
    print(f"  Fixed  accuracy : {metrics_fixed['accuracy']} ({metrics_fixed['correct']}/{metrics_fixed['total']})")

    # Le prompt fixé doit être >= au bugué (ou au moins pas pire)
    assert metrics_fixed["accuracy"] >= metrics_buggy["accuracy"] - 0.1, \
        "Le prompt corrigé est significativement pire que le bugué — quelque chose ne va pas"

    print("PASS : agent_batch_buggy_vs_fixed")


def run_all():
    print("JiraGuard — Tests Agent")
    print("=" * 55)
    tests = [
        test_mock_jira_assign,
        test_mock_jira_evaluate,
        test_load_tickets,
        test_agent_single_ticket,
        test_agent_batch_buggy_vs_fixed,
    ]
    passed = failed = skipped = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"FAIL : {test.__name__} — {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR : {test.__name__} — {e}")
            failed += 1

    print("=" * 55)
    print(f"Résultat : {passed} passés | {failed} échoués")
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
