"""Enforced EUR budget, pinned-model checks, adapter payloads, smoke/publish gates (no network, no paid calls)."""

import json
from pathlib import Path

import pytest

from experiments import adapters, models_file, runner
from experiments.adapters import (
    GeminiAdapter,
    MistralAdapter,
    ModelMismatch,
    OpenAIAdapter,
    SpendNotApproved,
    make_adapter,
)
from experiments.budget import Budget, BudgetConfig, BudgetExceeded, Price
from experiments.config import ExperimentConfig, ModelSpec, RetryPolicy

ROOT = Path(__file__).resolve().parent.parent
PRICES = {"m": Price(1.0, 2.0)}  # USD per 1M tokens
SYS, USER = "s" * 300, "u" * 300


def bud(tmp_path, cap_eur=1.0, **kw):
    cfg = BudgetConfig(cap_eur=cap_eur, usd_per_eur=1.0, fx_safety_factor=1.0, **kw)
    return Budget(cfg, PRICES, {"m": 1000}, tmp_path / "ledger.jsonl")


def test_fx_cap_is_conservative():
    c = BudgetConfig(cap_eur=5.0, usd_per_eur=1.0968, fx_safety_factor=0.95)
    assert c.cap_usd == pytest.approx(5.0 * 1.0968 * 0.95) and c.cap_usd < 5.0 * 1.0968


def test_estimate_is_worst_case_and_unknown_model_fails_closed(tmp_path):
    b = bud(tmp_path)
    est = b.estimate_usd("m", SYS, USER)
    assert est >= 1000 * 2.0 / 1e6  # at least the full output cap
    with pytest.raises(KeyError):
        b.estimate_usd("unknown", SYS, USER)


def test_unverified_price_order_budgets_higher_rate_both_ways():
    p = Price(0.15, 0.60, order_verified=False)
    assert p.budget_in == 0.60 and p.budget_out == 0.60
    assert Price(0.15, 0.60).budget_in == 0.15


def test_reserve_settle_tracks_actual_and_persists(tmp_path):
    b = bud(tmp_path)
    rid = b.reserve("m", SYS, USER)
    assert b.spent_usd() == pytest.approx(
        b.estimate_usd("m", SYS, USER)
    )  # reserved counts immediately
    cost = b.settle(rid, 100, 50)
    assert cost == pytest.approx(
        (100 * 1.0 + 50 * 2.0) / 1e6
    ) and b.spent_usd() == pytest.approx(cost)
    assert bud(tmp_path).spent_usd() == pytest.approx(
        cost
    )  # a fresh object (restart) sees the ledger


def test_missing_usage_and_crash_charge_worst_case(tmp_path):
    b = bud(tmp_path)
    est = b.estimate_usd("m", SYS, USER)
    b.settle(b.reserve("m", SYS, USER), None, None)
    assert b.spent_usd() == pytest.approx(est)
    b.reserve("m", SYS, USER)  # never settled (simulated crash)
    assert bud(tmp_path).spent_usd() == pytest.approx(2 * est)


def test_refuses_before_call_when_cap_would_be_exceeded(tmp_path):
    est = bud(tmp_path).estimate_usd("m", SYS, USER)
    b = bud(tmp_path / "x", cap_eur=est * 2.5)  # room for exactly two worst-case calls
    b.reserve("m", SYS, USER)
    b.reserve("m", SYS, USER)
    with pytest.raises(BudgetExceeded):
        b.reserve("m", SYS, USER)


def test_overrun_by_actual_usage_stops_run(tmp_path):
    b = bud(tmp_path, cap_eur=0.01)
    rid = b.reserve("m", "a", "b")
    with pytest.raises(BudgetExceeded):
        b.settle(rid, 10_000_000, 10_000_000)


class Fake(adapters.Adapter):
    provider, is_mock = "openai", False
    calls = 0

    def complete(self, system, user):
        Fake.calls += 1
        return adapters.Completion(json.dumps({"events": []}), 200, 100, {})


def run_with(tmp_path, cap_eur, n_records=6):
    Fake.calls = 0
    spec = ModelSpec("openai", "m", None, 1000)
    cfg = ExperimentConfig(
        models=(spec,), techniques=("zero_shot",), retry=RetryPolicy(max_attempts=2)
    )
    recs = [{"id": f"r{i}", "text": f"t{i}" * 40} for i in range(n_records)]
    b = bud(tmp_path, cap_eur=cap_eur)
    st = runner.run(
        cfg,
        recs,
        tmp_path / "out.jsonl",
        adapters={("openai", "m"): Fake("m")},
        budget=b,
    )
    return st, b


def test_runner_terminates_mid_run_at_budget_and_resume_keeps_counting(tmp_path):
    from experiments.prompts import render

    class Heavy(Fake):  # actual usage close to the worst case, so the cap bites mid-run
        def complete(self, system, user):
            Fake.calls += 1
            return adapters.Completion(json.dumps({"events": []}), 200, 1000, {})

    s, u = render("zero_shot", "t0" * 40)
    est = bud(tmp_path / "e").estimate_usd("m", s, u)
    cfg = ExperimentConfig(
        models=(ModelSpec("openai", "m", None, 1000),), techniques=("zero_shot",)
    )
    recs = [{"id": f"r{i}", "text": f"t{i}" * 40} for i in range(8)]
    Fake.calls = 0
    b = bud(tmp_path, cap_eur=est * 3.5)
    st = runner.run(
        cfg,
        recs,
        tmp_path / "o.jsonl",
        adapters={("openai", "m"): Heavy("m")},
        budget=b,
    )
    assert (
        st["halted"] == "budget"
        and 2 <= Fake.calls <= 4
        and b.spent_usd() <= b.cfg.cap_usd
    )
    done = Fake.calls
    st2 = runner.run(
        cfg,
        recs,
        tmp_path / "o.jsonl",
        adapters={("openai", "m"): Heavy("m")},
        budget=bud(tmp_path, cap_eur=est * 3.5),
    )
    assert (
        st2["halted"] == "budget" and Fake.calls == done
    )  # ledger persisted: no further spend after restart


def test_runner_halts_when_estimate_exceeds_remaining(tmp_path):
    from experiments.prompts import render

    s, u = render("zero_shot", "t0" * 40)
    est = bud(tmp_path / "e").estimate_usd("m", s, u)
    st, _ = run_with(tmp_path, cap_eur=est * 0.5)  # not even one worst-case call fits
    assert (
        st["halted"] == "budget"
        and Fake.calls == 0
        and not (tmp_path / "out.jsonl").read_text().strip()
    )


def test_runner_refuses_real_adapter_without_budget(tmp_path):
    spec = ModelSpec("openai", "m")
    cfg = ExperimentConfig(models=(spec,), techniques=("zero_shot",))
    with pytest.raises(RuntimeError, match="require an enforced Budget"):
        runner.run(
            cfg,
            [{"id": "r", "text": "t"}],
            tmp_path / "o.jsonl",
            adapters={("openai", "m"): Fake("m")},
        )


def test_failed_attempts_are_charged(tmp_path):
    class Flaky(Fake):
        def complete(self, system, user):
            raise adapters.TransientError("503")

    spec = ModelSpec("openai", "m", None, 1000)
    cfg = ExperimentConfig(
        models=(spec,), techniques=("zero_shot",), retry=RetryPolicy(max_attempts=3)
    )
    b = bud(tmp_path, cap_eur=1.0)
    runner.run(
        cfg,
        [{"id": "r", "text": "t"}],
        tmp_path / "o.jsonl",
        adapters={("openai", "m"): Flaky("m")},
        budget=b,
        sleep=lambda s: None,
    )
    assert b.spent_usd() > 0  # 3 failed attempts each charged the worst-case estimate


# ---- pinned model / adapter payloads ---------------------------------------------------
ENV = {
    "FASHIONGRAPH_APPROVED_SPEND": "1",
    "OPENAI_API_KEY": "k",
    "GEMINI_API_KEY": "k",
    "MISTRAL_API_KEY": "k",
}


def capture(monkeypatch, response):
    seen = {}

    def fake_post(self, url, headers, payload):
        seen.update(url=url, headers=headers, payload=payload)
        return response

    monkeypatch.setattr(adapters.Adapter, "_post", fake_post)
    return seen


def test_openai_payload_and_pinned_model(monkeypatch):
    resp = {
        "model": "gpt-5.4-mini-2026-03-17",
        "choices": [{"message": {"content": "{}"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3},
    }
    seen = capture(monkeypatch, resp)
    a = OpenAIAdapter(
        "gpt-5.4-mini-2026-03-17",
        env=ENV,
        served_model="gpt-5.4-mini-2026-03-17",
        max_output_tokens=400,
    )
    c = a.complete("s", "u")
    p = seen["payload"]
    assert (
        p["reasoning_effort"] == "none"
        and p["temperature"] == 0
        and p["max_completion_tokens"] == 400
        and "max_tokens" not in p
    )
    assert p["response_format"]["json_schema"]["strict"] is True and (
        c.input_tokens,
        c.output_tokens,
    ) == (5, 3)
    monkeypatch.setattr(
        adapters.Adapter,
        "_post",
        lambda self, u, h, p: {**resp, "model": "gpt-6-other"},
    )
    with pytest.raises(ModelMismatch):
        a.complete("s", "u")


def test_gemini_payload_thinking_level_no_temperature_counts_thoughts_and_guards_model(
    monkeypatch,
):
    resp = {
        "modelVersion": "gemini-3.5-flash-lite",
        "candidates": [{"content": {"parts": [{"text": "{}"}]}}],
        "usageMetadata": {
            "promptTokenCount": 7,
            "candidatesTokenCount": 4,
            "thoughtsTokenCount": 9,
        },
    }
    seen = capture(monkeypatch, resp)
    a = GeminiAdapter(
        "gemini-3.5-flash-lite",
        env=ENV,
        served_model="gemini-3.5-flash-lite",
        max_output_tokens=1024,
    )
    c = a.complete("s", "u")
    g = seen["payload"]["generationConfig"]
    assert (
        "temperature" not in g and "temperature" not in seen["payload"]
    )  # deprecated/ignored for Gemini 3.x
    assert g["thinkingConfig"] == {
        "thinkingLevel": "MINIMAL"
    } and "thinkingBudget" not in json.dumps(g)
    assert g["maxOutputTokens"] == 1024 and g["responseMimeType"] == "application/json"
    props = g["responseJsonSchema"]["properties"]["events"]["items"]
    assert g["responseJsonSchema"]["additionalProperties"] is False and props[
        "properties"
    ]["venue"]["type"] == ["string", "null"]
    assert seen["url"].endswith("/models/gemini-3.5-flash-lite:generateContent")
    assert (
        c.output_tokens == 13 and c.served_model == "gemini-3.5-flash-lite"
    )  # thinking tokens billed as output; served id recorded
    for wrong in ("gemini-3.5-flash-lite-preview", "gemini-2.5-flash", None):
        monkeypatch.setattr(
            adapters.Adapter,
            "_post",
            lambda self, u, h, p, w=wrong: {**resp, "modelVersion": w},
        )
        with pytest.raises(ModelMismatch):
            a.complete("s", "u")


def test_gemini_thought_parts_are_not_returned_as_answer(monkeypatch):
    resp = {
        "modelVersion": "gemini-3.5-flash-lite",
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "thinking...", "thought": True},
                        {"text": '{"events": []}'},
                    ]
                }
            }
        ],
        "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
    }
    capture(monkeypatch, resp)
    c = GeminiAdapter(
        "gemini-3.5-flash-lite", env=ENV, served_model="gemini-3.5-flash-lite"
    ).complete("s", "u")
    assert c.text == '{"events": []}'


def test_mistral_payload(monkeypatch):
    resp = {
        "model": "mistral-small-2603",
        "choices": [{"message": {"content": "{}"}}],
        "usage": {"prompt_tokens": 2, "completion_tokens": 1},
    }
    seen = capture(monkeypatch, resp)
    MistralAdapter(
        "mistral-small-2603",
        env=ENV,
        served_model="mistral-small-2603",
        max_output_tokens=400,
    ).complete("s", "u")
    p = seen["payload"]
    assert (
        p["max_tokens"] == 400
        and p["response_format"]["type"] == "json_schema"
        and p["temperature"] == 0
    )


def test_runner_stops_on_model_mismatch_without_continuing(tmp_path, monkeypatch):
    resp = {
        "model": "substituted",
        "choices": [{"message": {"content": '{"events": []}'}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    capture(monkeypatch, resp)
    spec = ModelSpec("openai", "m", "pinned", 400)
    cfg = ExperimentConfig(models=(spec,), techniques=("zero_shot",))
    ad = make_adapter(
        "openai", "m", env=ENV, served_model="pinned", max_output_tokens=400
    )
    st = runner.run(
        cfg,
        [{"id": "a", "text": "x"}, {"id": "b", "text": "y"}],
        tmp_path / "o.jsonl",
        adapters={("openai", "m"): ad},
        budget=bud(tmp_path),
    )
    assert st["halted"] == "model_mismatch"
    rows = [json.loads(x) for x in (tmp_path / "o.jsonl").read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["status"] == "model_mismatch"


# ---- models.json / smoke / publish ------------------------------------------------------
def test_models_json_valid_pinned_and_priced():
    mf = models_file.load(ROOT / "models.json")
    ids = {s.provider: s.model_id for s in mf.specs}
    assert ids == {
        "openai": "gpt-5.4-mini-2026-03-17",
        "gemini": "gemini-3.5-flash-lite",
        "mistral": "mistral-small-2603",
    }
    assert all(s.served_model for s in mf.specs) and mf.budget_cfg.cap_eur == 5.0
    assert mf.prices["mistral-small-2603"].order_verified is False


def test_models_file_fails_closed(tmp_path):
    d = json.loads((ROOT / "models.json").read_text())
    for mutate in (
        lambda x: x["models"].pop(),
        lambda x: x["models"][0].update(served_model=""),
        lambda x: x["models"][0]["price"].pop("source"),
        lambda x: x["models"][0].update(model_id="PLACEHOLDER-x"),
        lambda x: x["budget"].update(cap_eur=0),
    ):
        dd = json.loads(json.dumps(d))
        mutate(dd)
        f = tmp_path / "m.json"
        f.write_text(json.dumps(dd))
        with pytest.raises((ValueError, KeyError)):
            models_file.load(f)


def test_smoke_refused_without_approval_and_cost_estimate_below_cap(monkeypatch):
    from experiments import cost_estimate, smoke

    monkeypatch.delenv("FASHIONGRAPH_APPROVED_SPEND", raising=False)
    with pytest.raises(SpendNotApproved):
        smoke.smoke("openai", str(ROOT / "models.json"))
    e = cost_estimate.estimate()
    assert (
        e["calls_total"] == 90
        and e["total_expected_eur"] < e["total_worst_eur"] < e["cap_eur"] / 10
    )


def test_smoke_runs_one_call_under_budget_with_fake_provider(monkeypatch, tmp_path):
    from experiments import smoke

    monkeypatch.setenv("FASHIONGRAPH_APPROVED_SPEND", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    good = {
        "events": [
            {
                k: None
                for k in (
                    "show_name",
                    "brand",
                    "event_type",
                    "date_time",
                    "venue",
                    "evidence_quote",
                )
            }
        ]
    }
    resp = {
        "model": "gpt-5.4-mini-2026-03-17",
        "choices": [{"message": {"content": json.dumps(good)}}],
        "usage": {"prompt_tokens": 300, "completion_tokens": 60},
    }
    n = {"calls": 0}

    def fake_post(self, u, h, p):
        n["calls"] += 1
        return resp

    monkeypatch.setattr(adapters.Adapter, "_post", fake_post)
    r = smoke.smoke("openai", str(ROOT / "models.json"), tmp_path)
    assert (
        n["calls"] == 1
        and r["ok"]
        and r["budget"]["spent_eur"] < 0.01
        and (tmp_path / "smoke_openai.json").exists()
    )


def synthetic_real_metrics(tmp_path, **over):
    """A NON-mock metrics file shaped like a genuine run: used only to test ingestion plumbing."""
    from experiments import inputs as inp
    from experiments.config import PROMPT_VERSION

    cur = inp.build(write=False)["manifest"]
    cells = [
        {
            "model_id": m,
            "technique": t,
            "n_records": 10,
            "is_mock": False,
            "precision": 0.9,
            "recall": 0.8,
            "f1": 0.85,
            "invalid_output_rate": 0.0,
            "unsupported_assertion_rate": None,
            "rdf_conforms_rate": 1.0,
            "errors": {},
        }
        for m in ("a", "b", "c")
        for t in ("zero_shot", "few_shot", "step_by_step")
    ]
    meta = {
        "complete": True,
        "expected_rows": 90,
        "answered_rows": 90,
        "dataset_sha256": cur["sha256"]["test_inputs.jsonl"],
        "gold_sha256": cur["gold_sha256"],
        "prompt_version": PROMPT_VERSION,
        "techniques_status": "PROVISIONAL",
        "run_stats": {},
        "budget": {"spent_eur": 0.03, "cap_eur": 5.0},
    }
    d = {
        "is_mock": False,
        "meta": {**meta, **over.pop("meta", {})},
        "cells": cells,
        **over,
    }
    f = tmp_path / "metrics.json"
    f.write_text(json.dumps(d))
    analysis = {
        "is_mock": False,
        "note": "Descriptive only.",
        "by_model": {
            m: {
                "mean_f1": 0.85,
                "mean_precision": 0.9,
                "mean_recall": 0.8,
                "mean_invalid_output_rate": 0.0,
                "mean_rdf_conforms_rate": 1.0,
                "top_errors": {"missing_field": 2},
            }
            for m in ("a", "b", "c")
        },
        "by_technique": {
            t_: {
                "mean_f1": 0.85,
                "mean_precision": 0.9,
                "mean_recall": 0.8,
                "mean_invalid_output_rate": 0.0,
                "mean_rdf_conforms_rate": 1.0,
                "top_errors": {},
            }
            for t_ in ("zero_shot", "few_shot", "step_by_step")
        },
        "cells": {
            "a | zero_shot": {
                "n_records": 10,
                "exact_records": 8,
                "records_with_errors": 2,
                "examples": [
                    {
                        "record": "r1",
                        "status": "ok",
                        "diffs": [
                            {
                                "field": "venue",
                                "expected": None,
                                "predicted": "Via X",
                                "error": "hallucinated_value",
                            }
                        ],
                    }
                ],
            }
        },
        "validated_triples": {"total": 12, "per_cell": {}, "is_mock": False},
    }
    (tmp_path / "analysis.json").write_text(json.dumps(analysis))
    return f


def test_publish_gate_accepts_complete_real_and_rejects_bad(tmp_path):
    from evaluation.publish import PublishRefused, publish

    res = tmp_path / "results"
    assert publish(synthetic_real_metrics(tmp_path), res).exists()
    for bad in (
        {"is_mock": True},
        {"meta": {"complete": False}},
        {"meta": {"dataset_sha256": "x"}},
        {"meta": {"gold_sha256": "x"}},
        {"meta": {"prompt_version": "old"}},
    ):
        with pytest.raises(PublishRefused):
            publish(synthetic_real_metrics(tmp_path, **bad), tmp_path / "r2")


def test_site_report_slides_ingest_published_results(tmp_path, monkeypatch):
    import importlib.util

    from evaluation.publish import publish

    publish(
        synthetic_real_metrics(tmp_path), ROOT / "results"
    )  # real location the builders read
    try:

        def load(rel, name):
            spec = importlib.util.spec_from_file_location(name, ROOT / rel)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            return m

        site = load("site/build.py", "sb")
        html_ = site.body_results()
        assert (
            "0.850" in html_
            and "PLACEHOLDER" not in html_
            and "Budget spent" in html_
            and "PROVISIONAL" in html_
        )
        rep = load("reports/build_report.py", "rb")
        assert (
            "0.850" in rep.results_section() and "Budget spent" in rep.results_section()
        )
        assert (
            "Example errors" in html_
            and "hallucinated_value" in html_
            and "Differences in behaviour" in html_
        )  # analysis reaches the site
        assert (
            "hallucinated_value" in rep.analysis_section()
            and "Validated triples" in rep.analysis_section()
        )  # and the report
        sl = load("slides/build_slides.py", "sl")
        monkeypatch.setattr(sl, "OUT", tmp_path)
        from pptx import Presentation

        prs = Presentation(sl.build())
        res_slide = list(prs.slides)[4]
        tables = [s for s in res_slide.shapes if s.has_table]
        assert (
            tables
            and tables[0].table.cell(1, 4).text == "0.85"
            and "PLACEHOLDER"
            not in " ".join(
                s.text_frame.text for s in res_slide.shapes if s.has_text_frame
            )
        )
    finally:
        import shutil

        shutil.rmtree(
            ROOT / "results", ignore_errors=True
        )  # never leave synthetic data behind


GOOD = json.dumps(
    {
        "events": [
            {
                k: None
                for k in (
                    "show_name",
                    "brand",
                    "event_type",
                    "date_time",
                    "venue",
                    "evidence_quote",
                )
            }
        ]
    }
)
FAKE_RESPONSES = {
    "openai": {
        "model": "gpt-5.4-mini-2026-03-17",
        "choices": [{"message": {"content": GOOD}}],
        "usage": {"prompt_tokens": 300, "completion_tokens": 60},
    },
    "gemini": {
        "modelVersion": "gemini-3.5-flash-lite",
        "candidates": [{"content": {"parts": [{"text": GOOD}]}}],
        "usageMetadata": {
            "promptTokenCount": 300,
            "candidatesTokenCount": 40,
            "thoughtsTokenCount": 20,
        },
    },
    "mistral": {
        "model": "mistral-small-2603",
        "choices": [{"message": {"content": GOOD}}],
        "usage": {"prompt_tokens": 300, "completion_tokens": 60},
    },
}


@pytest.mark.parametrize("provider", ["openai", "gemini", "mistral"])
def test_smoke_one_call_per_provider_records_requested_and_served_model(
    provider, monkeypatch, tmp_path
):
    from experiments import smoke

    monkeypatch.setenv("FASHIONGRAPH_APPROVED_SPEND", "1")
    for k in ("OPENAI_API_KEY", "GEMINI_API_KEY", "MISTRAL_API_KEY"):
        monkeypatch.setenv(k, "k")
    n = {"calls": 0}

    def fake_post(self, u, h, p):
        n["calls"] += 1
        return FAKE_RESPONSES[provider]

    monkeypatch.setattr(adapters.Adapter, "_post", fake_post)
    r = smoke.smoke(provider, str(ROOT / "models.json"), tmp_path)
    ids = {
        "openai": "gpt-5.4-mini-2026-03-17",
        "gemini": "gemini-3.5-flash-lite",
        "mistral": "mistral-small-2603",
    }
    assert n["calls"] == 1 and r["ok"] and r["json_valid"] and r["usage_present"]
    assert r["requested_model"] == ids[provider] and r["served_model"] == ids[provider]
    assert (
        0 < r["budget"]["spent_eur"] < 0.01
    )  # one call costs a fraction of a cent, far below the EUR 5 cap
    assert (tmp_path / f"smoke_{provider}.json").exists()


@pytest.mark.parametrize("provider", ["openai", "gemini", "mistral"])
def test_smoke_aborts_on_wrong_served_model_and_is_charged(
    provider, monkeypatch, tmp_path
):
    from experiments import smoke

    monkeypatch.setenv("FASHIONGRAPH_APPROVED_SPEND", "1")
    for k in ("OPENAI_API_KEY", "GEMINI_API_KEY", "MISTRAL_API_KEY"):
        monkeypatch.setenv(k, "k")
    bad = json.loads(json.dumps(FAKE_RESPONSES[provider]))
    bad["modelVersion" if provider == "gemini" else "model"] = "some-other-model"
    monkeypatch.setattr(adapters.Adapter, "_post", lambda self, u, h, p: bad)
    with pytest.raises(ModelMismatch):
        smoke.smoke(provider, str(ROOT / "models.json"), tmp_path)
    ledger = [
        json.loads(x) for x in (tmp_path / "ledger.jsonl").read_text().splitlines()
    ]
    assert [x["type"] for x in ledger] == [
        "reserve",
        "settle",
    ]  # the billed-but-rejected call is still counted


def test_run_rows_record_requested_and_served_model(tmp_path, monkeypatch):
    for k in ("OPENAI_API_KEY",):
        monkeypatch.setenv(k, "k")
    monkeypatch.setenv("FASHIONGRAPH_APPROVED_SPEND", "1")
    monkeypatch.setattr(
        adapters.Adapter, "_post", lambda self, u, h, p: FAKE_RESPONSES["openai"]
    )
    spec = ModelSpec(
        "openai", "gpt-5.4-mini-2026-03-17", "gpt-5.4-mini-2026-03-17", 400
    )
    cfg = ExperimentConfig(models=(spec,), techniques=("zero_shot",))
    prices = {"gpt-5.4-mini-2026-03-17": Price(0.75, 4.5)}
    b = Budget(
        BudgetConfig(5.0, 1.0968),
        prices,
        {"gpt-5.4-mini-2026-03-17": 400},
        tmp_path / "l.jsonl",
    )
    runner.run(cfg, [{"id": "r", "text": "x"}], tmp_path / "o.jsonl", budget=b)
    row = json.loads((tmp_path / "o.jsonl").read_text().splitlines()[0])
    assert row["requested_model"] == row[
        "served_model"
    ] == "gpt-5.4-mini-2026-03-17" and row["status"] in ("ok", "invalid")


def test_env_template_is_empty_and_real_env_is_ignored():
    ex = (ROOT / ".env.example").read_text()
    assert all(
        line.split("=", 1)[1].strip() == ""
        for line in ex.splitlines()
        if "=" in line and not line.startswith("#")
    )
    gi = (ROOT / ".gitignore").read_text().splitlines()
    assert ".env" in gi and "!.env.example" in gi and "models.json" not in gi
    mk = (ROOT / "Makefile").read_text()
    assert all(t in mk for t in ("smoke-all:", "run-real:", "publish-results:"))
