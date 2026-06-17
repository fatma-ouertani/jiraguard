"""
JiraGuard — Génération automatique des captures d'écran (headless).
Rend les 4 pages clés de l'UI en PNG dans docs/screenshots/.

Prérequis : proxy démarré sur http://localhost:8000 avec données seedées.
Usage : python scripts/capture_screenshots.py <RECORD_ID> <WHATIF_ID>
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8000"
OUT = Path(__file__).parent.parent / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

REC = sys.argv[1] if len(sys.argv) > 1 else "6206c1c0"
WI = sys.argv[2] if len(sys.argv) > 2 else "06ab38c9"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        # 1. Liste des runs
        page.goto(f"{BASE}/ui/runs", wait_until="networkidle")
        page.screenshot(path=str(OUT / "01_runs_list.png"), full_page=True)
        print("OK 01_runs_list.png")

        # 2. Timeline du run RECORD
        page.goto(f"{BASE}/ui/runs/{REC}", wait_until="networkidle")
        page.screenshot(path=str(OUT / "02_run_timeline.png"), full_page=True)
        print("OK 02_run_timeline.png")

        # 3. Même page, premier step déplié (input/output)
        details = page.locator("details").first
        details.locator("summary").click()
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "03_step_detail.png"), full_page=True)
        print("OK 03_step_detail.png")

        # 4. Vue diff (JSM-001 FIXED)
        page.goto(f"{BASE}/ui/diff/{REC}/{WI}", wait_until="networkidle")
        page.screenshot(path=str(OUT / "04_diff_view.png"), full_page=True)
        print("OK 04_diff_view.png")

        browser.close()


if __name__ == "__main__":
    main()
