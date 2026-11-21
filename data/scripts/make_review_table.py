"""Generate docs/gold-review.md: compact human-review table of all 10 records (frozen gold + second-pass JSON)."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
gold = [
    json.loads(x)
    for x in (ROOT / "data/gold/gold_pilot.jsonl").read_text().splitlines()
]
exp = {
    r["id"]: r["expected"]
    for r in map(
        json.loads, (ROOT / "data/experiment/expected.jsonl").read_text().splitlines()
    )
}
sp = {
    r["gold_id"]: r
    for r in json.loads((ROOT / "data/review/second_pass.json").read_text())["records"]
}
man = json.loads((ROOT / "data/gold/MANIFEST.json").read_text())
SHORT = {
    "time_local_no_timezone_published": "tz?",
    "live_flag_ignored": "live",
    "asterisk_suffix_unexplained_preserved": "*",
    "entry_kind_unclassified_not_assumed_brand": "not-brand",
}
L = [
    f"# Gold pilot v{man['version']} - human review table (10/10 records)",
    "",
    f"File `data/gold/gold_pilot.jsonl`, sha256 `{man['sha256'][:16]}...`. Policy: `docs/annotation-guidelines.md` (provisionally approved). **v0.2.2: all 10 records owner-verified (`human_verified=true`) on 2026-11-19.** Source: https://www.cameramoda.it/en/milano-moda-donna/calendar/ (captured 2026-11-19). No independent corroboration exists.",
    "Check each row against the live page: *Source row* is the verbatim calendar row under the stated day heading. *Extracted* = what the gold expects a correct extractor to output. `2nd` = machine second pass (different parsing route + live drift check) - guards extraction errors only.",
    "",
    "| # | id | day | source row (verbatim) | extracted: name / brand / type / date_time / venue | venue status | kind | 2nd | ambiguities | OK / fix / drop |",
    "|---|---|---|---|---|---|---|---|---|---|",
]
for i, g in enumerate(gold, 1):
    e = exp[g["gold_id"]]
    ex = " / ".join(
        "null" if e[k] is None else str(e[k])
        for k in ("show_name", "brand", "event_type", "date_time", "venue")
    )
    amb = ", ".join(SHORT.get(a, a) for a in g["ambiguities"])
    L.append(
        f"| {i} | {g['cnmi_event_id']} | {g['date']} | `{g['source_row_text'].replace('|', chr(92) + '|')}` | {ex} | {g['venue_status']} | {g['entry_kind']} | {'pass' if sp[g['gold_id']]['all_ok'] else 'FAIL'} | {amb} | |"
    )
L += [
    "",
    "Legend: `tz?` no timezone published (kept local) · `live` the word 'live' in the time cell is ignored · `*` unexplained asterisk preserved · `not-brand` VOGUE WORLD kept, not assumed a brand (brand = null, not scored) · `venue_*_null` venue null for that status · `map_coordinates_placeholder_ignored` coordinates exist on the page but are not locations.",
    "",
    "## Questions raised in review (resolved by owner approval 2026-11-19)",
    "- Dates under day headings: owner approved all 10 records after review (four-route automated agreement plus a spot-check of the page); the page itself remains the only source.",
    "- Resolved: the 9 ordinary rows are `listed_show_entry` (listed by CNMI; not verified as fashion houses); organizer typing as `schema:Brand` is a documented assumption.",
    "- Resolved: rows whose only missing field is the venue are `confirmed_no_venue`.",
    "",
    "Sign-off: owner approved all 10 records and both renames (2026-11-19); recorded in v0.2.1; v0.2.2 is a wording-only provenance correction. v0.1.0 to v0.2.1 are archived.",
]
(ROOT / "docs/gold-review.md").write_text("\n".join(L) + "\n")
print("ok")
