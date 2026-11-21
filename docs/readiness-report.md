# Final readiness report (2026-11-19) — real three-model run

**Status: engineering ready; blocked only on human decisions and credentials. No paid call has been made.**
Verified by `make readiness`, 101 passing tests, ruff clean (see docs/model-selection.md, docs/cost-estimate.md).

## Ready (verified)
- Gold v0.2.2 owner-verified, checksummed; inputs match gold; no few-shot leakage; prompts versioned and checksummed.
- Pinned models in `models.json` with official prices and sources: `gpt-5.4-mini-2026-03-17`, `gemini-3.5-flash-lite`, `mistral-small-2603`. Provider-reported model must equal the pinned one, otherwise the run aborts.
- **EUR 5 budget enforced** per attempt (reserve worst case before the call, settle from provider usage, persistent ledger, safe halt, real adapters refused without a budget); tested with mid-run exhaustion, restart, failed attempts and missing usage.
- Estimated cost for 90 calls: about EUR 0.03 expected, EUR 0.16 worst case.
- One-call smoke tests prepared (`python -m experiments.smoke --provider <openai|gemini|mistral>`), tested against faked providers only.
- Genuine outputs flow automatically: `python -m evaluation.publish outputs/real/metrics.json` (refuses mock, incomplete, stale-checksum runs) then `make all` rebuilds the report (`reports/report.md`), the site Results page and the slide results table; tested with a synthetic non-mock fixture that is removed afterwards.

## Run sequence (docs/runbook.md)
`make readiness` -> `make smoke-all` (3 billed calls) -> `make run-real` (90 calls, resumable) -> `make publish-results` (gate, then report, site, slides). Error analysis and validated-triple export are produced automatically; the written discussion is not.

## Unresolved human decisions and credentials
1. **API keys**: `OPENAI_API_KEY`, `GEMINI_API_KEY`, `MISTRAL_API_KEY` in the environment.
2. **Spend approval**: `FASHIONGRAPH_APPROVED_SPEND=1` for the 3 smoke calls (about EUR 0.01) and then the 90-call run.
3. **Gemini sampling**: `temperature` is deprecated for Gemini 3.x and not sent, so Gemini output cannot be pinned to deterministic sampling (accepted as a documented limitation unless you object).
4. **Course prompting techniques**: names unconfirmed; results stay labelled PROVISIONAL until the owner confirms them against the teaching materials.
5. **Group size** (2 vs 3 LLMs required) and team names/contributions.
6. **Publication**: GitHub repository and Pages deployment approval.

## Open technical risks (resolved only by the smoke tests)
Adapters have never run against live APIs; Gemini `thinkingLevel MINIMAL`, `responseJsonSchema` and the exact `modelVersion` string for `gemini-3.5-flash-lite`, and the Mistral `response_format` and served-model string, are taken from documentation that did not fully state them; Gemini uses the legacy `generateContent` endpoint. Mistral input/output price order is unlabelled (budgeted conservatively).
