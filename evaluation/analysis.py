"""Error analysis and validated-triple export for a finished run (real or mock; mock output is labelled and unpublishable).

Produces, from the raw run rows only:
 - field-level error examples (record, field, expected, predicted, error type) for the report's "differences in behaviour";
 - descriptive model-level and technique-level summaries (unweighted means over cells; no significance claims, n is small);
 - Turtle for predictions that are EXACTLY correct (all scored fields match gold, verbatim evidence, SHACL-valid): these are the
   model-produced candidate triples that count as validated. Wrong or unsupported predictions are never exported as knowledge.
Nothing is interpreted automatically: the text of the discussion is written by people from these tables."""

from __future__ import annotations

import collections
import json
import re
from pathlib import Path

from evaluation.score import FIELDS, PLACEHOLDERS, norm, rdf_check
from rdf.convert import events_to_graph
from rdf.validate import serialize, shacl_validate


def _ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def field_diffs(expected: dict, parsed: dict | None, text: str) -> list[dict]:
    """One entry per scored-field disagreement or output-level failure."""
    if parsed is None:
        return [
            {
                "field": "*",
                "expected": None,
                "predicted": None,
                "error": "invalid_output",
            }
        ]
    events = parsed.get("events", [])
    if not events:
        return [
            {"field": "*", "expected": None, "predicted": None, "error": "no_event"}
        ]
    ev = events[0]
    out = []
    unscored = set(expected.get("_unscored", []))
    for f in FIELDS:
        if f in unscored:
            continue
        g, p = norm(f, expected.get(f)), norm(f, ev.get(f))
        if g == p:
            continue
        if g is not None and p is None:
            err = "missing_field"
        elif g is not None:
            err = (
                "date_time_missing_time"
                if f == "date_time" and p == g[:10]
                else "wrong_value"
            )
        else:
            err = (
                "placeholder_as_venue"
                if f == "venue" and p in PLACEHOLDERS
                else "hallucinated_value"
            )
        out.append(
            {
                "field": f,
                "expected": expected.get(f),
                "predicted": ev.get(f),
                "error": err,
            }
        )
    q = ev.get("evidence_quote")
    if q is None:
        out.append(
            {
                "field": "evidence_quote",
                "expected": "verbatim quote",
                "predicted": None,
                "error": "missing_evidence",
            }
        )
    elif _ws(q) not in _ws(text):
        out.append(
            {
                "field": "evidence_quote",
                "expected": "verbatim quote",
                "predicted": q,
                "error": "evidence_not_verbatim",
            }
        )
    if len(events) > 1:
        out.append(
            {
                "field": "events",
                "expected": "1 event",
                "predicted": f"{len(events)} events",
                "error": "extra_event",
            }
        )
    return out


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def summaries(agg: list[dict]) -> dict:
    """Descriptive means over cells (each cell weighted equally)."""
    by_model, by_tech = collections.defaultdict(list), collections.defaultdict(list)
    for c in agg:
        by_model[c["model_id"]].append(c)
        by_tech[c["technique"]].append(c)

    def summ(cells):
        errs = collections.Counter()
        for c in cells:
            errs.update(c["errors"])
        return {
            "cells": len(cells),
            "mean_f1": _mean([c["f1"] for c in cells]),
            "mean_precision": _mean([c["precision"] for c in cells]),
            "mean_recall": _mean([c["recall"] for c in cells]),
            "mean_invalid_output_rate": _mean(
                [c["invalid_output_rate"] for c in cells]
            ),
            "mean_rdf_conforms_rate": _mean([c["rdf_conforms_rate"] for c in cells]),
            "top_errors": dict(errs.most_common(5)),
        }

    return {
        "by_model": {k: summ(v) for k, v in sorted(by_model.items())},
        "by_technique": {k: summ(v) for k, v in sorted(by_tech.items())},
    }


def analyse(
    rows: list[dict],
    inputs: dict[str, str],
    expected: dict[str, dict],
    agg: list[dict],
    examples_per_cell: int = 3,
) -> dict:
    ex_by_cell: dict[str, list[dict]] = collections.defaultdict(list)
    exact: dict[str, list[dict]] = collections.defaultdict(list)
    outcomes: dict[str, dict[str, dict]] = collections.defaultdict(dict)
    usage: dict[str, dict] = collections.defaultdict(
        lambda: {"answered": 0, "input_tokens": 0, "output_tokens": 0}
    )
    for r in sorted(
        rows, key=lambda r: (r["model_id"], r["technique"], r["record_id"])
    ):
        parsed = r.get("parsed") if r.get("status") == "ok" else None
        diffs = field_diffs(expected[r["record_id"]], parsed, inputs[r["record_id"]])
        key = f"{r['model_id']} | {r['technique']}"
        if parsed is None:
            kind = "invalid"
        elif diffs:
            kind = "errors"
        else:
            kind = "exact"
        outcomes[key][r["record_id"]] = {
            "kind": kind,
            "n_diffs": len(diffs),
            "error_class": r.get("error_class"),
        }
        u = usage[r["model_id"]]
        u["answered"] += 1
        u["input_tokens"] += r.get("input_tokens") or 0
        u["output_tokens"] += r.get("output_tokens") or 0
        if diffs:
            ex_by_cell[key].append(
                {"record": r["record_id"], "status": r.get("status"), "diffs": diffs}
            )
        elif rdf_check(parsed, key) == "conforms":
            exact[key].append({"record": r["record_id"], "parsed": parsed})
    cells = {}
    for c in agg:
        key = f"{c['model_id']} | {c['technique']}"
        cells[key] = {
            "n_records": c["n_records"],
            "exact_records": len(exact.get(key, [])),
            "records_with_errors": len(ex_by_cell.get(key, [])),
            "examples": ex_by_cell.get(key, [])[:examples_per_cell],
            "outcomes": dict(sorted(outcomes.get(key, {}).items())),
        }
    return {
        "cells": cells,
        "usage": dict(usage),
        **summaries(agg),
        "note": "Descriptive only: unweighted means over cells, n small, no significance claims. No interpretation is generated.",
    }


def export_valid_turtle(
    rows: list[dict],
    inputs: dict[str, str],
    expected: dict[str, dict],
    out_dir: Path,
    prefix: str = "",
) -> dict[str, int]:
    """Write one Turtle file per (model, technique) with the exactly-correct, SHACL-valid predictions. Returns triple counts."""
    out_dir.mkdir(parents=True, exist_ok=True)
    groups: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    for r in rows:
        if r.get("status") == "ok" and not field_diffs(
            expected[r["record_id"]], r.get("parsed"), inputs[r["record_id"]]
        ):
            groups[(r["model_id"], r["technique"])].append(r)
    counts = {}
    for (m, t), rs in sorted(groups.items()):
        g = None
        for r in sorted(rs, key=lambda r: r["record_id"]):
            gg = events_to_graph(r["parsed"], run_id=f"{m}|{t}")
            if not shacl_validate(gg)[0]:
                continue
            g = gg if g is None else g + gg
        if g is not None and len(g):
            safe = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{prefix}{m}__{t}")
            (out_dir / f"{safe}.ttl").write_text(serialize(g))
            counts[f"{m} | {t}"] = len(g)
    return counts


def to_markdown(an: dict, mock: bool, valid_counts: dict[str, int]) -> str:
    fx = lambda x: "n/a" if x is None else f"{x:.3f}"
    L = []
    if mock:
        L += [
            "> **MOCK RUN: scripted stand-ins for plumbing tests. Not model behaviour.**",
            "",
        ]
    L += [
        "# Error analysis",
        "",
        an["note"],
        "",
        "## By model (mean over its 3 techniques)",
        "",
        "| model | mean F1 | mean P | mean R | invalid | RDF conforms | most common errors |",
        "|---|---|---|---|---|---|---|",
    ]
    for m, s in an["by_model"].items():
        L.append(
            f"| {m} | {fx(s['mean_f1'])} | {fx(s['mean_precision'])} | {fx(s['mean_recall'])} | {fx(s['mean_invalid_output_rate'])} | {fx(s['mean_rdf_conforms_rate'])} | {', '.join(f'{k}:{v}' for k, v in s['top_errors'].items()) or '-'} |"
        )
    L += [
        "",
        "## By prompting technique (mean over its 3 models)",
        "",
        "| technique | mean F1 | mean P | mean R | invalid | most common errors |",
        "|---|---|---|---|---|---|",
    ]
    for t, s in an["by_technique"].items():
        L.append(
            f"| {t} | {fx(s['mean_f1'])} | {fx(s['mean_precision'])} | {fx(s['mean_recall'])} | {fx(s['mean_invalid_output_rate'])} | {', '.join(f'{k}:{v}' for k, v in s['top_errors'].items()) or '-'} |"
        )
    L += ["", "## Per cell: exactly-correct records and example errors", ""]
    for key, c in an["cells"].items():
        L.append(
            f"### {key}\n\n{c['exact_records']} of {c['n_records']} records exactly correct and SHACL-valid; {valid_counts.get(key, 0)} validated triples exported.\n"
        )
        for e in c["examples"]:
            for d in e["diffs"]:
                L.append(
                    f"- `{e['record']}` field `{d['field']}`: expected `{d['expected']}`, got `{d['predicted']}` ({d['error']})"
                )
        L.append("")
    return "\n".join(L) + "\n"


def write_analysis(
    rows: list[dict],
    inputs: dict[str, str],
    expected: dict[str, dict],
    agg: list[dict],
    out_dir: str | Path,
) -> dict:
    out = Path(out_dir)
    mock = any(a["is_mock"] for a in agg)
    an = analyse(rows, inputs, expected, agg)
    prefix = "MOCK_" if mock else ""
    counts = export_valid_turtle(rows, inputs, expected, out / "rdf", prefix)
    an["validated_triples"] = {
        "per_cell": counts,
        "total": sum(counts.values()),
        "is_mock": mock,
    }
    an["is_mock"] = mock
    name = "analysis_MOCK" if mock else "analysis"
    (out / f"{name}.json").write_text(json.dumps(an, indent=1, default=str))
    (out / f"{name}.md").write_text(to_markdown(an, mock, counts))
    return an
