"""Provider adapters. Keys come from env only. Real providers need FASHIONGRAPH_APPROVED_SPEND=1.

UNTESTED against live APIs (no keys/approval); request/response shapes follow public docs
and must be verified in an owner-approved pilot.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import requests

APPROVAL_ENV = "FASHIONGRAPH_APPROVED_SPEND"
KEY_ENVS = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "groq": "GROQ_API_KEY",
}


class SpendNotApproved(RuntimeError):
    pass


class ModelMismatch(RuntimeError):
    """Provider served a different model than pinned (e.g. silent routing). Never retried, never accepted."""


class GenerationFailed(RuntimeError):
    """The provider's constrained decoding could not produce schema-valid JSON (e.g. Groq HTTP 400 'Failed to generate JSON').
    A final model outcome (scored as an invalid output), never retried: retrying until success would be cherry-picking."""


class PaidTierDetected(RuntimeError):
    """Free-tier-only run, but the provider's rate-limit headers show a paid plan (or cannot confirm the free plan). Fatal."""


class TransientError(RuntimeError):
    """Retryable (429/5xx/network). `retry_after` (seconds) is honoured when the provider sends it."""

    def __init__(self, msg: str = "", retry_after: float | None = None):
        super().__init__(msg)
        self.retry_after = retry_after


@dataclass
class Completion:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw: object = None
    served_model: str | None = (
        None  # model identifier reported by the provider (audit trail)
    )
    meta: dict | None = None  # e.g. rate-limit headers seen with this response


def require_approval(env=None):
    env = os.environ if env is None else env
    if env.get(APPROVAL_ENV) != "1":
        raise SpendNotApproved(
            f"real provider calls refused: set {APPROVAL_ENV}=1 after owner approval"
        )


def _retry_hint(r) -> float | None:
    """Seconds the provider asks us to wait: `Retry-After` header, else Google's RetryInfo `retryDelay` ("17s") in the JSON body."""
    ra = r.headers.get("retry-after")
    if ra and ra.replace(".", "", 1).isdigit():
        return float(ra)
    try:
        for det in r.json().get("error", {}).get("details", []):
            delay = det.get("retryDelay")
            if delay and str(delay).rstrip("s").replace(".", "", 1).isdigit():
                return float(str(delay).rstrip("s"))
    except (ValueError, AttributeError):
        pass
    return None


class Adapter:
    provider = "base"
    is_mock = False

    def __init__(
        self,
        model_id: str,
        timeout_s: float = 60.0,
        env=None,
        served_model: str | None = None,
        max_output_tokens: int = 512,
        params: dict | None = None,
        plan_guard: tuple | None = None,
    ):
        self.model_id, self.timeout_s = model_id, timeout_s
        self.served_model, self.max_output_tokens = served_model, max_output_tokens
        self.params = dict(
            params or {}
        )  # extra request parameters (e.g. reasoning effort), from models file
        self.plan_guard = plan_guard  # (max tokens-per-minute header, max requests-per-day header) for a FREE plan
        self.last_headers: dict = {}
        self._env = os.environ if env is None else env

    def complete(self, system: str, user: str) -> Completion:
        raise NotImplementedError

    def _check_served(self, reported) -> None:
        if self.served_model is not None and reported != self.served_model:
            raise ModelMismatch(
                f"pinned {self.served_model!r} but provider reported {reported!r}"
            )

    def _key(self) -> str:
        require_approval(self._env)
        key = self._env.get(KEY_ENVS[self.provider])
        if not key:
            raise RuntimeError(f"missing env {KEY_ENVS[self.provider]}")
        return key

    def _post(self, url, headers, payload):
        try:
            r = requests.post(
                url, headers=headers, json=payload, timeout=self.timeout_s
            )
        except requests.RequestException as e:
            raise TransientError(str(e)) from e
        self.last_headers = {k.lower(): v for k, v in r.headers.items()}
        if r.status_code == 429 or r.status_code >= 500:
            raise TransientError(f"HTTP {r.status_code}", _retry_hint(r))
        if r.status_code >= 400:
            if r.status_code == 400 and (
                "Failed to generate JSON" in r.text or "failed_generation" in r.text
            ):
                raise GenerationFailed(
                    f"HTTP 400: {r.text[:2000]}"
                )  # the model could not produce schema-valid output: an outcome, not an outage
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        return r.json()


def _schema() -> dict:
    from .schema import RESPONSE_SCHEMA

    return RESPONSE_SCHEMA


class OpenAIAdapter(Adapter):
    """gpt-5.4-mini: Chat Completions, Structured Outputs (strict json_schema), reasoning_effort none so that
    temperature 0 is accepted (per OpenAI docs, temperature is only supported with effort none). max_completion_tokens
    bounds visible + reasoning tokens."""

    provider = "openai"

    def build_payload(self, system, user):
        return {
            "model": self.model_id,
            "temperature": 0,
            "reasoning_effort": "none",
            "max_completion_tokens": self.max_output_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "fashion_events",
                    "strict": True,
                    "schema": _schema(),
                },
            },
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }

    def complete(self, system, user):
        key = self._key()
        d = self._post(
            "https://api.openai.com/v1/chat/completions",
            {"Authorization": f"Bearer {key}"},
            self.build_payload(system, user),
        )
        self._check_served(d.get("model"))
        u = d.get("usage", {})
        return Completion(
            d["choices"][0]["message"]["content"],
            u.get("prompt_tokens"),
            u.get("completion_tokens"),
            d,
            d.get("model"),
        )


class MistralAdapter(Adapter):
    provider = "mistral"

    def build_payload(self, system, user):
        return {
            "model": self.model_id,
            "temperature": 0,
            "max_tokens": self.max_output_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "fashion_events",
                    "strict": True,
                    "schema": _schema(),
                },
            },
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }

    def complete(self, system, user):
        key = self._key()
        d = self._post(
            "https://api.mistral.ai/v1/chat/completions",
            {"Authorization": f"Bearer {key}"},
            self.build_payload(system, user),
        )
        self._check_served(d.get("model"))
        u = d.get("usage", {})
        return Completion(
            d["choices"][0]["message"]["content"],
            u.get("prompt_tokens"),
            u.get("completion_tokens"),
            d,
            d.get("model"),
        )


class GeminiAdapter(Adapter):
    """gemini-3.5-flash-lite via the (legacy but fully supported) generateContent endpoint, per Google docs retrieved 2026-11-19:
    - `temperature` is deprecated/ignored for Gemini 3.x (HTTP 400 planned) => NOT sent; determinism cannot be requested;
    - thinking is set with thinkingConfig.thinkingLevel (thinkingBudget is for 2.x; 'MINIMAL' is the near-off default for Flash-Lite;
      thinking cannot be fully disabled and its tokens are billed as output, so they are bounded by maxOutputTokens);
    - structured output: responseMimeType application/json + responseJsonSchema (JSON Schema with type arrays; field listed in the
      reference, request behaviour unverified until the smoke test);
    - the response's modelVersion MUST equal the pinned model (strict mismatch guard)."""

    provider = "gemini"

    def build_payload(self, system, user):
        return {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "maxOutputTokens": self.max_output_tokens,
                "responseMimeType": "application/json",
                "responseJsonSchema": _schema(),
                "thinkingConfig": {"thinkingLevel": "MINIMAL"},
            },
        }

    def complete(self, system, user):
        key = self._key()
        d = self._post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_id}:generateContent",
            {"x-goog-api-key": key},
            self.build_payload(system, user),
        )
        self._check_served(d.get("modelVersion"))
        u = d.get("usageMetadata", {})
        text = "".join(
            p.get("text", "")
            for p in d["candidates"][0]["content"]["parts"]
            if not p.get("thought")
        )
        out = (
            None
            if u.get("candidatesTokenCount") is None
            else u["candidatesTokenCount"] + u.get("thoughtsTokenCount", 0)
        )
        return Completion(
            text, u.get("promptTokenCount"), out, d, d.get("modelVersion")
        )


class GroqAdapter(Adapter):
    """GroqCloud (OpenAI-compatible Chat Completions) on the FREE plan: strict json_schema structured output (supported by
    openai/gpt-oss-120b and qwen/qwen3.8-27b), temperature 0, max_completion_tokens cap, plus per-model parameters from the
    models file (gpt-oss: reasoning_effort low, include_reasoning false; qwen3.8: reasoning_effort none).
    Free-plan guard: Groq reports the plan's limits in headers (x-ratelimit-limit-tokens = TPM, -requests = RPD). If they exceed the
    configured FREE values, or are missing, the run aborts (PaidTierDetected) so nothing is silently billed."""

    provider = "groq"

    def build_payload(self, system, user):
        payload = {
            "model": self.model_id,
            "temperature": 0,
            "max_completion_tokens": self.max_output_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "fashion_events",
                    "strict": True,
                    "schema": _schema(),
                },
            },
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        payload.update(self.params)
        return payload

    def _check_plan(self) -> dict:
        h = self.last_headers
        tok, req = (
            h.get("x-ratelimit-limit-tokens"),
            h.get("x-ratelimit-limit-requests"),
        )
        meta = {k: v for k, v in h.items() if k.startswith("x-ratelimit")}
        if self.plan_guard is None:
            return meta
        max_tpm, max_rpd = self.plan_guard
        try:
            over = int(tok) > max_tpm or int(req) > max_rpd
        except (TypeError, ValueError) as e:
            raise PaidTierDetected(
                "rate-limit headers missing or unreadable: cannot confirm the Free plan; stopping"
            ) from e
        if over:
            raise PaidTierDetected(
                f"headers show tokens/min {tok} and requests/day {req}, above the Free plan ({max_tpm}/{max_rpd}): paid plan suspected; stopping"
            )
        return meta

    def complete(self, system, user):
        key = self._key()
        d = self._post(
            "https://api.groq.com/openai/v1/chat/completions",
            {"Authorization": f"Bearer {key}"},
            self.build_payload(system, user),
        )
        meta = self._check_plan()
        self._check_served(d.get("model"))
        u = d.get("usage", {})
        return Completion(
            d["choices"][0]["message"]["content"],
            u.get("prompt_tokens"),
            u.get("completion_tokens"),
            d,
            d.get("model"),
            meta,
        )


class MockAdapter(Adapter):
    """DETERMINISTIC MOCK for plumbing tests. Output is NOT research data."""

    provider = "mock"
    is_mock = True

    def complete(self, system, user):
        body = {
            "events": [
                {
                    "show_name": None,
                    "brand": None,
                    "event_type": None,
                    "date_time": None,
                    "venue": None,
                    "evidence_quote": None,
                }
            ]
        }
        return Completion(json.dumps(body), len(user) // 4, 10, {"MOCK": True})


def make_adapter(
    provider: str,
    model_id: str,
    timeout_s: float = 60.0,
    env=None,
    served_model: str | None = None,
    max_output_tokens: int = 512,
    params: dict | None = None,
    plan_guard: tuple | None = None,
) -> Adapter:
    if provider == "mock":
        return MockAdapter(
            model_id,
            timeout_s,
            env,
            served_model,
            max_output_tokens,
            params,
            plan_guard,
        )
    classes = {
        "openai": OpenAIAdapter,
        "gemini": GeminiAdapter,
        "mistral": MistralAdapter,
        "groq": GroqAdapter,
    }
    if provider not in classes:
        raise ValueError(f"unknown provider {provider}")
    require_approval(env)  # refuse at construction, before anything else
    return classes[provider](
        model_id, timeout_s, env, served_model, max_output_tokens, params, plan_guard
    )
