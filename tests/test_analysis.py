"""Error analysis + validated-triple export (mock data only; mock output stays labelled and unpublishable)."""

import json
from pathlib import Path

import pytest

from evaluation.analysis import field_diffs
from evaluation.publish import PublishRefused, publish
from experiments import pipeline

ROOT = Path(__file__).resolve().parent.parent
TEXT = "Row (type | time | title | address): F | 14:00 live | PRADA | Via Lorenzini, 14"
EXP = {
    "show_name": "PRADA",
    "brand": "PRADA",
    "event_type": "fashion show",
    "date_time": "2026-09-22T14:00",
    "venue": "Via Lorenzini, 14",
}
EV = {**EXP, "evidence_quote": "F | 14:00 live | PRADA | Via Lorenzini, 14"}


def errs(ev_over=None, exp=EXP, parsed="default"):
    p = {"events": [{**EV, **(ev_over or {})}]} if parsed == "default" else parsed
    return [(d["field"], d["error"]) for d in field_diffs(exp, p, TEXT)]


def test_field_diffs_cover_every_error_type():
    assert errs() == []
    assert errs({"venue": None}) == [("venue", "missing_field")]
    assert errs({"venue": "Via Roma 1"}) == [("venue", "wrong_value")]
    assert errs({"date_time": "2026-09-22"}) == [
        ("date_time", "date_time_missing_time")
    ]
    assert errs({"venue": "Via X"}, {**EXP, "venue": None}) == [
        ("venue", "hallucinated_value")
    ]
    assert errs({"venue": "DIGITAL"}, {**EXP, "venue": None}) == [
        ("venue", "placeholder_as_venue")
    ]
    assert errs({"evidence_quote": "invented"}) == [
        ("evidence_quote", "evidence_not_verbatim")
    ]
    assert errs({"evidence_quote": None}) == [("evidence_quote", "missing_evidence")]
    assert errs(parsed=None) == [("*", "invalid_output")] and errs(
        parsed={"events": []}
    ) == [("*", "no_event")]
    assert ("events", "extra_event") in errs(parsed={"events": [EV, EV]})


def test_unscored_field_and_asterisk_are_not_errors():
    assert (
        errs({"brand": "Anything"}, {**EXP, "brand": None, "_unscored": ["brand"]})
        == []
    )
    assert (
        errs({"show_name": "PRADA *"}) == []
    )  # trailing asterisk is normalised, as in scoring


@pytest.fixture(scope="module")
def mock_out(tmp_path_factory):
    out = tmp_path_factory.mktemp("an")
    pipeline.run_mock(out)
    return out


def test_mock_analysis_files_labelled_and_complete(mock_out):
    assert (mock_out / "analysis_MOCK.json").exists() and (
        mock_out / "analysis_MOCK.md"
    ).exists()
    assert not (mock_out / "analysis.json").exists()
    an = json.loads((mock_out / "analysis_MOCK.json").read_text())
    assert an["is_mock"] is True and len(an["cells"]) == 9
    assert "MOCK RUN" in (mock_out / "analysis_MOCK.md").read_text()


def test_exact_records_and_error_examples_behave(mock_out):
    an = json.loads((mock_out / "analysis_MOCK.json").read_text())
    for key, c in an["cells"].items():
        if key.startswith("mock-perfect"):
            assert c["exact_records"] == 10 and c["examples"] == []
        if key.startswith("mock-broken"):
            assert (
                any(
                    d["error"] == "invalid_output"
                    for e in c["examples"]
                    for d in e["diffs"]
                )
                and c["exact_records"] < 10
            )
        if key.startswith("mock-noisy"):
            assert c["exact_records"] < 10 and c["records_with_errors"] > 0
    assert set(an["by_model"]) == {"mock-perfect", "mock-noisy", "mock-broken"} and set(
        an["by_technique"]
    ) == {"zero_shot", "few_shot", "step_by_step"}


def test_only_exactly_correct_predictions_become_valid_turtle(mock_out):
    from rdflib import Graph

    an = json.loads((mock_out / "analysis_MOCK.json").read_text())
    files = sorted((mock_out / "rdf").glob("*.ttl"))
    assert files and all(f.name.startswith("MOCK_") for f in files)
    perfect = [f for f in files if "mock-perfect" in f.name]
    assert len(perfect) == 3
    g = Graph().parse(perfect[0], format="turtle")
    assert len(g) > 0 and an["validated_triples"]["total"] == sum(
        an["validated_triples"]["per_cell"].values()
    )


def test_publish_refuses_mock_analysis_even_if_metrics_were_relabelled(
    mock_out, tmp_path
):
    d = json.loads((mock_out / "metrics_MOCK.json").read_text())
    d["is_mock"] = False
    for c in d["cells"]:
        c["is_mock"] = False
    d["meta"]["complete"] = True
    (tmp_path / "metrics.json").write_text(json.dumps(d))
    (tmp_path / "analysis.json").write_text(
        (mock_out / "analysis_MOCK.json").read_text()
    )  # still says is_mock
    with pytest.raises(PublishRefused, match="mock analysis"):
        publish(tmp_path / "metrics.json", tmp_path / "results")
    (tmp_path / "analysis.json").unlink()
    with pytest.raises(PublishRefused, match="analysis.json missing"):
        publish(tmp_path / "metrics.json", tmp_path / "results")
