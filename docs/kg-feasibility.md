# KG feasibility memo (M1) — Wikidata / Milan Fashion Week

**Status: GO, narrowed to edition-level relations only** — recommended 2026-11-19. Human sign-off on research claims still required.
Evidence: executed queries in `queries/01–16b` (17 queries), raw responses with timestamps in `docs/kg-evidence/*.json` (endpoint https://query.wikidata.org/sparql, read-only, HTTP 200 each). Runner: `kg/run_query.py` (hash-cached, bounded timeout).

## Executed queries and what they show
| Query | Rows | Observation |
|---|---|---|
| 01 inspect Q130829 | 23 | Q130829 = "Milan Fashion Week" (*Italian clothing trade show*): instance of fashion week (Q253946), country Italy, location Milan, inception/start 1958, official site cameramoda.it, 3 `significant place` values (Fondazione Prada, Vigentino, Fashion District of Milano), many external IDs. **No edition, program, participant or show statements.** |
| 02 UNION/REGEX entity scan | 1 | Only Q130829 itself matches (instance/part-of/subclass/participant/significant-event links). Earlier broader versions returned HTTP 504 (logged as a challenge; the final version is selective). |
| 03 inbound links | 13 | Items pointing to Q130829: a Commons category, one image-main-subject item, 4 people via `participant in` (Q135188665, Q138427211, Q138335797, Q139062822), and venues/people via `significant event` (Palazzo Moncler, Ristorante Torre (Prada), Teatro Principe, Via Quaranta, Fashion District of Milano, Piazza Adriano Olivetti, …). |
| 04 MWAPI entity search "Milan Fashion Week" | 1 | Only Q130829. No separate edition/season item found by this search. |
| 05 Prada brand check | 30 | Brand entity Q193136 (fashion house, HQ Milan) exists. Most rows are noise (villages named Prada) — query is too loose, kept as a documented false start. |
| 06 fashion-show/event search | 0 | No show/collection event items found with the searched labels. Narrow regex; negative result is weak evidence on its own. |
| 07 class reuse | 1 | 28 instances of fashion week (Q253946) in all of Wikidata. |
| 08 Milan fashion houses coverage | 1 | 19 fashion houses with HQ Milan; **0 with `participant in` (P1344)**; 16 have website and inception. |
| 09 structure of all 28 fashion weeks | 28 | Start date on 4, location on 13, **0 with an edition item (P179) and 0 with part-of**. No fashion week in Wikidata is modelled with editions. |
| 10 venues linked | 22 | Linked venues exist with coordinates/address (e.g. Fondazione Prada, Palazzo Moncler). Links run venue→MFW (P793) or MFW→venue (P7153), not per show. |
| 11 GirlsAward editions (modelling precedent, noted during exploration then verified) | 8 | Wikidata does model other fashion events as separate edition items (e.g. GirlsAward 2024–2027 SPRING/SUMMER and AUTUMN/WINTER) with venue (P276); start dates are sparse/inconsistent. Supports creating MFW edition items. |

| 12 Italian entity search "Milano Moda Donna" | 0 | No item with that Italian label (alternative edition terminology). |
| 13 edition/collection terms (it, "Milano Fashion Week 2026") | 0 | No edition/season items. First draft filtered on a label-service variable (invalid); rewritten with rdfs:label and rerun. |
| 14 Prada collection/show items | 0 | No collection or show items for Prada (EN+IT regex). |
| 15 CONTROL: Italian search "Settimana della moda di Milano" | 1 | Returns Q130829, proving the Italian-language search path works, so 12–14 are genuine negatives (still bounded by label search). |

| 16a/16b participant/organizer sweep (bounded; a combined first draft 16 timed out 3 times and was split) | 5 / 4 | 5 of 28 fashion-week items carry organizer P664 (e.g. GirlsAward 2024 SPRING/SUMMER → GirlsAward); **0 carry P710 or P1344, and Q130829 has none**; only the 4 already-known people point to Q130829 via P1344. Conclusion unchanged: participant/brand relations absent; organizer-on-event has precedent. |

## Interpretation (observed vs. inference)
Observed: the top-level item exists and is well described; no edition or per-show items were found; brand items exist but none of 19 Milan houses record participation in any event; linked venues are attached to the whole week, not to a show; the pattern (no editions) holds across all 28 fashion weeks.
Inference (not proven): per-show date, venue and participating-brand relations for an edition are absent in Wikidata. We did **not** rely on the top-level item lacking properties; the gap is supported by the entity-level checks (queries 03, 04, 08, 09, 10).

## Recommendation
- **GO**, re-scoped to a specific missing relation set: *edition → show → (brand, date/time, venue)*.
- **Modelling:** reuse Wikidata properties where they exist — `part of` (P361), `instance of` (P31), `start time` (P580), `location` (P276), `participant` (P710), `organizer` (P664), `has part` (P527) and `series` (P179) — and schema.org (`Event`, `startDate`, `location`) in the RDF output. Add `ex:` terms only for evidence provenance (`ex:evidenceQuote`, `ex:extractionRun`) and show type. Property choice must still be checked against live property constraints before any claim.
- Candidate triples remain **candidates**; no Wikidata edits.

## Limits and open risks
1. Absence checks use EntitySearch (English and Italian labels, queries 12–15) and fixed property lists; items with unusual labels could still be missed. The P710/P664/P1344 sweep (16a/16b) is done and did not change the conclusion.
2. CNMI check done 2026-11-19: the SS2027 edition (22–28 Sep 2026) and a 63-show F-calendar exist (docs/data-coverage.md). The GO condition is met for show date/time/brand/address; collections are not published.
3. Evidence snapshots are point-in-time (2026-11-19); WDQS data changes.
4. Query 02 earlier versions timed out (504); the committed version is bounded.
5. Not tested: collection items, other participation properties (only P1344 swept), Italian-language labels. Entity-search negatives are weak evidence.
6. An earlier count of 6 inbound P793 venues was not independently re-counted; queries 03/10 list the actual rows.
