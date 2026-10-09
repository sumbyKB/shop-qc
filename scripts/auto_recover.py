"""Low-frequency recovery watcher: probe the reviews endpoint every 10 min (single request).
When TikTok's endpoint recovers, harvest the pending product and build the report.
Also records whether the previously-working lipstick product is restored (compat check)."""
import json
import subprocess
import sys
import time
from pathlib import Path

SKILL = Path(r"D:\code\codeMy\shop-qc\.claude\skills\tiktok-review-harvest\scripts")
TARGET_PID = "1732081180796228517"   # hiking pants (pending)
CANARY_PID = "1732394770018636376"   # lipstick (worked this morning)

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


def probe(pid, url):
    from playwright.sync_api import sync_playwright
    body = {"product_id": pid, "page_start": 1, "page_size": 20, "sort_rule": 1,
            "review_filter": {"filter_type": 1, "filter_value": 6},
            "component_name": "pdp_left_reviews"}
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://127.0.0.1:9334")
        ctx = b.contexts[0]
        page = None
        for pg in ctx.pages:
            if pid in pg.url:
                page = pg
                break
        if page is None:
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(7000)
        raw = page.evaluate(FETCH, body)
        d = json.loads(raw)
        return d.get("code"), len((d.get("data") or {}).get("product_reviews", []))


def main():
    canary_url = f"https://shop.tiktok.com/us/pdp/{CANARY_PID}"
    target_url = f"https://shop.tiktok.com/us/pdp/{TARGET_PID}"
    deadline = time.time() + 6 * 3600  # watch for up to 6 hours
    n = 0
    while time.time() < deadline:
        n += 1
        try:
            code, cnt = probe(TARGET_PID, target_url)
            print(f"[watch {n} @ {time.strftime('%H:%M:%S')}] target code={code} n={cnt}",
                  flush=True)
            if code == 0 and cnt > 0:
                # compat check once with the canary product
                try:
                    ccode, ccnt = probe(CANARY_PID, canary_url)
                    print(f"[compat canary] code={ccode} n={ccnt}", flush=True)
                except Exception as e:
                    print(f"[compat canary] error {str(e)[:80]}", flush=True)
                print("[recovered] running full harvest + report for target", flush=True)
                r = subprocess.run([sys.executable, str(SKILL / "tiktok_reviews.py"),
                                    "all", TARGET_PID],
                                   cwd=r"D:\code\codeMy\shop-qc")
                print(f"[all] exit={r.returncode}", flush=True)
                return
        except Exception as e:
            print(f"[watch {n}] error {str(e)[:100]}", flush=True)
        time.sleep(600)
    print("[watch] 6h elapsed, endpoint still down. Stopping watcher.", flush=True)


if __name__ == "__main__":
    main()
