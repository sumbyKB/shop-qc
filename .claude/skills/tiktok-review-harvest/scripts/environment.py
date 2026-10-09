"""Machine-independent network and Chromium/CDP setup (standard library only)."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlsplit

IP_URLS = ('https://api.country.is/', 'https://ipwho.is/')
PROXY_PORTS = (7897, 7890, 7891, 10809, 8080)


def cdp_port():
    try:
        port = int(os.environ.get('TT_CDP_PORT', '9333'))
        if 1 <= port <= 65535:
            return port
    except ValueError:
        pass
    raise ValueError('TT_CDP_PORT must be an integer from 1 to 65535.')


def cdp_live():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f'http://127.0.0.1:{cdp_port()}/json/version', timeout=3) as response:
            data = json.load(response)
        return bool(data.get('webSocketDebuggerUrl'))
    except (OSError, ValueError):
        return False


def detect_proxy():
    """Use explicit configuration, then a local HTTP/mixed port, then direct access."""
    proxy = os.environ.get('TT_PROXY')
    if proxy:
        if proxy.lower() in ('direct', 'direct://'):
            return 'direct://'
        parsed = urlsplit(proxy)
        if parsed.scheme != 'http' or not parsed.hostname or not parsed.port:
            raise ValueError('TT_PROXY must be http://host:port or direct (SOCKS-only ports are unsupported).')
        if parsed.username or parsed.password:
            raise ValueError('Authenticated proxies are unsupported; use a local HTTP/mixed proxy port.')
        return proxy
    for port in PROXY_PORTS:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                return f'http://127.0.0.1:{port}'
        except OSError:
            continue
    return 'direct://'


def country_code(data):
    cc = data.get('country_code') or data.get('country')
    return cc.upper() if isinstance(cc, str) and len(cc) == 2 else None


def exit_country(proxy):
    proxies = {} if proxy == 'direct://' else {'http': proxy, 'https': proxy}
    opener = urllib.request.build_opener(urllib.request.ProxyHandler(proxies))
    for url in IP_URLS:
        try:
            with opener.open(url, timeout=8) as response:
                cc = country_code(json.load(response))
            if cc:
                return cc
        except (OSError, ValueError):
            continue
    raise RuntimeError('Cannot verify exit country. Check TT_PROXY/network; use --skip-ip-check only after manual verification.')


def browser_country(ctx):
    """Check the browser's actual route, including when attaching to an existing CDP."""
    page = ctx.new_page()
    try:
        for url in IP_URLS:
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=15000)
                cc = country_code(json.loads(page.locator('body').inner_text()))
                if cc:
                    return cc
            except Exception:
                continue
    finally:
        page.close()
    raise RuntimeError('Cannot verify browser exit country. Close the skill browser and check TT_PROXY; see --skip-ip-check.')


def find_browser():
    override = os.environ.get('TT_BROWSER_PATH') or os.environ.get('TT_EDGE_PATH')
    if override:
        path = Path(override).expanduser()
        if not path.is_file():
            raise ValueError(f'Browser executable does not exist: {path}')
        return str(path)
    candidates = []
    if sys.platform == 'win32':
        for key in ('PROGRAMFILES(X86)', 'PROGRAMFILES', 'LOCALAPPDATA'):
            base = os.environ.get(key)
            if base:
                candidates.extend(Path(base) / part for part in (
                    'Microsoft/Edge/Application/msedge.exe', 'Google/Chrome/Application/chrome.exe'))
    elif sys.platform == 'darwin':
        for base in (Path('/Applications'), Path.home() / 'Applications'):
            candidates.extend(base / part for part in (
                'Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
                'Google Chrome.app/Contents/MacOS/Google Chrome'))
    for path in candidates:
        if path.is_file():
            return str(path)
    for name in ('microsoft-edge', 'microsoft-edge-stable', 'google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'):
        path = shutil.which(name)
        if path:
            return path
    return None


def profile_dir():
    override = os.environ.get('TT_PROFILE_DIR')
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData/Local')
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library/Application Support'
    else:
        base = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
    return base / 'tiktok-review-harvest' / f'browser-{cdp_port()}'


def ensure_browser(proxy):
    if cdp_live():
        print(f'[browser] attaching to existing local CDP {cdp_port()}; proxy changes require restarting that browser')
        return
    # Do not try to launch into an occupied non-CDP port.
    with socket.socket() as sock:
        try:
            sock.bind(('127.0.0.1', cdp_port()))
        except OSError as exc:
            raise RuntimeError('CDP port is occupied; choose another TT_CDP_PORT.') from exc
    browser = find_browser()
    if not browser:
        raise RuntimeError('Install Microsoft Edge or Google Chrome, or set TT_BROWSER_PATH.')
    profile = profile_dir()
    profile.mkdir(parents=True, exist_ok=True)
    args = [browser, f'--remote-debugging-port={cdp_port()}', '--remote-debugging-address=127.0.0.1',
            f'--user-data-dir={profile}', f'--proxy-server={proxy}', '--no-first-run',
            '--no-default-browser-check', '--window-size=1400,950', 'about:blank']
    kwargs = {'creationflags': subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP} if sys.platform == 'win32' else {'start_new_session': True}
    subprocess.Popen(args, close_fds=True, **kwargs)
    for _ in range(20):
        time.sleep(1)
        if cdp_live():
            print(f'[browser] CDP ready; private profile: {profile}')
            return
    raise RuntimeError('Browser CDP did not start. Check executable, desktop availability and TT_PROFILE_DIR; do not use your daily browser profile.')


def check_dependencies():
    if sys.version_info < (3, 10):
        raise RuntimeError('Python 3.10 or newer is required.')
    missing = [name for name in ('playwright', 'openpyxl') if importlib.util.find_spec(name) is None]
    if missing:
        requirements = Path(__file__).resolve().parent.parent / 'requirements.txt'
        raise RuntimeError(f'Missing {", ".join(missing)}. Run: "{sys.executable}" -m pip install -r "{requirements}"')
