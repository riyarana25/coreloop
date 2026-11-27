"""Capture real screenshots of the running app (synthetic data) for the deck.
Usage: streamlit run ui/app.py --server.port 8599 &  then  python presentation/capture_screens.py"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "screens"
BASE = "http://localhost:8599/?page="
PAGES = ["operations-overview", "core-inventory", "shipment-optimisation", "credit-monitoring",
         "dispute-queue", "audit-frequency-simulator", "audit-trail"]

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1500, "height": 1150})
    for slug in PAGES:
        pg.goto(BASE + slug)
        pg.wait_for_selector("h2", timeout=60000)
        pg.wait_for_timeout(3500)
        pg.screenshot(path=str(OUT / f"{slug}.png"), full_page=False)
        print("saved", slug)
    b.close()
