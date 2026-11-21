"""DETERMINISTIC MOCK 'models' for end-to-end plumbing tests. Their outputs are NOT research data.
They parse the standard input text with fixed rules and inject scripted, reproducible errors:
  mock-perfect : rule-based correct extraction (upper bound for plumbing; not a real model)
  mock-noisy   : drops/hallucinates/misformats fields on a fixed schedule keyed by the record hash
  mock-broken  : returns non-JSON / schema-violating / fenced JSON
"""

from __future__ import annotations

import hashlib
import json
import re

from .adapters import Adapter, Completion

MOCK_MODELS = ("mock-perfect", "mock-noisy", "mock-broken")


def _parse(user: str) -> dict:
    text = user.rsplit("TEXT:", 1)[-1] if "TEXT:" in user else user
    day = re.search(r"Day: \w+ (\d{1,2}) (\w+) (\d{4})", text)
    row = re.search(
        r"Row \(type \| time \| title \| address\): (.*)$", text.strip(), re.MULTILINE
    )
    cells = [c.strip() for c in row.group(1).strip().split(" | ", 3)]
    cells += [""] * (4 - len(cells))  # empty trailing address cell
    _typ, time_raw, title, addr = (c.removesuffix("|").strip() for c in cells)
    hhmm = re.search(r"\d{1,2}:\d{2}", time_raw).group(0)
    h, m = hhmm.split(":")
    return {
        "name": title.strip(),
        "dt": f"2026-09-{int(day.group(1)):02d}T{int(h):02d}:{m}",
        "addr": addr,
        "quote": row.group(1).strip(),
    }


def _venue(addr: str):
    return (
        None
        if addr.strip().lower() in ("", "digital", "location in the invitation")
        else addr
    )


class ScriptedMock(Adapter):
    provider = "mock"
    is_mock = True

    def complete(self, system, user):
        p = _parse(user)
        h = int(hashlib.sha256(p["quote"].encode()).hexdigest(), 16)
        ev = {
            "show_name": p["name"],
            "brand": p["name"],
            "event_type": "fashion show",
            "date_time": p["dt"],
            "venue": _venue(p["addr"]),
            "evidence_quote": p["quote"],
        }
        if self.model_id == "mock-noisy":
            k = h % 5
            if k == 0 and ev["venue"] is None:
                ev["venue"] = (
                    p["addr"] or "Piazza Duomo"
                )  # hallucinated / placeholder-as-venue
            elif k == 1:
                ev["date_time"] = ev["date_time"][:10]  # date only (time dropped)
            elif k == 2:
                ev["evidence_quote"] = (
                    "paraphrased: " + p["name"].lower()
                )  # not verbatim
            elif k == 3:
                ev["brand"] = None  # missing field
            out = json.dumps({"events": [ev]})
        elif self.model_id == "mock-broken":
            k = h % 3
            out = [
                "Sure! Here is the data: " + p["name"],
                json.dumps({"events": [{"show_name": p["name"]}]}),
                "```json\n" + json.dumps({"events": [ev]}) + "\n```",
            ][k]
        else:
            out = json.dumps({"events": [ev]})
        return Completion(out, len(user) // 4, len(out) // 4, {"MOCK": True})
