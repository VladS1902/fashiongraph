"""Load and validate models.json (pinned model IDs, official prices, budget). Fail closed on anything missing."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .budget import Budget, BudgetConfig, Price
from .config import ModelSpec, RetryPolicy

PAID_PROVIDERS = {"openai", "gemini", "mistral"}
FREE_PROVIDERS = {"gemini", "groq"}


@dataclass(frozen=True)
class ModelsFile:
    specs: tuple[ModelSpec, ...]
    prices: dict
    budget_cfg: BudgetConfig
    technique_status: str
    raw: dict
    mode: str = "paid"
    limits: dict | None = None
    retry: RetryPolicy = field(default_factory=RetryPolicy)

    def make_budget(self, ledger) -> Budget:
        return Budget(
            self.budget_cfg,
            self.prices,
            {s.model_id: s.max_output_tokens for s in self.specs},
            ledger,
        )

    def make_guard(self, ledger):
        """Paid mode: the EUR budget. Free mode: the free-quota guard (zero cost, paced, fail-closed)."""
        if self.mode == "free":
            from .ratelimit import FreeTierGuard

            return FreeTierGuard(
                self.limits,
                {s.model_id: s.max_output_tokens for s in self.specs},
                ledger,
                self.budget_cfg,
            )
        return self.make_budget(ledger)


FREE_CONFIRM_ENV = "FASHIONGRAPH_FREE_TIER_CONFIRMED"


class FreeTierNotConfirmed(RuntimeError):
    pass


def require_free_confirmation(mf: ModelsFile, env=None) -> None:
    """A free-tier run needs the owner's explicit statement that no billing is attached to the keys used."""
    import os

    env = os.environ if env is None else env
    if mf.mode == "free" and env.get(FREE_CONFIRM_ENV) != "1":
        raise FreeTierNotConfirmed(
            f"set {FREE_CONFIRM_ENV}=1 only after confirming the Gemini key's project has no billing account and the Groq organisation is on the Free plan"
        )


def load(path: str | Path) -> ModelsFile:
    d = json.loads(Path(path).read_text())
    mode = d.get("mode", "paid")
    if mode not in ("paid", "free"):
        raise ValueError(f"unknown mode {mode}")
    models = d["models"]
    provs = [m["provider"] for m in models]
    families = [m.get("family", m["provider"]) for m in models]
    if len(models) != 3 or len(set(families)) != 3:
        raise ValueError(
            "models file must define exactly three models from three distinct model families"
        )
    if mode == "paid" and set(provs) != PAID_PROVIDERS:
        raise ValueError(
            "paid configuration must define exactly one model for each of openai, gemini, mistral"
        )
    if mode == "free" and not set(provs) <= FREE_PROVIDERS:
        raise ValueError(
            "free configuration may only use providers with a documented free tier: gemini, groq"
        )
    specs, prices, limits = [], {}, {}
    for m in models:
        mid = m["model_id"]
        if "PLACEHOLDER" in mid or not mid:
            raise ValueError(f"placeholder model id: {mid}")
        if not m.get("served_model"):
            raise ValueError(f"{mid}: served_model required (no silent substitution)")
        pr = m.get("price") or {}
        for k in ("usd_in_per_m", "usd_out_per_m", "source", "retrieved"):
            if k not in pr:
                raise ValueError(f"{mid}: price.{k} missing")
        prices[mid] = Price(
            float(pr["usd_in_per_m"]),
            float(pr["usd_out_per_m"]),
            bool(pr.get("order_verified", False)),
        )
        guard = None
        if m["provider"] == "groq":
            pg = m.get("plan_guard") or {}
            if mode == "free" and not pg:
                raise ValueError(
                    f"{mid}: a free Groq model needs plan_guard (free-plan header maxima)"
                )
            guard = (
                (int(pg["max_tpm_header"]), int(pg["max_rpd_header"])) if pg else None
            )
        if mode == "free":
            lm = m.get("limits") or {}
            for k in ("rpm", "rpd", "tpm", "tpd", "verified", "source", "retrieved"):
                if k not in lm:
                    raise ValueError(
                        f"{mid}: limits.{k} missing (free mode needs documented or explicitly assumed limits)"
                    )
            if any(lm[k] is None for k in ("rpm", "rpd", "tpm", "tpd")):
                raise ValueError(
                    f"{mid}: free limits must all be set (an unlimited assumption is not safe)"
                )
            from .ratelimit import Limits

            pace = lm.get("pace_rpm")
            if pace is not None and not (0 < int(pace) <= int(lm["rpm"])):
                raise ValueError(f"{mid}: pace_rpm must be between 1 and the rpm limit")
            limits[mid] = Limits(
                int(pace) if pace is not None else int(lm["rpm"]),
                int(lm["rpd"]),
                int(lm["tpm"]),
                int(lm["tpd"]),
                bool(lm["verified"]),
                lm["source"],
            )
        specs.append(
            ModelSpec(
                m["provider"],
                mid,
                m["served_model"],
                int(m["max_output_tokens"]),
                tuple(sorted((m.get("params") or {}).items())),
                guard,
            )
        )
    b = d["budget"]
    cfg = BudgetConfig(
        float(b["cap_eur"]),
        float(b["usd_per_eur"]),
        float(b.get("fx_safety_factor", 0.95)),
        float(b.get("chars_per_token", 3.0)),
        float(b.get("input_margin", 1.25)),
    )
    if (mode == "paid" and cfg.cap_eur <= 0) or cfg.fx_safety_factor > 1:
        raise ValueError("invalid budget config")
    rp = d.get("retry") or {}
    retry = RetryPolicy(
        int(rp.get("max_attempts", 4)),
        float(rp.get("base_delay_s", 1.0)),
        float(rp.get("max_delay_s", 30.0)),
    )
    if not (
        1 <= retry.max_attempts <= 6 and 0 < retry.base_delay_s <= retry.max_delay_s
    ):
        raise ValueError("invalid retry policy")
    rp = d.get("retry") or {}
    retry = RetryPolicy(
        int(rp.get("max_attempts", 4)),
        float(rp.get("base_delay_s", 1.0)),
        float(rp.get("max_delay_s", 30.0)),
    )
    if not (
        1 <= retry.max_attempts <= 6 and 0 < retry.base_delay_s <= retry.max_delay_s
    ):
        raise ValueError("invalid retry policy")
    return ModelsFile(
        tuple(specs),
        prices,
        cfg,
        d.get("technique_status", "PROVISIONAL"),
        d,
        mode,
        limits or None,
        retry,
    )
