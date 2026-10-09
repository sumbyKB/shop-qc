"""US PDP review capture v2: reconnect existing Edge CDP, robust captcha wait, capture."""
import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"D:\code\codeMy\shop-qc\probe\us_cdp")
OUT.mkdir(parents=True, exist_ok=True)
URL = ("https://shop.tiktok.com/us/pdp/shoulder-bag-by-womens-solid-color-pu-leather-"
       "stylish-large-capacity/1729483763488494309")

captured = []
body_idx = 0


def on_response(resp):
    global body_idx
    url = resp.url
    if not re.search(r"review|comment", url, re.I):
        return
    if re.search(r"\.(png|jpg|webp|gif|js|css|woff)", url, re.I):
        return
    entry = {"url": url[:800], "status": resp.status,
             "method": resp.request.method}
    try:
        ct = resp.headers.get("content-type", "")
        if resp.status == 200 and ("json" in ct or "text" in ct or "octet" in ct):
            body = resp.text()
            if body:
                fn = OUT / f"resp_{body_idx:03d}.json"
                fn.write_text(body, encoding="utf-8")
                entry["body_file"] = fn.name
                entry["body_size"] = len(body)
                body_idx += 1
    except Exception as e:
        entry["body_error"] = str(e)[:200]
    captured.append(entry)
    print(f"[capture] {resp.status} {url[:180]}", flush=True)


def safe_title(page):
    try:
        return page.title()
    except Exception:
        return "<navigating>"


def main():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9333")
        ctx = browser.contexts[0]
        # reuse the page from the failed run if it is on tiktok, else new page
        page = None
        for pg in ctx.pages:
            if "tiktok.com" in pg.url:
                page = pg
                break
        if page is None:
            page = ctx.new_page()
        page.on("response", on_response)
        try:
            page.set_viewport_size({"width": 1380, "height": 900})
        except Exception:
            pass

        print(f"[goto] {URL}", flush=True)
        for attempt in range(3):
            try:
                page.goto(URL, wait_until="domcontentloaded", timeout=60000)
                break
            except Exception as e:
                print(f"[goto retry {attempt}] {str(e)[:120]}", flush=True)
                time.sleep(3)

        # robust captcha wait (up to 5 min), tolerant of mid-check navigations
        solved = False
        for i in range(150):
            t = safe_title(page)
            if "Security Check" not in t and t != "<navigating>" and t.strip():
                solved = True
                break
            if i % 5 == 0:
                print(f"[waiting captcha] title={t!r} t={i*2}s", flush=True)
                try:
                    page.screenshot(path=str(OUT / "captcha_wait.png"))
                except Exception:
                    pass
            time.sleep(2)
        print(f"[captcha solved={solved}] title={safe_title(page)!r}", flush=True)
        if not solved:
            (OUT / "result.json").write_text(json.dumps(
                {"solved": False, "captured": captured}, ensure_ascii=False, indent=2),
                encoding="utf-8")
            return

        page.wait_for_timeout(6000)
        page.screenshot(path=str(OUT / "page_top.png"))

        for i in range(12):
            try:
                page.mouse.wheel(0, 1400)
            except Exception:
                pass
            page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT / "page_scrolled.png"))

        for sel in [r"text=/^[\d,.K]+\s+reviews?$/i", "text=Reviews",
                    r"text=/\d+\s+reviews?/i"]:
            try:
                loc = page.locator(sel).first
                loc.scroll_into_view_if_needed(timeout=4000)
                loc.click(timeout=4000)
                print(f"[clicked] {sel}", flush=True)
                page.wait_for_timeout(5000)
                break
            except Exception:
                continue
        page.screenshot(path=str(OUT / "review_area.png"))

        paged = 0
        for sel in ["[class*='pagination' i] [class*='next' i]",
                    r"button:has-text('Next')", "[aria-label*='Next' i]"]:
            try:
                loc = page.locator(sel).first
                for k in range(3):
                    loc.scroll_into_view_if_needed(timeout=4000)
                    loc.click(timeout=4000)
                    paged += 1
                    page.wait_for_timeout(3500)
                    print(f"[paged] {sel} x{k+1}", flush=True)
                break
            except Exception:
                continue

        dom_reviews = []
        try:
            cards = page.locator("[class*='review' i]").all()
            for c in cards[:60]:
                try:
                    t = (c.inner_text(timeout=1500) or "").strip()
                    if 10 < len(t) < 1200:
                        dom_reviews.append(t)
                except Exception:
                    pass
        except Exception:
            pass
        print(f"[dom] review blocks: {len(dom_reviews)}", flush=True)

        try:
            (OUT / "page.html").write_text(page.content(), encoding="utf-8")
            page.screenshot(path=str(OUT / "final.png"))
        except Exception:
            pass
        result = {"solved": True, "title": safe_title(page), "paged_clicks": paged,
                  "dom_review_blocks": dom_reviews,
                  "captured_count": len(captured), "captured": captured}
        (OUT / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[done] captured={len(captured)} paged={paged}", flush=True)


if __name__ == "__main__":
    main()
