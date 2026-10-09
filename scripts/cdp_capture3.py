"""US PDP review capture v3: US IP active, clear stale cookies, capture review API + pagination."""
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
    if not re.search(r"review|comment|rating", url, re.I):
        return
    if re.search(r"\.(png|jpg|webp|gif|js|css|woff)", url, re.I):
        return
    entry = {"url": url[:900], "status": resp.status,
             "method": resp.request.method}
    try:
        ct = resp.headers.get("content-type", "")
        if resp.status == 200 and ("json" in ct or "text" in ct):
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
    print(f"[capture] {resp.status} {url[:200]}", flush=True)


def safe_shot(page, name):
    try:
        page.screenshot(path=str(OUT / name), timeout=8000)
    except Exception as e:
        print(f"[shot skip] {name}: {str(e)[:80]}", flush=True)


def safe_title(page):
    try:
        return page.title()
    except Exception:
        return "<navigating>"


def main():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9333")
        ctx = browser.contexts[0]
        ctx.clear_cookies()  # drop TH-region cookies from previous session
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
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"[goto error] {str(e)[:150]}", flush=True)
        page.wait_for_timeout(9000)
        t = safe_title(page)
        print(f"[title] {t}", flush=True)
        if "Security Check" in t:
            print("[captcha] waiting for manual solve (5 min)...", flush=True)
            for i in range(150):
                t = safe_title(page)
                if "Security Check" not in t and t.strip():
                    break
                time.sleep(2)
            print(f"[captcha done] {safe_title(page)}", flush=True)

        safe_shot(page, "v3_top.png")

        # scroll down to review section progressively
        for i in range(15):
            page.mouse.wheel(0, 1300)
            page.wait_for_timeout(900)
        safe_shot(page, "v3_scrolled.png")

        # click review entry if present
        for sel in [r"text=/^[\d,.K]+\s+reviews?$/i", r"text=/\d+(\.\d+)?\s*★/i",
                    "text=Reviews", r"text=/\d+\s+reviews?/i"]:
            try:
                loc = page.locator(sel).first
                loc.scroll_into_view_if_needed(timeout=3500)
                loc.click(timeout=3500)
                print(f"[clicked] {sel}", flush=True)
                page.wait_for_timeout(4500)
                break
            except Exception:
                continue
        safe_shot(page, "v3_review_area.png")

        # pagination clicks
        paged = 0
        for sel in ["[class*='pagination' i] li:last-child",
                    "[class*='pagination' i] [class*='next' i]",
                    r"button:has-text('Next')", "[aria-label*='Next' i]",
                    "[data-testid*='next' i]"]:
            try:
                loc = page.locator(sel).first
                for k in range(4):
                    loc.scroll_into_view_if_needed(timeout=3500)
                    loc.click(timeout=3500)
                    paged += 1
                    page.wait_for_timeout(3000)
                    print(f"[paged] {sel} x{k+1}", flush=True)
                break
            except Exception:
                continue
        safe_shot(page, "v3_after_paging.png")

        try:
            (OUT / "v3_page.html").write_text(page.content(), encoding="utf-8")
        except Exception:
            pass
        result = {"title": safe_title(page), "paged_clicks": paged,
                  "captured_count": len(captured), "captured": captured}
        (OUT / "v3_result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[done] captured={len(captured)} paged={paged}", flush=True)


if __name__ == "__main__":
    main()
