"""
Tests du proxy — sans démarrer le serveur FastAPI.
Teste uniquement la logique de ProxyState et les endpoints
via le TestClient de FastAPI.
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

from fastapi.testclient import TestClient
from core.proxy import app, state

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "mode" in data
    print(f"PASS : health → mode={data['mode']}")


def test_set_mode_record():
    r = client.post("/mode", json={"mode": "RECORD"})
    assert r.status_code == 200
    data = r.json()
    assert data["mode"] == "RECORD"
    assert "run_id" in data
    assert data["run_id"] is not None
    print(f"PASS : set_mode_record → run_id={data['run_id']}")


def test_mode_unknown_returns_400():
    r = client.post("/mode", json={"mode": "INVALID"})
    assert r.status_code == 400
    print("PASS : mode_unknown_returns_400")


def test_replay_without_run_id_returns_400():
    r = client.post("/mode", json={"mode": "REPLAY"})
    assert r.status_code == 400
    print("PASS : replay_without_run_id_returns_400")


def test_replay_unknown_run_returns_404():
    r = client.post("/mode", json={"mode": "REPLAY", "run_id": "nonexistent"})
    assert r.status_code == 404
    print("PASS : replay_unknown_run_returns_404")


def test_stats_endpoint():
    r = client.get("/stats")
    assert r.status_code == 200
    data = r.json()
    assert "total_runs" in data
    assert "total_steps" in data
    print(f"PASS : stats → {data}")


def test_list_runs():
    r = client.get("/runs")
    assert r.status_code == 200
    data = r.json()
    assert "runs" in data
    assert isinstance(data["runs"], list)
    print(f"PASS : list_runs → {len(data['runs'])} runs")


def test_complete_run():
    # Crée un run RECORD d'abord
    r = client.post("/mode", json={"mode": "RECORD"})
    run_id = r.json()["run_id"]
    # Complete
    r2 = client.post("/run/complete")
    assert r2.status_code == 200
    print(f"PASS : complete_run → {r2.json()}")


def run_all():
    print("JiraGuard — Tests Proxy")
    print("=" * 50)
    tests = [
        test_health,
        test_set_mode_record,
        test_mode_unknown_returns_400,
        test_replay_without_run_id_returns_400,
        test_replay_unknown_run_returns_404,
        test_stats_endpoint,
        test_list_runs,
        test_complete_run,
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
    print(f"Résultat : {passed} passés | {failed} échoués")
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
