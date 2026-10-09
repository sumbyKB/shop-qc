"""TikTok Shop reviews CLI; executable paths are independent of the working directory."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlsplit

from environment import (browser_country, cdp_live, cdp_port, check_dependencies,
                         detect_proxy, ensure_browser, exit_country, find_browser)

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except (AttributeError, OSError):
    pass

REGION_CC = {'us': 'US', 'th': 'TH', 'gb': 'GB', 'uk': 'GB', 'de': 'DE', 'fr': 'FR',
             'it': 'IT', 'es': 'ES', 'sa': 'SA', 'id': 'ID', 'vn': 'VN', 'ph': 'PH',
             'my': 'MY', 'sg': 'SG', 'jp': 'JP', 'kr': 'KR', 'mx': 'MX', 'br': 'BR'}
FETCH = """async (body) => {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 20000);
    try {
        const r = await fetch('/api/shop/pdp_desktop/get_product_reviews', {
            method: 'POST', headers: {'content-type': 'application/json'},
            body: JSON.stringify(body), signal: ctrl.signal});
        return {status: r.status, text: await r.text()};
    } catch (e) { return {status: -1, text: String(e)}; }
    finally { clearTimeout(timer); }
}"""
BACKOFFS = (5, 10, 20)


def extract_product_id(value):
    if re.fullmatch(r'\d{10,25}', value):
        return value
    parts = urlsplit(value).path.rstrip('/').split('/')
    if 'pdp' in parts and re.fullmatch(r'\d{10,25}', parts[-1]):
        return parts[-1]
    return None


def product_url(value, region=None):
    value = value.strip()
    pid = extract_product_id(value)
    if not pid:
        raise ValueError('Use a full https://shop.tiktok.com/<region>/pdp/.../<product_id> URL or numeric product ID; short links are unsupported.')
    if re.fullmatch(r'\d{10,25}', value):
        region = region or 'us'
        if region not in REGION_CC:
            raise ValueError('Unsupported region.')
        return pid, region, f'https://shop.tiktok.com/{region}/pdp/{pid}'
    parsed = urlsplit(value)
    match = re.match(r'^/([a-z]{2})/pdp/', parsed.path)
    if parsed.scheme != 'https' or parsed.netloc != 'shop.tiktok.com' or not match:
        raise ValueError('Only full HTTPS shop.tiktok.com regional PDP URLs are supported.')
    actual_region = match.group(1)
    if actual_region not in REGION_CC:
        raise ValueError(f'Unsupported region: {actual_region}')
    if region and REGION_CC[region] != REGION_CC[actual_region]:
        raise ValueError('--region conflicts with the product URL.')
    return pid, actual_region, value


def cmd_check(args):
    check_dependencies()
    cdp_port()
    browser = find_browser()
    live = cdp_live()
    if not browser and not live:
        raise RuntimeError('Install Edge/Chrome or set TT_BROWSER_PATH.')
    proxy = detect_proxy()
    print(f'[python] {sys.version.split()[0]} ({sys.executable})')
    print(f'[browser] {browser or "existing CDP"}; CDP {cdp_port()}: {"live" if live else "will launch"}')
    print(f'[network] configured route: {proxy}')
    region = product_url(args.url_or_id, args.region)[1] if args.url_or_id else args.region
    if args.skip_ip_check:
        print('[warn] Exit-country check skipped; verify the actual browser route manually.')
    else:
        if live:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                b = p.chromium.connect_over_cdp(f'http://127.0.0.1:{cdp_port()}', timeout=15000)
                if not b.contexts:
                    raise RuntimeError('CDP browser has no default context.')
                cc = browser_country(b.contexts[0])
        else:
            cc = exit_country(proxy)
        print(f'[network] exit country: {cc}')
        if region and cc != REGION_CC[region]:
            raise RuntimeError(f'Exit country {cc} must match product region {REGION_CC[region]}.')
    print('[check] PASS')
    return 0


def get_pdp_page(ctx, url, captcha_timeout=300):
    pid, region, _ = product_url(url)
    page = next((pg for pg in ctx.pages if pg.url == url), None) or ctx.new_page()
    if page.url != url:
        page.goto(url, wait_until='domcontentloaded', timeout=60000)
    deadline = time.monotonic() + captcha_timeout
    notified = False
    while True:
        try:
            title = page.title()
        except Exception:
            title = ''
        if title.strip() and 'security check' not in title.lower():
            break
        if time.monotonic() >= deadline:
            raise RuntimeError('Security Check was not completed within 5 minutes; solve it manually and retry.')
        if not notified:
            print('[captcha] Complete the browser Security Check manually (up to 5 minutes).', flush=True)
            notified = True
        page.wait_for_timeout(2000)
    try:
        final_pid, final_region, _ = product_url(page.url)
    except ValueError as exc:
        raise RuntimeError('PDP redirected to another page. Check proxy region and login/challenge state.') from exc
    if final_pid != pid or REGION_CC[final_region] != REGION_CC[region]:
        raise RuntimeError('PDP product/region does not match request; stopping before review requests.')
    page.wait_for_timeout(1500)
    return page


def extract_ssr_reviews(html):
    out, pos = [], 0
    decoder = json.JSONDecoder()
    while True:
        index = html.find('"product_reviews":', pos)
        if index < 0:
            return out
        start = index + len('"product_reviews":')
        tail = html[start:].lstrip()
        try:
            values, consumed = decoder.raw_decode(tail)
            if isinstance(values, list):
                out.extend(values)
            pos = start + len(html[start:]) - len(tail) + consumed
        except ValueError:
            pos = start


class HarvestStopped(RuntimeError):
    """A terminal request failure; partial data may still be saved."""


def fetch_page(page, body, errors, sleep=time.sleep):
    throttle_hits = 0
    for attempt in range(len(BACKOFFS) + 1):
        try:
            response = page.evaluate(FETCH, body)
            if response['status'] in (401, 403, 429):
                raise HarvestStopped(f'HTTP {response["status"]}: stopped; check challenge/login or wait before retrying.')
            data = json.loads(response['text'])
            if response['status'] == 200 and data.get('code') == 0 and isinstance(data.get('data'), dict):
                return data['data']
            code = data.get('code')
            message = f'HTTP {response["status"]}, code={code}'
            if code == 100000:
                throttle_hits += 1
                if throttle_hits >= 2:
                    raise HarvestStopped('code=100000 twice: stopped ALL rating passes; wait before retrying.')
            else:
                throttle_hits = 0
        except HarvestStopped:
            raise
        except Exception as exc:
            throttle_hits = 0
            message = f'{type(exc).__name__}: {str(exc)[:120]}'
        errors.append(message)
        if attempt < len(BACKOFFS):
            print(f'[retry] {message}; waiting {BACKOFFS[attempt]}s', flush=True)
            sleep(BACKOFFS[attempt])
    raise HarvestStopped('Review request failed after bounded retries; stopping all rating passes.')


def collect_reviews(page, pid, page_size, sleep=time.sleep):
    reviews, ratings, star_totals, errors = {}, None, {}, []
    stopped = None
    try:
        for star in (6, 5, 4, 3, 2, 1):
            start, duplicates = 1, 0
            while True:
                body = {'product_id': pid, 'page_start': start, 'page_size': page_size,
                        'sort_rule': 1, 'review_filter': {'filter_type': 1, 'filter_value': star},
                        'component_name': 'pdp_left_reviews'}
                data = fetch_page(page, body, errors, sleep)
                if data.get('review_ratings'):
                    if not isinstance(data['review_ratings'], dict):
                        raise HarvestStopped('Review ratings schema changed.')
                    ratings = data['review_ratings']
                if star != 6 and data.get('total_reviews') is not None:
                    try:
                        star_totals[str(star)] = int(data['total_reviews'])
                    except (TypeError, ValueError) as exc:
                        raise HarvestStopped('Invalid per-star review total.') from exc
                batch = data.get('product_reviews')
                if not isinstance(batch, list) or not isinstance(data.get('has_more'), (bool, int)):
                    raise HarvestStopped('Review response schema changed; inspect API before retrying.')
                new = 0
                for review in batch:
                    if not isinstance(review, dict) or not review.get('review_id'):
                        raise HarvestStopped('Review response lacks review_id.')
                    try:
                        review['review_rating'] = int(review['review_rating'])
                        if not 1 <= review['review_rating'] <= 5:
                            raise ValueError('rating outside 1..5')
                    except (KeyError, TypeError, ValueError) as exc:
                        raise HarvestStopped('Review rating schema changed.') from exc
                    key = str(review['review_id'])
                    if key not in reviews:
                        reviews[key] = review
                        new += 1
                print(f'[star={star} page={start}] got={len(batch)} new={new} total={len(reviews)}', flush=True)
                if not data['has_more']:
                    break
                duplicates = duplicates + 1 if new == 0 else 0
                if not batch or duplicates >= 2:
                    raise HarvestStopped('Pagination stalled while has_more=true; data is incomplete.')
                start += 1
                sleep(1.5)
            sleep(1.5)
    except HarvestStopped as exc:
        stopped = str(exc)
        errors.append(stopped)
        print(f'[stopped] {stopped}', flush=True)
    try:
        for review in extract_ssr_reviews(page.content()):
            if isinstance(review, dict) and review.get('review_id'):
                reviews.setdefault(str(review['review_id']), review)
    except Exception as exc:
        errors.append(f'SSR merge failed: {type(exc).__name__}')
    return list(reviews.values()), ratings, star_totals, errors, stopped


def completeness(reviews, ratings, star_totals, stopped):
    expected = (ratings or {}).get('review_count')
    try:
        expected = int(expected) if expected is not None else None
    except (ValueError, TypeError):
        expected = None
    counts = Counter(str(review.get('review_rating')) for review in reviews)
    if stopped or (expected is not None and len(reviews) < expected):
        return 'partial', expected
    if any(counts.get(star, 0) < total for star, total in star_totals.items()):
        return 'partial', expected
    if expected is None or set(star_totals) != {'1', '2', '3', '4', '5'}:
        return 'unknown', expected
    if len(reviews) != expected or sum(star_totals.values()) != expected:
        return 'unknown', expected
    if any(counts.get(star, 0) != total for star, total in star_totals.items()):
        return 'unknown', expected
    return 'complete', expected


def cmd_harvest(args):
    check_dependencies()
    pid, region, url = product_url(args.url_or_id, args.region)
    proxy = detect_proxy()
    ensure_browser(proxy)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(f'http://127.0.0.1:{cdp_port()}', timeout=15000)
        if not b.contexts:
            raise RuntimeError('CDP browser has no default context.')
        ctx = b.contexts[0]
        if not args.skip_ip_check:
            cc = browser_country(ctx)
            if cc != REGION_CC[region]:
                raise RuntimeError(f'Browser exit {cc} != product region {REGION_CC[region]}; restart skill browser after switching proxy.')
        else:
            print('[warn] Actual browser IP verification skipped.')
        page = get_pdp_page(ctx, url)
        reviews, ratings, star_totals, errors, stopped = collect_reviews(page, pid, args.page_size)
    status, expected = completeness(reviews, ratings, star_totals, stopped)
    result = {'product_id': pid, 'source_url': url,
              'harvested_at': time.strftime('%Y-%m-%d %H:%M:%S'),
              'total_reviews_claimed': expected, 'overall_score': (ratings or {}).get('overall_score'),
              'rating_breakdown': (ratings or {}).get('rating_result'), 'review_ratings': ratings,
              'star_filter_totals': star_totals, 'harvested_count': len(reviews),
              'status': status, 'stop_reason': stopped, 'errors': errors[:50], 'reviews': reviews}
    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    fn = out / f'reviews_{pid}.json'
    if fn.exists():
        fn = out / f'reviews_{pid}_{time.time_ns()}.json'
    fn.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'[saved] status={status}; {len(reviews)}/{expected} reviews -> {fn}', flush=True)
    return fn, 3 if not reviews else (0 if status == 'complete' else 4)


def cmd_report(src, xlsx=None):
    if not xlsx:
        data = json.loads(Path(src).read_text(encoding='utf-8'))
        suffix = '_部分数据' if data.get('status') != 'complete' else ''
        xlsx = Path.cwd() / 'report' / f'TikTok评论分析报告_{data["product_id"]}{suffix}.xlsx'
        if xlsx.exists():
            xlsx = xlsx.with_name(f'{xlsx.stem}_{time.time_ns()}.xlsx')
    return subprocess.run([sys.executable, str(Path(__file__).with_name('build_excel.py')), str(src), str(xlsx)], check=False).returncode


def main(argv=None):
    ap = argparse.ArgumentParser(description='TikTok Shop reviews + report (Python 3.10+, Edge/Chrome)')
    sub = ap.add_subparsers(dest='cmd', required=True)
    check = sub.add_parser('check')
    check.add_argument('url_or_id', nargs='?')
    for parser in (check, sub.add_parser('harvest'), sub.add_parser('all')):
        if parser is not check:
            parser.add_argument('url_or_id')
            parser.add_argument('--page-size', type=int, choices=range(1, 51), default=50, metavar='1..50')
            parser.add_argument('--out', default='./output')
        parser.add_argument('--region', choices=tuple(REGION_CC))
        parser.add_argument('--skip-ip-check', action='store_true', help='Only after manually verifying browser exit country')
    report = sub.add_parser('report')
    report.add_argument('src')
    report.add_argument('--xlsx')
    args = ap.parse_args(argv)
    try:
        if args.cmd == 'check':
            return cmd_check(args)
        if args.cmd == 'report':
            return cmd_report(args.src, args.xlsx)
        fn, code = cmd_harvest(args)
        if args.cmd == 'all' and code != 3:
            report_code = cmd_report(fn)
            return report_code or code
        return code
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        print(f'[error] {exc}', file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print('[stopped] Interrupted by user.', file=sys.stderr)
        return 130
    except Exception as exc:
        # Playwright errors are imported lazily so dependency preflight can run without it.
        print(f'[error] {type(exc).__name__}: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
