"""Report generation from scored aggregates. Mock aggregates can NEVER be published as results."""

from __future__ import annotations

import json
from pathlib import Path

MOCK_BANNER = "MOCK RUN - scripted rule-based stand-ins used to test plumbing. NOT model performance. No real LLM was called."


class MockPublicationError(RuntimeError):
    pass


def _f(x):
    return "n/a" if x is None else f"{x:.3f}"


def render_markdown(agg: list[dict], meta: dict) -> str:
    mock = any(a["is_mock"] for a in agg)
    lines = []
    if mock:
        lines += [f"> **{MOCK_BANNER}**", ""]
    lines += [
        f"# Extraction results ({'MOCK' if mock else 'provisional techniques'})",
        "",
        f"Dataset: `{meta.get('dataset_sha256', '?')[:12]}` | prompts: `{meta.get('prompt_version')}` | techniques: {meta.get('techniques_status')} | n per cell = {agg[0]['n_records'] if agg else 0}",
        "",
        "| model | technique | P | R | F1 | invalid | unsupported | RDF conforms | top errors |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for a in agg:
        top = (
            ", ".join(
                f"{k}:{v}"
                for k, v in sorted(a["errors"].items(), key=lambda kv: -kv[1])[:3]
            )
            or "-"
        )
        lines.append(
            f"| {a['model_id']} | {a['technique']} | {_f(a['precision'])} | {_f(a['recall'])} | {_f(a['f1'])} | {_f(a['invalid_output_rate'])} | {_f(a['unsupported_assertion_rate'])} | {_f(a['rdf_conforms_rate'])} | {top} |"
        )
    lines += [
        "",
        "Small n: no confidence intervals are claimed; differences are descriptive only.",
    ]
    return "\n".join(lines) + "\n"


def write_report(
    agg: list[dict], meta: dict, out_dir: str | Path, publish: bool = False
) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    mock = any(a["is_mock"] for a in agg)
    if publish and mock:
        raise MockPublicationError("refusing to publish mock aggregates as results")
    payload = {
        "banner": MOCK_BANNER if mock else None,
        "is_mock": mock,
        "meta": meta,
        "cells": agg,
    }
    name = "metrics_MOCK.json" if mock else "metrics.json"
    (out / name).write_text(json.dumps(payload, indent=1))
    (out / ("report_MOCK.md" if mock else "report.md")).write_text(
        render_markdown(agg, meta)
    )
    return {
        "json": str(out / name),
        "md": str(out / ("report_MOCK.md" if mock else "report.md")),
    }
