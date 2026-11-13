from __future__ import annotations
import json, time, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse, unquote
from pageorbit.data import items_wave1, items_wave2, orders_wave1, orders_wave2, shipments_wave1, shipments_wave2

API_KEY = "po-fixture-key-7f3a"
STATE = {"wave": 1, "hits": []}  # hits: (key, t)

def current(kind):
    w = STATE["wave"]
    if kind == "items":
        return items_wave2() if w == 2 else items_wave1()
    if kind == "orders":
        return orders_wave2() if w == 2 else orders_wave1()
    if kind == "shipments":
        return shipments_wave2() if w == 2 else shipments_wave1()
    return []

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        return

    def _send(self, status, body, headers=None, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if headers:
            for k,v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _auth(self):
        if self.headers.get("X-Api-Key") != API_KEY:
            self._send(401, {"error": "unauthorized"})
            return False
        return True

    def _rate(self):
        now = time.monotonic()
        window = [t for t in STATE["hits"] if now - t < 0.2]
        if len(window) >= 3:
            STATE["hits"] = window
            self._send(429, {"error": "rate"}, headers={"Retry-After": "0", "X-Retry-After-Ms": "150"})
            return False
        window.append(now)
        STATE["hits"] = window
        return True

    def _read_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw.decode() or "{}")

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        if path == "/_ctl/wave":
            body = self._read_json()
            STATE["wave"] = int(body.get("wave", 1))
            return self._send(200, {"wave": STATE["wave"]})
        return self._send(404, {"error": "no"})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        qs = parse_qs(parsed.query)
        if not self._auth():
            return
        if not self._rate():
            return
        if path == "/v1/items":
            return self._items(qs)
        if path == "/v1/orders":
            return self._orders(qs)
        if path == "/v1/shipments":
            return self._shipments(qs, parsed)
        return self._send(404, {"error": "no"})

    def _items(self, qs):
        rows = current("items")
        per = int(qs.get("per_page", ["10"])[0])
        page = int(qs.get("page", ["1"])[0])
        pages = (len(rows) + per - 1) // per
        start = (page - 1) * per
        chunk = rows[start:start+per]
        # truncated page 2 in wave 1 only, unless after is provided
        if STATE["wave"] == 1 and page == 2 and per == 10:
            after = qs.get("after", [None])[0]
            if not after:
                chunk = chunk[:3]
                resume = chunk[-1]["id"] if chunk else None
                return self._send(200, {"page": page, "pages": pages, "items": chunk, "truncated": True, "resume_after": resume})
            # return remainder of page 2 after id
            full = rows[start:start+per]
            idx = next((i for i,r in enumerate(full) if r["id"]==after), None)
            if idx is None:
                chunk = full
            else:
                chunk = full[idx+1:]
        return self._send(200, {"page": page, "pages": pages, "items": chunk})

    def _orders(self, qs):
        rows = current("orders")
        limit = int(qs.get("limit", ["7"])[0])
        cursor = qs.get("cursor", [None])[0]
        start = 0
        if cursor:
            start = next((i+1 for i,r in enumerate(rows) if r["id"]==cursor), 0)
        chunk = rows[start:start+limit]
        nxt = chunk[-1]["id"] if start+limit < len(rows) and chunk else None
        return self._send(200, {"data": chunk, "next_cursor": nxt})

    def _shipments(self, qs, parsed):
        rows = current("shipments")
        # ignore page= if present
        marker = qs.get("marker", [None])[0]
        limit = 4
        start = 0
        if marker:
            start = next((i+1 for i,r in enumerate(rows) if r["id"]==marker), 0)
        chunk = rows[start:start+limit]
        headers = {}
        if start+limit < len(rows) and chunk:
            next_marker = chunk[-1]["id"]
            # Link uses the incoming host
            host = self.headers.get("Host") or "127.0.0.1"
            scheme = "http"
            link = f'<{scheme}://{host}/v1/shipments?marker={next_marker}>; rel="next"'
            headers["Link"] = link
        return self._send(200, {"shipments": chunk}, headers=headers)


def serve(host="127.0.0.1", port=8763, wave=1):
    STATE["wave"] = wave
    STATE["hits"] = []
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"pageorbit fixture API on http://{host}:{port} wave={wave}")
    httpd.serve_forever()

if __name__ == "__main__":
    serve()
