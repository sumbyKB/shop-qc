"""v6: pierce shadow DOM via playwright locators; trigger sort/pagination to reveal API params."""
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"D:\code\codeMy\shop-qc\probe\us_cdp")

req_log = []


def on_request(req):
    if "get_product_reviews" in req.url:
        entry = {"url": req.url, "method": req.method,
                 "post_data": (req.post_data or "")[:4000]}
        req_log.append(entry)
        print(f"[req] {req.method} url_len={len(req.url)} post={len(entry['post_data'])}B", flush=True)
        if entry["post_data"]:
            print(f"      BODY: {entry['post_data'][:500]}", flush=True)
        # show query params excluding the big opaque token
        try:
            from urllib.parse import urlparse, parse_qsl
            q = parse_qsl(urlparse(req.url).query)
            small = [(k, v[:60]) for k, v in q if k != "X-Tts-Oec-Bsid"]
            print(f"      QUERY: {small}", flush=True)
        except Exception:
            pass


def main():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9333")
        ctx = browser.contexts[0]
        page = None
        for pg in ctx.pages:
            if "pdp" in pg.url.lower():
                page = pg
                break
        page.on("request", on_request)
        page.bring_to_front()
        page.wait_for_timeout(800)

        # scroll review list into view (pierces shadow DOM)
        try:
            page.locator("text=/2235|条评价|reviews/i").first.scroll_into_view_if_needed(timeout=8000)
            print("[scroll] review list visible", flush=True)
        except Exception as e:
            print(f"[scroll fail] {str(e)[:100]}", flush=True)

        # 1) trigger sort change -> reveals sort param
        try:
            sort_dd = page.locator("text=/^推荐$|^Recommended$/i").first
            sort_dd.click(timeout=5000)
            print("[clicked] sort dropdown", flush=True)
            page.wait_for_timeout(1200)
            opts = page.locator("text=/^最新$|^Newest$|时间排序/i")
            if opts.count() > 0:
                opts.first.click(timeout=4000)
                print("[clicked] Newest option", flush=True)
                page.wait_for_timeout(3000)
        except Exception as e:
            print(f"[sort fail] {str(e)[:120]}", flush=True)

        # 2) star filter -> reveals filter param
        try:
            star_dd = page.locator("text=/^★ 全部$|^All$/i").first
            star_dd.click(timeout=5000)
            print("[clicked] star filter", flush=True)
            page.wait_for_timeout(1200)
            opt5 = page.locator("text=/5 ★|5星|5 stars/i").first
            if opt5.count() > 0:
                opt5.click(timeout=4000)
                print("[clicked] 5-star filter", flush=True)
                page.wait_for_timeout(3000)
        except Exception as e:
            print(f"[star fail] {str(e)[:120]}", flush=True)

        # 3) pagination: look for page numbers / next arrow at list bottom
        pagi_found = False
        for sel in [r"text=/^2$/ >> visible=true", r"[aria-label*='Next' i]",
                    r"text=/^>|下一页|Next$/i", r"text=/查看更多|Load more|See more/i"]:
            try:
                loc = page.locator(sel).first
                loc.scroll_into_view_if_needed(timeout=3500)
                loc.click(timeout=3500)
                print(f"[clicked] pagination: {sel}", flush=True)
                page.wait_for_timeout(3000)
                pagi_found = True
                break
            except Exception:
                continue
        print(f"[pagination clicked] {pagi_found}", flush=True)

        (OUT / "v6_requests.json").write_text(
            json.dumps(req_log, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[done] api_calls={len(req_log)}", flush=True)


if __name__ == "__main__":
    main()
