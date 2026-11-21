# Decisions

| Date | Decision | Reason | Evidence |
|---|---|---|---|
| 2026-11-19 | GO, narrowed to edition→show→(brand, date/time, venue) | No edition/show items or participant statements found for MFW; gap shown by entity-level queries, not by missing properties on Q130829 | docs/kg-feasibility.md, queries 01–16b |
| 2026-11-19 | Reuse schema.org + existing Wikidata items; custom `ex:` only for edition, show, collection and bookkeeping | Wikidata models no fashion-week editions (0/28) | docs/ontology.md |
| 2026-11-19 | CNMI calendar as sole primary source for the pilot; annotation-policy-v1 | Owner decision; no independent corroboration available (2nd CNMI domain 503) | docs/annotation-guidelines.md |
| 2026-11-19 | Gold v0.2.1 owner-verified 10/10; renames listed_show_entry, confirmed_no_venue | Owner approval; v0.1.0/v0.2.0 archived | data/gold/MANIFEST.json |
| 2026-11-21 | Gold v0.2.2: wording-only correction of the provenance text; v0.2.1 archived with the same correction and a new checksum | Owner decision; no scored, descriptive or status value changed | data/gold/MANIFEST.json |
| 2026-11-19 | JSON→RDF is deterministic code; LLM-written RDF only as a separate ablation | Reproducibility, spec §7 | rdf/convert.py |
| 2026-11-19 | Mock outputs never published; site reads only results/metrics.json | Prevent mock numbers appearing as research results | evaluation/report.py, tests/test_pipeline.py |
| 2026-11-19 | Site pages generated from docs/queries/prompts/artefacts (markdown lib), no hardcoded results | Spec §6 contract | site/build.py |
| 2026-11-19 | Site redesign: pattern-drafting visual language (solid = present/verified, dashed = missing/pending), original SVG visuals generated from artefacts, one staged hero animation, no external fonts/scripts/images | The site looked generic; visuals must be honest, offline-safe and copyright-free | site/viz.py, site/assets/ |
| 2026-11-19 | Zero-cost configuration added (Gemini free tier + Groq free plan: gpt-oss-120b, qwen3.8-27b), paid configuration kept | Owner request to avoid spend; free access verified in official docs; free-quota guard + Groq paid-plan header guard replace the money cap | docs/free-tier-investigation.md, models.free.json |
| 2026-11-19 | Site now reflects the real comparison: conditional status text everywhere, F1 chart, per-answer outcome strips, conditions, compute, run record, model triples, downloads; slides and README updated | Site still said no experiment had been run after results existed | site/build.py, site/viz.py |
| 2026-11-20 | Reviewer feedback (Vlad): footer text, Cost estimate section and course-unit reference removed; Challenges menu item removed but its content kept as a Methodology section (PDF p.4 #5 and p.16 make it mandatory); Vlad Sapytskii added to Team | External review of the draft site | site/build.py |
| 2026-11-21 | Owner confirmed: Challenges stays a section of the Methodology page (no separate menu page) | PDF p.4 #5 / p.16 require the content; menu item removed per reviewer | site/build.py |
| 2026-11-21 | Team is Vlad Sapytskii only (group size 1): team.json is the single source for the Team page, slides and readiness; deck cut to 6 slides / 120 s; LLM rule (>=2) met with 3 | Owner statement; PDF p.4 #3 and p.17 | team.json |
| 2026-11-21 | Published: https://vlads1902.github.io/fashiongraph/ (repo VladS1902/fashiongraph, public, Pages via GitHub Actions). First CI run failed on plain pytest (missing pythonpath); fixed and verified on a fresh clone before the second run | Deployment | .github/workflows/ci.yml, pytest.ini |
