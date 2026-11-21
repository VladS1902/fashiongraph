#!/usr/bin/env python3
"""Run a .rq file against Wikidata WDQS; cache JSON keyed by query hash.
Usage: run_query.py queries/x.rq [--force]
Cache file: kg/cache/<name>.<sha256[:12]>.json with endpoint, query, timestamp, status, response."""

import datetime
import hashlib
import json
import pathlib
import sys
import time

import requests

EP = "https://query.wikidata.org/sparql"
UA = "FashionGraphStudentProject/0.1 (university coursework; read-only queries)"
CACHE = pathlib.Path(__file__).parent / "cache"


def run(path, force=False):
    p = pathlib.Path(path)
    q = p.read_text()
    h = hashlib.sha256(q.encode()).hexdigest()[:12]
    out = CACHE / f"{p.stem}.{h}.json"
    if out.exists() and not force:
        c = json.loads(out.read_text())
        if c.get("http_status") == 200:  # never reuse cached failures (e.g. 429)
            return c, True
    CACHE.mkdir(exist_ok=True)
    time.sleep(1.0)
    for attempt in range(4):
        r = requests.post(
            EP,
            data={"query": q},
            headers={"User-Agent": UA, "Accept": "application/sparql-results+json"},
            timeout=70,
        )
        if r.status_code != 429:
            break
        time.sleep(int(r.headers.get("Retry-After", 10)) + 2)
    rec = {
        "endpoint": EP,
        "query_file": str(p),
        "query_sha256_12": h,
        "query": q,
        "timestamp_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "http_status": r.status_code,
    }
    if r.ok:
        rec["response"] = r.json()
        rec["row_count"] = len(rec["response"]["results"]["bindings"])
    else:
        rec["error"] = r.text[:500]
    out.write_text(json.dumps(rec, indent=1, ensure_ascii=False))
    return rec, False


if __name__ == "__main__":
    rec, cached = run(sys.argv[1], "--force" in sys.argv)
    print(
        f"{'CACHED' if cached else 'LIVE'} status={rec['http_status']} rows={rec.get('row_count')} ts={rec['timestamp_utc']}"
    )
    if "error" in rec:
        print(rec["error"])
        sys.exit(1)
    for b in rec["response"]["results"]["bindings"][:40]:
        print(
            " | ".join(
                f"{k}={v['value'].replace('http://www.wikidata.org/entity/', 'wd:')}"
                for k, v in b.items()
            )
        )
