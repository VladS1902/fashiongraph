"""Immutable experiment configuration. Techniques are PROVISIONAL (R5: names not in PDF)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

TECHNIQUES_PROVISIONAL = ("zero_shot", "few_shot", "step_by_step")
PROMPT_VERSION = "v0.2-provisional"


@dataclass(frozen=True)
class ModelSpec:
    provider: str  # openai | gemini | mistral | groq | mock
    model_id: str  # exact ID; PLACEHOLDER until owner confirms accessible versions
    served_model: str | None = (
        None  # value the provider response must report; mismatch aborts (no silent substitution)
    )
    max_output_tokens: int = (
        512  # hard per-call output cap (also the worst case used for budgeting)
    )
    params: tuple = ()  # extra request parameters as (key, value) pairs, e.g. reasoning effort
    plan_guard: tuple | None = (
        None  # (max tokens/min header, max requests/day header) of the FREE plan; Groq only
    )


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 4
    base_delay_s: float = 1.0
    max_delay_s: float = 30.0

    def delay(self, attempt: int) -> float:
        """Delay before retry number `attempt` (1-based); bounded exponential."""
        return min(self.max_delay_s, self.base_delay_s * 2 ** (attempt - 1))


@dataclass(frozen=True)
class ExperimentConfig:
    models: tuple[ModelSpec, ...]
    techniques: tuple[str, ...] = TECHNIQUES_PROVISIONAL
    prompt_version: str = PROMPT_VERSION
    dataset_sha256: str = ""
    cost_ceiling_usd: float = 0.0
    timeout_s: float = 60.0
    retry: RetryPolicy = RetryPolicy()
    techniques_status: str = "PROVISIONAL"

    def __post_init__(self):
        unknown = set(self.techniques) - set(TECHNIQUES_PROVISIONAL)
        if unknown:
            raise ValueError(f"unknown techniques: {sorted(unknown)}")


# Placeholder IDs, NOT confirmed accessible; owner must set before any real run.
DEFAULT_MODELS = (
    ModelSpec("openai", "PLACEHOLDER-openai-model"),
    ModelSpec("gemini", "PLACEHOLDER-gemini-model"),
    ModelSpec("mistral", "PLACEHOLDER-mistral-model"),
)


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
