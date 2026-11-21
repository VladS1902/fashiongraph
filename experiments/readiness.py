"""Pre-flight readiness checks for the REAL three-model experiment. Makes NO network or API calls and prints no secrets.
  python -m experiments.readiness [--models models.json]
Exit code 0 only if every gate passes. Gates marked HUMAN need an owner decision, not code."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

from experiments import cost_estimate, models_file
from experiments import inputs as inp
from experiments.adapters import APPROVAL_ENV, KEY_ENVS
from experiments.config import PROMPT_VERSION, TECHNIQUES_PROVISIONAL
from experiments.prompts import render

ROOT = Path(__file__).resolve().parent.parent
PROMPT_FILES = ("system", "zero_shot", "few_shot", "step_by_step")


FREE_CONFIRM_ENV = "FASHIONGRAPH_FREE_TIER_CONFIRMED"
SMOKE_DIR = ROOT / "outputs" / "smoke"


def prompt_checksum() -> str:
    h = hashlib.sha256()
    for n in PROMPT_FILES:
        h.update((ROOT / "experiments/prompts" / f"{n}.txt").read_bytes())
    h.update((ROOT / "data/experiment/fewshot_train.jsonl").read_bytes())
    return h.hexdigest()


def checks(models_json: str | None = None, env=None) -> list[dict]:
    env = os.environ if env is None else env
    out = []

    def add(name, ok, detail, kind="code"):
        out.append({"gate": name, "pass": bool(ok), "kind": kind, "detail": detail})

    gold_m = json.loads((ROOT / "data/gold/MANIFEST.json").read_text())
    gold = [
        json.loads(x)
        for x in (ROOT / "data/gold/gold_pilot.jsonl").read_text().splitlines()
    ]
    add(
        "gold frozen + checksum",
        gold_m["sha256"]
        == hashlib.sha256(
            (ROOT / "data/gold/gold_pilot.jsonl").read_bytes()
        ).hexdigest(),
        f"v{gold_m['version']} {gold_m['sha256'][:12]}",
    )
    add(
        "gold human-verified",
        all(g["human_verified"] for g in gold),
        f"{sum(g['human_verified'] for g in gold)}/{len(gold)} records (owner approval recorded)",
        "human",
    )
    im = json.loads((ROOT / "data/experiment/MANIFEST.json").read_text())
    add(
        "inputs match gold + manifest",
        im == inp.build(write=False)["manifest"]
        and im["gold_sha256"] == gold_m["sha256"],
        f"inputs v{im['version']}, n_test={im['n_test']}, n_train={im['n_train_examples']}",
    )
    built = inp.build(write=False)
    test_ids = {t["id"].removeprefix("mfw-ss27-") for t in built["test"]}
    add(
        "no few-shot leakage",
        not ({t["id"].removeprefix("train-") for t in built["train"]} & test_ids),
        "train ids disjoint from test ids",
    )
    try:
        n_chars = sum(
            len(s) + len(u)
            for t in TECHNIQUES_PROVISIONAL
            for r in built["test"]
            for s, u in [render(t, r["text"])]
        )
        add(
            "prompts render for all 3x10 inputs",
            True,
            f"{n_chars} prompt chars total (~{n_chars // 4} input tokens per model); 30 calls/model, 90 total",
        )
    except Exception as e:  # noqa: BLE001
        add("prompts render for all 3x10 inputs", False, repr(e))
    add(
        "prompt/example checksum",
        True,
        f"{PROMPT_VERSION} sha256 {prompt_checksum()[:16]} (record in run metadata; freeze before first run)",
    )
    add(
        "techniques confirmed by course",
        False,
        f"{TECHNIQUES_PROVISIONAL} are PROVISIONAL; names/mandatory set not in the PDF",
        "human",
    )
    team_file = ROOT / "team.json"
    team = json.loads(team_file.read_text()) if team_file.exists() else None
    add(
        "group size known (2 vs 3 LLMs required)",
        bool(team and team.get("group_size")),
        f"group size {team['group_size']}: {', '.join(m['name'] for m in team['members'])} (team.json)"
        if team
        else "team.json missing",
        "human",
    )
    if team:
        need = 2 if team["group_size"] <= 4 else 3
        add(
            "LLM count meets the course rule (PDF p.4 #3)",
            3 >= need,
            f"group of {team['group_size']} needs at least {need} LLMs; this project compares 3",
        )
    mpath = Path(models_json) if models_json else ROOT / "models.json"
    mf = None
    try:
        mf = models_file.load(mpath)
        label = f"3 pinned models ({mpath.name}, mode {mf.mode})"
        add(label, True, ", ".join(f"{s.provider}:{s.model_id}" for s in mf.specs))
        if mf.mode == "paid":
            unverified = [
                s.model_id for s in mf.specs if not mf.prices[s.model_id].order_verified
            ]
            add(
                "price in/out order (non-blocking note)",
                True,
                f"unverified for {unverified or 'none'}: budgeted at the higher rate for both directions, so the cap stays safe",
                "note",
            )
            est = cost_estimate.estimate(mpath)
            add(
                "worst-case cost within EUR cap",
                est["total_worst_eur"] < mf.budget_cfg.cap_eur,
                f"expected EUR {est['total_expected_eur']:.3f}, worst case EUR {est['total_worst_eur']:.3f}, cap EUR {mf.budget_cfg.cap_eur} (enforced per attempt, experiments/budget.py)",
            )
        else:
            plan = cost_estimate.free_plan(mpath)
            within = all(r["rpd_use"] <= 1 and r["tpd_use"] <= 1 for r in plan["rows"])
            add(
                "free quotas sufficient for 90 calls",
                within,
                f"at least {plan['total_minutes']:.0f} min paced; "
                + "; ".join(
                    f"{r['model_id']}: {r['rpd_use']:.0%} of requests/day, {r['tpd_use']:.0%} of tokens/day"
                    for r in plan["rows"]
                ),
            )
            unv = [s.model_id for s in mf.specs if not mf.limits[s.model_id].verified]
            add(
                "free limits documented for every model",
                not unv,
                f"assumed (not published) for: {unv or 'none'}; confirm in the provider console",
                "human",
            )
            add(
                "free plan confirmed by owner",
                env.get(FREE_CONFIRM_ENV) == "1",
                f"{FREE_CONFIRM_ENV}=1 means: the Gemini key's project has NO billing account and the Groq organisation is on the Free plan (Groq plan is also checked from response headers at run time)",
                "human",
            )
    except Exception as exc:  # noqa: BLE001
        add(f"3 pinned models ({mpath.name})", False, repr(exc), "human")
    needed = sorted({s.provider for s in mf.specs}) if mf else sorted(KEY_ENVS)
    for prov in needed:
        var = KEY_ENVS[prov]
        add(
            f"API key present: {prov}",
            bool(env.get(var)),
            f"{var} is {'set' if env.get(var) else 'NOT set'} (value never printed)",
            "human",
        )
    free = bool(mf and mf.mode == "free")
    add(
        "owner authorisation to run" if free else "spend approved",
        env.get(APPROVAL_ENV) == "1",
        f"{APPROVAL_ENV}={'1' if env.get(APPROVAL_ENV) == '1' else 'unset'}"
        + (
            " (free tier: nothing is billed; this flag is the explicit go-ahead for live calls)"
            if free
            else ""
        ),
        "human",
    )
    if mf:
        done, missing = [], []
        for s in mf.specs:
            slug = re.sub(r"[^A-Za-z0-9._-]+", "_", s.model_id)
            ok = False
            for name in (f"smoke_{slug}.json", f"smoke_{s.provider}.json"):
                f = SMOKE_DIR / name
                if f.exists():
                    r = json.loads(f.read_text())
                    ok = ok or bool(
                        r.get("ok")
                        and r.get("model_id") == s.model_id
                        and r.get("requested_model")
                        == r.get("served_model")
                        == s.model_id
                    )
            (done if ok else missing).append(s.model_id)
        add(
            "live smoke tests passed (requests, served model, JSON, usage)",
            not missing,
            f"passed: {done or 'none'}; still to run: {missing or 'none'} (`make smoke-free` or `make smoke-all`)",
            "human",
        )
    else:
        add(
            "live smoke tests passed (requests, served model, JSON, usage)",
            False,
            "models file not loadable",
            "human",
        )
    return out


def main(argv=None) -> int:
    models = argv[argv.index("--models") + 1] if argv and "--models" in argv else None
    res = checks(models)
    for r in res:
        print(
            f"[{'PASS' if r['pass'] else 'BLOCK' if r['kind'] == 'human' else 'FAIL'}] {r['gate']}: {r['detail']}"
        )
    ready = all(r["pass"] for r in res)
    print(
        "READY for real run"
        if ready
        else "NOT READY: resolve BLOCK/FAIL gates above (no paid call was made)"
    )
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
