"""ONE-call smoke test per provider (NOT executed in CI; makes a real, billed call when run).
  FASHIONGRAPH_APPROVED_SPEND=1 <PROVIDER>_API_KEY=... python -m experiments.smoke --provider openai --models models.json
Sends the first test record with the zero_shot prompt, max_attempts=1, under the enforced EUR budget. Checks: HTTP success,
pinned served model, strict-JSON validity against the schema, usage fields present, cost recorded. Writes outputs/smoke/."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from . import inputs as inp
from . import models_file
from .adapters import APPROVAL_ENV, SpendNotApproved, make_adapter
from .config import ExperimentConfig, RetryPolicy
from .prompts import render
from .runner import call_with_retry
from .schema import ValidationError, parse_and_validate

ROOT = Path(__file__).resolve().parent.parent


def smoke(
    provider: str,
    models_json: str,
    out_dir: str | Path = ROOT / "outputs" / "smoke",
    model_id: str | None = None,
) -> dict:
    if os.environ.get(APPROVAL_ENV) != "1":
        raise SpendNotApproved(
            f"set {APPROVAL_ENV}=1 only after the owner approves spend"
        )
    mf = models_file.load(models_json)
    models_file.require_free_confirmation(mf)
    cands = [
        s
        for s in mf.specs
        if s.provider == provider and (model_id is None or s.model_id == model_id)
    ]
    if len(cands) != 1:
        raise ValueError(
            f"need exactly one model for provider {provider!r} (got {len(cands)}); pass --model-id"
        )
    spec = cands[0]
    out = Path(out_dir)
    budget = mf.make_guard(
        out / "ledger.jsonl"
    )  # paid: EUR budget; free: free-quota guard
    built = inp.build(write=False)
    rec = built["test"][0]
    system, user = render("zero_shot", rec["text"])
    ad = make_adapter(
        provider,
        spec.model_id,
        60.0,
        served_model=spec.served_model,
        max_output_tokens=spec.max_output_tokens,
        params=dict(spec.params),
        plan_guard=spec.plan_guard,
    )
    cfg = ExperimentConfig(models=(spec,), retry=RetryPolicy(max_attempts=1))
    res = {
        "provider": provider,
        "model_id": spec.model_id,
        "record": rec["id"],
        "ok": False,
    }
    comp, _ = call_with_retry(ad, system, user, cfg, budget=budget)
    res.update(
        requested_model=spec.model_id,
        served_model=comp.served_model,
        input_tokens=comp.input_tokens,
        output_tokens=comp.output_tokens,
        usage_present=comp.input_tokens is not None and comp.output_tokens is not None,
    )
    try:
        parsed = parse_and_validate(comp.text)
        res["json_valid"] = True
        res["parsed"] = parsed
    except ValidationError as e:
        res.update(json_valid=False, error=str(e), raw=comp.text[:500])
    res["budget"] = budget.summary()
    res["ok"] = bool(res.get("json_valid") and res["usage_present"])
    out.mkdir(parents=True, exist_ok=True)
    (
        out
        / f"smoke_{re.sub(r'[^A-Za-z0-9._-]+', '_', model_id) if model_id else provider}.json"
    ).write_text(json.dumps(res, indent=1, ensure_ascii=False))
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--provider", required=True, choices=["openai", "gemini", "mistral", "groq"]
    )
    ap.add_argument(
        "--model-id",
        default=None,
        help="needed when a provider has several models (Groq in models.free.json)",
    )
    ap.add_argument("--models", default=str(ROOT / "models.json"))
    a = ap.parse_args(argv)
    r = smoke(a.provider, a.models, model_id=a.model_id)
    print(json.dumps({k: v for k, v in r.items() if k != "parsed"}, indent=1))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
