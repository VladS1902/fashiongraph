# Source dataset coverage (M2) — pilot, captured 2026-11-19

**Source (authoritative, official):** CNMI calendar https://www.cameramoda.it/en/milano-moda-donna/calendar/ — page title "Milano Moda Donna SS 2027 - 22-28 September 2026". robots.txt allows crawling; licence not stated (©CNMI): only factual fields are stored; raw HTML is git-ignored (sha256 in `data/source_register.jsonl`). Edition existence is confirmed by the page's own heading; the CNMI home/MMD pages were used for confirmation only.

**Parsed:** 63 rows of calendar type F (fashion shows) — `data/cnmi_calendar_parsed.jsonl` (parser `data/scripts/parse_cnmi.py`, unit-tested on a fixture). All 63 have a time. Venue field: 46 street address, 7 "Location In The Invitation", 7 "DIGITAL", 3 empty. 22 titles end in "*" (meaning not explained on the page — kept verbatim, unresolved). Types P (presentations), E (events), A (appointments) exist on the page but were **not** parsed.

**Gold pilot:** `data/gold/gold_pilot.jsonl` (v0.2.2, `docs/annotation-guidelines.md`), 10 records by documented rule (see `data/scripts/build_gold.py`): 6 `confirmed` (name, date, time, street address), 4 `confirmed_no_venue` (1 empty address, 2 invitation-only, 1 digital). Fields copied verbatim from the page; no inference. Manual review: each record's evidence string was checked against the saved calendar row by an automated test; a machine second pass with a different parsing route agrees on all 10; **owner-verified on 2026-11-19** (`human_verified=true`, v0.2.1; review table `docs/gold-review.md`); single source, no independent corroboration.

**Ambiguities (unresolved):** meaning of "*" and "live"; "venue" is a street address, not a venue name; "VOGUE WORLD: MILANO" is typed F but is not a fashion house; times are local with no timezone published (none inferred); the page is a live schedule, so later changes are possible; calendar rows have no per-event URL (the page URL is cited with CNMI event id).

**Not covered:** collections, brand QIDs (only Prada verified), non-F calendar types, men's/other editions, brand-site corroboration. `split` is null: assign train/dev/test deliberately before experiments.
