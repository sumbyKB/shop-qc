"""v11: locate pagination row by digit-cluster, click page 2, capture API."""
import base64
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"D:\code\codeMy\shop-qc\probe\us_cdp")
req_log = []


def on_response(resp):
    if "get_product_reviews" not in resp.url:
        return
    req = resp.request
    entry = {"method": req.method, "status": resp.status, "url": resp.url,
             "post_data": req.post_data}
    try:
        d = json.loads(resp.text())["data"]
        revs = d.get("product_reviews", [])
        entry["n_reviews"] = len(revs)
        entry["first_id"] = revs[0]["review_id"] if revs else None
        entry["has_more"] = d.get("has_more")
        (OUT / "v10_p2.json").write_text(resp.text(), encoding="utf-8")
        entry["body_file"] = "v10_p2.json"
    except Exception as e:
        entry["err"] = str(e)[:150]
    req_log.append(entry)
    safe = {k: (v[:260] if isinstance(v, str) else v) for k, v in entry.items() if k != "url"}
    print(f"[api] {json.dumps(safe, ensure_ascii=False)[:450]}", flush=True)


def shot(ctx, page, name):
    try:
        cdp = ctx.new_cdp_session(page)
        r = cdp.send("Page.captureScreenshot", {"format": "png"})
        (OUT / name).write_bytes(base64.b64decode(r["data"]))
        print(f"[shot] {name}", flush=True)
    except Exception as e:
        print(f"[shot skip] {name}: {str(e)[:70]}", flush=True)


FIND_ROW = """() => {
    const sc = document.querySelector('.overflow-y-scroll');
    const digitLeafs = [];
    for (const e of sc.querySelectorAll('*')) {
        if (e.childElementCount !== 0) continue;
        const t = (e.textContent || '').trim();
        const cs = getComputedStyle(e);
        if (!/^\\d{1,4}$/.test(t) || cs.display === 'none' || cs.visibility === 'hidden') continue;
        const r = e.getBoundingClientRect();
        if (r.x > 720) continue;
        digitLeafs.push({el: e, text: t, x: r.x, y: r.y});
    }
    // cluster by y (within 6px)
    const rows = {};
    for (const d of digitLeafs) {
        const key = Math.round(d.y / 6);
        (rows[key] = rows[key] || []).push(d);
    }
    // find a row containing >=3 digits forming 1..N sequence
    for (const key of Object.keys(rows)) {
        const row = rows[key];
        if (row.length < 3) continue;
        const nums = row.map(d => parseInt(d.text));
        const sorted = [...nums].sort((a, b) => a - b);
        let seq = true;
        for (let i = 1; i < sorted.length; i++) if (sorted[i] !== sorted[i-1] + 1) seq = false;
        if (seq && sorted[0] >= 1 && row.length >= 3) {
            return {found: true, digits: sorted, y: Math.round(row[0].y)};
        }
    }
    return {found: false, nDigitLeafs: digitLeafs.length};
}"""


def main():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9333")
        ctx = browser.contexts[0]
        page = [pg for pg in ctx.pages if "pdp" in pg.url.lower()][0]
        page.on("response", on_response)
        page.bring_to_front()
        page.wait_for_timeout(500)

        # scroll until pagination row is in viewport
        ok = False
        for i in range(12):
            state = page.evaluate(FIND_ROW)
            print(f"[scan {i}] {json.dumps(state)}", flush=True)
            if state.get("found"):
                ok = True
                break
            page.evaluate("() => { const sc = document.querySelector('.overflow-y-scroll'); sc.scrollTop += 500; }")
            page.wait_for_timeout(800)
        if not ok:
            print("[fail] pagination row not found", flush=True)
            return
        page.wait_for_timeout(800)
        shot(ctx, page, "v11_before.png")

        clicked = page.evaluate("""() => {
            const sc = document.querySelector('.overflow-y-scroll');
            const digitLeafs = [];
            for (const e of sc.querySelectorAll('*')) {
                if (e.childElementCount !== 0) continue;
                const t = (e.textContent || '').trim();
                if (!/^\\d{1,4}$/.test(t)) continue;
                const r = e.getBoundingClientRect();
                if (r.x > 720 || r.y < 0 || r.y > 900) continue;
                digitLeafs.push({el: e, text: t, x: r.x, y: r.y});
            }
            const rows = {};
            for (const d of digitLeafs) {
                const key = Math.round(d.y / 6);
                (rows[key] = rows[key] || []).push(d);
            }
            for (const key of Object.keys(rows)) {
                const row = rows[key];
                if (row.length < 3) continue;
                const two = row.find(d => d.text === '2');
                if (!two) continue;
                const t = two.el.closest('button,[role=button],li,a,div[class*=item],span');
                (t || two.el).click();
                return 'clicked 2 via ' + (t ? t.tagName : 'leaf');
            }
            return 'no clickable 2 found';
        }""")
        print(f"[click] {clicked}", flush=True)
        page.wait_for_timeout(4500)
        shot(ctx, page, "v11_after.png")

        (OUT / "v11_requests.json").write_text(
            json.dumps(req_log, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[done] api_calls={len(req_log)}", flush=True)


if __name__ == "__main__":
    main()
