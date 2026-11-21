# Ontology design (M3) — `ontology/fashiongraph.ttl`, `rdf/shapes.ttl`
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
