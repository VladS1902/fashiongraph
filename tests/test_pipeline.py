import hashlib
import json
from pathlib import Path

import pytest

from evaluation.report import MockPublicationError, write_report
from evaluation.score import norm, rdf_check, score_record
from experiments import inputs as inp
from experiments import pipeline
from experiments.adapters import SpendNotApproved

ROOT = Path(__file__).resolve().parent.parent
TEXT = "Day: Tuesday 22 September 2026\nRow (type | time | title | address): F | 14:00 live PRADA | Via Lorenzini, 14"
EXP = {
    "show_name": "PRADA",
    "brand": "PRADA",
    "event_type": "fashion show",
    "date_time": "2026-09-22T14:00",
    "venue": "Via Lorenzini, 14",
}
EV = {**EXP, "evidence_quote": "F | 14:00 live PRADA | Via Lorenzini, 14"}


def sc(ev_overrides=None, exp=EXP, parsed="default"):
    ev = {**EV, **(ev_overrides or {})}
    p = {"events": [ev]} if parsed == "default" else parsed
    return score_record(exp, p, TEXT)


# ---- freeze / leakage / determinism ---------------------------------------
def test_gold_freeze_checksum_matches_manifest():
    m = json.loads((ROOT / "data/gold/MANIFEST.json").read_text())
    assert (
        m["sha256"]
        == hashlib.sha256(
            (ROOT / "data/gold/gold_pilot.jsonl").read_bytes()
        ).hexdigest()
    )
    assert "HUMAN VERIFIED" in m["review_status"] and m["version"] == "0.2.2"
    assert [h["version"] for h in m["history"]] == ["0.1.0", "0.2.0", "0.2.1"]
    for h in m["history"]:  # every prior version intact and checksummed
        old = ROOT / "data/gold" / h["file"]
        assert h["sha256"] == hashlib.sha256(old.read_bytes()).hexdigest()


def test_inputs_deterministic_and_match_committed_manifest():
    a, b = inp.build(write=False), inp.build(write=False)
    assert a["manifest"] == b["manifest"]
    committed = json.loads((ROOT / "data/experiment/MANIFEST.json").read_text())
    assert committed == a["manifest"]


def test_no_leakage_between_fewshot_and_test():
    train = [
        json.loads(x)
        for x in (ROOT / "data/experiment/fewshot_train.jsonl").read_text().splitlines()
    ]
    test = [
        json.loads(x)
        for x in (ROOT / "data/experiment/test_inputs.jsonl").read_text().splitlines()
    ]
    assert train and len(test) == 10
    assert not {t["id"].removeprefix("train-") for t in train} & {
        t["id"].removeprefix("mfw-ss27-") for t in test
    }
    names = {e["output"]["events"][0]["show_name"].casefold() for e in train}
    assert not names & {
        json.loads(x)["expected"]["show_name"].casefold()
        for x in (ROOT / "data/experiment/expected.jsonl").read_text().splitlines()
    }
    from experiments.prompts import render

    for (
        t
    ) in test:  # no test text appears inside any rendered few-shot prompt's examples
        ex = render("few_shot", "")[1]
        assert t["text"].split("Row")[-1] not in ex


def test_identical_input_across_models_and_techniques():
    from experiments.prompts import render

    t = "X"
    assert all(t in render(k, t)[1] for k in ("zero_shot", "few_shot", "step_by_step"))


# ---- scoring ----------------------------------------------------------------
def test_perfect():
    s = sc()
    assert (
        (s["tp"], s["fp"], s["fn"]) == (5, 0, 0)
        and s["errors"] == []
        and s["unsupported"] == 0
    )


def test_normalisation():
    assert norm("show_name", "PRADA *") == "prada"
    assert norm("date_time", "2026-09-22T14:00:00") == "2026-09-22T14:00"
    assert norm("event_type", "Runway show") == "fashion show"


def test_missing_wrong_hallucinated_placeholder():
    assert "missing_field" in sc({"brand": None})["errors"]
    assert "wrong_value" in sc({"venue": "Via Roma, 1"})["errors"]
    exp_null = {**EXP, "venue": None}
    s = sc({"venue": "Via Roma, 1"}, exp_null)
    assert (
        "hallucinated_value" in s["errors"] and s["fp"] == 1 and s["unsupported"] == 1
    )
    assert "placeholder_as_venue" in sc({"venue": "DIGITAL"}, exp_null)["errors"]
    s = sc({"venue": None}, exp_null)
    assert s["abstain_ok"] == 1 and s["fp"] == 0  # correct abstention is not an error


def test_date_only_and_evidence_errors_and_extra_event():
    assert "date_time_missing_time" in sc({"date_time": "2026-09-22"})["errors"]
    assert "evidence_not_verbatim" in sc({"evidence_quote": "made up"})["errors"]
    assert "missing_evidence" in sc({"evidence_quote": None})["errors"]
    two = {"events": [EV, EV]}
    assert "extra_event" in sc(parsed=two)["errors"]
    assert sc(parsed={"events": []})["errors"] == ["no_event"]


def test_invalid_output_counts_all_expected_as_fn():
    s = sc(parsed=None)
    assert s["fn"] == 5 and s["tp"] == 0 and s["errors"] == ["invalid_output"]


def test_rdf_outcome_classes():
    assert rdf_check({"events": [EV]}, "t") == "conforms"
    assert rdf_check({"events": [{**EV, "show_name": None}]}, "t") == "empty_graph"
    assert rdf_check({"events": [{**EV, "evidence_quote": None}]}, "t") == "shacl_fail"
    assert rdf_check(None, "t") == "no_prediction"


# ---- end-to-end (mock) --------------------------------------------------------
@pytest.fixture(scope="module")
def e2e(tmp_path_factory):
    out = tmp_path_factory.mktemp("mock")
    return out, pipeline.run_mock(out)


def test_e2e_cells_and_flags(e2e):
    out, res = e2e
    assert res["cells"] == 9 and all(a["is_mock"] for a in res["agg"])
    assert (out / "metrics_MOCK.json").exists() and (out / "report_MOCK.md").exists()
    assert not (out / "metrics.json").exists()
    assert "NOT model performance" in (out / "report_MOCK.md").read_text()
    assert json.loads((out / "metrics_MOCK.json").read_text())["is_mock"] is True


def test_e2e_correct_and_erroneous_outputs_behave(e2e):
    by = {}
    for a in e2e[1]["agg"]:
        by.setdefault(a["model_id"], []).append(a)
    for a in by["mock-perfect"]:
        assert (
            a["f1"] == 1.0
            and a["invalid_output_rate"] == 0
            and a["rdf_conforms_rate"] == 1.0
        )
    for a in by["mock-broken"]:
        assert 0 < a["invalid_output_rate"] < 1 and a["recall"] < 1
    noisy = by["mock-noisy"][0]
    assert noisy["f1"] < 1 and {"date_time_missing_time", "missing_field"} <= set(
        noisy["errors"]
    )


def test_e2e_resume_is_idempotent(e2e):
    out, first = e2e
    again = pipeline.run_mock(out)
    assert (
        again["stats"]["new"] == 0 and again["stats"]["cached"] >= first["stats"]["new"]
    )
    assert [a["f1"] for a in again["agg"]] == [a["f1"] for a in first["agg"]]


def test_mock_never_publishable(e2e, tmp_path):
    with pytest.raises(MockPublicationError):
        write_report(e2e[1]["agg"], {}, tmp_path, publish=True)


def test_site_ignores_mock_results():
    assert not (ROOT / "results" / "metrics.json").exists()


def test_real_run_refused_without_approval_or_with_placeholders(monkeypatch, tmp_path):
    monkeypatch.delenv("FASHIONGRAPH_APPROVED_SPEND", raising=False)
    with pytest.raises(SpendNotApproved):
        pipeline.run_real("x.json", tmp_path)
    monkeypatch.setenv("FASHIONGRAPH_APPROVED_SPEND", "1")
    f = tmp_path / "m.json"
    f.write_text(
        json.dumps(
            {
                "budget": {"cap_eur": 5, "usd_per_eur": 1.1},
                "models": [{"provider": "openai", "model_id": "PLACEHOLDER-x"}] * 3,
            }
        )
    )
    with pytest.raises(ValueError):
        pipeline.run_real(str(f), tmp_path)


def test_readiness_blocks_without_human_gates_and_never_leaks_keys():
    from experiments.readiness import checks

    env = {"OPENAI_API_KEY": "sk-SECRET-VALUE"}
    res = checks(None, env)
    by = {r["gate"]: r for r in res}
    assert by["gold human-verified"]["pass"] and by["gold frozen + checksum"]["pass"]
    assert (
        by["no few-shot leakage"]["pass"] and by["inputs match gold + manifest"]["pass"]
    )
    assert (
        not by["spend approved"]["pass"]
        and by["3 pinned models (models.json, mode paid)"]["pass"]
        and by["worst-case cost within EUR cap"]["pass"]
    )
    assert not by["techniques confirmed by course"]["pass"]
    assert (
        by["API key present: openai"]["pass"]
        and not by["API key present: gemini"]["pass"]
    )
    assert "SECRET" not in json.dumps(res)
    assert not all(r["pass"] for r in res)  # cannot be 'ready' in this session
