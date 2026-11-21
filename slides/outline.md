# Slide outline (generated)

Budget: max 2 minutes per member (PDF p.17); group size 1, so 120 s in total. Slides are due 48 h before the exam; website link on the title slide.

## 1. FashionGraph (Vlad Sapytskii, ~10 s)
- Comparing three language models for fashion-event knowledge-graph enrichment
- Team: Vlad Sapytskii
- Website: https://vlads1902.github.io/fashiongraph/
_Notes: Website link must stay on this slide._

## 2. The gap and how we found it (Vlad Sapytskii, ~20 s)
- Wikidata has one item for Milan Fashion Week (Q130829); no editions or shows found
- 0 of 19 Milan fashion houses record taking part in any event
- 17 bounded SPARQL queries on Wikidata, with a control search against false negatives
_Notes: Gap shown with entity-level queries, not by missing properties on Q130829. All queries are on the website SPARQL page._

## 3. Source data and gold set (Vlad Sapytskii, ~15 s)
- Official CNMI calendar, Milano Moda Donna SS2027 (22-28 Sep 2026)
- 10 records, gold v0.2.2, owner-verified, checksummed
- Single source: no independent corroboration; missing venues stay null
_Notes: Annotation policy and review table are on the Data page._

## 4. Ontology and RDF (Vlad Sapytskii, ~15 s)
- Reuse Wikidata and schema.org; three small custom classes
- 153 candidate triples, valid and SHACL-conformant; only 39 potentially new
- Valid, source-supported and new are audited separately
_Notes: Do not say 153 novel triples._

## 5. Experiment and results (Vlad Sapytskii, ~40 s)
- 3 language models x 3 prompting strategies x 10 records, free tiers
- n = 10 per cell, descriptive only; techniques provisional
_Notes: gemini-3.5-flash-lite: F1 1.00 in every strategy; gpt-oss-120b: F1 1.00 in every strategy; qwen3.8-27b: F1 0.73 to 0.93. Two models are at the ceiling on this easy single-row task; Qwen differences come mostly from provider-side generation failures. Conditions differ by necessity (reasoning level, no Gemini temperature)._

## 6. Challenges, limits and next steps (Vlad Sapytskii, ~20 s)
- Provider outages, generation failures, interrupted runs: all logged and handled
- Ten records, one source; two models at the ceiling
- Next: written discussion and confirmed technique names; publish after approval
_Notes: Full list on the website Methodology page, section Challenges and how we addressed them._
