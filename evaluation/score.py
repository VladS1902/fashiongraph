"""Scoring of extraction predictions against frozen gold-derived expectations (see docs/experiment-protocol.md).

Unit of assertion: (record, field, normalised value) for fields show_name, brand, event_type, date_time, venue.
 TP  : predicted non-null == expected non-null (after normalisation)
 FP  : predicted non-null that is wrong, or predicted where expected is null
 FN  : expected non-null that is missing or wrong (invalid/unparseable output => all expected are FN)
Expected-null & predicted-null is a correct abstention (not counted in P/R, reported separately).
Error taxonomy (each occurrence counted): invalid_output, no_event, extra_event, missing_field, wrong_value,
 hallucinated_value, placeholder_as_venue, date_time_missing_time, evidence_not_verbatim, missing_evidence.
Support check: predicted show_name/brand/venue must appear (normalised) in the source text else `unsupported`.
SHACL/RDF validity is computed per prediction and is independent of correctness."""

from __future__ import annotations

import collections
import re

from rdf.convert import events_to_graph
from rdf.validate import parse_turtle, serialize, shacl_validate

FIELDS = ("show_name", "brand", "event_type", "date_time", "venue")
PLACEHOLDERS = ("location in the invitation", "digital")
SUPPORT_FIELDS = ("show_name", "brand", "venue")


def _ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def norm(field: str, v):
    if v is None:
        return None
    s = _ws(str(v))
    if field in ("show_name", "brand", "venue"):
        s = s.rstrip(" *").strip()
    if field == "date_time":
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}):(\d{2})(?::\d{2})?)?", s)
        return (
            None
            if s == ""
            else (
                f"{m.group(1)}T{m.group(2)}:{m.group(3)}"
                if m and m.group(2)
                else (m.group(1) if m else s.casefold())
            )
        )
    if field == "event_type":
        return (
            "fashion show"
            if re.search(r"show|runway|sfilata|défilé", s, re.IGNORECASE)
            else s.casefold()
        )
    return s.casefold() or None


def score_record(expected: dict, parsed: dict | None, text: str) -> dict:
    """Returns counts + error list for one record. parsed=None means invalid output."""
    c = collections.Counter()
    errors = []
    unscored = set(
        expected.get("_unscored", [])
    )  # e.g. brand for unclassified entries (policy 2)
    gold = {f: norm(f, expected.get(f)) for f in FIELDS}
    if parsed is None:
        c["fn"] = sum(1 for f, v in gold.items() if v is not None and f not in unscored)
        return {
            "tp": 0,
            "fp": 0,
            "fn": c["fn"],
            "abstain_ok": 0,
            "unsupported": 0,
            "predicted": 0,
            "errors": ["invalid_output"],
        }
    events = parsed.get("events", [])
    if not events:
        errors.append("no_event")
        return {
            "tp": 0,
            "fp": 0,
            "fn": sum(
                1 for f, v in gold.items() if v is not None and f not in unscored
            ),
            "abstain_ok": 0,
            "unsupported": 0,
            "predicted": 0,
            "errors": errors,
        }
    ev = events[0]
    ntext = _ws(text).casefold()
    for extra in events[1:]:
        errors.append("extra_event")
        c["fp"] += sum(1 for f in FIELDS if extra.get(f) is not None)
        c["predicted"] += sum(1 for f in FIELDS if extra.get(f) is not None)
    for f in FIELDS:
        if f in unscored:
            continue
        g, p = gold[f], norm(f, ev.get(f))
        if (
            f == "show_name"
            and ev.get(f)
            and expected.get(f)
            and _ws(str(ev[f])) != _ws(expected[f])
            and p == g
        ):
            errors.append(
                "asterisk_not_preserved"
            )  # diagnostic only; does not change TP/FP/FN
        if p is not None:
            c["predicted"] += 1
            if f in SUPPORT_FIELDS and p not in ntext:
                c["unsupported"] += 1
        if g is not None and p == g:
            c["tp"] += 1
        elif g is not None and p is None:
            c["fn"] += 1
            errors.append("missing_field")
        elif g is not None:
            c["fp"] += 1
            c["fn"] += 1
            errors.append(
                "date_time_missing_time"
                if f == "date_time" and p == g[:10]
                else "wrong_value"
            )
        elif p is not None:
            c["fp"] += 1
            errors.append(
                "placeholder_as_venue"
                if f == "venue" and p in PLACEHOLDERS
                else "hallucinated_value"
            )
        else:
            c["abstain_ok"] += 1
    q = ev.get("evidence_quote")
    if q is None:
        errors.append("missing_evidence")
    elif _ws(q) not in _ws(text):
        errors.append("evidence_not_verbatim")
    return {
        k: c[k] for k in ("tp", "fp", "fn", "abstain_ok", "unsupported", "predicted")
    } | {"errors": errors}


def rdf_check(parsed: dict | None, run_id: str) -> str:
    """'no_prediction' | 'empty_graph' | 'invalid_syntax' | 'shacl_fail' | 'conforms'."""
    if parsed is None:
        return "no_prediction"
    g = events_to_graph(parsed, run_id=run_id)
    if len(g) == 0:
        return "empty_graph"
    try:
        parse_turtle(serialize(g))
    except Exception:  # noqa: BLE001
        return "invalid_syntax"
    return "conforms" if shacl_validate(g)[0] else "shacl_fail"


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = (
        2 * p * r / (p + r)
        if p and r
        else (0.0 if p is not None and r is not None else None)
    )
    return p, r, f


def aggregate(
    rows: list[dict], inputs: dict[str, str], expected: dict[str, dict]
) -> list[dict]:
    """rows: runner JSONL rows. Groups by (model_id, technique)."""
    groups = collections.defaultdict(list)
    for r in rows:
        groups[(r["model_id"], r["technique"])].append(r)
    out = []
    for (model, tech), rs in sorted(groups.items()):
        tot = collections.Counter()
        errs = collections.Counter()
        rdf = collections.Counter()
        for r in rs:
            parsed = r.get("parsed") if r.get("status") == "ok" else None
            s = score_record(expected[r["record_id"]], parsed, inputs[r["record_id"]])
            for k in ("tp", "fp", "fn", "abstain_ok", "unsupported", "predicted"):
                tot[k] += s[k]
            errs.update(s["errors"])
            rdf[rdf_check(parsed, f"{model}|{tech}")] += 1
        p, rec, f1 = _prf(tot["tp"], tot["fp"], tot["fn"])
        n = len(rs)
        out.append(
            {
                "model_id": model,
                "technique": tech,
                "n_records": n,
                "is_mock": any(r.get("is_mock") for r in rs),
                "precision": p,
                "recall": rec,
                "f1": f1,
                **{k: tot[k] for k in ("tp", "fp", "fn", "abstain_ok")},
                "invalid_output_rate": errs["invalid_output"] / n,
                "unsupported_assertion_rate": tot["unsupported"] / tot["predicted"]
                if tot["predicted"]
                else None,
                "rdf_outcomes": dict(rdf),
                "rdf_conforms_rate": rdf["conforms"] / n,
                "errors": dict(errs),
            }
        )
    return out
