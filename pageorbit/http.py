from __future__ import annotations
import urllib.error, urllib.request, json
from dataclasses import dataclass

@dataclass
class Response:
    status: int
    headers: dict
    body: bytes
    url: str

class ApiClient:
    def __init__(self, base: str, api_key: str):
        self.base = base.rstrip("/")
        self.api_key = api_key

    def get(self, path: str) -> Response:
        url = path if path.startswith("http") else self.base + path
        req = urllib.request.Request(url, headers={"X-Api-Key": self.api_key, "User-Agent": "pageorbit/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return Response(r.getcode(), {k.lower(): v for k,v in r.headers.items()}, r.read(), r.geturl())
        except urllib.error.HTTPError as e:
            return Response(e.code, {k.lower(): v for k,v in (e.headers.items() if e.headers else [])}, e.read() if e.fp else b"", url)

    def post_json(self, path: str, payload: dict) -> Response:
        url = path if path.startswith("http") else self.base + path
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "X-Api-Key": self.api_key}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return Response(r.getcode(), {k.lower(): v for k,v in r.headers.items()}, r.read(), r.geturl())
        except urllib.error.HTTPError as e:
            return Response(e.code, {k.lower(): v for k,v in (e.headers.items() if e.headers else [])}, e.read() if e.fp else b"", url)
