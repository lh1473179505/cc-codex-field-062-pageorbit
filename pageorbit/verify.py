from __future__ import annotations
import json
from pathlib import Path

def _load_jsonl(path: Path):
    if not path.is_file():
        return []
    rows=[]
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows

def run_verify(args) -> int:
    sink = Path(args.sink)
    expect = json.loads(Path(args.expect).read_text())
    errors=[]
    for res in ("items","orders","shipments"):
        got={r["id"]: r for r in _load_jsonl(sink / f"{res}.jsonl")}
        exp={r["id"]: r for r in expect[res]}
        if set(got)!=set(exp):
            errors.append(f"{res} ids extra={sorted(set(got)-set(exp))} missing={sorted(set(exp)-set(got))}")
            continue
        for i,e in exp.items():
            g=got[i]
            for k,v in e.items():
                if k=="id":
                    continue
                if g.get(k)!=v:
                    errors.append(f"{res} {i} {k} {g.get(k)!r} != {v!r}")
    if errors:
        print("verify failed:")
        for e in errors:
            print(" -", e)
        return 1
    print("verify ok")
    return 0
