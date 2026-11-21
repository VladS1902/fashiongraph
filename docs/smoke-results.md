# Live smoke test results, free-tier configuration (2026-11-19)
Three single calls, one per model, zero-shot prompt v0.1, first test record (`mfw-ss27-13639`, PRADA). Free tier only; nothing was billed. Raw files: `outputs/smoke/` (git-ignored).

| model | result | served model | tokens in / out | notes |
|---|---|---|---|---|
| `gemini-3.5-flash-lite` | pass on the 2nd attempt | `gemini-3.5-flash-lite` (exact match) | 351 / 115 | The 1st attempt returned HTTP 503 (service unavailable, transient); one retry after 20 s succeeded. Counted as 2 requests in the quota ledger. `responseJsonSchema`, `thinkingLevel MINIMAL`, `generateContent` all accepted. |
| `openai/gpt-oss-120b` (Groq) | pass | `openai/gpt-oss-120b` (exact match) | 526 / 188 | Strict `json_schema`, `reasoning_effort low`, `include_reasoning false`, `temperature 0` accepted. Free-plan header guard passed (headers reported the Free-plan maxima or lower). |
| `qwen/qwen3.8-27b` (Groq) | pass | `qwen/qwen3.8-27b` (exact match) | 353 / 91 | Strict `json_schema`, `reasoning_effort none`, `temperature 0` accepted. Free-plan header guard passed. |

## What the calls settled
- Request formats, served-model strings and usage fields for all three providers are now confirmed live (previously documentation-only). The Groq free-plan guard accepted both models, so the Groq organisation reports a Free plan.
- The assumption that Gemini returns `modelVersion` equal to the pinned ID holds.

## What they did not settle
- Gemini's real free limits (still the low assumptions in `models.free.json`), whether Groq counts the output cap against tokens/min, and how Gemini's 503s behave under the full 30-call load. The runner retries transient errors with bounded back-off; a persistent outage would halt and resume rather than substitute.

## A finding that changed the protocol
All three models returned `show_name: null` for this record (every other scored field matched the gold). The prompt said "null when not stated" while the gold defines `show_name` as the row's title. Prompt v0.2 (rule 8) states the gold's rule; see `docs/experiment-protocol.md` for the disclosure. The smoke calls were made with v0.1; no full run has been made with either version.
