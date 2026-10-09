"""After cooldown, probe the reviews endpoint once; if unblocked, run full harvest + report."""
import json
import subprocess
import sys
import time
from pathlib import Path

PID = "1732081180796228517"
SKILL = Path(r"D:\code\codeMy\shop-qc\.claude\skills\tiktok-review-harvest\scripts")
sys.path.insert(0, str(SKILL))

print(f"[wait] cooling down 12 min from {time.strftime('%H:%M:%S')}...", flush=True)
time.sleep(720)

from playwright.sync_api import sync_playwright  # noqa: E402

FETCH = """async (body) => {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 15000);
    try {
        const r = await fetch('/api/shop/pdp_desktop/get_product_reviews', {
            method: 'POST', headers: {'content-type': 'application/json'},
            body: JSON.stringify(body), signal: ctrl.signal});
        clearTimeout(timer);
        return await r.text();
    } catch (e) { clearTimeout(timer); return String(e); }
}"""
BODY = {"product_id": PID, "page_start": 1, "page_size": 50, "sort_rule": 1,
        "review_filter": {"filter_type": 1, "filter_value": 6},
        "component_name": "pdp_left_reviews"}

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9333")
    ctx = b.contexts[0]
    page = None
    for pg in ctx.pages:
        if PID in pg.url:
            page = pg
            break
    if page is None:
        page = ctx.new_page()
        page.goto(f"https://shop.tiktok.com/us/pdp/{PID}",
                  wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
    raw = page.evaluate(FETCH, BODY)
    d = json.loads(raw)
    revs = (d.get("data") or {}).get("product_reviews", [])
    print(f"[probe] code={d.get('code')} n={len(revs)} total={(d.get('data') or {}).get('total_reviews')}",
          flush=True)

if d.get("code") == 0 and revs:
    print("[probe] unblocked -> running full harvest + report", flush=True)
    r = subprocess.run([sys.executable, str(SKILL / "tiktok_reviews.py"), "all", PID],
                       cwd=r"D:\code\codeMy\shop-qc")
    print(f"[all] exit={r.returncode}", flush=True)
else:
    print("[probe] STILL THROTTLED. Will need a longer cooldown.", flush=True)
