"""Validate data/source_register.jsonl records (no jsonschema dep: checks required keys/enums)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCHEMA = json.loads(Path(__file__).with_name("source_register.schema.json").read_text())


def check_record(r: dict) -> list[str]:
    errs = [f"missing {k}" for k in SCHEMA["required"] if k not in r]
    props = SCHEMA["properties"]
    if "retrieved_on" in r and not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", str(r["retrieved_on"])
    ):
        errs.append("bad retrieved_on")
    for k in ("verification_status", "split"):
        if k in r and r[k] not in props[k]["enum"]:
            errs.append(f"bad {k}")
    if "url" in r and not str(r["url"]).startswith(("http://", "https://")):
        errs.append("bad url")
    return errs


def main(path: str) -> int:
    bad = 0
    for i, line in enumerate(Path(path).read_text().splitlines(), 1):
        if line.strip():
            for e in check_record(json.loads(line)):
                print(f"line {i}: {e}")
                bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
