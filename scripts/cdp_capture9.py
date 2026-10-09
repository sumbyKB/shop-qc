"""v9: incremental scroll through review area, detect pagination when rendered, click it."""
import base64
import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"D:\code\codeMy\shop-qc\probe\us_cdp")
req_log = []


def on_response(resp):
    url = resp.url
    if "get_product_reviews" in url:
        req_log.append({"url": url, "method": resp.request.method,
                        "post_data": (resp.request.post_data or "")[:3000],
                        "body_file": None})
        idx = len(req_log) - 1
        try:
            body = resp.text()
            fn = OUT / f"v9_resp_{idx:02d}.json"
            fn.write_text(body, encoding="utf-8")
            req_log[idx]["body_file"] = fn.name
            req_log[idx]["review_count"] = json.loads(body)["data"].get("total_reviews")
            req_log[idx]["n_reviews"] = len(json.loads(body)["data"].get("product_reviews", []))
            req_log[idx]["first_id"] = json.loads(body)["data"]["product_reviews"][0]["review_id"]
        except Exception as e:
            req_log[idx]["err"] = str(e)[:120]
        print(f"[api] got response #{idx}: {json.dumps(req_log[idx], ensure_ascii=False)[:220]}", flush=True)


PROBE = """() => {
    const sc = document.querySelector('.overflow-y-scroll');
    if (!sc) return {err: 'no scroller'};
    const hits = [];
    for (const e of sc.querySelectorAll('*')) {
        const cs = getComputedStyle(e);
        if (cs.display === 'none' || cs.visibility === 'hidden' || !e.offsetParent) continue;
        const t = (e.childElementCount === 0 ? e.textContent : '').trim();
        if (!t) continue;
        const r = e.getBoundingClientRect();
        if (r.y < 0 || r.y > window.innerHeight) continue;
        if (/^(\\\\d{1,4})$/.test(t) || /^(查看更多|更多评价|下一页|下一页|next)$/i.test(t)
            || /paginat|page-num|arrow-next/i.test((e.className||'').toString() + (e.dataset?.testid||'')))
            hits.push({tag: e.tagName, text: t.slice(0,12), y: Math.round(r.y),
                       cls: (e.className||'').toString().slice(0,46)});
    }
    const cards = [...sc.querySelectorAll('*')].filter(e => {
        const t = e.childElementCount === 0 ? (e.textContent||'') : '';
        return t.length > 80 && /bag|purse/i.test(t);
    }).length;
    return {scrollTop: Math.round(sc.scrollTop), max: sc.scrollHeight - sc.clientHeight, hits: hits.slice(0,15), textCards: cards};
}"""


def main():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9333")
        ctx = browser.contexts[0]
        page = [pg for pg in ctx.pages if "pdp" in pg.url.lower()][0]
        page.on("response", on_response)
        page.bring_to_front()
        page.wait_for_timeout(500)

        # jump to review filter row first
        page.evaluate("""() => {
            const sc = document.querySelector('.overflow-y-scroll');
            const anchor = [...sc.querySelectorAll('*')].find(e => (e.textContent||'').trim() === '排序依据');
            if (anchor) anchor.scrollIntoView({block: 'start'});
        }""")
        page.wait_for_timeout(1200)

        found = None
        for step in range(22):
            state = page.evaluate(PROBE)
            n_hits = len(state.get("hits", []))
            print(f"[step {step}] top={state.get('scrollTop')}/{state.get('max')} "
                  f"cards={state.get('textCards')} hits={n_hits}", flush=True)
            if n_hits > 0:
                print(f"  HITS: {json.dumps(state['hits'], ensure_ascii=False)[:800]}", flush=True)
                found = state["hits"]
                break
            if state.get("scrollTop", 0) >= state.get("max", 0) - 5:
                print("[scroll] reached container bottom", flush=True)
                break
            page.evaluate("""() => {
                const sc = document.querySelector('.overflow-y-scroll');
                sc.scrollTop += sc.clientHeight * 0.6;
            }""")
            page.wait_for_timeout(1100)

        cdp = ctx.new_cdp_session(page)
        r = cdp.send("Page.captureScreenshot", {"format": "png"})
        (OUT / "v9_found.png").write_bytes(base64.b64decode(r["data"]))

        # click best candidate: a bare number >1 or next-ish text
        target = None
        if found:
            for h in found:
                if re.match(r"^(2|下一页|next|查看更多|更多评价)$", h["text"], re.I):
                    target = h
                    break
            if not target:
                target = found[0]
            print(f"[clicking] {target}", flush=True)
            try:
                page.evaluate("""(sel) => {
                    const sc = document.querySelector('.overflow-y-scroll');
                    const els = [...sc.querySelectorAll(sel.tag)];
                    const el = els.find(e => (e.textContent||'').trim() === sel.text);
                    if (el) { el.scrollIntoView({block:'center'}); el.click(); return 'clicked'; }
                    return 'not found';
                }""", target)
                print("[click sent]", flush=True)
            except Exception as e:
                print(f"[click err] {str(e)[:100]}", flush=True)
            page.wait_for_timeout(4000)
            r = cdp.send("Page.captureScreenshot", {"format": "png"})
            (OUT / "v9_after_click.png").write_bytes(base64.b64decode(r["data"]))

        (OUT / "v9_requests.json").write_text(
            json.dumps(req_log, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[done] api_calls={len(req_log)}", flush=True)


if __name__ == "__main__":
    main()
