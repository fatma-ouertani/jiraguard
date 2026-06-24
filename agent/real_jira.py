"""
JiraGuard — Real Jira Client
Connexion au vrai Jira Cloud via REST API v3.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests
import json
import base64
from pathlib import Path

# Charge un .env local (gitignoré) si présent, avant de lire les variables.
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "")
JIRA_EMAIL    = os.environ.get("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "")


def _auth_header() -> dict:
    creds = base64.b64encode(
        f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()
    ).decode()
    return {
        "Authorization": f"Basic {creds}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }


def _get(path: str) -> dict:
    url = f"{JIRA_BASE_URL}/rest/api/3{path}"
    r = requests.get(url, headers=_auth_header(), timeout=15)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict) -> dict:
    url = f"{JIRA_BASE_URL}/rest/api/3{path}"
    r = requests.post(url, headers=_auth_header(),
                      json=body, timeout=15)
    r.raise_for_status()
    return r.json()


def _put(path: str, body: dict) -> dict:
    url = f"{JIRA_BASE_URL}/rest/api/3{path}"
    r = requests.put(url, headers=_auth_header(),
                     json=body, timeout=15)
    r.raise_for_status()
    return r.json() if r.content else {}


class RealJiraClient:
    """Client Jira Cloud REST API v3."""

    def __init__(self):
        self.base_url   = JIRA_BASE_URL
        self.email      = JIRA_EMAIL
        self.api_token  = JIRA_API_TOKEN
        self.project_key = None

    def test_connection(self) -> dict:
        """Vérifie que les credentials fonctionnent."""
        try:
            data = _get("/myself")
            return {
                "success": True,
                "user": data.get("displayName"),
                "email": data.get("emailAddress"),
                "account_id": data.get("accountId"),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_projects(self) -> list:
        """Liste tous les projets accessibles."""
        data = _get("/project")
        return [
            {"key": p["key"], "name": p["name"], "id": p["id"]}
            for p in data
        ]

    def get_or_create_project(self, key: str = "JG",
                               name: str = "JiraGuard Demo") -> dict:
        """Récupère ou crée le projet de démo."""
        try:
            data = _get(f"/project/{key}")
            self.project_key = data["key"]
            return {"key": data["key"], "name": data["name"], "created": False}
        except Exception:
            pass

        try:
            me = _get("/myself")
            account_id = me["accountId"]
            body = {
                "key": key,
                "name": name,
                "projectTypeKey": "software",
                "projectTemplateKey":
                    "com.pyxis.greenhopper.jira:gh-scrum-template",
                "description": "JiraGuard Hackathon Demo Project",
                "leadAccountId": account_id,
                "assigneeType": "UNASSIGNED",
            }
            data = _post("/project", body)
            self.project_key = data["key"]
            return {"key": data["key"], "name": name, "created": True}
        except Exception as e:
            return {"error": str(e)}

    def create_ticket(self, title: str, description: str,
                      issue_type: str = "Bug") -> dict:
        """Crée un vrai ticket Jira."""
        if not self.project_key:
            raise ValueError("Project key not set. Call get_or_create_project first.")

        body = {
            "fields": {
                "project":     {"key": self.project_key},
                "summary":     title,
                "description": {
                    "type":    "doc",
                    "version": 1,
                    "content": [{
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}]
                    }]
                },
                "issuetype": {"name": issue_type},
            }
        }
        data = _post("/issue", body)
        return {
            "success": True,
            "issue_key": data["key"],
            "issue_id":  data["id"],
            "url": f"{self.base_url}/browse/{data['key']}",
        }

    def update_labels(self, issue_key: str,
                      team: str, priority_label: str) -> dict:
        """Met à jour les labels d'un ticket avec team et priority."""
        body = {
            "fields": {
                "labels": [
                    f"team:{team}",
                    f"priority-assessed:{priority_label}",
                    "jiraguard-processed",
                ]
            }
        }
        try:
            _put(f"/issue/{issue_key}", body)
            return {
                "success": True,
                "issue_key": issue_key,
                "labels_set": body["fields"]["labels"],
            }
        except Exception as e:
            return {"success": False, "error": str(e),
                    "issue_key": issue_key}

    def add_comment(self, issue_key: str, comment: str) -> dict:
        """Ajoute un commentaire sur un ticket."""
        body = {
            "body": {
                "type": "doc", "version": 1,
                "content": [{
                    "type": "paragraph",
                    "content": [{"type": "text", "text": comment}]
                }]
            }
        }
        data = _post(f"/issue/{issue_key}/comment", body)
        return {"success": True, "comment_id": data.get("id")}

    def get_ticket(self, issue_key: str) -> dict:
        """Récupère un ticket par sa clé."""
        data = _get(f"/issue/{issue_key}")
        fields = data.get("fields", {})
        return {
            "key":         data["key"],
            "summary":     fields.get("summary", ""),
            "status":      fields.get("status", {}).get("name", ""),
            "labels":      fields.get("labels", []),
            "issue_type":  fields.get("issuetype", {}).get("name", ""),
            "url":         f"{self.base_url}/browse/{data['key']}",
        }

    def evaluate_assignments(self, assignments: list,
                              tickets: list) -> dict:
        """
        Compare les assignations de l'agent avec expected_team/priority.
        assignments : [{"ticket_id": "JG-1", "team": "backend", ...}]
        tickets : liste des tickets avec expected_team/priority
        """
        ticket_map = {t["id"]: t for t in tickets}
        results = []
        for a in assignments:
            tid  = a.get("ticket_id", "")
            orig = ticket_map.get(tid, {})
            team_ok = a.get("team") == orig.get("expected_team")
            prio_ok = a.get("priority") == orig.get("expected_priority")
            results.append({
                "ticket_id":         tid,
                "team_correct":      team_ok,
                "priority_correct":  prio_ok,
                "fully_correct":     team_ok and prio_ok,
                "assigned_team":     a.get("team"),
                "expected_team":     orig.get("expected_team"),
                "assigned_priority": a.get("priority"),
                "expected_priority": orig.get("expected_priority"),
            })
        total   = len(results)
        correct = sum(1 for r in results if r["fully_correct"])
        return {
            "total":             total,
            "correct":           correct,
            "accuracy":          round(correct / total, 2) if total else 0,
            "team_accuracy":     round(
                sum(1 for r in results if r["team_correct"]) / total, 2
            ) if total else 0,
            "priority_accuracy": round(
                sum(1 for r in results if r["priority_correct"]) / total, 2
            ) if total else 0,
            "details": results,
        }


jira_client = RealJiraClient()
