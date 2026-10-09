"""Optional mihomo/Clash controller helper. Does not change proxies unless 'switch' is requested."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from urllib.parse import quote, urlsplit

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except (AttributeError, OSError):
    pass


def controller_request(method, path, body=None):
    base = os.environ.get('CLASH_API', 'http://127.0.0.1:9090').rstrip('/')
    parsed = urlsplit(base)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('CLASH_API must be an HTTP(S) controller URL without credentials.')
    secret = os.environ.get('CLASH_SECRET')
    headers = {'Content-Type': 'application/json'}
    if secret:
        headers['Authorization'] = f'Bearer {secret}'
    payload = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    req = urllib.request.Request(base + path, data=payload, headers=headers, method=method)
    # Controller calls must not go through the traffic proxy being changed.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=10) as response:
            raw = response.read()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise RuntimeError('Controller authentication failed; set CLASH_SECRET.') from exc
        raise RuntimeError(f'Controller returned HTTP {exc.code}; check group/node names.') from exc
    except urllib.error.URLError as exc:
        raise RuntimeError('Cannot connect to controller. Enable external-controller and set CLASH_API, or switch nodes manually in your proxy app.') from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description='Optional Clash/mihomo HTTP controller helper')
    sub = parser.add_subparsers(dest='cmd', required=True)
    sub.add_parser('list')
    switch = sub.add_parser('switch')
    switch.add_argument('group')
    switch.add_argument('node')
    args = parser.parse_args(argv)
    try:
        if args.cmd == 'list':
            proxies = controller_request('GET', '/proxies').get('proxies', {})
            for name, info in proxies.items():
                if info.get('type') in ('Selector', 'URLTest', 'Fallback'):
                    print(f'[{info["type"]}] {name} | now={info.get("now", "")} | nodes={info.get("all", [])}')
        else:
            controller_request('PUT', '/proxies/' + quote(args.group, safe=''), {'name': args.node})
            selected = controller_request('GET', '/proxies/' + quote(args.group, safe=''))
            if selected.get('now') != args.node:
                raise RuntimeError('Controller did not confirm requested node; inspect the proxy app.')
            print(f'Switched {args.group} -> {args.node}')
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f'[error] {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
