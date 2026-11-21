"""CLI: data/gold/gold_pilot.jsonl -> rdf/out/gold_pilot.ttl, with parse + SHACL validation report."""

import sys
from pathlib import Path

from rdf.gold_to_rdf import gold_to_graph, load_gold
from rdf.validate import parse_turtle, serialize, shacl_validate

ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    g = gold_to_graph(load_gold(ROOT / "data/gold/gold_pilot.jsonl"))
    ttl = serialize(g)
    parse_turtle(ttl)
    ok, report = shacl_validate(g)
    out = ROOT / "rdf/out"
    out.mkdir(exist_ok=True)
    (out / "gold_pilot.ttl").write_text(ttl)
    (out / "gold_pilot.shacl.txt").write_text(report)
    print(f"triples={len(g)} shacl_conforms={ok}")
    sys.exit(0 if ok else 1)
