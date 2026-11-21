# FashionGraph: Enriching Wikidata with Knowledge about Milan Fashion Week

*A comparative study of three language models for fashion-event knowledge-graph enrichment.* Status: work in progress; see the Results section.

Gold dataset v0.2.2 (sha256 `0265b3dd5a457020...`), 10 CNMI calendar records, owner-verified, single source.

## 1. Topic, gap and feasibility
### KG feasibility memo (M1) — Wikidata / Milan Fashion Week

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

## 2. Source data and annotation
# Source dataset coverage (M2) — pilot, captured 2026-11-19

**Source (authoritative, official):** CNMI calendar https://www.cameramoda.it/en/milano-moda-donna/calendar/ — page title "Milano Moda Donna SS 2027 - 22-28 September 2026". robots.txt allows crawling; licence not stated (©CNMI): only factual fields are stored; raw HTML is git-ignored (sha256 in `data/source_register.jsonl`). Edition existence is confirmed by the page's own heading; the CNMI home/MMD pages were used for confirmation only.

**Parsed:** 63 rows of calendar type F (fashion shows) — `data/cnmi_calendar_parsed.jsonl` (parser `data/scripts/parse_cnmi.py`, unit-tested on a fixture). All 63 have a time. Venue field: 46 street address, 7 "Location In The Invitation", 7 "DIGITAL", 3 empty. 22 titles end in "*" (meaning not explained on the page — kept verbatim, unresolved). Types P (presentations), E (events), A (appointments) exist on the page but were **not** parsed.

**Gold pilot:** `data/gold/gold_pilot.jsonl` (v0.2.2, `docs/annotation-guidelines.md`), 10 records by documented rule (see `data/scripts/build_gold.py`): 6 `confirmed` (name, date, time, street address), 4 `confirmed_no_venue` (1 empty address, 2 invitation-only, 1 digital). Fields copied verbatim from the page; no inference. Manual review: each record's evidence string was checked against the saved calendar row by an automated test; a machine second pass with a different parsing route agrees on all 10; **owner-verified on 2026-11-19** (`human_verified=true`, v0.2.1; review table `docs/gold-review.md`); single source, no independent corroboration.

**Ambiguities (unresolved):** meaning of "*" and "live"; "venue" is a street address, not a venue name; "VOGUE WORLD: MILANO" is typed F but is not a fashion house; times are local with no timezone published (none inferred); the page is a live schedule, so later changes are possible; calendar rows have no per-event URL (the page URL is cited with CNMI event id).

**Not covered:** collections, brand QIDs (only Prada verified), non-F calendar types, men's/other editions, brand-site corroboration. `split` is null: assign train/dev/test deliberately before experiments.

### Gold annotation guidelines — annotation-policy-v1
Status: policy **provisionally approved by the project owner on 2026-11-19**; the owner then approved all 10 gold records and two label renames the same day, recorded as gold **v0.2.1** (and, after a wording-only provenance correction, **v0.2.2**; `human_verified=true`, `data/gold/MANIFEST.json`). Verification means owner review of the single official source; there is no independent corroboration.

## Source and unit
Unit = one type-F row of the official CNMI calendar for Milano Moda Donna SS2027 (22–28 Sep 2026). Fields are copied from the page; nothing is inferred. Primary and only source (policy 5): **no independent corroboration exists** — the second CNMI domain returned 503 and no brand-site check was done. This is recorded in `data/source_register.jsonl` (`corroboration`) and must appear in the report's limitations.

## Policies
| # | Policy | Implementation |
|---|---|---|
| 1 | Unexplained `*` suffixes are preserved exactly as published | `name_raw` keeps the `*`; expected `show_name`/`brand` keep it; RDF show `rdfs:label` keeps it; prompts tell models to copy names exactly. The meaning is **unknown** and never interpreted. Scoring compares names after normalising a trailing `*` (so the unknown suffix cannot cost P/R); dropping it is logged as the diagnostic `asterisk_not_preserved`. Brand/organization *nodes* use the name without `*` (derived label; the published string stays on the show). |
| 2 | VOGUE WORLD: MILANO is kept but not assumed to be a fashion brand | `entry_kind = unclassified_entry` (all others `listed_show_entry`, i.e. "listed by CNMI as an F row"; being a fashion house/brand is **not** verified, and typing the organizer as `schema:Brand` is a documented assumption). `brand_raw = null`; RDF organizer is a `schema:Organization`, never `schema:Brand`; `brand` is excluded from scoring for this record (`_unscored`). |
| 3 | Missing venues stay null, with distinct statuses; placeholder coordinates are not locations | `venue_status`: `address` (street address published), `unpublished` (address cell empty), `invitation_only` ("Location in the invitation"), `digital` ("DIGITAL"). All non-`address` ⇒ `venue_address_raw = null`, no `schema:location` triple, status `incomplete`. Map coordinates present on invitation-only rows are placeholders: never stored, never used (`map_coordinates_placeholder_ignored`). A model predicting a venue for these rows is scored as an error (`hallucinated_value` / `placeholder_as_venue`). |
| 4 | Published local clock times are kept without inferring a timezone | `time` = clock time as published (`time_raw` keeps "live"); date from the day heading; RDF `xsd:dateTime` literal without offset; the word "live" is ignored and flagged (`live_flag_ignored`). |
| 5 | CNMI calendar is the primary source for the pilot | see above; `ambiguities` always contains `time_local_no_timezone_published`. |

## Field definitions
`name_raw` title as published · `brand_raw` derived name without trailing `*` (null for unclassified) · `date` ISO date from the day heading · `time`/`time_raw` · `venue_address_raw` street address only (no venue *name* is published) · `venue_status` · `entry_kind` · `status` (`confirmed` = name, date, time and street address all present; `confirmed_no_venue` = only the venue is null; `incomplete` = anything else missing) · `source_row_text` verbatim row · `ambiguities` codes · `human_verified` + `human_verified_by` + `basis` (owner sign-off).

## Change control
Any content change ⇒ new version + new SHA-256 in `data/gold/MANIFEST.json`; superseded versions stay in `data/gold/archive/` (v0.1.0 kept with its original checksum). v0.2.0 changed: `withheld`→`invitation_only`; added `entry_kind`, `source_row_text`, `ambiguities`, `annotation_policy`, `human_verified`; VOGUE brand null. v0.2.1 (owner approval): `human_verified=true`; `fashion_house_entry`→`listed_show_entry`; `incomplete`→`confirmed_no_venue` for the 4 venue-null records; no change to names, dates, times or venues. v0.2.2: wording-only correction of the provenance text; no scored, descriptive or status value changed. Selection rule unchanged.

## 3. Ontology
### Ontology design (M3) — `ontology/fashiongraph.ttl`, `rdf/shapes.ttl`
Principle: reuse schema.org and existing Wikidata items; add `ex:` terms only where reuse fails (docs/kg-feasibility.md: no edition/show modelling in Wikidata for any of 28 fashion weeks).

| Concept | Representation | Reuse / justification |
|---|---|---|
| Fashion week (series) | existing Wikidata item `wd:Q130829` (class `wd:Q253946`) | reused as-is (verified, query 01); RDF points to it via `schema:superEvent` |
| Specific edition | `ex:FashionWeekEdition` ⊑ `schema:Event`; `schema:startDate/endDate`, `schema:superEvent` → series | **custom class**: no edition items exist (queries 04, 09, 12) |
| Individual show | `ex:FashionShow` ⊑ `schema:Event`; `schema:superEvent` → edition; `schema:startDate` (xsd:dateTime, no timezone inferred) | **custom class**: no show items (queries 06, 13) |
| Fashion house / brand | `schema:Brand`, `schema:organizer` (show → brand; `schema:Organization` instead for the unclassified entry VOGUE WORLD: MILANO); `owl:sameAs wd:Q…` only when verified (currently only Prada Q193136) | reuse; Wikidata has brand items but 0/19 Milan houses have participation (query 08) |
| Collection | `ex:FashionCollection` ⊑ `schema:CreativeWork`; `ex:presentsCollection` | **custom, modelled but empty**: CNMI calendar rows do not name collections; no Prada collection items in Wikidata (query 14) |
| Venue | `schema:Place` with `schema:streetAddress`; `schema:location` | reuse. CNMI publishes street addresses only, no venue names; invitation-only / unpublished / digital venues yield **no** location triple (annotation-policy-v1) |
| Provenance | `prov:wasDerivedFrom`, `ex:evidenceQuote`, `ex:cnmiEventId`, `ex:calendarTypeCode` | `prov:` reused; `ex:` literals are custom bookkeeping |

Mapping to Wikidata properties for a future upload (not performed): superEvent ≈ P361/P179, startDate ≈ P580, location ≈ P276, organizer ≈ P664, participant ≈ P710 (property constraints to be checked before any claim). No Wikidata edits are made.
Validation: SHACL shapes enforce one edition per show, ≥1 brand, CNMI id, dateTime start, date-typed edition bounds, evidence quote.

## 4. SPARQL queries (all)
### 01_inspect_q130829.rq
```sparql
# Inspect starting point Q130829: label, description, instance of, all direct statements
SELECT DISTINCT ?label ?desc ?prop ?propLabel ?val ?valLabel WHERE {
  VALUES ?s { wd:Q130829 }
  OPTIONAL { ?s rdfs:label ?label FILTER(LANG(?label)="en") }
  OPTIONAL { ?s schema:description ?desc FILTER(LANG(?desc)="en") }
  OPTIONAL { ?s ?p ?val . ?prop wikibase:directClaim ?p .
    OPTIONAL { ?prop rdfs:label ?propLabel FILTER(LANG(?propLabel)="en") } }
  OPTIONAL { ?val rdfs:label ?valLabel FILTER(LANG(?valLabel)="en") }
}
ORDER BY ?propLabel
LIMIT 60
```

### 02_mfw_entities_regex.rq
```sparql
# Fashion-week entities: UNION of (a) instances of fashion week (Q253946) and (b) items linked to Q130829
# by part-of / instance-of / participant-in. REGEX keeps Milan-related labels only.
# (An unbounded label scan over all items timed out with HTTP 504, so the query is restricted by class/links.)
SELECT DISTINCT ?item ?label ?desc WHERE {
  { ?item wdt:P31 wd:Q253946 }
  UNION { ?item wdt:P361 wd:Q130829 }
  UNION { ?item wdt:P31 wd:Q130829 }
  UNION { ?item wdt:P1344 wd:Q130829 }
  ?item rdfs:label ?label . FILTER(LANG(?label)="en")
  FILTER(REGEX(?label, "Milan|Milano|Settimana", "i"))
  OPTIONAL { ?item schema:description ?desc FILTER(LANG(?desc)="en") }
}
ORDER BY ?label
LIMIT 50
```

### 03_inbound_links_q130829.rq
```sparql
# Which entities point TO Q130829 (any direct property)? Tests whether editions/brands/venues are linked.
SELECT DISTINCT ?s ?sLabel ?propLabel WHERE {
  ?s ?p wd:Q130829 . FILTER(?s != wd:Q130829)
  ?prop wikibase:directClaim ?p .
  OPTIONAL { ?s rdfs:label ?sLabel FILTER(LANG(?sLabel)="en") }
  OPTIONAL { ?prop rdfs:label ?propLabel FILTER(LANG(?propLabel)="en") }
}
ORDER BY ?propLabel ?sLabel
LIMIT 100
```

### 04_edition_search_mwapi.rq
```sparql
# Entity search via MediaWiki API service: any item whose label/alias matches "Milan Fashion Week" (editions, seasons).
SELECT DISTINCT ?item ?label ?desc WHERE {
  SERVICE wikibase:mwapi {
    bd:serviceParam wikibase:api "EntitySearch" ; wikibase:endpoint "www.wikidata.org" ;
      mwapi:search "Milan Fashion Week" ; mwapi:language "en" .
    ?item wikibase:apiOutputItem mwapi:item .
  }
  ?item rdfs:label ?label . FILTER(LANG(?label)="en")
  FILTER(REGEX(?label, "fashion week|moda", "i"))
  OPTIONAL { ?item schema:description ?desc FILTER(LANG(?desc)="en") }
}
ORDER BY ?label
LIMIT 30
```

### 05_milan_fashion_houses_gaps.rq
```sparql
# Brands found by name (UNION of label VALUES via REGEX) : classes, HQ, participant-in, venue-like links.
# Tests whether linked brand entities exist and carry event-related statements.
SELECT DISTINCT ?brand ?brandLabel ?classLabel ?hqLabel ?event ?eventLabel WHERE {
  SERVICE wikibase:mwapi {
    bd:serviceParam wikibase:api "EntitySearch" ; wikibase:endpoint "www.wikidata.org" ;
      mwapi:search "Prada" ; mwapi:language "en" .
    ?brand wikibase:apiOutputItem mwapi:item .
  }
  ?brand rdfs:label ?l . FILTER(REGEX(?l, "^(Prada|Fondazione Prada|Miu Miu)$", "i"))
  OPTIONAL { ?brand wdt:P31 ?class }
  OPTIONAL { ?brand wdt:P159 ?hq }
  OPTIONAL { ?brand wdt:P1344 ?event }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
ORDER BY ?brandLabel
LIMIT 50
```

### 06_fashion_show_events.rq
```sparql
# Look for Milan fashion-show style events (editions/shows) by label REGEX on items located in Milan or labelled with Milan.
SELECT DISTINCT ?item ?label ?desc ?start ?venue WHERE {
  SERVICE wikibase:mwapi {
    bd:serviceParam wikibase:api "EntitySearch" ; wikibase:endpoint "www.wikidata.org" ;
      mwapi:search "fashion show Milan" ; mwapi:language "en" .
    ?item wikibase:apiOutputItem mwapi:item .
  }
  ?item rdfs:label ?label .
  FILTER(LANG(?label)="en" && REGEX(?label, "fashion (show|week)|collection|Spring|Autumn|Fall|Winter|Summer", "i"))
  OPTIONAL { ?item schema:description ?desc FILTER(LANG(?desc)="en") }
  OPTIONAL { ?item wdt:P580 ?start }
  OPTIONAL { ?item wdt:P276 ?venue }
}
ORDER BY ?label
LIMIT 50
```

### 07_class_fashion_show.rq
```sparql
# Which Wikidata classes exist for fashion shows / weeks and how many instances (reuse check for modelling).
SELECT DISTINCT ?class ?classLabel (COUNT(?i) AS ?n) WHERE {
  VALUES ?class { wd:Q253946 wd:Q1171323 wd:Q1067375 }
  ?i wdt:P31 ?class .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
GROUP BY ?class ?classLabel
ORDER BY DESC(?n)
LIMIT 10
```

### 08_milan_houses_coverage.rq
```sparql
# Coverage of Milan-headquartered fashion houses (class resolved from Prada's own P31 labelled "fashion house").
# Counts houses overall, with a participant-in (P1344) statement, with website, with inception.
SELECT (COUNT(DISTINCT ?b) AS ?houses) (COUNT(DISTINCT ?bPart) AS ?withParticipantIn)
       (COUNT(DISTINCT ?bWeb) AS ?withWebsite) (COUNT(DISTINCT ?bInc) AS ?withInception) WHERE {
  wd:Q193136 wdt:P31 ?cls . ?cls rdfs:label "fashion house"@en .
  ?b wdt:P31 ?cls ; wdt:P159 wd:Q490 .
  OPTIONAL { ?b wdt:P1344 ?e . BIND(?b AS ?bPart) }
  OPTIONAL { ?b wdt:P856 ?w . BIND(?b AS ?bWeb) }
  OPTIONAL { ?b wdt:P571 ?i . BIND(?b AS ?bInc) }
}
LIMIT 1
```

### 09_fashion_weeks_structure.rq
```sparql
# All fashion-week items (n=28): which carry edition/series/start/location/part-of structure? Shows modelling in other cities.
SELECT DISTINCT ?fw ?fwLabel ?start ?loc ?locLabel ?edition ?editionLabel ?partOf ?partOfLabel WHERE {
  ?fw wdt:P31 wd:Q253946 .
  OPTIONAL { ?fw wdt:P580 ?start }
  OPTIONAL { ?fw wdt:P276 ?loc }
  OPTIONAL { ?edition wdt:P179 ?fw }
  OPTIONAL { ?fw wdt:P361 ?partOf }
  FILTER(!BOUND(?loc) || ?loc != wd:Q0)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
ORDER BY ?fwLabel
LIMIT 100
```

### 10_venues_linked.rq
```sparql
# Venues linked to MFW via P793 (inbound) or P7153 (outbound): class, coordinates, address presence.
SELECT DISTINCT ?v ?vLabel ?classLabel ?coord ?street ?link WHERE {
  { ?v wdt:P793 wd:Q130829 . BIND("P793 significant event (venue->MFW)" AS ?link) }
  UNION { wd:Q130829 wdt:P7153 ?v . BIND("P7153 significant place (MFW->venue)" AS ?link) }
  OPTIONAL { ?v wdt:P31 ?class }
  OPTIONAL { ?v wdt:P625 ?coord }
  OPTIONAL { ?v wdt:P6375 ?street }
  FILTER(!REGEX(STR(?v), "Q0$"))
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
ORDER BY ?link ?vLabel
LIMIT 60
```

### 11_girlsaward_editions.rq
```sparql
# Modelling precedent check: do GirlsAward editions exist as separate items with venue and date?
SELECT DISTINCT ?item ?itemLabel ?start ?venueLabel WHERE {
  SERVICE wikibase:mwapi {
    bd:serviceParam wikibase:api "EntitySearch" ; wikibase:endpoint "www.wikidata.org" ;
      mwapi:search "GirlsAward" ; mwapi:language "en" .
    ?item wikibase:apiOutputItem mwapi:item .
  }
  ?item rdfs:label ?l . FILTER(REGEX(?l, "GirlsAward", "i"))
  OPTIONAL { ?item wdt:P580 ?start }
  OPTIONAL { ?item wdt:P276 ?venue }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
ORDER BY ?itemLabel
LIMIT 15
```

### 12_italian_labels_editions.rq
```sparql
# Follow-up (Italian labels / alternative terminology): items named Milano Moda Donna / Settimana della moda di Milano / Milano Fashion Week.
SELECT DISTINCT ?item ?itemLabel ?itemDescription ?class ?classLabel WHERE {
  SERVICE wikibase:mwapi {
    bd:serviceParam wikibase:api "EntitySearch" ; wikibase:endpoint "www.wikidata.org" ;
      mwapi:search "Milano Moda Donna" ; mwapi:language "it" .
    ?item wikibase:apiOutputItem mwapi:item .
  }
  OPTIONAL { ?item wdt:P31 ?class }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "it,en". }
}
ORDER BY ?itemLabel
LIMIT 20
```

### 13_edition_and_collection_terms.rq
```sparql
# Follow-up: edition / season / collection terminology (Spring/Summer 2027, Primavera/Estate) near Milan fashion.
SELECT DISTINCT ?item ?itemLabel ?itemDescription WHERE {
  SERVICE wikibase:mwapi {
    bd:serviceParam wikibase:api "EntitySearch" ; wikibase:endpoint "www.wikidata.org" ;
      mwapi:search "Milano Fashion Week 2026" ; mwapi:language "it" .
    ?item wikibase:apiOutputItem mwapi:item .
  }
  ?item rdfs:label ?itemLabel . FILTER(LANG(?itemLabel) IN ("it","en") && REGEX(?itemLabel, "moda|fashion|collezione|sfilata|Spring|Primavera|2026|2027", "i"))
  OPTIONAL { ?item schema:description ?itemDescription FILTER(LANG(?itemDescription) IN ("it","en")) }
}
ORDER BY ?itemLabel
LIMIT 20
```

### 14_prada_collections_shows.rq
```sparql
# Follow-up: are there collection/show items for Prada (e.g. Prada Spring/Summer ...)? Label-bounded, English + Italian.
SELECT DISTINCT ?item ?itemLabel ?itemDescription ?class WHERE {
  SERVICE wikibase:mwapi {
    bd:serviceParam wikibase:api "EntitySearch" ; wikibase:endpoint "www.wikidata.org" ;
      mwapi:search "Prada collection" ; mwapi:language "en" .
    ?item wikibase:apiOutputItem mwapi:item .
  }
  OPTIONAL { ?item wdt:P31 ?class }
  ?item rdfs:label ?itemLabel . FILTER(LANG(?itemLabel) IN ("it","en") && REGEX(?itemLabel, "Prada.*(collection|fashion show|Spring|Autumn|Fall|Winter|Summer)|collezione", "i"))
  OPTIONAL { ?item schema:description ?itemDescription FILTER(LANG(?itemDescription) IN ("it","en")) }
}
ORDER BY ?itemLabel
LIMIT 20
```

### 15_control_it_search.rq
```sparql
# CONTROL: Italian entity search must find a known item (Milano), proving the it-language MWAPI path works (guards against false negatives in 12-14).
SELECT DISTINCT ?item ?itemLabel WHERE {
  SERVICE wikibase:mwapi {
    bd:serviceParam wikibase:api "EntitySearch" ; wikibase:endpoint "www.wikidata.org" ;
      mwapi:search "Settimana della moda di Milano" ; mwapi:language "it" .
    ?item wikibase:apiOutputItem mwapi:item .
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "it,en". }
}
LIMIT 10
```

### 16a_fashion_week_participant_organizer.rq
```sparql
# Bounded check A: P710/P664/P1344 statements on the fashion-week items (class Q253946), ids only.
SELECT DISTINCT ?subject ?p ?object WHERE {
  ?subject wdt:P31 wd:Q253946 .
  VALUES ?p { wdt:P710 wdt:P664 wdt:P1344 }
  ?subject ?p ?object .
}
ORDER BY ?subject
LIMIT 50
```

### 16b_inbound_participant_organizer.rq
```sparql
# Bounded check B: items pointing to Q130829 with P710/P664/P1344, ids only.
SELECT DISTINCT ?object ?p WHERE {
  VALUES ?p { wdt:P710 wdt:P664 wdt:P1344 }
  ?object ?p wd:Q130829 .
}
ORDER BY ?object
LIMIT 50
```

## 5. Models, cost and protocol
### Experiment protocol v0.1 (provisional) — 3 LLMs × 3 prompting strategies
Status: **executed on 2026-11-19 on the free-tier configuration (`models.free.json`); see the run log at the end.** The paid configuration (`models.json`, EUR 5 cap) was not used. Prerequisites that applied: owner approval and API keys, passing one-call smoke tests, a statement that no billing was attached, and acceptance that Gemini sampling cannot be pinned (temperature is deprecated for Gemini 3.x and is not sent). Techniques remain PROVISIONAL until confirmed against the course materials. Gold is owner-verified (v0.2.2). The design below is what ran.

## Design
| Item | Decision |
|---|---|
| Task | From one CNMI calendar row (plus day heading and edition line) extract show name, brand, event type, ISO date-time, venue, verbatim evidence quote. One event per row. |
| Inputs | `data/experiment/test_inputs.jsonl` (10 records = frozen gold v0.1.0, sha256 in `data/experiment/MANIFEST.json`). Byte-identical text for every model and technique. The ` \| ` cell separators and the header line are our formatting, not CNMI text. |
| Expected values | `expected.jsonl`, derived mechanically from the parsed source row + frozen gold `venue_status`; names kept exactly as published incl. unexplained `*` (policy 1; scoring normalises a trailing `*`, loss is logged as diagnostic `asterisk_not_preserved`); `venue = null` unless a street address is published (invitation-only / empty / DIGITAL → null, policy 3); for the one unclassified entry (VOGUE WORLD: MILANO) `brand` is `_unscored` (policy 2). |
| Models | GPT-5.4 mini (`gpt-5.4-mini-2026-03-17`), Gemini 3.5 Flash-Lite (`gemini-3.5-flash-lite`, owner-approved replacement for the deprecated 2.5 Flash; see docs/model-selection.md) and Mistral Small 4 (`mistral-small-2603`), pinned in `models.json` with official prices. The provider-reported model must equal the pinned one or the run aborts. Temperature 0 for OpenAI and Mistral; **not available for Gemini 3.5 Flash-Lite** (deprecated/ignored), so provider nondeterminism is possible for all models; each call is logged once, no cherry-picking. Rows record requested and served model. |
| Techniques (PROVISIONAL) | `zero_shot`, `few_shot`, `step_by_step` — names **not confirmed** by the course; do not count towards PDF p.4 rule 2 until confirmed. Rename/replace only by editing `experiments/prompts/*.txt` and bumping `prompt_version`. |
| Prompts | `experiments/prompts/{system,zero_shot,few_shot,step_by_step}.txt`, version `v0.2-provisional` (in every output row and the request hash). |
| Splits | **test** = 10 gold records (scored). **train** = 3 few-shot examples from other calendar rows (`fewshot_train.jsonl`, incl. one withheld-venue example teaching `null`). No dev split yet (n too small); prompts must be frozen **before** the first real run — no tuning on test results. |
| Leakage guard | `experiments/inputs.py` asserts train ids and normalised titles are disjoint from test; `tests/test_pipeline.py` re-checks and verifies the manifest checksums. |
| Output schema | `experiments/schema.py` (strict; fenced JSON tolerated, anything else is `invalid`). Invalid output is logged raw and scored as all-FN. |
| JSON → RDF | deterministic `rdf/convert.py` (no LLM). LLM-generated Turtle is out of scope (optional ablation, separately evaluated). |
| Execution | `python -m experiments.smoke --provider <p>` (one billed call each), then `python -m experiments.pipeline real --models models.json` (guarded) / `mock`; publish with `python -m evaluation.publish outputs/real/metrics.json` (gate: complete, current checksums, non-mock). Checkpointed JSONL, request-hash cache, bounded retries, `max_calls` and cost ceiling (needs per-model prices). 3×3×10 = 90 calls. |

## Scoring (implemented in `evaluation/score.py`)
Assertion = (record, field, normalised value) for 5 fields. TP exact normalised match; FP wrong value or value where expected null; FN missing/wrong expected value (invalid output ⇒ all expected FN). Correct abstention (null/null) is reported (`abstain_ok`), not in P/R. Micro P/R/F1 per (model, technique) cell. Also reported: invalid-output rate; unsupported-assertion rate (name/brand/venue not in the source text); RDF outcome per prediction (`conforms | shacl_fail | empty_graph | invalid_syntax | no_prediction`), reported **separately** from correctness. n = 10 per cell: **no confidence intervals or significance claims**; differences are descriptive.
Error taxonomy: `invalid_output, no_event, extra_event, missing_field, wrong_value, hallucinated_value, placeholder_as_venue, date_time_missing_time, evidence_not_verbatim, missing_evidence`.
Novel-triple counting is a separate, manual step (see docs/rdf-audit.md): a model triple is "novel" only if it is source-supported, passes SHACL and has no Wikidata counterpart.

## Known limitations (state them in the report)
- Task is easy (single structured row): ceiling effects likely; harder variants (multi-row day windows, prose descriptions of E rows, collections) need more gold.
- Gold is derived from the same page the models read; human adjudication pending.
- 10 records, one source, one edition; few-shot examples teach the same row format.
- Mock models ignore the technique, so the mock run says nothing about prompting effects and nothing about real LLMs. Mock outputs are tagged `is_mock`, written to `*_MOCK` files, refused by the publisher (`MockPublicationError`), and the site only reads `results/metrics.json`.

## Reproduce (mock)
`make all` → gold inputs, RDF, audit, mock pipeline, site, lint, tests. Raw HTML is git-ignored; re-download it from the CNMI calendar URL if absent.

## Prompt version history (disclosed changes)
- **v0.2-provisional (2026-11-19):** rule 8 added to the system prompt: for a calendar row the title names the show, so `show_name` is the title as written and never null. Reason: the first live smoke calls (3 calls, one per free-tier model, all on the first test record, zero-shot) showed that **all three models returned `show_name: null`** because rule 1 says "null when not stated" and the row has no separate show-name field, while the gold defines `show_name` as the title. This was a mismatch between prompt and gold definition, not a model difference; left unfixed it would have failed every model on that field for every record. Disclosure: one test record's output was seen before the change; the change is definitional (it states the gold's own rule), applies identically to all models and techniques, and no other field or rule changed. The few-shot examples already showed `show_name` = title. v0.1 is superseded; no full run was made with it.


## Run log: free-tier experiment (2026-11-19)
Configuration `models.free.json` (Gemini 3.5 Flash-Lite on the Google free tier; `openai/gpt-oss-120b` and `qwen/qwen3.8-27b` on the Groq free plan), prompt `v0.2-provisional`, inputs v0.1.1, gold v0.2.2, techniques PROVISIONAL. All 90 cells (3 models x 3 techniques x 10 records) have a final outcome; no billing was enabled (the owner confirmed both accounts are on free plans; every successful Groq response reported Free-plan header limits to the guard, and the 7 failed Qwen calls returned no such response; Gemini's billing state cannot be seen from code).
- **Requests made** (ledger, includes retries and failed attempts): gemini-3.5-flash-lite: 79, openai/gpt-oss-120b: 67, qwen/qwen3.8-27b: 30.
- **Interruptions, all resumed from the checkpoint without repeating any successful call:** (1) the run was paused once because the Gemini daily limit had been assumed (50/day) instead of read from the account; the owner then supplied the real AI Studio limits (15/min, 500/day, 250K tokens/min) and calls were paced at 9/min; (2) Gemini returned many HTTP 503 (overloaded) responses, retried with 10/20/40 s back-off; (3) the laptop slept and the network dropped for a period, producing connection errors that were retried on resume. Infrastructure errors that were later retried successfully: gemini-3.5-flash-lite: 8 logged attempts, openai/gpt-oss-120b: 8 logged attempts.
- **Provider-side generation failures, scored as invalid outputs and never retried:** 7 Qwen3.8-27B cells (few_shot, step_by_step, zero_shot) received HTTP 400 "Failed to generate JSON" from Groq's constrained decoding. The runner first labelled these as infrastructure errors; after seeing them they were reclassified as final outcomes (invalid output, all expected fields counted as missing), because the protocol scores a model that cannot produce valid output as invalid and a retry-until-success policy would be cherry-picking. The rule is general: it applies to every model, and schema-invalid outputs are likewise final on resume. Legacy rows are relabelled at load time; the raw log is unchanged.
- **Ceiling effect:** two models answered every cell correctly under every technique, so this single-row extraction task cannot separate them or show prompting effects for them; the only differences are in Qwen3.8-27B, mostly through generation failures. Scoring is case-insensitive, so a model that changes capitalisation (Qwen returned "JIL Sander *") is not penalised.
- **Conditions differ by necessity:** reasoning effort (Qwen none, gpt-oss low, Gemini minimal), no temperature control for Gemini, output caps (400 / 1,500 / 1,024 tokens). Results are comparable, not identical-condition.

### Cost estimate: 90 calls (3 models x 3 techniques x 10 records)

Generated by `python -m experiments.cost_estimate` from the real rendered prompts and `models.json` (prices from official pages, retrieved 2026-11-19; FX 1.0968 USD/EUR, ECB 2026-11-18). No call has been made.

| model | calls | input tok (expected / budgeted) | output tok (expected / capped) | expected | worst case |
|---|---|---|---|---|---|
| gpt-5.4-mini-2026-03-17 | 30 | 14687 / 25453 | 2184 / 12000 | $0.0208 (EUR 0.0190) | $0.0731 (EUR 0.0666) |
| gemini-3.5-flash-lite | 30 | 14687 / 25453 | 2184 / 30720 | $0.0099 (EUR 0.0090) | $0.0844 (EUR 0.0770) |
| mistral-small-2603 | 30 | 14687 / 25453 | 2184 / 12000 | $0.0035 (EUR 0.0032) | $0.0225 (EUR 0.0205) |

**Total expected:** $0.0342 (EUR 0.0312). **Total worst case:** $0.1800 (EUR 0.1641) against the enforced cap of EUR 5.0 (= $5.21 after a 5% FX safety margin).

Assumptions: expected tokens use chars/4 for input and chars/3.3 for output (not the providers' tokenisers, so +/-30%); worst case reserves chars/3 x 1.25 input plus the full per-call output cap, and charges Mistral at its higher listed rate for both directions (input/output order unverified). Gemini thinking tokens (level MINIMAL) are billed as output and are NOT in the expected figure, but the worst case already reserves the full per-call output cap (1024 tokens) for them. The budget is enforced per attempt (see `experiments/budget.py`), including retries.

## 6. Prompts (all)
### system
```
You extract fashion-show facts from the given source text. Output ONLY JSON of the form
{"events":[{"show_name":str|null,"brand":str|null,"event_type":str|null,"date_time":str|null,"venue":str|null,"evidence_quote":str|null}]}
Rules: (1) Use null when the text does not state a field; never guess. (2) evidence_quote must be copied verbatim from the text. (3) date_time is ISO 8601 local time, YYYY-MM-DDTHH:MM, built from the Day line and the row time (ignore the word "live"). (4) venue is a physical street address stated in the row; if the row says "Location In The Invitation", "DIGITAL" or has no address, venue is null. (5) Copy names exactly as written in the row, including any trailing "*" (its meaning is unknown; do not interpret or remove it). If the row is not clearly a fashion house/brand, still fill brand with the title as written. (6) event_type is "fashion show" for calendar type F. (7) One event per source row. (8) For a calendar row, the title names the show: show_name is that title exactly as written, never null (the row has no separate show-name field). Do not invent facts.
```

### zero_shot
```
Extract the fashion events from this text.

TEXT:
{text}
```

### few_shot
```
Extract the fashion events from this text. Worked examples (training split, disjoint from the evaluated records) follow.

{examples}

TEXT:
{text}
```

### step_by_step
```
Extract the fashion events from this text. Think step by step: (1) list candidate events, (2) for each, find the supporting sentence, (3) fill each field or null. Then output ONLY the final JSON (no reasoning text).

TEXT:
{text}
```

## 7. RDF enrichment and audit
### RDF audit — `rdf/out/gold_pilot.ttl` (153 triples; generated by `python -m rdf.audit` → `rdf/out/audit.json`)
Three questions are kept apart: **(1) is it valid RDF?** (2) **is it supported by the source?** (3) **is it new to the knowledge graph?** A triple can pass 1 and 2 and still not be novel knowledge.

## 1. Validity (syntax + SHACL)
Parses as Turtle; SHACL shapes (`rdf/shapes.ttl`) conform. This says nothing about truth or novelty; the shapes have negative tests.

## 2. What the 153 triples are
| kind | triples | meaning |
|---|---|---|
| structural | 49 | `rdf:type` (38; 11 of them use the custom classes `ex:FashionShow`/`ex:FashionWeekEdition`) and `schema:superEvent` (11: 10 show→edition, 1 edition→Q130829) |
| factual (source-checkable) | 61 | 27 labels, 11 start dates, 1 end date, 10 organizer, 6 location and 6 street-address triples (edition, 10 shows, brand and venue nodes) — **all 61 mechanically checked against the parsed CNMI row; 0 unsupported** |
| provenance/bookkeeping | 42 | `prov:wasDerivedFrom` (11), custom `ex:evidenceQuote` (11), `ex:cnmiEventId` (10), `ex:calendarTypeCode` (10) |
| link | 1 | `owl:sameAs` Prada → Wikidata Q193136 (the only verified brand link) |
Vocabulary: 111 triples use reused vocabularies (rdf/rdfs/owl/schema.org/prov); **42 involve custom `ex:` terms** (31 provenance + 11 class typings). Custom classes/properties are justified in docs/ontology.md.

## 3. Novelty versus Wikidata (bounded evidence only)
- **113 triples are about new local entities** (1 edition + 10 shows and their attributes, incl. provenance). Wikidata label/EntitySearch (EN+IT) found **no edition or show items** (queries 04, 06, 09, 12–15) and 0 of 19 Milan fashion houses carry participation (queries 08, 16a/16b). The **39 factual triples about these 11 events** (date/time, brand, address, label, edition bounds) are the *potentially novel knowledge*.
- **38 triples are about brand/venue nodes** minted locally and **not linked** to Wikidata (except Prada). Their novelty is **unknown**: the brands very likely have Wikidata items (e.g. Prada, Armani), so these triples are mostly entity descriptions, not new knowledge.
- **2 triples touch existing entities** (edition `superEvent` Q130829; Prada `sameAs` Q193136); neither is a new fact about the world.
- Provenance (42) and typing triples are bookkeeping/structure, not knowledge claims.
Caveats: absence is shown by bounded label/property searches, not proof; other KGs (e.g. Wikipedia infoboxes, DBpedia) were not checked; the gold set (v0.2.2: 6 `confirmed`, 4 `confirmed_no_venue`, all owner-verified, single source) leaves 4 shows without a location triple. **Do not report "153 novel triples"**; the defensible claim is: valid, source-supported candidate triples for 10 shows/1 edition that Wikidata (as searched) does not contain, pending manual review of any model-generated triples (the gold records themselves are owner-verified).

## 8. Results
| model | technique | P | R | F1 | invalid | unsupported | RDF conforms |
|---|---|---|---|---|---|---|---|
| gemini-3.5-flash-lite | few_shot | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 |
| gemini-3.5-flash-lite | step_by_step | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 |
| gemini-3.5-flash-lite | zero_shot | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 |
| openai/gpt-oss-120b | few_shot | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 |
| openai/gpt-oss-120b | step_by_step | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 |
| openai/gpt-oss-120b | zero_shot | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 |
| qwen/qwen3.8-27b | few_shot | 0.976 | 0.889 | 0.930 | 0.100 | 0.024 | 0.900 |
| qwen/qwen3.8-27b | step_by_step | 1.000 | 0.822 | 0.902 | 0.200 | 0.000 | 0.800 |
| qwen/qwen3.8-27b | zero_shot | 1.000 | 0.578 | 0.732 | 0.400 | 0.000 | 0.600 |

Techniques: PROVISIONAL (names unconfirmed against course materials). Prompt version v0.2-provisional. n = 10 per cell; descriptive only. Free-tier run: nothing was billed.

## 9. Differences between models and prompting effects
Descriptive means over cells; n is small, no significance claims. The interpretation is written by the team.

| model | mean F1 | mean P | mean R | invalid | most common errors |
|---|---|---|---|---|---|
| gemini-3.5-flash-lite | 1.000 | 1.000 | 1.000 | 0.000 | none |
| openai/gpt-oss-120b | 1.000 | 1.000 | 1.000 | 0.000 | none |
| qwen/qwen3.8-27b | 0.855 | 0.992 | 0.763 | 0.233 | invalid_output: 7, wrong_value: 1, asterisk_not_preserved: 1, evidence_not_verbatim: 1 |

| technique | mean F1 | mean P | mean R | invalid | most common errors |
|---|---|---|---|---|---|
| few_shot | 0.977 | 0.992 | 0.963 | 0.033 | invalid_output: 1, wrong_value: 1 |
| step_by_step | 0.967 | 1.000 | 0.941 | 0.067 | invalid_output: 2 |
| zero_shot | 0.911 | 1.000 | 0.859 | 0.133 | invalid_output: 4, asterisk_not_preserved: 1, evidence_not_verbatim: 1 |

Validated triples from exactly-correct, SHACL-valid predictions: 876.

- qwen/qwen3.8-27b | few_shot, `mfw-ss27-13659` brand: expected `ERMANNO SCERVINO`, got `ERMANNO SCERFINO` (wrong_value)
- qwen/qwen3.8-27b | few_shot, `mfw-ss27-13685` *: expected `None`, got `None` (invalid_output)
- qwen/qwen3.8-27b | step_by_step, `mfw-ss27-13639` *: expected `None`, got `None` (invalid_output)
- qwen/qwen3.8-27b | step_by_step, `mfw-ss27-13700` *: expected `None`, got `None` (invalid_output)
- qwen/qwen3.8-27b | zero_shot, `mfw-ss27-13645` evidence_quote: expected `verbatim quote`, got `F | 10:30 live | JIL Sander * | Location in the invitation` (evidence_not_verbatim)
- qwen/qwen3.8-27b | zero_shot, `mfw-ss27-13659` *: expected `None`, got `None` (invalid_output)
- qwen/qwen3.8-27b | zero_shot, `mfw-ss27-13669` *: expected `None`, got `None` (invalid_output)

## 10. Challenges and limitations
See the website Methodology page, section 'Challenges and how we addressed them' (generated from the same repository).
