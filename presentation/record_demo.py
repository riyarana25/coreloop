"""Record a captioned screen demo of the running app (synthetic data) to presentation/CoreLoop_demo.mp4.
Usage: streamlit run ui/app.py --server.port 8599 &  (fresh data/coreloop_demo.sqlite)  then  python presentation/record_demo.py"""
import subprocess
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent
URL = "http://localhost:8599/?page=operations-overview"
tmp = Path(tempfile.mkdtemp())

CAP_JS = """(t) => { let d = document.getElementById('cap'); if(!d){d=document.createElement('div'); d.id='cap';
 d.style.cssText='position:fixed;left:50%;bottom:22px;transform:translateX(-50%);z-index:999999;background:#12263A;color:#fff;padding:12px 22px;border-radius:10px;font:600 19px Calibri,Arial,sans-serif;max-width:1100px;text-align:center;box-shadow:0 4px 14px rgba(0,0,0,.3)'; document.body.appendChild(d);} d.textContent=t; }"""

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1400, "height": 900}, record_video_dir=str(tmp), record_video_size={"width": 1400, "height": 900})
    pg = ctx.new_page()
    cap = lambda t: pg.evaluate(CAP_JS, t)
    nav = lambda name: pg.get_by_text(name, exact=True).first.click()
    pg.goto(URL); pg.wait_for_selector("h2", timeout=60000); pg.wait_for_timeout(2500)
    cap("Synthetic dealership, day 130: 115 open cores, 18 need action, 31 windows already missed ($9.2k forfeited)")
    pg.wait_for_timeout(6500)
    nav("Shipment optimisation"); pg.wait_for_timeout(2500)
    cap("42 unshipped cores need only 3 shipments to meet every OEM window")
    pg.wait_for_timeout(5000)
    pg.mouse.wheel(0, 500); pg.wait_for_timeout(1500)
    cap("Counterfactual: waiting one more day saves $11 of freight and forfeits two cores ($672)")
    pg.wait_for_timeout(6000)
    pg.mouse.wheel(0, 700); pg.wait_for_timeout(1500)
    cap("Core 76 has zero days left: ship today")
    pg.wait_for_timeout(2500)
    pg.get_by_role("button", name="Ship today").first.click(); pg.wait_for_timeout(4000)
    cap("The alert is gone: the decision changed state and was saved")
    pg.wait_for_timeout(3500)
    nav("Credit monitoring"); pg.wait_for_timeout(2500)
    cap("Slow vs missing credit: wait while it is safe, using each OEM's own posting history")
    pg.wait_for_timeout(6500)
    nav("Dispute queue"); pg.wait_for_timeout(2500)
    cap("Disputes ordered by expected value per staff minute; drafts built from ledger facts")
    try:
        pg.get_by_text("Draft dispute text").first.click(timeout=15000)
    except Exception:
        pg.screenshot(path="/tmp/fail.png"); raise
    pg.wait_for_timeout(5500)
    for _ in range(2):
        pg.get_by_role("button", name="Submit").first.click(); pg.wait_for_timeout(2500)
    cap("Two disputes submitted. Advancing the simulated clock by 7 days")
    pg.wait_for_timeout(2500)
    pg.get_by_role("button", name="+7d").click(); pg.wait_for_timeout(3000)
    pg.mouse.wheel(0, 3000); pg.wait_for_timeout(1500)
    cap("Outcomes are simulated from hidden draws that never reach the classifier")
    pg.wait_for_timeout(5500)
    nav("Audit-frequency simulator"); pg.wait_for_timeout(3000)
    cap("Versus 90- and 30-day audits the gain is large; versus weekly it is staff time (30.2 vs 134.8 h)")
    pg.wait_for_timeout(7500)
    nav("Audit trail"); pg.wait_for_timeout(2500)
    cap("Every decision is logged and survives a restart. All data synthetic.")
    pg.wait_for_timeout(5000)
    ctx.close(); b.close()
vid = next(tmp.glob("*.webm"))
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(vid), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "26", str(OUT / "CoreLoop_demo.mp4")], check=True)
print("saved", OUT / "CoreLoop_demo.mp4")
