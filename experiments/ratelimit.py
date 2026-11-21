"""Free-tier quota guard: a zero-cost counterpart of `Budget` with the same reserve/settle/summary interface.

Nothing is billed in free mode, so instead of a money cap we enforce the provider's documented FREE quotas, conservatively:
 - RPM / TPM: calls are paced (the guard sleeps) so that requests and RESERVED tokens (input estimate + full output cap, because
   it is not documented whether max tokens count against TPM) in any rolling 60 s window stay within the limit;
 - RPD / TPD: a rolling 24 h window (safe whatever the provider's reset time); if the next call would exceed it the guard raises
   QuotaExhausted and the run halts safely, to be resumed later from its checkpoint;
 - failed attempts count as requests and are charged their reservation; an unsettled reservation counts as used (crash safety).
Limits come from models.free.json with their source and a `verified` flag (False = assumption, not published in the docs)."""

from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from .budget import BudgetConfig, BudgetExceeded


class QuotaExhausted(BudgetExceeded):
    """A daily free quota would be exceeded; halt and resume later. Subclasses BudgetExceeded so the runner halts safely."""


@dataclass(frozen=True)
class Limits:
    rpm: int | None = None
    rpd: int | None = None
    tpm: int | None = None
    tpd: int | None = None
    verified: bool = False
    source: str = ""


class FreeTierGuard:
    def __init__(
        self,
        limits: dict[str, Limits],
        max_output: dict[str, int],
        ledger: str | Path,
        cfg: BudgetConfig | None = None,
        clock=time.time,
        sleep=time.sleep,
    ):
        self.limits, self.max_output = limits, max_output
        self.cfg = cfg or BudgetConfig()
        self.ledger = Path(ledger)
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self.clock, self.sleep = clock, sleep
        self._open: dict[str, tuple[str, int]] = {}
        self.waited_s = 0.0

    # ledger -------------------------------------------------------------------------
    def _events(self, model_id: str, since: float) -> list[tuple[float, int]]:
        """(time, tokens) per request of this model since `since`; settled = actual tokens, unsettled = reservation."""
        if not self.ledger.exists():
            return []
        res, act = {}, {}
        for line in self.ledger.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r["model"] != model_id:
                continue
            if r["type"] == "reserve":
                res[r["id"]] = (r["t"], r["est"])
            else:
                act[r["id"]] = r["tokens"]
        return [(t, act.get(i, est)) for i, (t, est) in res.items() if t >= since]

    def _reserved_window(self, model_id: str, since: float) -> list[tuple[float, int]]:
        """Reservations (not actuals) in the window: conservative for TPM."""
        if not self.ledger.exists():
            return []
        out = []
        for line in self.ledger.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if (
                    r["type"] == "reserve"
                    and r["model"] == model_id
                    and r["t"] >= since
                ):
                    out.append((r["t"], r["est"]))
        return out

    def _append(self, rec: dict) -> None:
        with self.ledger.open("a") as fh:
            fh.write(json.dumps(rec) + "\n")
            fh.flush()

    def estimate_tokens(self, model_id: str, system: str, user: str) -> int:
        return (
            math.ceil(
                (len(system) + len(user))
                / self.cfg.chars_per_token
                * self.cfg.input_margin
            )
            + 32
            + self.max_output[model_id]
        )

    # reserve / settle ---------------------------------------------------------------
    def reserve(self, model_id: str, system: str, user: str) -> str:
        lim = self.limits[model_id]  # KeyError => fail closed
        est = self.estimate_tokens(model_id, system, user)
        if lim.tpm is not None and est > lim.tpm:
            raise QuotaExhausted(
                f"{model_id}: one call reserves {est} tokens, above the {lim.tpm} tokens-per-minute limit"
            )
        while True:
            now = self.clock()
            day = self._events(model_id, now - 86400)
            if lim.rpd is not None and len(day) + 1 > lim.rpd:
                raise QuotaExhausted(
                    f"{model_id}: free requests-per-day limit ({lim.rpd}) reached; resume later"
                )
            if lim.tpd is not None and sum(tk for _, tk in day) + est > lim.tpd:
                raise QuotaExhausted(
                    f"{model_id}: free tokens-per-day limit ({lim.tpd}) would be exceeded; resume later"
                )
            minute = self._reserved_window(model_id, now - 60)
            wait = 0.0
            if lim.rpm is not None and len(minute) + 1 > lim.rpm:
                wait = max(wait, minute[len(minute) - lim.rpm][0] + 60 - now)
            if lim.tpm is not None and sum(tk for _, tk in minute) + est > lim.tpm:
                acc, need = sum(tk for _, tk in minute) + est, 0.0
                for t, tk in sorted(minute):
                    acc -= tk
                    need = t + 60 - now
                    if acc <= lim.tpm:
                        break
                wait = max(wait, need)
            if wait <= 0:
                break
            wait += 0.5  # safety margin
            self.waited_s += wait
            self.sleep(wait)
        rid = uuid.uuid4().hex
        self._open[rid] = (model_id, est)
        self._append(
            {
                "type": "reserve",
                "id": rid,
                "model": model_id,
                "t": self.clock(),
                "est": est,
            }
        )
        return rid

    def settle(
        self, rid: str, input_tokens: int | None, output_tokens: int | None
    ) -> int:
        model_id, est = self._open.pop(rid)
        tokens = (
            est
            if input_tokens is None or output_tokens is None
            else input_tokens + output_tokens
        )
        self._append(
            {
                "type": "settle",
                "id": rid,
                "model": model_id,
                "t": self.clock(),
                "tokens": tokens,
            }
        )
        return tokens

    def summary(self) -> dict:
        now = self.clock()
        per = {
            m: {
                "calls_24h": len(self._events(m, now - 86400)),
                "tokens_24h": sum(tk for _, tk in self._events(m, now - 86400)),
            }
            for m in self.limits
        }
        return {
            "mode": "free",
            "spent_eur": 0.0,
            "cap_eur": 0.0,
            "waited_s": round(self.waited_s, 1),
            "per_model": per,
        }
