"""US PDP probe v2: headed Edge + persistent profile, capture review API traffic."""
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"D:\code\codeMy\shop-qc\probe\us_probe1")
PROFILE = r"D:\code\codeMy\shop-qc\.browser-profile"
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
    entry = {"url": url[:800], "status": resp.status, "method": resp.request.method,
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
    print(f"[capture] {resp.status} {resp.request.method} {url[:180]}")


def main():
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            PROFILE,
            channel="msedge",
            headless=False,
            proxy={"server": PROXY},
            locale="en-US",
            timezone_id="America/New_York",
            viewport={"width": 1440, "height": 900},
            no_viewport=False,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.on("response", on_response)

        print(f"[goto] {URL}")
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"[goto error] {e}")
        page.wait_for_timeout(10000)
        print(f"[title] {page.title()}")
        page.screenshot(path=str(OUT / "v2_landing.png"))

        # progressive scroll to trigger lazy loading
        for i in range(10):
            page.mouse.wheel(0, 1500)
            page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT / "v2_scrolled.png"))

        # try clicking a reviews entry point if one exists
        for sel in ["text=/^\\s*[\\d,.K]+\\s+reviews?\\b/i", "text=Reviews",
                    "[class*='review' i]"]:
            try:
                loc = page.locator(sel).first
                loc.scroll_into_view_if_needed(timeout=4000)
                loc.click(timeout=4000)
                print(f"[clicked] {sel}")
                page.wait_for_timeout(5000)
                break
            except Exception:
                continue

        page.screenshot(path=str(OUT / "v2_after_click.png"))
        (OUT / "v2_page.html").write_text(page.content(), encoding="utf-8")

        result = {"title": page.title(), "final_url": page.url[:300],
                  "captured_count": len(captured), "captured": captured}
        (OUT / "v2_result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[done] captured {len(captured)} review-related responses")
        ctx.close()


if __name__ == "__main__":
    main()
