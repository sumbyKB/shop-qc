"""v5: enumerate iframes, record full review API requests, drive pagination, multi screenshots."""
import base64
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"D:\code\codeMy\shop-qc\probe\us_cdp")
OUT.mkdir(parents=True, exist_ok=True)

req_log = []
body_idx = 0


def on_request(req):
    if "get_product_reviews" in req.url:
        entry = {"url": req.url, "method": req.method,
                 "post_data": (req.post_data or "")[:4000],
                 "headers": {k: v for k, v in req.headers.items()
                             if k.lower() in ("content-type", "x-tts-oec-bsid", "user-agent")}}
        req_log.append(entry)
        print(f"[req] {req.method} post={len(entry['post_data'])}B", flush=True)
        print(f"      {entry['post_data'][:400]}", flush=True)


def shot(page, name, cdp=None):
    try:
        if cdp:
            r = cdp.send("Page.captureScreenshot", {"format": "png"})
            (OUT / name).write_bytes(base64.b64decode(r["data"]))
        else:
            page.screenshot(path=str(OUT / name), timeout=8000)
        print(f"[shot] {name}", flush=True)
    except Exception as e:
        print(f"[shot skip] {name}: {str(e)[:70]}", flush=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9333")
        ctx = browser.contexts[0]
        page = None
        for pg in ctx.pages:
            if "pdp" in pg.url.lower():
                page = pg
                break
        if page is None:
            print("no pdp tab", flush=True)
            return
        page.on("request", on_request)
        page.bring_to_front()
        cdp = ctx.new_cdp_session(page)
        page.wait_for_timeout(1000)

        # enumerate frames
        print(f"[frames] {len(page.frames)}", flush=True)
        review_frame = None
        for fr in page.frames:
            print(f"  frame: {fr.url[:110]}", flush=True)
            if fr != page.main_frame and "tiktok" in fr.url:
                review_frame = fr

        # find the frame that has review text
        target = None
        for fr in page.frames:
            try:
                n = fr.evaluate("() => document.body ? document.body.innerText.length : 0")
                has_rev = fr.evaluate(
                    "() => document.body ? /条评价|reviews|真实购买/i.test(document.body.innerText) : false")
                print(f"  [dom] {fr.url[:60]} innerText={n} hasReviews={has_rev}", flush=True)
                if has_rev and n > 500:
                    target = fr
            except Exception:
                pass

        f = target or review_frame or page.main_frame
        print(f"[working frame] {f.url[:100]}", flush=True)

        # screenshot current review area state
        shot(page, "v5_reviews_state0.png", cdp)

        # trigger fresh API calls: change star filter to 5-star and back via UI dropdown
        # first inspect filter controls
        info = f.evaluate("""() => {
            const out = [];
            for (const el of document.querySelectorAll('button, [role=button], select, li, [class*=select i], [class*=filter i]')) {
                const t = (el.innerText || '').trim().replace(/\\n/g, ' ');
                if (t && t.length < 40 && /全部|筛选|排序|推荐|真实|图片|视频|star|filter|sort/i.test(t))
                    out.push({tag: el.tagName, text: t.slice(0, 36)});
            }
            return out.slice(0, 30);
        }""")
        print(f"[controls] {json.dumps(info, ensure_ascii=False)[:900]}", flush=True)

        # scroll the review list to bottom to trigger load-more / pagination API
        f.evaluate("""() => {
            const sc = [...document.querySelectorAll('*')].filter(e => e.scrollHeight > e.clientHeight + 300 && /scroll|auto/i.test(getComputedStyle(e).overflowY));
            sc.forEach(e => e.scrollTop = e.scrollHeight);
            window.scrollTo(0, document.body.scrollHeight);
        }""")
        page.wait_for_timeout(3500)
        shot(page, "v5_reviews_bottom.png", cdp)
        print(f"[after scroll] api calls: {len(req_log)}", flush=True)

        # look for pagination controls at list bottom
        pagi = f.evaluate("""() => {
            const out = [];
            for (const el of document.querySelectorAll('button, [role=button], li, a, [class*=pag i], [class*=next i], [class*=arrow i], [class*=page i]')) {
                const t = (el.innerText || el.getAttribute('aria-label') || '').trim().replace(/\\n/g, ' ');
                if (t && t.length < 24 && /^(next|prev|>|<|\\d{1,3}|查看更多|下一页|加载更多|load more|see more)$/i.test(t))
                    out.push({tag: el.tagName, text: t, visible: !!el.offsetParent});
            }
            return out.slice(0, 30);
        }""")
        print(f"[pagination] {json.dumps(pagi, ensure_ascii=False)[:700]}", flush=True)

        (OUT / "v5_requests.json").write_text(
            json.dumps(req_log, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[done] api_calls={len(req_log)}", flush=True)


if __name__ == "__main__":
    main()
