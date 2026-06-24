"""
JiraGuard — Setup Jira
Crée le projet et les tickets de démo dans Jira Cloud.
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from agent.real_jira import RealJiraClient
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

TICKETS_PATH = Path("data/tickets.json")
JIRA_MAP_PATH = Path("data/jira_ticket_map.json")


def main():
    client = RealJiraClient()

    print("1. Test de connexion Jira...")
    conn = client.test_connection()
    if not conn["success"]:
        print(f"ERREUR connexion : {conn['error']}")
        print("Verifie JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN")
        sys.exit(1)
    print(f"   Connecte en tant que : {conn['user']} ({conn['email']})")

    print("\n2. Projet JiraGuard Demo...")
    proj = client.get_or_create_project(key="JG", name="JiraGuard Demo")
    if "error" in proj:
        print(f"   Erreur creation projet : {proj['error']}")
        print("   Tentative avec les projets existants...")
        projects = client.get_projects()
        if projects:
            proj = projects[0]
            client.project_key = proj["key"]
            print(f"   Utilise projet existant : {proj['key']} - {proj['name']}")
        else:
            print("   Aucun projet disponible.")
            sys.exit(1)
    else:
        action = "cree" if proj.get("created") else "existant"
        print(f"   Projet {action} : {proj['key']} - {proj['name']}")

    print("\n3. Chargement des tickets locaux...")
    with open(TICKETS_PATH) as f:
        local_tickets = json.load(f)
    print(f"   {len(local_tickets)} tickets a creer")

    print("\n4. Creation des vrais tickets Jira...")
    ticket_map = {}
    for ticket in local_tickets:
        result = client.create_ticket(
            title=ticket["title"],
            description=ticket.get("description", ticket["title"]),
            issue_type="Bug",
        )
        if result.get("success"):
            ticket_map[ticket["id"]] = {
                "jira_key":         result["issue_key"],
                "url":              result["url"],
                "local_id":         ticket["id"],
                "expected_team":    ticket.get("expected_team"),
                "expected_priority":ticket.get("expected_priority"),
                "title":            ticket["title"],
            }
            print(f"   {ticket['id']} -> {result['issue_key']} ({result['url']})")
        else:
            print(f"   ERREUR {ticket['id']} : {result}")

    with open(JIRA_MAP_PATH, "w", encoding="utf-8") as f:
        json.dump(ticket_map, f, indent=2, ensure_ascii=False)

    print(f"\n5. Mapping sauvegarde dans {JIRA_MAP_PATH}")
    print(f"\nResultat : {len(ticket_map)}/{len(local_tickets)} tickets crees dans Jira")
    print(f"\nVois tes tickets sur : {client.base_url}/jira/software/projects/{client.project_key}/boards")


if __name__ == "__main__":
    main()
