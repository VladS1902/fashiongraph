# Runbook: real three-model experiment

Everything below is implemented and tested against fakes and mocks only. **Nothing has run against a live API yet.**

## 0. Prerequisites (owner)
1. Create a git-ignored `.env` from `.env.example` with your three API keys. Keys are read from the environment only and never printed or logged.
2. Setting `FASHIONGRAPH_APPROVED_SPEND=1` in `.env` is your explicit spend approval. The EUR 5 cap in `models.json` is a safeguard, not a target; expected cost is about EUR 0.03.
3. Confirm the three course prompting techniques (names are provisional) and your group size. Results are labelled PROVISIONAL until then.

## 1. Check
`make readiness` should show only the gates you have not yet resolved.

## 2. Smoke tests (3 billed calls, one per provider)
`make smoke-all`. Each call uses the first test record under the enforced budget and writes `outputs/smoke/smoke_<provider>.json` (requested and served model, tokens, cost). A failure stops the sequence and explains why; nothing larger runs. Things only these calls can confirm: the exact `modelVersion` Gemini reports for `gemini-3.5-flash-lite`, the `responseJsonSchema` field, and Mistral's served-model string and `response_format`. If a provider rejects a request, the fix is an adapter change you approve, never a silent fallback to another model or setting.

## 3. Full run (90 calls)
`make run-real`. Every attempt first reserves its worst-case cost; the run halts safely when the cap would be exceeded, and a model-mismatch aborts immediately. It is resumable: rerun the same command to continue from the checkpoint (`outputs/real/raw_runs.jsonl`, ledger `outputs/real/ledger.jsonl`). Outputs: `metrics.json`, `report.md`, `analysis.json`, `analysis.md`, `rdf/*.ttl` (only exactly-correct, SHACL-valid predictions).

## 4. Publish the results
`make publish-results`. The gate refuses mock data, incomplete runs, stale dataset/gold/prompt versions and a missing analysis. On success `results/` is populated and the report, website Results page and slide results table rebuild from it.

## 5. Write the discussion (people, not code)
The site and report show tables, example errors and validated triples. The written discussion of differences between models and prompting strategies is deliberately not generated.

## Zero-cost alternative (models.free.json)
Gemini 3.5 Flash-Lite (free tier) + `openai/gpt-oss-120b` and `qwen/qwen3.8-27b` (Groq free plan). Read `docs/free-tier-investigation.md` first. In `.env` set `GEMINI_API_KEY`, `GROQ_API_KEY`, `FASHIONGRAPH_APPROVED_SPEND=1` (go-ahead for live calls) and `FASHIONGRAPH_FREE_TIER_CONFIRMED=1` (your statement that the Gemini key's project has no billing account and the Groq organisation is on the Free plan). Then `make readiness-free`, `make smoke-free`, `make run-free`, `make publish-results`. Nothing is billed; the paid path above stays available.
