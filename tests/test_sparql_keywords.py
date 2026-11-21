import re
from pathlib import Path

REQUIRED = ["OPTIONAL", "DISTINCT", "UNION", "FILTER", "REGEX", "LIMIT", "ORDER BY"]
ROOT = Path(__file__).resolve().parent.parent


def test_all_mandatory_keywords_present_in_executed_queries():
    """PDF p.4 rule 1. Only queries with a committed successful result in docs/kg-evidence count."""
    ev = {p.stem for p in (ROOT / "docs" / "kg-evidence").glob("*.json")}
    text = "\n".join(
        re.sub(r"(?m)^\s*#.*$", "", p.read_text())
        for p in (ROOT / "queries").glob("*.rq")
        if p.stem in ev
    ).upper()
    missing = [k for k in REQUIRED if k not in text]
    assert not missing, missing
