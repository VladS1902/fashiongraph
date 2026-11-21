"""Build the pilot gold set + source register from the parsed CNMI rows. Deterministic selection rule:
 R1: among type-F rows that are brand shows (exclude CNMI institutional rows), take the first row per calendar day
     (sorted by date, time, id) that has a published address  -> 7 rows;
 R2: add the first 3 type-F brand rows (same ordering) whose address is 'Location In The Invitation' or missing;
 R3: add the first row published with address 'DIGITAL' (ambiguity coverage) -> 10 rows total.
Fields are copied verbatim; nothing inferred. Gold is separate from any LLM prediction."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
URL = "https://www.cameramoda.it/en/milano-moda-donna/calendar/"
RETRIEVED = "2026-11-19"
EXCLUDE = {"CNMI FASHION HUB OPENING", "MILANO MODA GRADUATE"}
UNDISCLOSED = ("location in the invitation", "digital")


def has_venue(a):
    return bool(a) and a.strip().lower() not in UNDISCLOSED


def venue_status(a):
    a = (a or "").strip().lower()
    if not a:
        return "unpublished"  # address field empty on the page
    if a == "digital":
        return "digital"
    if a in UNDISCLOSED:
        return "invitation_only"  # page says 'Location in the invitation'
    return "address"


def select(rows):
    fs = sorted(
        (
            r
            for r in rows
            if r["type"] == "F" and r["title"].rstrip(" *") not in EXCLUDE
        ),
        key=lambda r: (r["day_heading_date"], r["time"] or "", r["cnmi_event_id"]),
    )
    out, days = [], set()
    for r in fs:
        if has_venue(r["address"]) and r["day_heading_date"] not in days:
            days.add(r["day_heading_date"])
            out.append(r)
    nov = [r for r in fs if not has_venue(r["address"])]
    wh = [r for r in nov if (r["address"] or "").strip().lower() != "digital"][:3]
    dg = [r for r in nov if (r["address"] or "").strip().lower() == "digital"][:1]
    out += wh + dg
    return sorted(
        out, key=lambda r: (r["day_heading_date"], r["time"] or "", r["cnmi_event_id"])
    )


UNCLASSIFIED = {
    "VOGUE WORLD: MILANO"
}  # policy 2: kept, but NOT assumed to be a fashion house/brand
VERSION = "0.2.2"
VERIFICATION = {
    "human_verified_by": "project owner (explicit approval, 2026-11-19: all 10 records approved)",
    "basis": "owner review of docs/gold-review.md v0.2.0; single official source, no independent corroboration",
}
POLICY = "annotation-policy-v1 (provisionally approved 2026-11-19; see docs/annotation-guidelines.md)"


def ambiguities(r, title):
    a = ["time_local_no_timezone_published"]
    if title.endswith("*"):
        a.append("asterisk_suffix_unexplained_preserved")
    if title.rstrip(" *") in UNCLASSIFIED:
        a.append("entry_kind_unclassified_not_assumed_brand")
    s = venue_status(r["address"])
    if s != "address":
        a.append(f"venue_{s}_null")
    if s == "invitation_only":
        a.append("map_coordinates_placeholder_ignored")
    if "live" in (r["time_raw"] or ""):
        a.append("live_flag_ignored")
    return a


def gold_record(r):
    title = r["title"]
    missing = [
        k
        for k in ("time", "address")
        if not r[k] or (k == "address" and not has_venue(r["address"]))
    ]
    return {
        "gold_id": f"mfw-ss27-{r['cnmi_event_id']}",
        "cnmi_event_id": r["cnmi_event_id"],
        "edition": "Milano Moda Donna Spring/Summer 2027, 22-28 September 2026",
        "name_raw": title,
        "entry_kind": "unclassified_entry"
        if title.rstrip(" *") in UNCLASSIFIED
        else "listed_show_entry",  # policy 2 / owner decision: CNMI-listed F row; not verified as a fashion house
        "brand_raw": None
        if title.rstrip(" *") in UNCLASSIFIED
        else (title[:-1].rstrip() if title.endswith("*") else title),
        "title_has_asterisk": title.endswith("*"),
        "event_type_code": r["type"],
        "event_type_label": "fashion show (CNMI code F, calendar section 'Fashion Shows')",
        "date": r["day_heading_date"],
        "time": r["time"],
        "time_raw": r["time_raw"],
        "venue_address_raw": r["address"] if has_venue(r["address"]) else None,
        "venue_address_published_as": r["address"],
        "venue_status": venue_status(r["address"]),
        "source_id": "cnmi-calendar-ss27",
        "source_row_text": f"{r['type']} | {r['time_raw']} | {title} | {r['address'] or ''}".strip(),
        "ambiguities": ambiguities(r, title),
        "annotation_policy": POLICY,
        "human_verified": True,
        **VERIFICATION,
        "evidence": f"Calendar row data-id-event={r['cnmi_event_id']}: type F, time '{r['time_raw']}', title '{title}', address '{r['address']}', under day heading {r['day_heading_date']}",
        "status": "confirmed"
        if not missing
        else ("confirmed_no_venue" if missing == ["address"] else "incomplete"),
        "missing_fields": missing,
        "notes": "venue is a street address only; no venue name published"
        if not missing
        else "no physical venue published (invitation_only / unpublished / digital, see venue_status); venue = null, any map coordinates ignored",
        "split": None,
    }


def main():
    rows = [
        json.loads(line)
        for line in (ROOT / "data/cnmi_calendar_parsed.jsonl").read_text().splitlines()
    ]
    sel = select(rows)
    (ROOT / "data/gold").mkdir(exist_ok=True)
    (ROOT / "data/gold/gold_pilot.jsonl").write_text(
        "".join(json.dumps(gold_record(r), ensure_ascii=False) + "\n" for r in sel)
    )
    raw = (ROOT / "data/raw/cnmi_calendar.html").read_bytes()
    src = {
        "source_id": "cnmi-calendar-ss27",
        "url": URL,
        "retrieved_on": RETRIEVED,
        "publisher": "Camera Nazionale della Moda Italiana (CNMI)",
        "licence": "unknown; (c) CNMI, robots.txt allows crawling; only factual fields stored, raw HTML not committed",
        "scope": "Milano Moda Donna SS2027 calendar, 22-28 Sep 2026; 63 type-F rows parsed",
        "evidence_snippet": "Calendar page heading: 'SPRING/SUMMER 2027 - 22-28 SEPTEMBER 2026'; page title 'Milano Moda Donna SS 2027 - 22-28 September 2026'",
        "verification_status": "verified",
        "corroboration": "none: single official source (CNMI calendar); second CNMI domain returned 503; no brand-site check (policy 5)",
        "html_sha256": hashlib.sha256(raw).hexdigest(),
        "split": None,
    }
    (ROOT / "data/source_register.jsonl").write_text(
        json.dumps(src, ensure_ascii=False) + "\n"
    )
    blob = (ROOT / "data/gold/gold_pilot.jsonl").read_bytes()
    history = []
    for mf in sorted((ROOT / "data/gold/archive").glob("MANIFEST.v*.json")):
        m = json.loads(mf.read_text())
        history.append(
            {
                "version": m["version"],
                "sha256": m["sha256"],
                "file": f"archive/gold_pilot.v{m['version']}.jsonl",
            }
        )
    manifest = {
        "dataset": "fashiongraph-pilot-gold",
        "version": VERSION,
        "records": len(sel),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "frozen_on": "2026-11-19",
        "source_id": "cnmi-calendar-ss27",
        "source_html_sha256": src["html_sha256"],
        "annotation_policy": POLICY,
        "review_status": "HUMAN VERIFIED by project owner (all 10 records, 2026-11-19); machine second-pass passed; single official source, no independent corroboration",
        "split_policy": "splits unassigned; test/train defined in data/experiment/MANIFEST.json",
        "change_rule": "any content change requires a new version + new checksum; previous versions are kept in data/gold/archive/",
        "history": history,
        "changes_vs_previous": "v0.2.1 -> v0.2.2: wording-only correction of the provenance text (human_verified_by). No scored, descriptive or status value changed.",
    }
    (ROOT / "data/gold/MANIFEST.json").write_text(json.dumps(manifest, indent=1))
    print(len(sel), "gold records, version", VERSION)


if __name__ == "__main__":
    main()
