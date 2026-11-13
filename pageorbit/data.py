"""Deterministic fixture records for two waves."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

def ts(days, seconds=0):
    return (T0 + timedelta(days=days, seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")

def items_wave1():
    rows=[]
    for i in range(1, 24):
        rows.append({
            "id": f"ITM-{i:04d}",
            "sku": f"SKU-{i:04d}",
            "qty": 10 + i,
            "updated_at": ts(1, i),
        })
    return rows

def items_wave2():
    rows=[]
    for r in items_wave1():
        if r["id"] == "ITM-0007":
            continue  # deleted
        q = r["qty"]
        if r["id"] == "ITM-0003":
            q = 99
            upd = ts(10, 3)
        else:
            upd = r["updated_at"]
        rows.append({"id": r["id"], "sku": r["sku"], "quantity": q, "updated_at": upd})
    rows.append({"id": "ITM-0100", "sku": "SKU-0100", "quantity": 4, "updated_at": ts(11, 1)})
    return rows

def orders_wave1():
    rows=[]
    for i in range(1, 16):
        rows.append({
            "id": f"ORD-{i:04d}",
            "code": f"C{i:04d}",
            "status": "open" if i % 3 else "paid",
            "total_cents": 1000 * i,
            "updated_at": ts(2, i * 3),
        })
    return rows

def orders_wave2():
    rows=[]
    for r in orders_wave1():
        if r["id"] == "ORD-0004":
            rows.append({**r, "status": "cancelled", "updated_at": ts(12, 4)})
        else:
            rows.append(dict(r))
    rows.append({"id": "ORD-0200", "code": "C0200", "status": "open", "total_cents": 888, "updated_at": ts(12, 20)})
    return rows

def shipments_wave1():
    rows=[]
    for i in range(1, 12):
        rows.append({
            "id": f"SHP-{i:04d}",
            "order_id": f"ORD-{((i % 15) + 1):04d}",
            "state": "in_transit" if i % 2 else "delivered",
            "tracking": f"TRK{i:04d}",
            "updated_at": ts(3, i * 2),
        })
    return rows

def shipments_wave2():
    rows=[]
    for r in shipments_wave1():
        if r["id"] == "SHP-0002":
            rows.append({**r, "state": "void", "updated_at": ts(13, 2)})
        else:
            rows.append(dict(r))
    rows.append({"id": "SHP-0200", "order_id": "ORD-0200", "state": "packed", "tracking": "TRK0200", "updated_at": ts(13, 9)})
    return rows
