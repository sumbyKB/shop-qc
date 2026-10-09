"""US PDP review capture: real Edge via CDP (manual captcha solve), capture review API + DOM."""
import json
import re
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"D:\code\codeMy\shop-qc\probe\us_cdp")
OUT.mkdir(parents=True, exist_ok=True)
PROFILE = r"D:\code\codeMy\shop-qc\.browser-profile-cdp"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 9333
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


def launch_edge():
    subprocess.Popen(
        [EDGE, f"--remote-debugging-port={PORT}", f"--user-data-dir={PROFILE}",
         "--proxy-server=http://127.0.0.1:7897", "--no-first-run",
         "--no-default-browser-check", "--window-size=1400,950", "about:blank"],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True)
    time.sleep(4)


def main():
    launch_edge()
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}")
        ctx = browser.contexts[0]
        page = ctx.new_page()
        page.on("response", on_response)
        page.set_viewport_size({"width": 1380, "height": 900})

        print(f"[goto] {URL}", flush=True)
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"[goto error] {e}", flush=True)

        # wait for manual captcha solve (up to 4 min)
        solved = False
        for i in range(120):
            title = page.title()
            if "Security Check" not in title and title.strip():
                solved = True
                break
            if i % 4 == 0:
                print(f"[waiting captcha] title={title!r} t={i*2}s", flush=True)
                page.screenshot(path=str(OUT / "captcha_wait.png"))
            time.sleep(2)
        print(f"[captcha solved={solved}] title={page.title()!r}", flush=True)
        if not solved:
            (OUT / "result.json").write_text(json.dumps(
                {"solved": False, "captured": captured}, ensure_ascii=False, indent=2),
                encoding="utf-8")
            return

        page.wait_for_timeout(6000)
        print(f"[title] {page.title()}", flush=True)
        page.screenshot(path=str(OUT / "page_top.png"))

        # progressive scroll to trigger lazy review loading
        for i in range(12):
            page.mouse.wheel(0, 1400)
            page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT / "page_scrolled.png"))

        # click reviews entry point if present
        for sel in [r"text=/^[\d,.K]+\s+reviews?$/i", "text=Reviews",
                    "text=/\\d+\\s+reviews?/i"]:
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

        # try pagination: click next-page arrows up to 3 times to capture paged API calls
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

        # DOM fallback: dump visible review-ish blocks
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

        (OUT / "page.html").write_text(page.content(), encoding="utf-8")
        result = {"solved": True, "title": page.title(), "paged_clicks": paged,
                  "dom_review_blocks": dom_reviews,
                  "captured_count": len(captured), "captured": captured}
        (OUT / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[done] captured={len(captured)} paged={paged}", flush=True)


if __name__ == "__main__":
    main()
