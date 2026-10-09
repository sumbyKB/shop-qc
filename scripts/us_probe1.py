"""US PDP probe: open page via proxy, capture review-related network traffic."""
import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"D:\code\codeMy\shop-qc\probe\us_probe1")
URL = ("https://shop.tiktok.com/us/pdp/shoulder-bag-by-womens-solid-color-pu-leather-"
       "stylish-large-capacity/1729483763488494309")
PROXY = "http://127.0.0.1:7897"

captured = []
body_idx = 0


def on_response(resp):
    global body_idx
    url = resp.url
    if not re.search(r"review", url, re.I):
        return
    entry = {"url": url[:500], "status": resp.status, "method": resp.request.method,
             "resource_type": resp.request.resource_type}
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
    print(f"[capture] {resp.status} {resp.request.method} {url[:160]}")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            proxy={"server": PROXY},
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            locale="en-US",
            timezone_id="America/New_York",
            viewport={"width": 1440, "height": 900},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        page = ctx.new_page()
        page.on("response", on_response)

        print(f"[goto] {URL}")
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"[goto error] {e}")
        page.wait_for_timeout(8000)
        print(f"[title] {page.title()}")

        # scroll to bottom progressively to trigger lazy-loaded review requests
        for i in range(8):
            page.mouse.wheel(0, 1200)
            page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / "page_full.png"), full_page=False)

        # find and click the reviews tab/section if present
        clicked = []
        for sel in ["text=/\\d+\\s*reviews?/i", "[class*='review' i] [class*='tab' i]",
                    "text=Reviews"]:
            try:
                loc = page.locator(sel).first
                loc.scroll_into_view_if_needed(timeout=5000)
                loc.click(timeout=5000)
                clicked.append(sel)
                page.wait_for_timeout(4000)
                break
            except Exception:
                continue
        print(f"[clicked] {clicked}")

        page.screenshot(path=str(OUT / "review_section.png"))
        html = page.content()
        (OUT / "page.html").write_text(html, encoding="utf-8")

        result = {"title": page.title(), "final_url": page.url[:300],
                  "clicked": clicked, "captured_count": len(captured),
                  "captured": captured}
        (OUT / "probe_result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[done] captured {len(captured)} review-related responses")
        browser.close()


if __name__ == "__main__":
    main()
