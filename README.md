# FashionGraph

**Enriching Wikidata with Knowledge about Milan Fashion Week** — a comparative study of three language models for fashion-event knowledge-graph enrichment.
University of Bologna, *Knowledge Engineering and Computation for the Humanities* (course unit [529334](https://www.unibo.it/en/study/course-units-transferable-skills-moocs/course-unit-catalogue/course-unit/2025/529334)).

> **Status: experiment complete, deployment pending.** The Wikidata gap analysis, source dataset, ontology and RDF pipeline are done and tested, and the three-model comparison has run (90 answers on free tiers: Gemini 3.5 Flash-Lite, gpt-oss-120b, Qwen3.8-27B). Results are in `results/` and on the Results page. The prompting techniques are still provisional (names unconfirmed against the course), each cell has only ten records, and the written discussion, team members and live site URL are placeholders.

**Website:** https://vlads1902.github.io/fashiongraph/  
**Repository:** https://github.com/VladS1902/fashiongraph

## What is here
| Path | Content |
|---|---|
| `site/`, `reports/`, `slides/` | static site generator (`python site/build.py` → `site/dist`), project report, slide deck generator |
| `queries/`, `docs/kg-evidence/` | all 17 SPARQL queries and their recorded Wikidata responses |
| `data/` | source register, parsed CNMI calendar rows, gold pilot dataset (frozen, versioned, checksummed), annotation scripts |
| `ontology/`, `rdf/` | vocabulary, deterministic JSON→RDF conversion, SHACL shapes, validation and audit |
| `models.json`, `models.free.json` | paid (OpenAI, Gemini, Mistral, EUR 5 cap) and zero-cost (Gemini free tier, Groq free plan) model configurations |
| `experiments/`, `evaluation/` | prompts, provider adapters, quota guard and EUR budget, runner, scorer, error analysis, publish gate |
| `docs/` | gap memo, ontology, annotation guidelines, protocol, model selection, cost estimate, readiness report |
| `tests/` | 140 tests (`pytest`) |

## Reproduce
```bash
make setup      # Python 3.12 virtualenv with dependencies
make all        # inputs, RDF, audit, mock pipeline, report, site, slides, lint, tests
make serve      # preview the site at http://127.0.0.1:8765
```
`make data` needs the raw CNMI calendar HTML (not redistributed; re-download from the calendar URL listed in `data/source_register.jsonl`).

## Honesty rules
- No result is shown unless it comes from a validated, complete real run (`results/metrics.json`, produced only by `python -m evaluation.publish`, which refuses mock, incomplete or stale runs).
- API keys are read from environment variables only and are never stored. Real provider calls require `FASHIONGRAPH_APPROVED_SPEND=1` and an enforced budget.
- The mock pipeline's output is labelled MOCK and can never be published.

## Data and licensing notes
- Source facts (show names, times, addresses) come from the official [CNMI calendar](https://www.cameramoda.it/en/milano-moda-donna/calendar/); CNMI states no licence, so only factual fields are stored and the raw page is not included. Wikidata content is CC0.
- The lecturer's course guideline PDF is not redistributed in this repository.
- No code licence has been chosen yet.
