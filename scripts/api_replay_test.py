"""Test review API replay from page context; results written to file (no stdout piping)."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"D:\code\codeMy\shop-qc\probe\us_cdp")
RESULT = OUT / "replay_test.json"
URL = ("https://shop.tiktok.com/us/pdp/shoulder-bag-by-womens-solid-color-pu-leather-"
       "stylish-large-capacity/1729483763488494309")

FETCH = """async (body) => {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 15000);
    try {
        const r = await fetch('/api/shop/pdp_desktop/get_product_reviews', {
            method: 'POST',
            headers: {'content-type': 'application/json'},
            body: JSON.stringify(body),
            signal: ctrl.signal
        });
        clearTimeout(timer);
        return {status: r.status, text: await r.text()};
    } catch (e) {
        clearTimeout(timer);
        return {status: -1, text: String(e)};
    }
}"""

BODY = {"product_id": "1729483763488494309", "page_size": 3, "sort_rule": 1,
        "review_filter": {"filter_type": 1, "filter_value": 6},
        "component_name": "pdp_left_reviews"}

results = {}
tests = [
    ("page1_size3", 1, 3),
    ("page3_size3", 3, 3),
    ("page1_size20", 1, 20),
    ("page1_size50", 1, 50),
]

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9333")
    ctx = b.contexts[0]
    page = None
    for pg in ctx.pages:
        if "pdp" in pg.url.lower():
            page = pg
            break
    if page is None:
        page = ctx.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)

    for tag, pstart, psize in tests:
        body = dict(BODY, page_start=pstart, page_size=psize)
        try:
            r = page.evaluate(FETCH, body)
            try:
                d = json.loads(r["text"])
                code = d.get("code")
                data = d.get("data") or {}
                revs = data.get("product_reviews", [])
                results[tag] = {"http": r["status"], "code": code,
                                "n": len(revs), "has_more": data.get("has_more"),
                                "first_id": revs[0]["review_id"] if revs else None,
                                "first_rating": revs[0]["review_rating"] if revs else None}
            except Exception as ex:
                results[tag] = {"http": r["status"], "parse_err": str(ex)[:100],
                                "raw_head": r["text"][:300]}
        except Exception as ex:
            results[tag] = {"eval_err": str(ex)[:200]}
        RESULT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

print(json.dumps(results, ensure_ascii=False, indent=2))
