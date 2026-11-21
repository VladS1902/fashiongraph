# Requirements traceability (M0) — source: references/ProjectGuidelinesKE4H.pdf (28 pp.; text in references/ProjectGuidelinesKE4H.txt)
Status legend: OPEN = not yet satisfied. UNKNOWN = needs external confirmation.

| ID | Requirement (PDF page) | Evidence needed | Status |
|----|------------------------|-----------------|--------|
| R1 | Combine KGs + LLMs; website with team, methodology, results (p.2) | site + report | OPEN |
| R2 | Individual assessment; each member knows all aspects + one SPARQL/LLM/HTML task in detail (p.2) | contribution statements | OPEN |
| R3 | Query KG; explore vocabulary; design triples via CONSTRUCT or LLM; prompt LLMs; verify outputs; engineer prompts (p.3) | queries/, prompts, eval | OPEN |
| R4 | MANDATORY: SPARQL OPTIONAL, DISTINCT, UNION, FILTER, REGEX, LIMIT, ORDER BY (p.4 #1) | queries/ with executed results; automated keyword check test | OPEN |
| R5 | MANDATORY: all 3 prompting techniques (p.4 #2). **Names NOT in PDF** | lecturer/lecture-note confirmation | UNKNOWN (provisional: zero-shot, few-shot, step-by-step) |
| R6 | MANDATORY: compare ≥2 LLMs (group of 4), ≥3 (group >4) (p.4 #3). Group size 1 (team.json): at least 2 required, 3 compared | 3 models run | OPEN / group size UNKNOWN |
| R7 | MANDATORY: website published on GitHub (p.4 #4, p.16) | public repo + Pages URL (needs owner approval) | OPEN |
| R8 | Report content: topic, how gap identified, methodology, tools, all steps, ALL SPARQL + ALL prompts with results, challenges (a section of the Methodology page, required by PDF p.4 #5 and p.16), LLM behaviour differences (p.4 #5, p.16) | site pages | OPEN |
| R9 | Website sections + menu (p.4 #6); menu identical, same position on every page (p.16) | site build test | OPEN |
| R10 | Enrich KG: identify entities/descriptions to enrich; produce new RDF triples; optional RDFS vocab extension (p.5) | gap matrix + validated Turtle | OPEN |
| R11 | Homepage index.html with title, abstract, team; links for browsable topics (p.16) | site test | OPEN |
| R12 | All code and material public on GitHub (p.16) | repo | OPEN |
| R13 | Oral: slides, max 2 min/member, slides uploaded 48h before exam, website link on title slide (p.17) | slides | OPEN |

## Observations / discrepancies
- PDF p.16 mentions "stories" and "Melody" — template residue from another project; not applicable to FashionGraph, noted only.
- PDF examples use ArCo; any KG allowed (p.7) → Wikidata is permitted.
- PDF p.12–15 show LLM-as-QA + NL→RDF pipelines (Q&A, extraction, RDF generation with a given ontology): hints at what the "techniques" might be; unconfirmed.
- Spec §7 "triple-level evaluation" etc. is project-added rigor, not PDF-mandated.

## Status (updated 2026-11-19, after internal review 1)
| ID | Status | Evidence |
|----|--------|----------|
| R1, R3, R10 | PARTIAL | gap memo docs/kg-feasibility.md; gold v0.2.2 (owner-verified, single source); candidate triples rdf/out/gold_pilot.ttl (153, SHACL conforms; docs/rdf-audit.md); ontology docs/ontology.md; no LLM run yet |
| R4 | MET | 17 executed queries (docs/kg-evidence); tests/test_sparql_keywords.py; review 1 PASS |
| R5 | OPEN (human) | technique names unconfirmed; prompts provisional |
| R6 | MET | 3 models compared (90 answers, free tiers); group size 1 needs at least 2 (PDF p.4 #3) |
| R2 | OPEN | contribution statements need team input |
| R7, R12 | OPEN (human) | local git repo only; CI workflow prepared (.github/workflows/ci.yml); no remote/Pages without owner approval |
| R8, R9, R11 | PARTIAL | 13-page site generated from artefacts (same menu, homepage with title/abstract, all queries + prompts); results/team placeholders; not visually checked |
| R13 | PARTIAL | draft deck slides/FashionGraph_slides.pptx (10 slides, website-link placeholder on title slide); team/results placeholders |
Review 1 (read-only checks of the traceability matrix): no code/data defects; blockers are the human gates above; minors fixed. A second review is required after real run, team info, publication and final slides.
