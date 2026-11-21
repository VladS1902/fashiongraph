"""Bounded, resumable runner over models x techniques x records.

Cache key = hash of (provider, model, prompt_version, technique, system, user).
Each completed/failed cell is appended to a JSONL checkpoint; reruns skip done cells.
Mock results are tagged is_mock=true and must never be reported as research data.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from .adapters import (
    Adapter,
    GenerationFailed,
    ModelMismatch,
    PaidTierDetected,
    TransientError,
    make_adapter,
)
from .budget import Budget, BudgetExceeded
from .config import ExperimentConfig
from .prompts import render
from .ratelimit import QuotaExhausted
from .schema import ValidationError, parse_and_validate


def request_hash(provider, model_id, prompt_version, technique, system, user) -> str:
    blob = json.dumps([provider, model_id, prompt_version, technique, system, user])
    return hashlib.sha256(blob.encode()).hexdigest()


def _now():
    return datetime.now(UTC).isoformat()


def normalise_row(rec: dict) -> dict:
    """Rows logged before GenerationFailed existed carry status 'error' for a provider-side generation failure; relabel them
    as the final outcome they are (invalid output). Deterministic and documented; the raw file is never rewritten."""
    if rec.get("status") == "error" and "Failed to generate JSON" in (
        rec.get("error") or ""
    ):
        return {
            **rec,
            "status": "invalid",
            "error_class": "provider_generation_failure",
        }
    return rec


FINAL = (
    "ok",
    "invalid",
)  # answered (usable or not). Only 'error' (infrastructure) cells are retried on resume.


def load_done(path: Path) -> dict:
    done = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                rec = normalise_row(json.loads(line))
                if rec.get("status") in FINAL:
                    done[rec["request_hash"]] = rec
    return done


def call_with_retry(
    adapter: Adapter,
    system,
    user,
    cfg: ExperimentConfig,
    sleep=time.sleep,
    budget: Budget | None = None,
):
    last = None
    for attempt in range(1, cfg.retry.max_attempts + 1):
        rid = (
            budget.reserve(adapter.model_id, system, user) if budget else None
        )  # may raise BudgetExceeded
        try:
            comp = adapter.complete(system, user)
        except Exception as e:
            if budget:
                budget.settle(rid, None, None)  # failed attempt: charge worst case
            if not isinstance(e, TransientError):
                raise
            last = e
            if attempt < cfg.retry.max_attempts:
                sleep(
                    max(cfg.retry.delay(attempt), getattr(e, "retry_after", None) or 0)
                )
            continue
        if budget:
            budget.settle(rid, comp.input_tokens, comp.output_tokens)
        return comp, attempt
    raise last


def run(
    cfg: ExperimentConfig,
    records: list[dict],
    out_path: str | Path,
    adapters: dict | None = None,
    max_calls: int | None = None,
    cost_per_1k: dict | None = None,
    sleep=time.sleep,
    budget: Budget | None = None,
) -> dict:
    """records: [{"id":..., "text":...}]. max_calls bounds new (non-cached) calls per invocation.
    cost_per_1k: {model_id: (usd_in_per_1k, usd_out_per_1k)}; if given, spend is tracked and
    the run halts before exceeding cfg.cost_ceiling_usd."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = load_done(out)
    stats = {"cached": 0, "new": 0, "failed": 0, "halted": None, "cost_usd": 0.0}
    for rec in done.values():
        stats["cost_usd"] += rec.get("est_cost_usd") or 0.0
    adapters = adapters or {}
    deferred: dict[str, str] = {}
    with out.open("a") as fh:
        for m in cfg.models:
            for tech in cfg.techniques:
                for r in records:
                    system, user = render(tech, r["text"])
                    h = request_hash(
                        m.provider, m.model_id, cfg.prompt_version, tech, system, user
                    )
                    if h in done:
                        stats["cached"] += 1
                        continue
                    if (
                        m.model_id in deferred
                    ):  # this model's free daily quota is used up: leave its cells for a later resume
                        stats["deferred_cells"] = stats.get("deferred_cells", 0) + 1
                        continue
                    if (
                        max_calls is not None
                        and stats["new"] + stats["failed"] >= max_calls
                    ):
                        stats["halted"] = "max_calls"
                        return stats
                    if cost_per_1k and stats["cost_usd"] >= cfg.cost_ceiling_usd:
                        stats["halted"] = "cost_ceiling"
                        return stats
                    ad = adapters.get((m.provider, m.model_id))
                    if ad is None:
                        ad = adapters[(m.provider, m.model_id)] = make_adapter(
                            m.provider,
                            m.model_id,
                            cfg.timeout_s,
                            served_model=m.served_model,
                            max_output_tokens=m.max_output_tokens,
                            params=dict(m.params),
                            plan_guard=m.plan_guard,
                        )
                    if not ad.is_mock and budget is None:
                        raise RuntimeError(
                            "real provider calls require an enforced Budget"
                        )
                    row = {
                        "request_hash": h,
                        "record_id": r["id"],
                        "provider": m.provider,
                        "model_id": m.model_id,
                        "technique": tech,
                        "techniques_status": cfg.techniques_status,
                        "prompt_version": cfg.prompt_version,
                        "dataset_sha256": cfg.dataset_sha256,
                        "is_mock": ad.is_mock,
                        "started_at": _now(),
                    }
                    try:
                        comp, attempts = call_with_retry(
                            ad, system, user, cfg, sleep, budget
                        )
                        row.update(
                            attempts=attempts,
                            requested_model=m.model_id,
                            served_model=comp.served_model,
                            provider_meta=comp.meta,
                            raw_output=comp.text,
                            input_tokens=comp.input_tokens,
                            output_tokens=comp.output_tokens,
                        )
                        if cost_per_1k and m.model_id in cost_per_1k:
                            ci, co = cost_per_1k[m.model_id]
                            row["est_cost_usd"] = (
                                (comp.input_tokens or 0) * ci
                                + (comp.output_tokens or 0) * co
                            ) / 1000
                            stats["cost_usd"] += row["est_cost_usd"]
                        try:
                            row["parsed"] = parse_and_validate(comp.text)
                            row["status"] = "ok"
                            stats["new"] += 1
                        except ValidationError as e:
                            row.update(status="invalid", error=str(e))
                            stats["failed"] += 1
                    except QuotaExhausted as e:
                        deferred[m.model_id] = str(
                            e
                        )  # a free DAILY quota of one model: defer that model, keep running the others
                        stats.setdefault("deferred", {})[m.model_id] = str(e)
                        stats["deferred_cells"] = (
                            stats.get("deferred_cells", 0) + 1
                        )  # this cell too
                        continue
                    except BudgetExceeded as e:
                        stats["halted"] = "budget"
                        stats["budget_message"] = str(e)
                        return stats  # safe termination: nothing further is called or logged as a result
                    except PaidTierDetected as e:
                        row.update(status="paid_tier_detected", error=str(e))
                        row["finished_at"] = _now()
                        fh.write(json.dumps(row) + "\n")
                        stats["halted"] = "paid_tier_detected"
                        stats["failed"] += 1
                        return stats  # stop at once: never continue on a possibly billed plan
                    except GenerationFailed as e:
                        row.update(
                            status="invalid",
                            error=str(e),
                            error_class="provider_generation_failure",
                            raw_output=str(e)[:2000],
                        )
                        stats["failed"] += (
                            1  # final outcome, logged once, never retried
                        )
                    except ModelMismatch as e:
                        row.update(status="model_mismatch", error=str(e))
                        row["finished_at"] = _now()
                        fh.write(json.dumps(row) + "\n")
                        stats["halted"] = "model_mismatch"
                        stats["failed"] += 1
                        return stats  # never continue with a substituted model
                    except Exception as e:  # noqa: BLE001 - failure isolation: log and continue
                        row.update(status="error", error=f"{type(e).__name__}: {e}")
                        stats["failed"] += 1
                    row["finished_at"] = _now()
                    fh.write(json.dumps(row) + "\n")
                    fh.flush()
    if deferred and not stats["halted"]:
        stats["halted"] = (
            "quota_deferred"  # incomplete on purpose: rerun later (the daily window rolls over) to finish
        )
    return stats
