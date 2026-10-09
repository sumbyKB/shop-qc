"""Harvest ALL product reviews v2: per-star partition + patient backoff + per-product output.

Usage: python harvest_reviews.py <product_id> [page_size]
Output: probe/us_cdp/reviews_<product_id>.json
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"D:\code\codeMy\shop-qc\probe\us_cdp")
PRODUCT_ID = sys.argv[1] if len(sys.argv) > 1 else "1729483763488494309"
PAGE_SIZE = int(sys.argv[2]) if len(sys.argv) > 2 else 50

FETCH = """async (arg) => {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 20000);
    try {
        const r = await fetch('/api/shop/pdp_desktop/get_product_reviews', {
            method: 'POST',
            headers: {'content-type': 'application/json'},
            body: JSON.stringify(arg.body),
            signal: ctrl.signal
        });
        clearTimeout(timer);
        return {status: r.status, text: await r.text()};
    } catch (e) {
        clearTimeout(timer);
        return {status: -1, text: String(e)};
    }
}"""

BACKOFFS = [5, 10, 20, 40]


def fetch_page(page, body, errors):
    for attempt, wait in enumerate(BACKOFFS, start=1):
        try:
            r = page.evaluate(FETCH, {"body": body})
            d = json.loads(r["text"])
            if d.get("code") == 0 and d.get("data"):
                return d["data"]
            errors.append(f"code={d.get('code')} msg={str(d.get('message'))[:60]}")
        except Exception as e:
            errors.append(str(e)[:120])
        print(f"    retry {attempt} in {wait}s...", flush=True)
        time.sleep(wait)
    return None


def main():
    all_reviews = {}
    ratings = None
    star_totals = {}
    errors = []

    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://127.0.0.1:9333")
        ctx = b.contexts[0]
        page = None
        for pg in ctx.pages:
            if "pdp" in pg.url.lower():
                page = pg
                break
        if page is None:
            print("FATAL: no PDP tab open in Edge", flush=True)
            sys.exit(1)

        # pass 1: all reviews (filter_value 6)
        # pass 2: per-star (1..5) — partition that stays under any deep-page cap
        for fv in (6, 5, 4, 3, 2, 1):
            page_start = 1
            before = len(all_reviews)
            while True:
                body = {"product_id": PRODUCT_ID, "page_start": page_start,
                        "page_size": PAGE_SIZE, "sort_rule": 1,
                        "review_filter": {"filter_type": 1, "filter_value": fv},
                        "component_name": "pdp_left_reviews"}
                data = fetch_page(page, body, errors)
                if data is None:
                    print(f"[fv={fv} page {page_start}] FAILED permanently, "
                          f"moving on ({len(all_reviews)} kept)", flush=True)
                    break
                if ratings is None and data.get("review_ratings"):
                    ratings = data["review_ratings"]
                revs = data.get("product_reviews", [])
                if fv != 6 and data.get("total_reviews"):
                    star_totals[fv] = int(data["total_reviews"])
                new = 0
                for rv in revs:
                    if rv["review_id"] not in all_reviews:
                        all_reviews[rv["review_id"]] = rv
                        new += 1
                has_more = bool(data.get("has_more"))
                print(f"[fv={fv} page {page_start}] got={len(revs)} new={new} "
                      f"total={len(all_reviews)} has_more={has_more}", flush=True)
                if not has_more or not revs:
                    break
                if new == 0:
                    print("[stop pass] no new reviews", flush=True)
                    break
                page_start += 1
                time.sleep(1.5)
            print(f"[pass fv={fv}] +{len(all_reviews) - before} reviews", flush=True)
            time.sleep(2)

    result = {
        "product_id": PRODUCT_ID,
        "harvested_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_reviews_claimed": (ratings or {}).get("review_count"),
        "overall_score": (ratings or {}).get("overall_score"),
        "rating_breakdown": (ratings or {}).get("rating_result"),
        "star_filter_totals": {str(k): v for k, v in sorted(star_totals.items(), reverse=True)},
        "harvested_count": len(all_reviews),
        "errors": errors[:50],
        "review_ratings": ratings,
        "reviews": list(all_reviews.values()),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"reviews_{PRODUCT_ID}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] harvested {len(all_reviews)} reviews -> reviews_{PRODUCT_ID}.json",
          flush=True)


if __name__ == "__main__":
    main()
