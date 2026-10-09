"""v10: click pagination page-2, capture full request details of the fired API call."""
import base64
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"D:\code\codeMy\shop-qc\probe\us_cdp")
req_log = []


def on_response(resp):
    url = resp.url
    if "get_product_reviews" not in url:
        return
    req = resp.request
    entry = {"method": req.method, "status": resp.status, "url": url,
             "post_data": req.post_data,
             "resource_type": req.resource_type}
    try:
        body = resp.text()
        d = json.loads(body)["data"]
        entry["n_reviews"] = len(d.get("product_reviews", []))
        entry["first_id"] = d["product_reviews"][0]["review_id"] if d.get("product_reviews") else None
        entry["has_more"] = d.get("has_more")
        fn = OUT / f"v10_p2.json"
        fn.write_text(body, encoding="utf-8")
        entry["body_file"] = fn.name
    except Exception as e:
        entry["err"] = str(e)[:150]
    req_log.append(entry)
    safe = {k: (v[:200] if isinstance(v, str) else v) for k, v in entry.items() if k != "url"}
    print(f"[api] {json.dumps(safe, ensure_ascii=False)[:400]}", flush=True)
    print(f"[api-url] {url[:600]}", flush=True)


def shot(ctx, page, name):
    try:
        cdp = ctx.new_cdp_session(page)
        r = cdp.send("Page.captureScreenshot", {"format": "png"})
        (OUT / name).write_bytes(base64.b64decode(r["data"]))
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

        # scroll pagination row into view
        page.evaluate("""() => {
            const sc = document.querySelector('.overflow-y-scroll');
            const leafs = [...sc.querySelectorAll('*')].filter(e => e.childElementCount === 0 && e.textContent.trim() === '2'
                && getComputedStyle(e).display !== 'none');
            const el = leafs.find(e => { const r = e.getBoundingClientRect(); return r.x < 720; });
            if (el) el.scrollIntoView({block: 'center'});
        }""")
        page.wait_for_timeout(1500)
        shot(ctx, page, "v10_pagi_before.png")

        # click the '2' page digit
        clicked = page.evaluate("""() => {
            const sc = document.querySelector('.overflow-y-scroll');
            const leafs = [...sc.querySelectorAll('*')].filter(e => e.childElementCount === 0 && e.textContent.trim() === '2'
                && getComputedStyle(e).display !== 'none');
            const el = leafs.find(e => { const r = e.getBoundingClientRect(); return r.x < 720 && r.y > 0 && r.y < 900; });
            if (!el) return 'pagination-2 not in viewport';
            const t = el.closest('button,[role=button],li,div,a,span');
            (t || el).click();
            return 'clicked ' + (t ? t.tagName : el.tagName);
        }""")
        print(f"[click] {clicked}", flush=True)
        page.wait_for_timeout(4000)
        shot(ctx, page, "v10_pagi_after.png")

        (OUT / "v10_requests.json").write_text(
            json.dumps(req_log, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[done] api_calls={len(req_log)}", flush=True)


if __name__ == "__main__":
    main()
