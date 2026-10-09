"""TikTok Shop review harvester — all-in-one CLI (portable across machines).

Subcommands:
  check                              environment preflight (proxy / exit IP / Edge / deps / CDP)
  harvest <url|product_id>           harvest all reviews -> <out>/reviews_<id>.json
  report <reviews.json> [--xlsx P]   build Excel report with native charts
  all <url|product_id>               harvest + report

Env overrides: TT_PROXY (e.g. http://127.0.0.1:7890), TT_CDP_PORT (default 9333),
TT_EDGE_PATH, CLASH_SECRET.
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CDP_PORT = int(__import__("os").environ.get("TT_CDP_PORT", "9333"))
PROXY_CANDIDATES = ["http://127.0.0.1:7897", "http://127.0.0.1:7890",
                    "http://127.0.0.1:7891", "http://127.0.0.1:10809",
                    "http://127.0.0.1:1080", "http://127.0.0.1:8080"]
EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
REGION_CC = {"us": "US", "th": "TH", "gb": "GB", "uk": "GB", "de": "DE", "fr": "FR",
             "it": "IT", "es": "ES", "sa": "SA", "id": "ID", "vn": "VN", "ph": "PH",
             "my": "MY", "sg": "SG", "jp": "JP", "kr": "KR", "mx": "MX", "br": "BR"}

FETCH = """async (arg) => {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 20000);
    try {
        const r = await fetch('/api/shop/pdp_desktop/get_product_reviews', {
            method: 'POST', headers: {'content-type': 'application/json'},
            body: JSON.stringify(arg.body), signal: ctrl.signal});
        clearTimeout(timer);
        return {status: r.status, text: await r.text()};
    } catch (e) { clearTimeout(timer); return {status: -1, text: String(e)}; }
}"""
BACKOFFS = [5, 10, 20, 40]


# ---------- helpers ----------
def detect_proxy():
    import urllib.request
    env = __import__("os").environ.get("TT_PROXY")
    cands = [env] if env else PROXY_CANDIDATES
    for proxy in cands:
        try:
            handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
            opener = urllib.request.build_opener(handler)
            req = urllib.request.Request("http://ip-api.com/json/?fields=countryCode,isp",
                                         headers={"User-Agent": "curl/8"})
            with opener.open(req, timeout=8) as resp:
                info = json.loads(resp.read())
                return proxy, info
        except Exception:
            continue
    return None, None


def cdp_live():
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=3) as r:
            return bool(json.loads(r.read()))
    except Exception:
        return False


def find_edge():
    import os
    paths = list(EDGE_PATHS)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        paths.append(Path(local) / "Microsoft/Edge/Application/msedge.exe")
    for pth in paths:
        if Path(pth).exists():
            return str(pth)
    return None


def extract_product_id(s):
    s = s.strip()
    m = re.search(r"/pdp/[^/]*/(\d{10,25})", s) or re.search(r"/pdp/(\d{10,25})", s)
    if m:
        return m.group(1)
    if re.fullmatch(r"\d{10,25}", s):
        return s
    m = re.search(r"(\d{15,22})", s)
    return m.group(1) if m else None


def url_region(url_or_none):
    if not url_or_none:
        return None
    m = re.search(r"tiktok\.com/([a-z]{2})/pdp/", url_or_none)
    return m.group(1).lower() if m else None


def ensure_edge(proxy, url):
    if cdp_live():
        print(f"[edge] CDP {CDP_PORT} already live", flush=True)
        return True
    edge = __import__("os").environ.get("TT_EDGE_PATH") or find_edge()
    if not edge:
        print("[edge] FATAL: Edge not found, install Microsoft Edge or set TT_EDGE_PATH",
              flush=True)
        return False
    profile = Path.cwd() / ".browser-profile-cdp"
    args = [edge, f"--remote-debugging-port={CDP_PORT}", f"--user-data-dir={profile}",
            f"--proxy-server={proxy or 'direct://'}", "--no-first-run",
            "--no-default-browser-check", "--window-size=1400,950"]
    if url:
        args.append(url)
    flags = 0
    if sys.platform == "win32":
        flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | NEW_PROCESS_GROUP
    subprocess.Popen(args, creationflags=flags, close_fds=True)
    print(f"[edge] launched, waiting for CDP {CDP_PORT}...", flush=True)
    for _ in range(20):
        time.sleep(1)
        if cdp_live():
            print("[edge] CDP ready", flush=True)
            return True
    print("[edge] FATAL: CDP did not come up", flush=True)
    return False


def get_pdp_page(ctx, url=None):
    target_pid = extract_product_id(url) if url else None
    page = None
    for pg in ctx.pages:
        if target_pid and extract_product_id(pg.url) == target_pid:
            page = pg
            break
    if page is None:
        for pg in ctx.pages:
            if pg.url == "about:blank":
                page = pg
                break
        if page is None:
            page = ctx.new_page()
    if url and extract_product_id(page.url) != target_pid:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
    # captcha wait
    for _ in range(150):
        try:
            t = page.title()
        except Exception:
            t = "<navigating>"
        if "Security Check" not in t and t.strip() and t != "<navigating>":
            break
        print("[captcha] waiting for manual slider solve (up to 5 min)...", flush=True)
        time.sleep(2)
    return page


# ---------- subcommands ----------
def cmd_check():
    print("== environment preflight ==", flush=True)
    proxy, info = detect_proxy()
    if proxy:
        print(f"[proxy] OK {proxy}  exit={info.get('countryCode')} ({info.get('isp')})",
              flush=True)
    else:
        print("[proxy] FAIL: no working proxy among candidates; set TT_PROXY", flush=True)
    edge = find_edge()
    print(f"[edge] {'OK ' + edge if edge else 'FAIL: not found'}", flush=True)
    print(f"[cdp]  {'OK live on ' + str(CDP_PORT) if cdp_live() else 'not running (will auto-launch on harvest)'}",
          flush=True)
    for mod in ("playwright", "openpyxl"):
        try:
            __import__(mod)
            print(f"[py]   OK {mod}", flush=True)
        except ImportError:
            print(f"[py]   FAIL missing {mod}  (pip install {mod})", flush=True)
    if info and proxy:
        m = re.search(r"tiktok\.com/([a-z]{2})/", sys.argv[-1] if len(sys.argv) > 2 else "")
        cc = REGION_CC.get(m.group(1)) if m else None
        if cc and info.get("countryCode") != cc:
            print(f"[warn] URL region {cc} != exit IP {info['countryCode']}: "
                  f"switch proxy node to {cc} first!", flush=True)


def extract_ssr_reviews(html):
    """Pull SSR-embedded product_reviews arrays out of the PDP HTML (template B / free bonus)."""
    out, pos = [], 0
    while True:
        i = html.find('"product_reviews":', pos)
        if i < 0:
            break
        arr_start = html.find("[", i)
        if arr_start < 0:
            break
        depth, in_str, esc, end = 0, False, False, None
        for j in range(arr_start, len(html)):
            c = html[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "[":
                    depth += 1
                elif c == "]":
                    depth -= 1
                    if depth == 0:
                        end = j + 1
                        break
        if end is None:
            break
        try:
            out.extend(json.loads(html[arr_start:end]))
        except Exception:
            pass
        pos = end
    return out


def cmd_harvest(url_or_id, page_size, out_dir):
    pid = extract_product_id(url_or_id)
    if not pid:
        print(f"FATAL: cannot extract product id from: {url_or_id}", flush=True)
        sys.exit(1)
    proxy, info = detect_proxy()
    if not proxy:
        print("FATAL: no working proxy", flush=True)
        sys.exit(1)
    region = url_region(url_or_id)
    if region and info and info.get("countryCode") != REGION_CC.get(region, region.upper()):
        print(f"[warn] exit {info.get('countryCode')} != region {region.upper()} — "
              f"expect geo-redirect; switch node and retry if title is not the product",
              flush=True)
    url = url_or_id.strip()
    if not url.startswith("http"):
        url = f"https://shop.tiktok.com/{region or 'us'}/pdp/{pid}"
    if not ensure_edge(proxy, url):
        sys.exit(1)

    from playwright.sync_api import sync_playwright
    all_reviews, ratings, errors = {}, None, []
    star_totals = {}
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
        ctx = b.contexts[0]
        page = get_pdp_page(ctx, url)
        print(f"[pdp] {page.title()[:80]}", flush=True)

        def fetch_page(body):
            throttle_hits = 0
            for attempt, wait in enumerate(BACKOFFS, start=1):
                try:
                    r = page.evaluate(FETCH, {"body": body})
                    d = json.loads(r["text"])
                    if d.get("code") == 0 and d.get("data"):
                        return d["data"]
                    errors.append(f"code={d.get('code')} {str(d.get('message'))[:60]}")
                    if d.get("code") == 100000:
                        throttle_hits += 1
                        if throttle_hits >= 2:
                            return "THROTTLED"
                except Exception as e:
                    errors.append(str(e)[:120])
                print(f"    rate-limited/backoff: retry {attempt} in {wait}s", flush=True)
                time.sleep(wait)
            return None

        for fv in (6, 5, 4, 3, 2, 1):  # 6=all, then per-star safety net
            start, before = 1, len(all_reviews)
            while True:
                body = {"product_id": pid, "page_start": start, "page_size": page_size,
                        "sort_rule": 1,
                        "review_filter": {"filter_type": 1, "filter_value": fv},
                        "component_name": "pdp_left_reviews"}
                data = fetch_page(body)
                if data == "THROTTLED":
                    print("[DIAGNOSE] code=100000 twice: endpoint throttled for this "
                          "session/IP. Stop hammering; wait 10-30 min then retry. "
                          "Keeping whatever was harvested.", flush=True)
                    break
                if data is None:
                    print(f"[fv={fv} p{start}] failed permanently, keep {len(all_reviews)}",
                          flush=True)
                    break
                if ratings is None and data.get("review_ratings"):
                    ratings = data["review_ratings"]
                if fv != 6 and data.get("total_reviews"):
                    star_totals[fv] = int(data["total_reviews"])
                revs = data.get("product_reviews", [])
                new = sum(1 for rv in revs if rv["review_id"] not in all_reviews)
                for rv in revs:
                    all_reviews.setdefault(rv["review_id"], rv)
                has_more = bool(data.get("has_more"))
                print(f"[fv={fv} p{start}] got={len(revs)} new={new} "
                      f"total={len(all_reviews)} has_more={has_more}", flush=True)
                if not has_more or not revs or new == 0:
                    break
                start += 1
                time.sleep(1.5)
            print(f"[pass fv={fv}] +{len(all_reviews) - before}", flush=True)
            time.sleep(2)

        # SSR bonus merge: templates embed up to a few reviews in the page HTML
        try:
            ssr = extract_ssr_reviews(page.content())
            ssr_new = sum(1 for rv in ssr if rv.get("review_id") not in all_reviews)
            for rv in ssr:
                all_reviews.setdefault(rv["review_id"], rv)
            if ssr_new:
                print(f"[ssr] +{ssr_new} embedded reviews merged", flush=True)
        except Exception:
            pass

    if not all_reviews:
        print("[DIAGNOSE] 0 reviews. Most likely the reviews endpoint is throttled "
              "(code=100000). Wait 10-30 minutes and re-run. If the product genuinely "
              "has no reviews, the PDP would show 'no reviews' - verify in the browser.",
              flush=True)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    result = {"product_id": pid, "source_url": url,
              "harvested_at": time.strftime("%Y-%m-%d %H:%M:%S"),
              "total_reviews_claimed": (ratings or {}).get("review_count"),
              "overall_score": (ratings or {}).get("overall_score"),
              "rating_breakdown": (ratings or {}).get("rating_result"),
              "star_filter_totals": {str(k): v for k, v in sorted(star_totals.items(),
                                                                  reverse=True)},
              "harvested_count": len(all_reviews), "errors": errors[:50],
              "review_ratings": ratings, "reviews": list(all_reviews.values())}
    fn = out / f"reviews_{pid}.json"
    fn.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] {len(all_reviews)} reviews -> {fn}", flush=True)
    if not all_reviews:
        sys.exit(3)  # signal caller (cmd_all) not to build an empty report
    return fn


def cmd_report(src, xlsx):
    here = Path(__file__).parent
    if not xlsx:
        d = json.loads(Path(src).read_text(encoding="utf-8"))
        xlsx = Path.cwd() / "report" / f"TikTok评论分析报告_{d['product_id']}.xlsx"
    r = subprocess.run([sys.executable, str(here / "build_excel.py"), str(src), str(xlsx)],
                       check=False)
    sys.exit(r.returncode)


def main():
    ap = argparse.ArgumentParser(description="TikTok Shop review harvester + report")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    h = sub.add_parser("harvest")
    h.add_argument("url_or_id")
    h.add_argument("--page-size", type=int, default=50)
    h.add_argument("--out", default="./output")
    r = sub.add_parser("report")
    r.add_argument("src")
    r.add_argument("--xlsx", default=None)
    a = sub.add_parser("all")
    a.add_argument("url_or_id")
    a.add_argument("--page-size", type=int, default=50)
    a.add_argument("--out", default="./output")
    args = ap.parse_args()

    if args.cmd == "check":
        cmd_check()
    elif args.cmd == "harvest":
        cmd_harvest(args.url_or_id, args.page_size, args.out)
    elif args.cmd == "report":
        cmd_report(args.src, args.xlsx)
    elif args.cmd == "all":
        fn = cmd_harvest(args.url_or_id, args.page_size, args.out)
        if fn is not None:
            cmd_report(fn, None)


if __name__ == "__main__":
    main()
