"""Build versioned, deterministic experiment inputs from the CNMI parse + frozen gold.
test split  = the 10 frozen gold records (scored);
train split = 2 few-shot examples from OTHER calendar rows (never scored, never in test).
Every model/technique receives byte-identical `text` for a given record."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "experiment"
VERSION = "0.1.1"
HEADER = "Source: CNMI official calendar, Milano Moda Donna Spring/Summer 2027, 22-28 September 2026."
FIELDS = ("show_name", "brand", "event_type", "date_time", "venue")
PLACEHOLDER_VENUES = ("location in the invitation", "digital")


def _strip_star(s: str) -> str:
    return s.rstrip(" *").strip()


def source_text(row: dict) -> str:
    day = dt.date.fromisoformat(row["day_heading_date"])
    return (
        f"{HEADER}\nDay: {day.strftime('%A')} {day.day} September {day.year}\n"
        f"Row (type | time | title | address): {row['type']} | {row['time_raw']} | {row['title']} | {row['address'] or ''}"
    )


def expected_from_row(
    row: dict, venue_is_address: bool, unclassified: bool = False
) -> dict:
    name = row[
        "title"
    ].strip()  # policy 1: unexplained "*" preserved exactly as published
    return {
        "show_name": name,
        "brand": None if unclassified else name,
        **({"_unscored": ["brand"]} if unclassified else {}),
        "event_type": "fashion show",
        "date_time": f"{row['day_heading_date']}T{int(row['time'].split(':')[0]):02d}:{row['time'].split(':')[1]}",
        "venue": row["address"] if venue_is_address else None,
    }


def example_output(row: dict, text: str, venue_is_address: bool = True) -> dict:
    e = expected_from_row(row, venue_is_address)
    quote = (
        f"{row['type']} | {row['time_raw']} | {row['title']} | {row['address'] or ''}"
    )
    assert quote in text
    return {"events": [{**e, "evidence_quote": quote}]}


def build(write: bool = True) -> dict:
    gold = [
        json.loads(line)
        for line in (ROOT / "data/gold/gold_pilot.jsonl").read_text().splitlines()
    ]
    rows = [
        json.loads(line)
        for line in (ROOT / "data/cnmi_calendar_parsed.jsonl").read_text().splitlines()
    ]
    by_id = {r["cnmi_event_id"]: r for r in rows}
    test_ids = {g["cnmi_event_id"] for g in gold}
    test, expected = [], []
    for g in gold:
        r = by_id[g["cnmi_event_id"]]
        test.append({"id": g["gold_id"], "split": "test", "text": source_text(r)})
        expected.append(
            {
                "id": g["gold_id"],
                "expected": expected_from_row(
                    r,
                    g["venue_status"] == "address",
                    g["entry_kind"] == "unclassified_entry",
                ),
            }
        )
    test_titles = {_strip_star(by_id[i]["title"]).casefold() for i in test_ids}
    cands = sorted(
        (
            r
            for r in rows
            if r["type"] == "F"
            and r["cnmi_event_id"] not in test_ids
            and r["address"]
            and r["address"].strip().lower() not in PLACEHOLDER_VENUES
            and _strip_star(r["title"]).casefold() not in test_titles
            and r["title"] != "CNMI FASHION HUB OPENING"
        ),
        key=lambda r: (r["day_heading_date"], r["time"], r["cnmi_event_id"]),
    )
    train, days = [], set()
    for r in cands:
        if r["day_heading_date"] not in days and len(train) < 2:
            days.add(r["day_heading_date"])
            t = source_text(r)
            train.append(
                {
                    "id": f"train-{r['cnmi_event_id']}",
                    "split": "train",
                    "text": t,
                    "output": example_output(r, t),
                }
            )
    withheld = sorted(
        (
            r
            for r in rows
            if r["type"] == "F"
            and r["cnmi_event_id"] not in test_ids
            and (r["address"] or "").strip().lower() == "location in the invitation"
            and _strip_star(r["title"]).casefold() not in test_titles
        ),
        key=lambda r: (r["day_heading_date"], r["time"], r["cnmi_event_id"]),
    )
    if withheld:  # teaches null for unavailable venue
        r = withheld[0]
        t = source_text(r)
        train.append(
            {
                "id": f"train-{r['cnmi_event_id']}",
                "split": "train",
                "text": t,
                "output": example_output(r, t, False),
            }
        )
    assert not ({t["id"].removeprefix("train-") for t in train} & test_ids)
    files = {
        "test_inputs.jsonl": test,
        "expected.jsonl": expected,
        "fewshot_train.jsonl": train,
    }
    blobs = {
        n: "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in v)
        for n, v in files.items()
    }
    manifest = {
        "version": VERSION,
        "gold_sha256": json.loads((ROOT / "data/gold/MANIFEST.json").read_text())[
            "sha256"
        ],
        "sha256": {n: hashlib.sha256(b.encode()).hexdigest() for n, b in blobs.items()},
        "n_test": len(test),
        "n_train_examples": len(train),
        "train_includes_withheld_venue_example": bool(withheld),
        "leakage_check": "train ids and normalised titles disjoint from test (asserted at build)",
    }
    if write:
        OUT.mkdir(parents=True, exist_ok=True)
        for n, b in blobs.items():
            (OUT / n).write_text(b)
        (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=1))
    return {"test": test, "expected": expected, "train": train, "manifest": manifest}


if __name__ == "__main__":
    m = build()["manifest"]
    print(json.dumps(m, indent=1))
