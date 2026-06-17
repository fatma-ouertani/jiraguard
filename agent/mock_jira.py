import json
import random
from datetime import datetime
from pathlib import Path

TICKETS_PATH = Path(__file__).parent.parent / "data" / "tickets.json"

class MockJiraAPI:
    """
    Simule l'API Jira pour la démo.
    Stocke les assignations en mémoire pour pouvoir les comparer
    avec les expected_team/expected_priority de tickets.json.
    """
    def __init__(self):
        self.assignments = {}   # ticket_id -> {team, priority, timestamp}
        self.comments    = {}   # ticket_id -> [comment, ...]
        self.call_log    = []   # historique de tous les appels

    def assign_ticket(self, ticket_id: str, team: str, priority: str) -> dict:
        entry = {
            "ticket_id": ticket_id,
            "team": team,
            "priority": priority,
            "timestamp": datetime.now().isoformat(),
            "success": True,
            "jira_response": "Issue updated successfully",
            "mock": True
        }
        self.assignments[ticket_id] = entry
        self.call_log.append({"action": "assign", **entry})
        return entry

    def add_comment(self, ticket_id: str, comment: str, visibility: str = "internal") -> dict:
        if ticket_id not in self.comments:
            self.comments[ticket_id] = []
        entry = {
            "ticket_id": ticket_id,
            "comment": comment,
            "visibility": visibility,
            "timestamp": datetime.now().isoformat(),
            "success": True,
            "mock": True
        }
        self.comments[ticket_id].append(entry)
        self.call_log.append({"action": "comment", **entry})
        return entry

    def get_ticket(self, ticket_id: str) -> dict:
        """Retourne un ticket depuis tickets.json."""
        with open(TICKETS_PATH) as f:
            tickets = json.load(f)
        ticket = next((t for t in tickets if t["id"] == ticket_id), None)
        if not ticket:
            return {"error": f"Ticket {ticket_id} not found"}
        result = dict(ticket)
        if ticket_id in self.assignments:
            result["current_assignment"] = self.assignments[ticket_id]
        return result

    def evaluate_assignments(self, tickets: list) -> dict:
        """
        Compare les assignations de l'agent avec expected_team/expected_priority.
        Retourne les métriques d'évaluation pour le rapport hackathon.
        """
        results = []
        for t in tickets:
            tid = t["id"]
            if tid not in self.assignments:
                continue
            assigned = self.assignments[tid]
            team_ok     = assigned["team"]     == t.get("expected_team")
            priority_ok = assigned["priority"] == t.get("expected_priority")
            results.append({
                "ticket_id":        tid,
                "team_correct":     team_ok,
                "priority_correct": priority_ok,
                "fully_correct":    team_ok and priority_ok,
                "assigned_team":    assigned["team"],
                "expected_team":    t.get("expected_team"),
                "assigned_priority":assigned["priority"],
                "expected_priority":t.get("expected_priority"),
            })
        total   = len(results)
        correct = sum(1 for r in results if r["fully_correct"])
        return {
            "total":             total,
            "correct":           correct,
            "accuracy":          round(correct / total, 2) if total else 0,
            "team_accuracy":     round(sum(1 for r in results if r["team_correct"])     / total, 2) if total else 0,
            "priority_accuracy": round(sum(1 for r in results if r["priority_correct"]) / total, 2) if total else 0,
            "details":           results,
        }

# Instance globale utilisée par l'agent
jira = MockJiraAPI()
