"""Enforced experiment budget (EUR cap). Fail-closed:
 - every provider attempt must `reserve` a WORST-CASE estimate (input chars-based with margin + full max_output cap)
   BEFORE the call; the call is refused if spent + estimate would exceed the cap;
 - after the call `settle` records actual cost from provider usage (missing usage => worst-case estimate is charged);
 - failed/timed-out attempts are charged the estimate (conservative: the provider may have billed them);
 - a persistent JSONL ledger survives restarts; a reserve with no settle (crash) counts as spent at its estimate;
 - prices come from models.json (official pricing, with source + retrieval date); unknown model => refuse;
 - FX is converted at ECB rate x safety factor (<1) so the USD cap is conservative.
This makes overspend impossible unless a provider bills far above its own reported usage."""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass
from pathlib import Path


class BudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class Price:
    usd_in_per_m: float
    usd_out_per_m: float
    order_verified: bool = (
        True  # False => in/out order unknown: BOTH rates budgeted at the higher value
    )

    @property
    def budget_in(self) -> float:
        return (
            self.usd_in_per_m
            if self.order_verified
            else max(self.usd_in_per_m, self.usd_out_per_m)
        )

    @property
    def budget_out(self) -> float:
        return (
            self.usd_out_per_m
            if self.order_verified
            else max(self.usd_in_per_m, self.usd_out_per_m)
        )


@dataclass(frozen=True)
class BudgetConfig:
    cap_eur: float = 5.0
    usd_per_eur: float = 1.0968
    fx_safety_factor: float = 0.95
    chars_per_token: float = 3.0  # pessimistic (English ~4)
    input_margin: float = 1.25

    @property
    def cap_usd(self) -> float:
        return self.cap_eur * self.usd_per_eur * self.fx_safety_factor


class Budget:
    def __init__(
        self,
        cfg: BudgetConfig,
        prices: dict[str, Price],
        max_output: dict[str, int],
        ledger: str | Path,
    ):
        self.cfg, self.prices, self.max_output = cfg, prices, max_output
        self.ledger = Path(ledger)
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self._open: dict[str, tuple[str, float]] = {}

    # --- ledger -----------------------------------------------------------------
    def _lines(self) -> list[dict]:
        if not self.ledger.exists():
            return []
        return [
            json.loads(x) for x in self.ledger.read_text().splitlines() if x.strip()
        ]

    def spent_usd(self) -> float:
        reserves, settled, total = {}, set(), 0.0
        for r in self._lines():
            if r["type"] == "reserve":
                reserves[r["id"]] = r["est_usd"]
            elif r["type"] == "settle":
                settled.add(r["id"])
                total += r["cost_usd"]
        return total + sum(
            e for i, e in reserves.items() if i not in settled
        )  # unsettled = worst case

    def spent_eur(self) -> float:
        return self.spent_usd() / (self.cfg.usd_per_eur * self.cfg.fx_safety_factor)

    def _append(self, rec: dict) -> None:
        with self.ledger.open("a") as fh:
            fh.write(json.dumps(rec) + "\n")
            fh.flush()

    # --- estimation ---------------------------------------------------------------
    def estimate_usd(self, model_id: str, system: str, user: str) -> float:
        p = self.prices[model_id]  # KeyError => fail closed
        in_tok = (
            math.ceil(
                (len(system) + len(user))
                / self.cfg.chars_per_token
                * self.cfg.input_margin
            )
            + 32
        )
        out_tok = self.max_output[model_id]
        return (in_tok * p.budget_in + out_tok * p.budget_out) / 1e6

    def reserve(self, model_id: str, system: str, user: str) -> str:
        est = self.estimate_usd(model_id, system, user)
        spent = self.spent_usd()
        if spent + est > self.cfg.cap_usd:
            raise BudgetExceeded(
                f"refused: spent ${spent:.4f} + worst-case ${est:.4f} > cap ${self.cfg.cap_usd:.4f} (EUR {self.cfg.cap_eur})"
            )
        rid = uuid.uuid4().hex
        self._open[rid] = (model_id, est)
        self._append({"type": "reserve", "id": rid, "model": model_id, "est_usd": est})
        return rid

    def settle(
        self, rid: str, input_tokens: int | None, output_tokens: int | None
    ) -> float:
        model_id, est = self._open.pop(rid)
        if input_tokens is None or output_tokens is None:
            cost = est  # usage unknown (failed call / missing field): charge worst case
        else:
            p = self.prices[model_id]
            cost = (input_tokens * p.budget_in + output_tokens * p.budget_out) / 1e6
        self._append(
            {
                "type": "settle",
                "id": rid,
                "model": model_id,
                "cost_usd": cost,
                "est_usd": est,
                "in": input_tokens,
                "out": output_tokens,
            }
        )
        if self.spent_usd() > self.cfg.cap_usd:
            raise BudgetExceeded("cap exceeded by actual usage; stopping")
        return cost

    def summary(self) -> dict:
        return {
            "cap_eur": self.cfg.cap_eur,
            "cap_usd_conservative": round(self.cfg.cap_usd, 4),
            "spent_usd": round(self.spent_usd(), 6),
            "spent_eur": round(self.spent_eur(), 6),
        }
