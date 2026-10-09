"""v7: broad API listener + scroll actual review list + real pagination clicks."""
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"D:\code\codeMy\shop-qc\probe\us_cdp")
req_log = []


def on_response(resp):
    url = resp.url
    if "tiktok" not in url or "/api/" not in url:
        return
    if any(x in url for x in (".png", ".jpg", ".webp", ".js", ".css", ".woff", "monitor",
                              "mcs", "tobid", "settings", "config", "report", "telemetry")):
        return
    entry = {"status": resp.status, "method": resp.request.method, "url": url[:400],
             "post_data": (resp.request.post_data or "")[:2500]}
    req_log.append(entry)
    print(f"[api] {resp.request.method} {resp.status} {url[ url.find('/api/'): url.find('/api/')+80 ]}", flush=True)
    if entry["post_data"]:
        print(f"      POST: {entry['post_data'][:300]}", flush=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9333")
        ctx = browser.contexts[0]
        page = [pg for pg in ctx.pages if "pdp" in pg.url.lower()][0]
        page.on("response", on_response)
        page.bring_to_front()
        page.wait_for_timeout(500)

        # locate a real review card via piercing locator and scroll it into view
        card = page.locator("text=/i LOVE this purse/i").first
        try:
            card.wait_for(timeout=6000)
            card.scroll_into_view_if_needed(timeout=6000)
            print("[scroll] first review card visible", flush=True)
        except Exception as e:
            print(f"[card fail] {str(e)[:100]}", flush=True)
        page.wait_for_timeout(1000)

        # walk up from the card to find the scrollable review container, scroll it
        scrolled = page.evaluate("""() => {
            function deepAll(root, out) {
                out.push(root);
                if (root.shadowRoot) for (const el of root.shadowRoot.querySelectorAll('*')) deepAll(el, out);
            }
            const all = [];
            deepAll(document.body, all);
            // find elements whose text mentions a distinctive review string
            let cardEl = null;
            for (const el of all) {
                if (el.shadowRoot) continue;
                const t = (el.textContent || '');
                if (t.includes('LOVE this purse') && t.length < 3000) { cardEl = el; break; }
            }
            if (!cardEl) return 'card not found among ' + all.length;
            // climb to scrollable ancestor
            let node = cardEl, hops = 0, found = null;
            while (node && hops < 40) {
                const cs = getComputedStyle(node);
                if (/(auto|scroll)/.test(cs.overflowY) && node.scrollHeight > node.clientHeight + 100) { found = node; break; }
                node = node.parentElement || (node.getRootNode && node.getRootNode().host) || null;
                hops++;
            }
            if (!found) return 'no scrollable ancestor';
            const before = found.scrollTop;
            found.scrollTop = found.scrollHeight;
            return {tag: found.tagName, cls: (found.className||'').toString().slice(0,60),
                    sh: found.scrollHeight, ch: found.clientHeight, from: before, to: found.scrollTop};
        }""")
        print(f"[inner scroll] {json.dumps(scrolled, ensure_ascii=False)[:300]}", flush=True)
        page.wait_for_timeout(3500)
        print(f"[after inner scroll] api calls: {len(req_log)}", flush=True)

        # window scroll further down to list bottom
        page.mouse.wheel(0, 4000)
        page.wait_for_timeout(2500)
        page.mouse.wheel(0, 4000)
        page.wait_for_timeout(2500)

        # find pagination-like controls now visible
        pagi = page.evaluate("""() => {
            function deepAll(root, out) {
                out.push(root);
                if (root.shadowRoot) for (const el of root.shadowRoot.querySelectorAll('*')) deepAll(el, out);
            }
            const all = [];
            deepAll(document.body, all);
            const out = [];
            for (const el of all) {
                if (el.shadowRoot) continue;
                const st = getComputedStyle(el);
                if (st.display === 'none' || st.visibility === 'hidden' || !el.offsetParent) continue;
                const t = (el.getAttribute && (el.getAttribute('aria-label') || '') || el.textContent || '').trim().replace(/\\s+/g, ' ');
                if (t && t.length <= 8 && /^(next|previous|>|<|>>|\\d{1,4}|go$|下一页|下一页|更多)/i.test(t))
                    out.push({tag: el.tagName, text: t.slice(0, 10), cls: (el.className || '').toString().slice(0, 50)});
            }
            return out.slice(0, 40);
        }""")
        print(f"[pagi visible] {json.dumps(pagi, ensure_ascii=False)[:1200]}", flush=True)

        (OUT / "v7_requests.json").write_text(
            json.dumps(req_log, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[done] api_calls={len(req_log)}", flush=True)


if __name__ == "__main__":
    main()
