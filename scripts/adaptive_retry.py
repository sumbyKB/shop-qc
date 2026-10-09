"""Adaptive probe: every 75s one lightweight request; on first unblock -> full harvest."""
import json
import subprocess
import sys
import time
from pathlib import Path

PID = "1732081180796228517"
SKILL = Path(r"D:\code\codeMy\shop-qc\.claude\skills\tiktok-review-harvest\scripts")

FETCH = """async (body) => {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 12000);
    try {
        const r = await fetch('/api/shop/pdp_desktop/get_product_reviews', {
            method: 'POST', headers: {'content-type': 'application/json'},
            body: JSON.stringify(body), signal: ctrl.signal});
        clearTimeout(timer);
        return await r.text();
    } catch (e) { clearTimeout(timer); return String(e); }
}"""
BODY = {"product_id": PID, "page_start": 1, "page_size": 20, "sort_rule": 1,
        "review_filter": {"filter_type": 1, "filter_value": 6},
        "component_name": "pdp_left_reviews"}

page = None


def probe_once(pw_browser_url):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(pw_browser_url)
        ctx = b.contexts[0]
        global page
        page = None
        for pg in ctx.pages:
            if PID in pg.url:
                page = pg
                break
        if page is None:
            page = ctx.new_page()
            page.goto(f"https://shop.tiktok.com/us/pdp/{PID}",
                      wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(6000)
        raw = page.evaluate(FETCH, BODY)
    return json.loads(raw)


def main():
    cdp = "http://127.0.0.1:9333"
    started = time.time()
    attempt = 0
    while time.time() - started < 900:  # give up after 15 min total
        attempt += 1
        try:
            d = probe_once(cdp)
            revs = (d.get("data") or {}).get("product_reviews", [])
            ok = d.get("code") == 0 and revs
            print(f"[probe {attempt} @ {time.strftime('%H:%M:%S')}] code={d.get('code')} "
                  f"n={len(revs)}", flush=True)
        except Exception as e:
            print(f"[probe {attempt}] error {str(e)[:100]}", flush=True)
            ok = False
        if ok:
            print("[unblocked] running full harvest + report", flush=True)
            r = subprocess.run([sys.executable, str(SKILL / "tiktok_reviews.py"), "all", PID],
                               cwd=r"D:\code\codeMy\shop-qc")
            print(f"[all] exit={r.returncode}", flush=True)
            return
        time.sleep(75)
    print("[give up] still throttled after 15 min of adaptive probing", flush=True)


if __name__ == "__main__":
    main()
