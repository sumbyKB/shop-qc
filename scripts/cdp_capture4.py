"""v4: full request capture (method+post_data), review section screenshots, pagination clicks."""
import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"D:\code\codeMy\shop-qc\probe\us_cdp")
OUT.mkdir(parents=True, exist_ok=True)

req_log = []
body_idx = 0


def on_response(resp):
    global body_idx
    url = resp.url
    if "get_product_reviews" not in url:
        return
    req = resp.request
    entry = {"url": url, "method": req.method, "status": resp.status,
             "post_data": (req.post_data or "")[:3000]}
    try:
        ct = resp.headers.get("content-type", "")
        if resp.status == 200 and "json" in ct:
            body = resp.text()
            if body:
                fn = OUT / f"v4_resp_{body_idx:03d}.json"
                fn.write_text(body, encoding="utf-8")
                entry["body_file"] = fn.name
                entry["body_size"] = len(body)
                body_idx += 1
    except Exception as e:
        entry["body_error"] = str(e)[:150]
    req_log.append(entry)
    print(f"[api] {req.method} {resp.status} body={len(entry['post_data'])}B -> {entry.get('body_file')}", flush=True)


def safe_shot(page, name):
    try:
        page.screenshot(path=str(OUT / name), timeout=8000)
        print(f"[shot] {name}", flush=True)
    except Exception as e:
        print(f"[shot skip] {name}: {str(e)[:80]}", flush=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9333")
        ctx = browser.contexts[0]
        page = None
        for pg in ctx.pages:
            if "tiktok.com" in pg.url:
                page = pg
                break
        if page is None:
            page = ctx.new_page()
        page.on("response", on_response)

        t = page.title()
        print(f"[title] {t}", flush=True)
        if "Security Check" in t or "pdp" not in page.url:
            print("[goto] reloading PDP", flush=True)
            page.goto(URL if False else page.url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(8000)

        # scroll progressively until review section appears
        review_sel = "[class*='review' i]"
        found = False
        for i in range(20):
            page.mouse.wheel(0, 900)
            page.wait_for_timeout(700)
            cnt = page.locator(review_sel).count()
            if cnt > 2:
                found = True
                break
        print(f"[scroll] review-ish nodes found={found}", flush=True)

        # locate review list container and screenshot it
        try:
            sec = page.locator("section:has([class*='review' i]), div:has(> [class*='review' i])").first
            sec.scroll_into_view_if_needed(timeout=6000)
        except Exception:
            pass
        page.wait_for_timeout(2500)
        safe_shot(page, "v4_review_1.png")

        # dump review section outer HTML for selector design
        try:
            html = page.evaluate("""() => {
                const els = [...document.querySelectorAll('[class*="review" i]')];
                let best = null;
                for (const el of els) {
                    const txt = el.innerText || '';
                    if (txt.length > 500 && (!best || txt.length > best.innerText.length)) best = el;
                }
                return best ? best.outerHTML.slice(0, 60000) : '';
            }""")
            (OUT / "v4_review_dom.html").write_text(html, encoding="utf-8")
            print(f"[dom] review container html {len(html)}B", flush=True)
        except Exception as e:
            print(f"[dom error] {str(e)[:120]}", flush=True)

        # find pagination-ish controls
        cands = page.evaluate("""() => {
            const out = [];
            for (const el of document.querySelectorAll('button, [role="button"], li, a, [class*="page" i], [class*="next" i], [class*="arrow" i]')) {
                const t = (el.innerText || el.getAttribute('aria-label') || '').trim();
                if (/^next$|^[2-9]$|load more|see more|more review/i.test(t) && t.length < 30)
                    out.push({tag: el.tagName, text: t.slice(0, 30), cls: (el.className||'').toString().slice(0,80)});
            }
            return out.slice(0, 25);
        }""")
        print(f"[pagi candidates] {json.dumps(cands, ensure_ascii=False)[:800]}", flush=True)

        # click next/page-2 up to 3 times, screenshot between
        clicked_any = False
        for c in cands:
            if not re.match(r"^(next|[2-9]|load more|see more)$", c["text"], re.I):
                continue
            try:
                loc = page.locator(f"{c['tag'].lower()}:has-text('{c['text']}')").first
                loc.scroll_into_view_if_needed(timeout=4000)
                loc.click(timeout=4000)
                clicked_any = True
                print(f"[clicked] {c['text']}", flush=True)
                page.wait_for_timeout(3000)
                safe_shot(page, f"v4_after_click_{c['text']}.png")
                break
            except Exception as e:
                print(f"[click fail] {c['text']}: {str(e)[:80]}", flush=True)
        if not clicked_any:
            print("[pagi] no clickable pagination found in DOM", flush=True)

        (OUT / "v4_requests.json").write_text(
            json.dumps(req_log, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[done] api_calls={len(req_log)}", flush=True)


if __name__ == "__main__":
    main()
