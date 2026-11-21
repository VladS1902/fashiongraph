# Model selection and configuration (official-documentation evidence, retrieved 2026-11-19)
Identifiers are pinned in `models.json` and **never substituted silently**: each adapter compares the provider's reported model with the pinned value and the runner aborts on mismatch (`ModelMismatch`). Each result row records `requested_model` and `served_model` (as exposed by the provider).

**Owner decision 2026-11-19:** the deprecated `gemini-2.5-flash` was replaced by `gemini-3.5-flash-lite`; GPT-5.4 mini and Mistral Small 4 unchanged.

| | GPT-5.4 mini | Gemini 3.5 Flash-Lite | Mistral Small 4 |
|---|---|---|---|
| Pinned ID | `gpt-5.4-mini-2026-03-17` (alias `gpt-5.4-mini`) | `gemini-3.5-flash-lite` (stable; no dated variants listed) | `mistral-small-2603` (v26.03) |
| Official pages | [model](https://developers.openai.com/api/docs/models/gpt-5.4-mini), [pricing](https://developers.openai.com/api/docs/pricing) | [model](https://aistudio.google.com/docs/models/gemini-3.5-flash-lite), [pricing](https://aistudio.google.com/docs/pricing), [generateContent reference](https://aistudio.google.com/api-reference/generate-content) | [model](https://docs.mistral.ai/models/mistral-small-4-0-26-03) |
| Price per 1M tokens (USD) | in 0.75, out 4.50 | in 0.30, out 2.50 (thinking tokens included in output); no context tiers listed | 0.15 and 0.60, **input/output order not labelled** |
| Structured output | Structured Outputs supported (strict `json_schema`) | supported (model page); `responseMimeType application/json` + `responseJsonSchema` | Structured Outputs listed; `json_schema` response_format |
| Sampling / thinking | `temperature 0` valid only with `reasoning_effort none` (both sent) | **`temperature` not sent** (deprecated/ignored on Gemini 3.x, HTTP 400 planned); `thinkingConfig.thinkingLevel MINIMAL` (Gemini 3+ only; 2.x used `thinkingBudget`; thinking cannot be fully disabled) | `temperature 0` |
| Served-model field | `model` | `modelVersion` (documented) | `model` |
| Limits | 400k context | 1,048,576 input / 65,536 output tokens | 256k context |

## Decisions and caveats
1. **Gemini determinism:** with `temperature` unavailable, Gemini sampling cannot be pinned; each cell is run once and logged, and the protocol states this limitation. Thinking tokens (minimal) are billed as output and bounded by `maxOutputTokens` 1024.
2. **Gemini endpoint:** the adapter uses `generateContent`, which Google calls legacy but "fully supported"; the Interactions API is recommended for new projects. If the smoke test shows `generateContent` rejects this model or the JSON-schema field, the fix is an owner-approved adapter change, not a silent fallback.
3. **Not stated in the pages read** (verified only by the smoke tests): the exact `modelVersion` string returned for `gemini-3.5-flash-lite`, behaviour of `responseJsonSchema`, Mistral's served-model string and `response_format` behaviour, and any deprecation date for Gemini 3.5 Flash-Lite (the page does not mention one).
4. **Mistral price order is unverified:** budgeting charges both input and output at $0.60 per 1M until confirmed.
5. Reasoning/thinking tokens count as output for cost; per-call output caps (400 / 1024 / 400 tokens) are the worst case used by the budget.

## Budget (enforced, EUR 5; an engineering safeguard, not permission to spend)
`experiments/budget.py`: every provider attempt first reserves a worst-case estimate (chars/3 x 1.25 input + full output cap) and is refused if the persistent ledger plus the estimate would exceed the cap; actual cost is settled from provider usage (missing usage or failed attempt = worst case); an unsettled reservation after a crash counts as spent; USD cap = EUR 5 x 1.0968 (ECB, 2026-11-18) x 0.95 = $5.21; real adapters are refused by the runner without a budget. Estimated cost: `docs/cost-estimate.md`.
