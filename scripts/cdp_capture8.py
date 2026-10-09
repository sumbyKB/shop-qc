"""v8: scroll inner container to review list bottom, find 'see more'/pagination, click, capture all APIs."""
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"D:\code\codeMy\shop-qc\probe\us_cdp")
req_log = []


def on_response(resp):
    url = resp.url
    if "tiktok" not in url or "/api/" not in url:
        return
    if any(x in url for x in (".png", ".jpg", ".webp", ".js", ".css", ".woff", "monitor",
                              "mcs", "tobid", "settings", "report", "telemetry", "teling",
                              "register", "verify", "captcha", "security")):
        return
    entry = {"status": resp.status, "method": resp.request.method, "url": url[:500],
             "post_data": (resp.request.post_data or "")[:2500]}
    req_log.append(entry)
    i = url.find("/api/")
    print(f"[api] {resp.request.method} {resp.status} {url[i:i+90]}", flush=True)


def cdp_shot(ctx, page, name):
    try:
        cdp = ctx.new_cdp_session(page)
        r = cdp.send("Page.captureScreenshot", {"format": "png"})
        (OUT / name).write_bytes(r and __import__("base64").b64decode(r["data"]))
        print(f"[shot] {name}", flush=True)
    except Exception as e:
        print(f"[shot skip] {name}: {str(e)[:70]}", flush=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9333")
        ctx = browser.contexts[0]
        page = [pg for pg in ctx.pages if "pdp" in pg.url.lower()][0]
        page.on("response", on_response)
        page.bring_to_front()
        page.wait_for_timeout(500)

        # scroll the app container to review area, then to list bottom
        page.evaluate("""() => {
            const sc = document.querySelector('.overflow-y-scroll');
            if (sc) { const card = [...sc.querySelectorAll('*')].find(e => (e.textContent||'').includes('LOVE this purse'));
                if (card) card.scrollIntoView({block: 'start'}); }
        }""")
        page.wait_for_timeout(1500)

        # scroll container progressively to its very bottom
        for i in range(6):
            page.evaluate("""() => {
                const sc = document.querySelector('.overflow-y-scroll');
                if (sc) sc.scrollTop += sc.clientHeight * 0.9;
            }""")
            page.wait_for_timeout(900)
        cdp_shot(ctx, page, "v8_list_bottom.png")

        # inventory of clickable things near list bottom
        cand = page.evaluate("""() => {
            const sc = document.querySelector('.overflow-y-scroll');
            const out = [];
            for (const e of (sc ? sc.querySelectorAll('button, [role=button], a') : [])) {
                const cs = getComputedStyle(e);
                if (cs.display === 'none' || cs.visibility === 'hidden' || !e.offsetParent) continue;
                const t = (e.textContent || '').trim().replace(/\\s+/g, ' ');
                const r = e.getBoundingClientRect();
                if (t && t.length <= 40 && r.y > 300)
                    out.push({tag: e.tagName, text: t.slice(0, 36), y: Math.round(r.y),
                              cls: (e.className || '').toString().slice(0, 44)});
            }
            return out;
        }""")
        print(f"[clickables] {json.dumps(cand, ensure_ascii=False)[:1600]}", flush=True)

        # click the most promising entry: 查看更多 / see more / next / page numbers
        import re
        clicked = None
        pri = [r"查看更多评价", r"查看更多", r"更多评价", r"see more review", r"view more",
               r"next", r"下一页", r"^\d{1,4}$"]
        for pat in pri:
            for c in cand:
                if re.search(pat, c["text"], re.I):
                    try:
                        loc = page.locator(f"{c['tag'].lower()}:has-text('{c['text'][:20]}')").last
                        loc.click(timeout=5000)
                        clicked = c
                        print(f"[clicked] {c}", flush=True)
                        break
                    except Exception as e:
                        print(f"[click fail] {c['text']}: {str(e)[:60]}", flush=True)
            if clicked:
                break
        page.wait_for_timeout(4000)
        cdp_shot(ctx, page, "v8_after_click.png")
        n1 = len(req_log)
        print(f"[after click] new api calls: {n1}", flush=True)

        (OUT / "v8_requests.json").write_text(
            json.dumps(req_log, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[done] api_calls={n1} clicked={bool(clicked)}", flush=True)


if __name__ == "__main__":
    main()
