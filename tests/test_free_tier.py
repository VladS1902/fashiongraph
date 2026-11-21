"""Zero-cost configuration: quota guard, Groq adapter, free-plan detection, models.free.json (no network, no calls)."""

import json
from pathlib import Path

import pytest

from experiments import adapters, models_file, runner
from experiments.adapters import (
    GroqAdapter,
    ModelMismatch,
    PaidTierDetected,
    TransientError,
)
from experiments.config import ExperimentConfig, ModelSpec, RetryPolicy
from experiments.ratelimit import FreeTierGuard, Limits, QuotaExhausted

ROOT = Path(__file__).resolve().parent.parent
ENV = {"FASHIONGRAPH_APPROVED_SPEND": "1", "GROQ_API_KEY": "k", "GEMINI_API_KEY": "k"}
FREE_HEADERS = {
    "x-ratelimit-limit-tokens": "8000",
    "x-ratelimit-limit-requests": "1000",
    "x-ratelimit-remaining-tokens": "7000",
}


class Clock:
    def __init__(self):
        self.t, self.slept = 1_000_000.0, []

    def now(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


def guard(tmp_path, lim, cap=100, clock=None):
    c = clock or Clock()
    return FreeTierGuard(
        {"m": lim}, {"m": cap}, tmp_path / "led.jsonl", clock=c.now, sleep=c.sleep
    ), c


# ---- quota guard ---------------------------------------------------------------
def test_rpm_pacing_sleeps_instead_of_failing(tmp_path):
    g, c = guard(tmp_path, Limits(rpm=2, rpd=100, tpm=10**6, tpd=10**7))
    for _ in range(3):
        g.settle(g.reserve("m", "s", "u"), 10, 5)
    assert (
        c.slept and sum(c.slept) >= 59
    )  # the 3rd call had to wait for the 60 s window


def test_tpm_counts_reserved_tokens_conservatively(tmp_path):
    g, c = guard(tmp_path, Limits(rpm=100, rpd=100, tpm=300, tpd=10**6), cap=100)
    est = g.estimate_tokens("m", "s" * 30, "u" * 30)
    assert (
        est > 100 and 2 * est <= 300 < 3 * est or est * 2 > 300
    )  # sanity for the numbers below
    for _ in range(4):
        g.settle(
            g.reserve("m", "s" * 30, "u" * 30), 1, 1
        )  # tiny ACTUAL usage must not loosen the pacing
    assert c.slept, "reserved (not actual) tokens must drive the pacing"


def test_daily_quota_halts_safely_and_persists(tmp_path):
    g, c = guard(tmp_path, Limits(rpm=100, rpd=3, tpm=10**6, tpd=10**7))
    for _ in range(3):
        g.settle(g.reserve("m", "s", "u"), 1, 1)
    with pytest.raises(QuotaExhausted):
        g.reserve("m", "s", "u")
    g2 = FreeTierGuard(
        {"m": Limits(rpm=100, rpd=3, tpm=10**6, tpd=10**7)},
        {"m": 100},
        tmp_path / "led.jsonl",
        clock=c.now,
        sleep=c.sleep,
    )
    with pytest.raises(QuotaExhausted):  # a restart cannot reset the daily count
        g2.reserve("m", "s", "u")
    c.t += 86401  # after 24 h the window has rolled over
    g2.reserve("m", "s", "u")


def test_tokens_per_day_and_oversized_call_refused(tmp_path):
    g, _ = guard(tmp_path, Limits(rpm=100, rpd=100, tpm=10**6, tpd=500), cap=100)
    g.settle(g.reserve("m", "s", "u"), 200, 200)
    with pytest.raises(QuotaExhausted, match="tokens-per-day"):
        g.reserve("m", "s", "u")
    g2, _ = guard(tmp_path / "x", Limits(rpm=100, rpd=100, tpm=50, tpd=10**6), cap=100)
    with pytest.raises(QuotaExhausted, match="tokens-per-minute"):
        g2.reserve("m", "s", "u")


def test_failed_attempts_and_unknown_model_fail_closed(tmp_path):
    g, _ = guard(tmp_path, Limits(rpm=100, rpd=2, tpm=10**6, tpd=10**7))
    g.settle(
        g.reserve("m", "s", "u"), None, None
    )  # failed attempt still counts as a request
    g.reserve("m", "s", "u")  # never settled: counts too
    with pytest.raises(QuotaExhausted):
        g.reserve("m", "s", "u")
    with pytest.raises(KeyError):
        g.reserve("unknown", "s", "u")
    assert g.summary()["mode"] == "free" and g.summary()["spent_eur"] == 0.0


# ---- Groq adapter -------------------------------------------------------------------
def groq(model="openai/gpt-oss-120b", params=None, guard_=(8000, 1000), served=None):
    return GroqAdapter(
        model,
        env=ENV,
        served_model=served or model,
        max_output_tokens=400,
        params=params,
        plan_guard=guard_,
    )


def fake_post(monkeypatch, resp, headers):
    seen = {}

    def _post(self, url, hdrs, payload):
        seen.update(url=url, payload=payload)
        self.last_headers = dict(headers)
        return resp

    monkeypatch.setattr(adapters.Adapter, "_post", _post)
    return seen


def groq_resp(model):
    return {
        "model": model,
        "choices": [{"message": {"content": "{}"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3},
    }


def test_groq_payloads_follow_each_models_documented_parameters(monkeypatch):
    seen = fake_post(monkeypatch, groq_resp("openai/gpt-oss-120b"), FREE_HEADERS)
    c = groq(params={"reasoning_effort": "low", "include_reasoning": False}).complete(
        "s", "u"
    )
    p = seen["payload"]
    assert seen["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert (
        p["reasoning_effort"] == "low"
        and p["include_reasoning"] is False
        and p["temperature"] == 0
        and p["max_completion_tokens"] == 400
    )
    assert (
        p["response_format"]["json_schema"]["strict"] is True
        and "reasoning_format" not in p
    )  # not supported for gpt-oss
    assert (
        c.served_model == "openai/gpt-oss-120b"
        and c.meta["x-ratelimit-limit-tokens"] == "8000"
        and (c.input_tokens, c.output_tokens) == (5, 3)
    )
    seen = fake_post(monkeypatch, groq_resp("qwen/qwen3.8-27b"), FREE_HEADERS)
    groq("qwen/qwen3.8-27b", {"reasoning_effort": "none"}).complete("s", "u")
    assert (
        seen["payload"]["reasoning_effort"] == "none"
        and "include_reasoning" not in seen["payload"]
    )


def test_paid_plan_detected_from_headers_and_missing_headers_fail_closed(monkeypatch):
    dev = {"x-ratelimit-limit-tokens": "250000", "x-ratelimit-limit-requests": "500000"}
    fake_post(monkeypatch, groq_resp("openai/gpt-oss-120b"), dev)
    with pytest.raises(PaidTierDetected, match="paid plan suspected"):
        groq().complete("s", "u")
    fake_post(monkeypatch, groq_resp("openai/gpt-oss-120b"), {})
    with pytest.raises(PaidTierDetected, match="cannot confirm"):
        groq().complete("s", "u")


def test_groq_served_model_guard(monkeypatch):
    fake_post(monkeypatch, groq_resp("other-model"), FREE_HEADERS)
    with pytest.raises(ModelMismatch):
        groq().complete("s", "u")


def test_retry_after_is_honoured(tmp_path):
    class Flaky(adapters.Adapter):
        provider, is_mock = "groq", False
        n = 0

        def complete(self, system, user):
            Flaky.n += 1
            if Flaky.n == 1:
                raise TransientError("HTTP 429", retry_after=42.0)
            return adapters.Completion('{"events": []}', 1, 1, {}, "m")

    slept = []
    cfg = ExperimentConfig(
        models=(ModelSpec("groq", "m"),),
        techniques=("zero_shot",),
        retry=RetryPolicy(max_attempts=3, base_delay_s=1),
    )
    _, attempts = runner.call_with_retry(Flaky("m"), "s", "u", cfg, sleep=slept.append)
    assert attempts == 2 and slept == [42.0]


# ---- runner integration -----------------------------------------------------------
def run_free(tmp_path, adapter, lim, n=6):
    c = Clock()
    g = FreeTierGuard(
        {"m": lim}, {"m": 100}, tmp_path / "led.jsonl", clock=c.now, sleep=c.sleep
    )
    cfg = ExperimentConfig(
        models=(ModelSpec("groq", "m", None, 100),), techniques=("zero_shot",)
    )
    recs = [{"id": f"r{i}", "text": f"t{i}" * 20} for i in range(n)]
    st = runner.run(
        cfg,
        recs,
        tmp_path / "o.jsonl",
        adapters={("groq", "m"): adapter},
        budget=g,
        sleep=c.sleep,
    )
    return st, c


class Ok(adapters.Adapter):
    provider, is_mock = "groq", False
    calls = 0

    def complete(self, system, user):
        Ok.calls += 1
        return adapters.Completion('{"events": []}', 10, 5, {}, "m")


def test_runner_paces_then_halts_on_daily_quota(tmp_path):
    Ok.calls = 0
    st, c = run_free(tmp_path, Ok("m"), Limits(rpm=2, rpd=4, tpm=10**6, tpd=10**7))
    assert (
        st["halted"] == "quota_deferred"
        and "m" in st["deferred"]
        and Ok.calls == 4
        and c.slept
    )  # paced, then stopped cleanly at the free daily cap
    rows = [json.loads(x) for x in (tmp_path / "o.jsonl").read_text().splitlines()]
    assert len(rows) == 4 and all(r["status"] in ("ok", "invalid") for r in rows)


def test_runner_stops_at_once_when_paid_plan_detected(tmp_path, monkeypatch):
    dev = {"x-ratelimit-limit-tokens": "250000", "x-ratelimit-limit-requests": "500000"}
    fake_post(monkeypatch, groq_resp("m"), dev)
    ad = GroqAdapter(
        "m", env=ENV, served_model="m", max_output_tokens=100, plan_guard=(8000, 1000)
    )
    st, _ = run_free(tmp_path, ad, Limits(rpm=30, rpd=1000, tpm=8000, tpd=200000))
    assert st["halted"] == "paid_tier_detected"
    rows = [json.loads(x) for x in (tmp_path / "o.jsonl").read_text().splitlines()]
    assert (
        len(rows) == 1 and rows[0]["status"] == "paid_tier_detected"
    )  # exactly one call, then nothing more


# ---- configuration -------------------------------------------------------------------
def test_free_config_valid_distinct_families_and_documented_limits():
    mf = models_file.load(ROOT / "models.free.json")
    assert mf.mode == "free"
    ids = {s.model_id for s in mf.specs}
    assert ids == {"gemini-3.5-flash-lite", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"}
    assert len({m.get("family") for m in mf.raw["models"]}) == 3
    for s in mf.specs:
        if s.provider == "groq":
            assert (
                s.plan_guard == (8000, 1000) and mf.limits[s.model_id].verified is True
            )
    assert (
        mf.limits["gemini-3.5-flash-lite"].verified is True
    )  # owner-confirmed from the AI Studio dashboard
    assert dict(
        next(s for s in mf.specs if s.model_id == "qwen/qwen3.8-27b").params
    ) == {"reasoning_effort": "none"}
    assert dict(
        next(s for s in mf.specs if s.model_id == "openai/gpt-oss-120b").params
    ) == {"reasoning_effort": "low", "include_reasoning": False}
    assert (
        models_file.load(ROOT / "models.json").mode == "paid"
    )  # the paid alternative is untouched


def test_free_config_fails_closed(tmp_path):
    d = json.loads((ROOT / "models.free.json").read_text())
    muts = [
        lambda x: x["models"][0].pop("limits"),
        lambda x: x["models"][1]["limits"].update(tpd=None),
        lambda x: x["models"][1].pop("plan_guard"),
        lambda x: x["models"][0].update(provider="openai"),
        lambda x: x["models"][2].update(
            family="openai-gpt-oss"
        ),  # two models of one family
        lambda x: x["models"][1]["limits"].pop("source"),
    ]
    for m in muts:
        dd = json.loads(json.dumps(d))
        m(dd)
        f = tmp_path / "m.json"
        f.write_text(json.dumps(dd))
        with pytest.raises((ValueError, KeyError)):
            models_file.load(f)


def test_free_runs_need_owner_confirmation(monkeypatch, tmp_path):
    from experiments import pipeline, smoke

    monkeypatch.setenv("FASHIONGRAPH_APPROVED_SPEND", "1")
    monkeypatch.delenv("FASHIONGRAPH_FREE_TIER_CONFIRMED", raising=False)
    with pytest.raises(models_file.FreeTierNotConfirmed):
        pipeline.run_real(str(ROOT / "models.free.json"), tmp_path)
    with pytest.raises(models_file.FreeTierNotConfirmed):
        smoke.smoke(
            "groq",
            str(ROOT / "models.free.json"),
            tmp_path,
            model_id="openai/gpt-oss-120b",
        )


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
FREE_FAKES = {
    "gemini-3.5-flash-lite": (
        "gemini",
        {
            "modelVersion": "gemini-3.5-flash-lite",
            "candidates": [{"content": {"parts": [{"text": GOOD}]}}],
            "usageMetadata": {"promptTokenCount": 300, "candidatesTokenCount": 40},
        },
    ),
    "openai/gpt-oss-120b": (
        "groq",
        groq_resp("openai/gpt-oss-120b")
        | {"choices": [{"message": {"content": GOOD}}]},
    ),
    "qwen/qwen3.8-27b": (
        "groq",
        groq_resp("qwen/qwen3.8-27b") | {"choices": [{"message": {"content": GOOD}}]},
    ),
}


@pytest.mark.parametrize("model_id", list(FREE_FAKES))
def test_three_free_smoke_tests_with_fake_providers(model_id, monkeypatch, tmp_path):
    from experiments import smoke

    provider, resp = FREE_FAKES[model_id]
    for k, v in {**ENV, "FASHIONGRAPH_FREE_TIER_CONFIRMED": "1"}.items():
        monkeypatch.setenv(k, v)
    n = {"calls": 0}

    def _post(self, url, hdrs, payload):
        n["calls"] += 1
        self.last_headers = dict(FREE_HEADERS)
        return resp

    monkeypatch.setattr(adapters.Adapter, "_post", _post)
    r = smoke.smoke(
        provider, str(ROOT / "models.free.json"), tmp_path, model_id=model_id
    )
    assert (
        n["calls"] == 1
        and r["ok"]
        and r["requested_model"] == r["served_model"] == model_id
    )
    assert r["budget"]["mode"] == "free" and r["budget"]["spent_eur"] == 0.0
    assert any(p.name.startswith("smoke_") for p in tmp_path.glob("smoke_*.json"))


def test_groq_smoke_needs_model_id_when_provider_has_two_models(monkeypatch, tmp_path):
    from experiments import smoke

    for k, v in {**ENV, "FASHIONGRAPH_FREE_TIER_CONFIRMED": "1"}.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(ValueError, match="--model-id"):
        smoke.smoke("groq", str(ROOT / "models.free.json"), tmp_path)


def test_free_plan_is_within_quotas_and_readiness_knows_free_mode(monkeypatch):
    from experiments import cost_estimate, readiness

    plan = cost_estimate.free_plan(ROOT / "models.free.json")
    assert plan["calls_total"] == 90 and all(
        r["rpd_use"] <= 1 and r["tpd_use"] <= 1 for r in plan["rows"]
    )
    assert all(
        r["max_reserved_per_call"] < r["limits"]["tpm"] for r in plan["rows"]
    )  # a single call always fits the minute window
    res = readiness.checks(
        str(ROOT / "models.free.json"), {"GROQ_API_KEY": "gsk-SECRET"}
    )
    by = {r["gate"]: r for r in res}
    assert (
        by["free quotas sufficient for 90 calls"]["pass"]
        and not by["free plan confirmed by owner"]["pass"]
    )
    assert (
        "API key present: groq" in by
        and "API key present: openai" not in by
        and "SECRET" not in json.dumps(res)
    )
    assert by["free limits documented for every model"][
        "pass"
    ]  # Gemini limits are now owner-confirmed


def test_free_run_results_say_nothing_was_billed(tmp_path, monkeypatch):
    import importlib.util

    (tmp_path / "results").mkdir()
    cell = {
        "n_records": 10,
        "is_mock": False,
        "model_id": "m",
        "technique": "t",
        "precision": 0.5,
        "recall": 0.5,
        "f1": 0.5,
        "invalid_output_rate": 0.0,
        "unsupported_assertion_rate": None,
        "rdf_conforms_rate": 1.0,
    }
    (tmp_path / "results" / "metrics.json").write_text(
        json.dumps(
            {
                "is_mock": False,
                "meta": {"budget": {"mode": "free", "spent_eur": 0.0, "cap_eur": 0.0}},
                "cells": [cell],
            }
        )
    )
    for rel, name in (("site/build.py", "sb"), ("reports/build_report.py", "rb")):
        spec = importlib.util.spec_from_file_location(name, ROOT / rel)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        monkeypatch.setattr(m, "ROOT", tmp_path)
        out = m.body_results() if name == "sb" else m.results_section()
        assert "nothing was billed" in out and "Budget spent" not in out


def test_readiness_reads_saved_smoke_results(tmp_path, monkeypatch):
    from experiments import readiness

    monkeypatch.setattr(readiness, "SMOKE_DIR", tmp_path)
    gate = "live smoke tests passed (requests, served model, JSON, usage)"
    f = str(ROOT / "models.free.json")
    assert not {r["gate"]: r for r in readiness.checks(f, {})}[gate]["pass"]
    for name, mid in (
        ("smoke_gemini.json", "gemini-3.5-flash-lite"),
        ("smoke_openai_gpt-oss-120b.json", "openai/gpt-oss-120b"),
        ("smoke_qwen_qwen3.8-27b.json", "qwen/qwen3.8-27b"),
    ):
        (tmp_path / name).write_text(
            json.dumps(
                {
                    "ok": True,
                    "model_id": mid,
                    "requested_model": mid,
                    "served_model": mid,
                }
            )
        )
    assert {r["gate"]: r for r in readiness.checks(f, {})}[gate]["pass"]
    (tmp_path / "smoke_qwen_qwen3.8-27b.json").write_text(
        json.dumps(
            {
                "ok": True,
                "model_id": "qwen/qwen3.8-27b",
                "requested_model": "qwen/qwen3.8-27b",
                "served_model": "other",
            }
        )
    )
    assert not {r["gate"]: r for r in readiness.checks(f, {})}[gate][
        "pass"
    ]  # a substituted model never counts as passed


def test_one_models_daily_quota_does_not_block_the_other_models(tmp_path):
    class Fast(adapters.Adapter):
        is_mock = False
        calls = 0

        def complete(self, system, user):
            Fast.calls += 1
            return adapters.Completion('{"events": []}', 10, 5, {}, self.model_id)

    class A(Fast):
        provider = "gemini"

    class B(Fast):
        provider = "groq"

    c = Clock()
    lims = {
        "a": Limits(rpm=100, rpd=2, tpm=10**6, tpd=10**7),
        "b": Limits(rpm=100, rpd=100, tpm=10**6, tpd=10**7),
    }
    g = FreeTierGuard(
        lims, {"a": 100, "b": 100}, tmp_path / "led.jsonl", clock=c.now, sleep=c.sleep
    )
    cfg = ExperimentConfig(
        models=(ModelSpec("gemini", "a", None, 100), ModelSpec("groq", "b", None, 100)),
        techniques=("zero_shot",),
    )
    recs = [{"id": f"r{i}", "text": f"t{i}" * 20} for i in range(5)]
    ads = {("gemini", "a"): A("a"), ("groq", "b"): B("b")}
    st = runner.run(
        cfg, recs, tmp_path / "o.jsonl", adapters=ads, budget=g, sleep=c.sleep
    )
    rows = [json.loads(x) for x in (tmp_path / "o.jsonl").read_text().splitlines()]
    done = {
        m: sum(
            1 for r in rows if r["model_id"] == m and r["status"] in ("ok", "invalid")
        )
        for m in ("a", "b")
    }
    assert (
        st["halted"] == "quota_deferred"
        and set(st["deferred"]) == {"a"}
        and st["deferred_cells"] == 3
    )
    assert done == {"a": 2, "b": 5}  # b was NOT blocked by a's exhausted daily quota
    c.t += (
        86401  # next day: resuming finishes only the deferred cells, repeating nothing
    )
    lims2 = {
        **lims,
        "a": Limits(rpm=100, rpd=100, tpm=10**6, tpd=10**7),
    }  # larger real limits confirmed by the owner
    g2 = FreeTierGuard(
        lims2, {"a": 100, "b": 100}, tmp_path / "led.jsonl", clock=c.now, sleep=c.sleep
    )
    Fast.calls = 0
    st2 = runner.run(
        cfg, recs, tmp_path / "o.jsonl", adapters=ads, budget=g2, sleep=c.sleep
    )
    assert Fast.calls == 3 and st2["halted"] is None and st2["cached"] == 7


def test_retry_policy_is_configured_per_models_file(tmp_path):
    free = models_file.load(ROOT / "models.free.json")
    assert (
        free.retry.max_attempts,
        free.retry.base_delay_s,
        free.retry.max_delay_s,
    ) == (4, 10.0, 60.0)
    assert [free.retry.delay(i) for i in (1, 2, 3, 4)] == [
        10.0,
        20.0,
        40.0,
        60.0,
    ]  # gentler on an overloaded provider
    assert (
        models_file.load(ROOT / "models.json").retry.base_delay_s == 1.0
    )  # the paid file keeps the default
    d = json.loads((ROOT / "models.free.json").read_text())
    d["retry"] = {"max_attempts": 99}
    f = tmp_path / "m.json"
    f.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="retry"):
        models_file.load(f)


class FakeResp:
    def __init__(self, status, headers=None, body=None):
        self.status_code, self.headers, self._body, self.text = (
            status,
            headers or {},
            body,
            "x",
        )

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


@pytest.mark.parametrize(
    "resp,expected",
    [
        (FakeResp(429, {"retry-after": "7"}), 7.0),
        (
            FakeResp(
                429,
                {},
                {
                    "error": {
                        "details": [
                            {
                                "@type": "type.googleapis.com/google.rpc.RetryInfo",
                                "retryDelay": "17s",
                            }
                        ]
                    }
                },
            ),
            17.0,
        ),
        (FakeResp(503, {}, {"error": {"details": [{"retryDelay": "2.5s"}]}}), 2.5),
        (FakeResp(503, {}, {"error": {"message": "overloaded"}}), None),
        (FakeResp(503, {}, None), None),
    ],
)
def test_retry_guidance_from_header_or_google_body(resp, expected):
    assert adapters._retry_hint(resp) == expected


def test_post_raises_transient_with_google_retry_delay(monkeypatch):
    resp = FakeResp(503, {}, {"error": {"details": [{"retryDelay": "4s"}]}})
    monkeypatch.setattr(adapters.requests, "post", lambda *a, **k: resp)
    with pytest.raises(TransientError) as e:
        adapters.GeminiAdapter("m", env=ENV)._post("u", {}, {})
    assert e.value.retry_after == 4.0


def test_gemini_limits_confirmed_and_paced_below_the_ceiling():
    mf = models_file.load(ROOT / "models.free.json")
    lim = mf.limits["gemini-3.5-flash-lite"]
    raw = next(m for m in mf.raw["models"] if m["model_id"] == "gemini-3.5-flash-lite")[
        "limits"
    ]
    assert (raw["rpm"], raw["rpd"], raw["tpm"]) == (15, 500, 250000) and lim.verified
    assert (
        lim.rpm == 9 < raw["rpm"] and lim.rpd == 500 and lim.tpm == 250000
    )  # guard paces at 9/min, under the confirmed 15
    assert "Owner-confirmed" in lim.source


def test_pace_rpm_cannot_exceed_the_limit(tmp_path):
    d = json.loads((ROOT / "models.free.json").read_text())
    next(m for m in d["models"] if m["provider"] == "gemini")["limits"]["pace_rpm"] = 20
    f = tmp_path / "m.json"
    f.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="pace_rpm"):
        models_file.load(f)


GEN_FAIL_BODY = '{"error":{"message":"Failed to generate JSON. Please adjust your prompt. See \'failed_generation\' for more details.","type":"invalid_request_error","code":"json_validate_failed","failed_generation":"{\\"events\\": [ {\\"show_na"}}'


def test_http_400_generation_failure_is_a_distinct_final_outcome(monkeypatch):
    r400 = FakeResp(400, {}, None)
    r400.text = GEN_FAIL_BODY
    monkeypatch.setattr(adapters.requests, "post", lambda *a, **k: r400)
    with pytest.raises(adapters.GenerationFailed, match="failed_generation"):
        GroqAdapter("m", env=ENV)._post("u", {}, {})
    other = FakeResp(400, {}, None)
    other.text = '{"error":{"message":"model not found"}}'
    monkeypatch.setattr(adapters.requests, "post", lambda *a, **k: other)
    with pytest.raises(RuntimeError) as e:  # any other 400 stays an ordinary error
        GroqAdapter("m", env=ENV)._post("u", {}, {})
    assert not isinstance(e.value, adapters.GenerationFailed)


def test_runner_scores_generation_failure_as_invalid_once_and_never_recalls_it(
    tmp_path,
):
    class Fails(adapters.Adapter):
        provider, is_mock = "groq", False
        calls = 0

        def complete(self, system, user):
            Fails.calls += 1
            raise adapters.GenerationFailed(
                "HTTP 400: Failed to generate JSON ... failed_generation"
            )

    c = Clock()
    lim = Limits(rpm=100, rpd=100, tpm=10**6, tpd=10**7)
    cfg = ExperimentConfig(
        models=(ModelSpec("groq", "m", None, 100),), techniques=("zero_shot",)
    )
    recs = [{"id": f"r{i}", "text": f"t{i}" * 20} for i in range(3)]

    def go():
        g = FreeTierGuard(
            {"m": lim}, {"m": 100}, tmp_path / "led.jsonl", clock=c.now, sleep=c.sleep
        )
        return runner.run(
            cfg,
            recs,
            tmp_path / "o.jsonl",
            adapters={("groq", "m"): Fails("m")},
            budget=g,
            sleep=c.sleep,
        )

    st = go()
    rows = [json.loads(x) for x in (tmp_path / "o.jsonl").read_text().splitlines()]
    assert (
        Fails.calls == 3 and st["failed"] == 3 and st["halted"] is None
    )  # one attempt per cell, no retries
    assert all(
        r["status"] == "invalid" and r["error_class"] == "provider_generation_failure"
        for r in rows
    )
    st2 = go()
    assert (
        Fails.calls == 3 and st2["cached"] == 3
    )  # a resume does not call them again (that would be cherry-picking)


def test_legacy_error_rows_are_relabelled_and_scored_as_invalid(tmp_path):
    from evaluation.score import aggregate

    legacy = {
        "request_hash": "h",
        "record_id": "r",
        "model_id": "m",
        "technique": "zero_shot",
        "status": "error",
        "error": 'RuntimeError: HTTP 400: {"error":{"message":"Failed to generate JSON. Please',
        "is_mock": False,
    }
    infra = {**legacy, "request_hash": "h2", "error": "TransientError: HTTP 503"}
    assert (
        runner.normalise_row(legacy)["status"] == "invalid"
        and runner.normalise_row(infra)["status"] == "error"
    )
    f = tmp_path / "o.jsonl"
    f.write_text(json.dumps(legacy) + "\n" + json.dumps(infra) + "\n")
    assert set(runner.load_done(f)) == {
        "h"
    }  # the generation failure is final; the outage is retried
    from experiments import pipeline

    rows = pipeline.load_rows(f)
    assert {r["request_hash"]: r["status"] for r in rows} == {
        "h": "invalid",
        "h2": "error",
    }
    exp = {
        "show_name": "A",
        "brand": "A",
        "event_type": "fashion show",
        "date_time": "2026-09-22T14:00",
        "venue": None,
    }
    cell = aggregate(
        [next(r for r in rows if r["request_hash"] == "h")], {"r": "text"}, {"r": exp}
    )[0]
    assert (
        cell["errors"].get("invalid_output") == 1
        and cell["invalid_output_rate"] == 1.0
        and cell["recall"] == 0.0
    )
