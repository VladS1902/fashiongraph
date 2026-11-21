import dataclasses
import json

import pytest

from experiments import adapters, runner
from experiments.config import ExperimentConfig, ModelSpec, RetryPolicy
from experiments.prompts import render
from experiments.schema import ValidationError, parse_and_validate

GOOD = {
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
MOCK_CFG = ExperimentConfig(models=(ModelSpec("mock", "mock-1"),), cost_ceiling_usd=1.0)
RECS = [{"id": "r1", "text": "abc"}, {"id": "r2", "text": "def"}]


def test_config_immutable_and_provisional():
    with pytest.raises(dataclasses.FrozenInstanceError):
        MOCK_CFG.timeout_s = 1  # type: ignore
    assert MOCK_CFG.techniques_status == "PROVISIONAL"
    with pytest.raises(ValueError):
        ExperimentConfig(models=(), techniques=("bogus",))


def test_backoff_bounded():
    p = RetryPolicy(base_delay_s=1, max_delay_s=5)
    assert [p.delay(i) for i in (1, 2, 3, 4, 5)] == [1, 2, 4, 5, 5]


def test_schema():
    assert parse_and_validate("```json\n" + json.dumps(GOOD) + "\n```") == GOOD
    for bad in [
        "not json",
        "[]",
        '{"events":[{"brand":"x"}]}',
        json.dumps({"events": [{**GOOD["events"][0], "venue": 3}]}),
        json.dumps({"events": [], "extra": 1}),
    ]:
        with pytest.raises(ValidationError):
            parse_and_validate(bad)


def test_prompts_render_all_techniques():
    for t in MOCK_CFG.techniques:
        s, u = render(t, "HELLO")
        assert "HELLO" in u and "{text}" not in u and "JSON" in s
    assert (
        "training split" in render("few_shot", "x")[1]
        and "{examples}" not in render("few_shot", "x")[1]
    )


def test_real_providers_refused_without_approval(monkeypatch):
    monkeypatch.delenv(adapters.APPROVAL_ENV, raising=False)
    for p in ("openai", "gemini", "mistral"):
        with pytest.raises(adapters.SpendNotApproved):
            adapters.make_adapter(p, "m")


def test_runner_refuses_real(tmp_path, monkeypatch):
    monkeypatch.delenv(adapters.APPROVAL_ENV, raising=False)
    cfg = ExperimentConfig(models=(ModelSpec("openai", "m"),))
    with pytest.raises(adapters.SpendNotApproved):
        runner.run(cfg, RECS, tmp_path / "o.jsonl")


def test_key_from_env_only(monkeypatch):
    ad = adapters.OpenAIAdapter("m", env={adapters.APPROVAL_ENV: "1"})
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        ad.complete("s", "u")


def test_run_resume_and_mock_flag(tmp_path):
    out = tmp_path / "o.jsonl"
    s1 = runner.run(MOCK_CFG, RECS, out, max_calls=4)
    assert s1["new"] == 4 and s1["halted"] == "max_calls"
    s2 = runner.run(MOCK_CFG, RECS, out)
    assert s2["cached"] == 4 and s2["new"] == 2 and s2["halted"] is None
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert len(rows) == 6 and all(r["is_mock"] and r["status"] == "ok" for r in rows)
    assert all(
        r["raw_output"] and r["started_at"] and "input_tokens" in r for r in rows
    )
    assert len({r["request_hash"] for r in rows}) == 6


class Flaky(adapters.Adapter):
    provider = "mock"
    is_mock = True

    def __init__(self, fails):
        super().__init__("f")
        self.fails = fails

    def complete(self, system, user):
        if self.fails:
            self.fails -= 1
            raise adapters.TransientError("429")
        return adapters.Completion(json.dumps(GOOD), 1, 1)


def test_retry_then_success_and_exhaustion(tmp_path):
    delays = []
    cfg = ExperimentConfig(
        models=(ModelSpec("mock", "f"),),
        techniques=("zero_shot",),
        retry=RetryPolicy(max_attempts=3, base_delay_s=1),
    )
    st = runner.run(
        cfg,
        RECS[:1],
        tmp_path / "a.jsonl",
        {("mock", "f"): Flaky(2)},
        sleep=delays.append,
    )
    assert st["new"] == 1 and delays == [1, 2]
    st = runner.run(
        cfg,
        RECS[:1],
        tmp_path / "b.jsonl",
        {("mock", "f"): Flaky(9)},
        sleep=lambda d: None,
    )
    row = json.loads((tmp_path / "b.jsonl").read_text())
    assert st["failed"] == 1 and row["status"] == "error"


def test_invalid_output_logged_not_trusted(tmp_path):
    class Bad(Flaky):
        def complete(self, s, u):
            return adapters.Completion("Brand X at Paris", 1, 1)

    cfg = ExperimentConfig(models=(ModelSpec("mock", "f"),), techniques=("zero_shot",))
    runner.run(cfg, RECS[:1], tmp_path / "c.jsonl", {("mock", "f"): Bad(0)})
    row = json.loads((tmp_path / "c.jsonl").read_text())
    assert row["status"] == "invalid" and "parsed" not in row and row["raw_output"]


def test_cost_ceiling(tmp_path):
    cfg = ExperimentConfig(
        models=(ModelSpec("mock", "mock-1"),), cost_ceiling_usd=0.0005
    )
    st = runner.run(cfg, RECS, tmp_path / "d.jsonl", cost_per_1k={"mock-1": (0.0, 1.0)})
    assert st["halted"] == "cost_ceiling" and st["new"] >= 1
