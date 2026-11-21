"""One-command pipeline: inputs -> prompts -> adapter -> parse -> RDF/SHACL -> score -> report.

  python -m experiments.pipeline mock [--out outputs/mock]   # deterministic, free, never counts as research data
  python -m experiments.pipeline real --models models.json   # REFUSED unless approved spend env is set and IDs are real
Checkpointed + resumable: re-running skips completed cells (request-hash cache)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from evaluation.analysis import write_analysis
from evaluation.report import write_report
from evaluation.score import aggregate
from experiments import inputs as inputs_mod
from experiments import models_file, runner
from experiments.adapters import APPROVAL_ENV, SpendNotApproved
from experiments.config import ExperimentConfig, ModelSpec
from experiments.mock_models import MOCK_MODELS, ScriptedMock

ROOT = Path(__file__).resolve().parent.parent


def load_rows(path: Path) -> list[dict]:
    last = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                r = runner.normalise_row(json.loads(line))
                last[r["request_hash"]] = r  # latest attempt wins
    return list(last.values())


def execute(
    cfg: ExperimentConfig,
    out_dir: Path,
    adapters: dict | None = None,
    publish: bool = False,
    max_calls: int | None = None,
    budget=None,
) -> dict:
    built = inputs_mod.build(write=True)
    texts = {r["id"]: r["text"] for r in built["test"]}
    expected = {r["id"]: r["expected"] for r in built["expected"]}
    records = [{"id": k, "text": v} for k, v in texts.items()]
    raw = out_dir / "raw_runs.jsonl"
    stats = runner.run(
        cfg, records, raw, adapters=adapters, max_calls=max_calls, budget=budget
    )
    rows = load_rows(raw)
    agg = aggregate(rows, texts, expected)
    meta = {
        "dataset_sha256": cfg.dataset_sha256,
        "prompt_version": cfg.prompt_version,
        "techniques_status": cfg.techniques_status,
        "gold_sha256": built["manifest"]["gold_sha256"],
        "run_stats": stats,
        "expected_rows": len(cfg.models) * len(cfg.techniques) * len(records),
        "answered_rows": sum(1 for r in rows if r.get("status") in ("ok", "invalid")),
        **({"budget": budget.summary()} if budget else {}),
    }
    meta["complete"] = meta["answered_rows"] == meta["expected_rows"] and not stats.get(
        "halted"
    )
    paths = write_report(agg, meta, out_dir, publish=publish)
    analysis = write_analysis(rows, texts, expected, agg, out_dir)
    return {
        "stats": stats,
        "cells": len(agg),
        "paths": paths,
        "agg": agg,
        "analysis": analysis,
    }


def mock_config(built_manifest: dict | None = None) -> ExperimentConfig:
    m = built_manifest or inputs_mod.build(write=False)["manifest"]
    return ExperimentConfig(
        models=tuple(ModelSpec("mock", x) for x in MOCK_MODELS),
        dataset_sha256=m["sha256"]["test_inputs.jsonl"],
        cost_ceiling_usd=0.0,
    )


def run_mock(out_dir: str | Path = ROOT / "outputs" / "mock") -> dict:
    cfg = mock_config()
    ads = {("mock", m): ScriptedMock(m) for m in MOCK_MODELS}
    return execute(cfg, Path(out_dir), adapters=ads)


def run_real(
    models_json: str,
    out_dir: str | Path = ROOT / "outputs" / "real",
    max_calls: int | None = None,
) -> dict:
    """Real 3x3x10 run. Refused without approval; budget (EUR cap, ledger in out_dir) is enforced per attempt."""
    if os.environ.get(APPROVAL_ENV) != "1":
        raise SpendNotApproved(
            f"set {APPROVAL_ENV}=1 only after the owner approves spend"
        )
    mf = models_file.load(
        models_json
    )  # validates pinned IDs, prices, budget; fails closed
    models_file.require_free_confirmation(mf)
    m = inputs_mod.build(write=True)["manifest"]
    cfg = ExperimentConfig(
        models=mf.specs,
        dataset_sha256=m["sha256"]["test_inputs.jsonl"],
        techniques_status=mf.technique_status,
        retry=mf.retry,
    )
    out = Path(out_dir)
    budget = mf.make_guard(
        out / "ledger.jsonl"
    )  # paid: EUR budget; free: documented free-quota guard
    return execute(cfg, out, budget=budget, max_calls=max_calls)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["mock", "real"])
    ap.add_argument("--out")
    ap.add_argument("--models")
    a = ap.parse_args(argv)
    res = (
        run_mock(a.out or ROOT / "outputs" / "mock")
        if a.mode == "mock"
        else run_real(a.models, a.out or ROOT / "outputs" / "real")
    )
    print(
        json.dumps({k: v for k, v in res.items() if k != "agg"}, indent=1, default=str)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
