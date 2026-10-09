"""Talk to mihomo REST API over named pipe: list proxy groups & US nodes."""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


import os


def http_over_pipe(method, path, secret=None, body=None):
    secret = secret or os.environ.get("CLASH_SECRET", "set-your-secret")
    handle = open(r"\\.\pipe\verge-mihomo", "r+b", buffering=0)
    try:
        payload = body.encode() if body else b""
        headers = (
            f"{method} {path} HTTP/1.1\r\n"
            f"Host: mihomo\r\n"
            f"Authorization: Bearer {secret}\r\n"
            f"Content-Length: {len(payload)}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode()
        handle.write(headers + payload)
        chunks = []
        while True:
            try:
                chunk = handle.read(65536)
            except OSError:
                break
            if not chunk:
                break
            chunks.append(chunk)
        raw = b"".join(chunks)
    finally:
        handle.close()
    head, _, body_raw = raw.partition(b"\r\n\r\n")
    status_line = head.split(b"\r\n")[0].decode(errors="replace")
    # handle chunked encoding minimally: try json parse of stripped body
    text = body_raw.decode(errors="replace")
    if "chunked" in head.decode(errors="replace").lower():
        # de-chunk
        out, pos = [], 0
        while pos < len(text):
            nl = text.find("\r\n", pos)
            if nl < 0:
                break
            try:
                size = int(text[pos:nl], 16)
            except ValueError:
                break
            if size == 0:
                break
            out.append(text[nl + 2:nl + 2 + size])
            pos = nl + 2 + size + 2
        text = "".join(out)
    return status_line, text


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        status, text = http_over_pipe("GET", "/proxies")
        print("status:", status)
        data, _ = json.JSONDecoder().raw_decode(text.lstrip())
        data = data.get("proxies", {})
        for name, info in data.items():
            if info.get("type") in ("Selector", "URLTest", "Fallback"):
                now = info.get("now", "")
                all_nodes = info.get("all", [])
                us = [n for n in all_nodes if any(
                    k in n.upper() for k in ("US", "UNITED STATES", "美国", "美國"))]
                print(f"[{info['type']}] {name} | now={now} | nodes={len(all_nodes)}"
                      + (f" | US候选: {us}" if us else ""))
    elif cmd == "switch":
        group, node = sys.argv[2], sys.argv[3]
        status, text = http_over_pipe("PUT", f"/proxies/{group}",
                                      body=json.dumps({"name": node}))
        print("switch status:", status, text[:200])


if __name__ == "__main__":
    main()
