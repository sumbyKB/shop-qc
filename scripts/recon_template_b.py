"""Recon template B: capture ALL /api/ requests during full page lifecycle."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"D:\code\codeMy\shop-qc\probe\demo")
URL = "https://shop.tiktok.com/us/pdp/insulated-waterproof-hiking-pants-by-fallfreshness-fleece-lined-4-zippered-pockets-windproof-outdoor/1732081180796228517"

seen = []


def main():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://127.0.0.1:9333")
        ctx = b.contexts[0]
        page = [pg for pg in ctx.pages if "1732081180796228517" in pg.url][0]
        page.bring_to_front()

        def on_req(req):
            u = req.url
            if "/api/" not in u:
                return
            if any(x in u for x in (".png", ".jpg", ".webp", ".js", ".css", ".woff",
                                    "monitor", "mcs", "tobid", "telemetry", "report")):
                return
            api_path = u[u.find("/api/"):].split("?")[0]
            seen.append({"method": req.method, "api": api_path,
                         "qs": u.split("?")[1][:200] if "?" in u else "",
                         "post": (req.post_data or "")[:600]})

        page.on("request", on_req)
        page.reload(wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(10000)
        n_after_load = len(seen)
        print(f"[after load] api requests: {n_after_load}", flush=True)

        # scroll to review section
        page.evaluate("""() => {
            const sc = document.querySelector('.overflow-y-scroll') || document.scrollingElement;
            const anchor = [...sc.querySelectorAll('*')].find(e =>
                /条全球评价|条评价|reviews/i.test((e.textContent||'')) && e.textContent.length < 60);
            if (anchor) anchor.scrollIntoView({block: 'start'});
        }""")
        page.wait_for_timeout(4000)
        print(f"[after scroll] total: {len(seen)}", flush=True)

        # click the rating summary header (may open review modal)
        try:
            loc = page.locator("text=/44 条全球评价|条全球评价/").first
            loc.click(timeout=5000)
            print("[clicked] rating summary header", flush=True)
        except Exception as e:
            print(f"[click fail] {str(e)[:80]}", flush=True)
        page.wait_for_timeout(6000)
        print(f"[after click] total: {len(seen)}", flush=True)

        (OUT / "all_api_requests.json").write_text(
            json.dumps(seen, ensure_ascii=False, indent=1), encoding="utf-8")
        for s in seen:
            print(f"  {s['method']:4} {s['api'][:70]} post={len(s['post'])}B", flush=True)


if __name__ == "__main__":
    main()
