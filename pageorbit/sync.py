from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlencode

from pageorbit.http import ApiClient

MAX_RETRIES = 20
PER_PAGE = 10
ORDER_LIMIT = 7


def run_sync(args) -> int:
    source = json.loads(Path(args.source).read_text())
    sink_dir = Path(args.sink)
    sink_dir.mkdir(parents=True, exist_ok=True)
    ckpt_path = Path(args.checkpoint)
    state = _load_checkpoint(ckpt_path)

    mirrors = {res: _load_mirror(sink_dir / f"{res}.jsonl") for res in source["resources"]}
    client = ApiClient(args.base, source["api_key"])

    def persist():
        _write_checkpoint(ckpt_path, state)

    for resource in source["resources"]:
        entry = state.setdefault(resource, {"watermark": None})
        sink_path = sink_dir / f"{resource}.jsonl"
        if resource == "items":
            _sync_items(client, mirrors[resource], sink_path, entry, persist)
        elif resource == "orders":
            _sync_orders(client, mirrors[resource], sink_path, entry, persist)
        elif resource == "shipments":
            _sync_shipments(client, mirrors[resource], sink_path, entry, persist)
        _write_mirror(sink_path, mirrors[resource])
        persist()
    return 0


def _get_json(client: ApiClient, url: str):
    """GET with 429 retry driven by Retry-After / X-Retry-After-Ms."""
    for attempt in range(MAX_RETRIES):
        resp = client.get(url)
        if resp.status != 429:
            if resp.status >= 400:
                raise RuntimeError(f"GET {url} failed: HTTP {resp.status} {resp.body!r}")
            return json.loads(resp.body.decode()), resp.headers
        delay_ms = _retry_delay_ms(resp.headers)
        time.sleep(delay_ms / 1000.0)
    raise RuntimeError(f"GET {url} still rate limited after {MAX_RETRIES} retries")


def _retry_delay_ms(headers: dict) -> float:
    raw_ms = headers.get("x-retry-after-ms")
    if raw_ms is not None:
        try:
            return float(raw_ms)
        except ValueError:
            pass
    raw = headers.get("retry-after")
    if raw is not None:
        try:
            return float(raw) * 1000.0
        except ValueError:
            pass
    return 150.0


def _next_link(headers: dict) -> str | None:
    link = headers.get("link")
    if not link:
        return None
    for part in link.split(","):
        match = re.match(r"\s*<([^>]+)>\s*;(.*)$", part)
        if not match:
            continue
        target, params = match.groups()
        if re.search(r'rel\s*=\s*("next"|next)', params):
            return target
    return None


def _normalize_item(row: dict) -> dict:
    quantity = row.get("quantity", row.get("qty"))
    return {
        "id": row["id"],
        "sku": row["sku"],
        "quantity": int(quantity),
        "updated_at": row["updated_at"],
        "deleted": bool(row.get("deleted", False)),
    }


def _normalize_order(row: dict) -> dict:
    return {
        "id": row["id"],
        "code": row["code"],
        "status": row["status"],
        "total_cents": row["total_cents"],
        "updated_at": row["updated_at"],
    }


def _normalize_shipment(row: dict) -> dict:
    return {
        "id": row["id"],
        "order_id": row["order_id"],
        "state": row["state"],
        "tracking": row["tracking"],
        "updated_at": row["updated_at"],
    }


def _upsert(mirror: dict, record: dict):
    mirror[record["id"]] = record


def _bump_watermark(entry: dict, records: list[dict]):
    for record in records:
        ts = record["updated_at"]
        if entry.get("watermark") is None or ts > entry["watermark"]:
            entry["watermark"] = ts


def _sync_items(client: ApiClient, mirror: dict, sink_path: Path, entry: dict, persist):
    # page/cursor/after pagination with truncated-page resume plus
    # full-id-set deletion detection across waves.
    if entry.get("done"):
        entry["page"] = 1
        entry["after"] = None
        entry["seen"] = []
        entry["done"] = False
    # Only ids observed during the current full scan count as present;
    # mirror-only ids (e.g. ITM-0007) are silent deletions.
    seen = set(entry.setdefault("seen", []))
    page = entry.setdefault("page", 1)
    after = entry.get("after")

    while True:
        query = {"page": page, "per_page": PER_PAGE}
        if after:
            query["after"] = after
        payload, _ = _get_json(client, "/v1/items?" + urlencode(query))
        rows = payload.get("items", [])
        records = [_normalize_item(row) for row in rows]
        for record in records:
            _upsert(mirror, record)
            seen.add(record["id"])
        _bump_watermark(entry, records)

        if payload.get("truncated"):
            # Same page, follow with ?after=resume_after before advancing.
            after = payload.get("resume_after")
            entry["after"] = after
        else:
            after = None
            entry["after"] = None
            page += 1
            entry["page"] = page
        entry["seen"] = sorted(seen)
        _write_mirror(sink_path, mirror)
        persist()

        if not payload.get("truncated") and page > payload.get("pages", page - 1):
            break

    # Rows that disappeared from the source (no delete event) are marked deleted.
    for item_id, row in list(mirror.items()):
        if item_id not in seen and not row.get("deleted"):
            row["deleted"] = True
            mirror[item_id] = row
    entry["done"] = True
    _write_mirror(sink_path, mirror)
    persist()


def _sync_orders(client: ApiClient, mirror: dict, sink_path: Path, entry: dict, persist):
    if entry.get("done"):
        entry["cursor"] = None
        entry["done"] = False
    cursor = entry.get("cursor")

    while True:
        query = {"limit": ORDER_LIMIT}
        if cursor:
            query["cursor"] = cursor
        payload, _ = _get_json(client, "/v1/orders?" + urlencode(query))
        records = [_normalize_order(row) for row in payload.get("data", [])]
        for record in records:
            _upsert(mirror, record)
        _bump_watermark(entry, records)
        cursor = payload.get("next_cursor")
        entry["cursor"] = cursor
        _write_mirror(sink_path, mirror)
        persist()
        if not cursor:
            break
    entry["done"] = True
    persist()


def _sync_shipments(client: ApiClient, mirror: dict, sink_path: Path, entry: dict, persist):
    if entry.get("done"):
        entry["next_url"] = None
        entry["done"] = False
    # Only follow Link rel=next; never send a page parameter.
    next_url = entry.get("next_url") or "/v1/shipments"

    while True:
        payload, headers = _get_json(client, next_url)
        records = [_normalize_shipment(row) for row in payload.get("shipments", [])]
        for record in records:
            _upsert(mirror, record)
        _bump_watermark(entry, records)
        next_url = _next_link(headers)
        entry["next_url"] = next_url
        _write_mirror(sink_path, mirror)
        persist()
        if not next_url:
            break
    entry["done"] = True
    persist()


def _load_mirror(path: Path) -> dict:
    mirror: dict = {}
    if path.is_file():
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                mirror[row["id"]] = row
    return mirror


def _write_mirror(path: Path, mirror: dict):
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w") as fh:
        for row in mirror.values():
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def _load_checkpoint(path: Path) -> dict:
    if path.is_file():
        return json.loads(path.read_text())
    return {}


def _write_checkpoint(path: Path, state: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True))
    os.replace(tmp, path)
