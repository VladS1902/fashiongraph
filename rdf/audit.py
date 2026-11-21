"""Audit of generated gold RDF. Three SEPARATE axes (never merged into one 'quality' number):
 1. kind: structural | factual | provenance | link
 2. vocabulary: reused (rdf/rdfs/owl/schema/prov) | custom (ex:)
 3. source support (factual only): checked mechanically against the parsed CNMI row,
 and novelty vs Wikidata: about_new_entity | about_existing_entity | unchecked_entity (see docs/kg-feasibility.md).
RDF validity (SHACL) is reported separately and says nothing about support or novelty."""

from __future__ import annotations

import collections
import json
from pathlib import Path

from rdflib import OWL, RDF, RDFS, Literal, URIRef

from rdf.gold_to_rdf import EDITION, EX, PROV, SDO, WD, gold_to_graph, load_gold
from rdf.validate import shacl_validate

ROOT = Path(__file__).resolve().parent.parent
REUSED = (
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "http://www.w3.org/2000/01/rdf-schema#",
    str(OWL),
    str(SDO),
    str(PROV),
)
STRUCT = {RDF.type, SDO.superEvent}
FACT = {
    RDFS.label,
    SDO.startDate,
    SDO.endDate,
    SDO.organizer,
    SDO.location,
    SDO.streetAddress,
}
PROVEN = {PROV.wasDerivedFrom, EX.evidenceQuote, EX.cnmiEventId, EX.calendarTypeCode}


def kind(p):
    return (
        "structural"
        if p in STRUCT
        else "factual"
        if p in FACT
        else "provenance"
        if p in PROVEN
        else "link"
        if p == OWL.sameAs
        else "other"
    )


def vocab(t):
    return "reused" if str(t).startswith(REUSED) else "custom"


def audit() -> dict:
    gold = load_gold(ROOT / "data/gold/gold_pilot.jsonl")
    parsed = {
        r["cnmi_event_id"]: r
        for r in map(
            json.loads,
            (ROOT / "data/cnmi_calendar_parsed.jsonl").read_text().splitlines(),
        )
    }
    g = gold_to_graph(gold)
    by_show = {
        str(next(g.subjects(EX.cnmiEventId, Literal(r["cnmi_event_id"])))): r
        for r in gold
    }
    brand_srcs, venue_srcs = collections.defaultdict(set), collections.defaultdict(set)
    for sh, r in by_show.items():
        src = parsed[r["cnmi_event_id"]]
        for b in g.objects(URIRef(sh), SDO.organizer):
            brand_srcs[b].add(src["title"].rstrip(" *"))
        for v in g.objects(URIRef(sh), SDO.location):
            venue_srcs[v].add(src["address"])
    rows, unsupported = [], []
    for s, p, o in g:
        k = kind(p)
        v = vocab(p) if p != RDF.type else vocab(o)
        supported = None
        if k == "factual":
            r = by_show.get(str(s))
            src = parsed.get(r["cnmi_event_id"]) if r else None
            if p == SDO.startDate and src:
                supported = (
                    str(o)
                    == f"{src['day_heading_date']}T{int(src['time'].split(':')[0]):02d}:{src['time'].split(':')[1]}:00"
                )
            elif p == RDFS.label and src:
                supported = str(o) == src["title"]
            elif p == SDO.organizer and src:
                supported = (o, RDFS.label, Literal(src["title"].rstrip(" *"))) in g
            elif p == SDO.location and src:
                supported = (
                    o,
                    SDO.streetAddress,
                    Literal(src["address"]),
                ) in g and src["address"] is not None
            elif s == EDITION:
                ev = json.loads((ROOT / "data/source_register.jsonl").read_text())[
                    "evidence_snippet"
                ]
                supported = "22-28 SEPTEMBER 2026" in ev.upper() and str(o) in (
                    "2026-09-22",
                    "2026-09-28",
                    "Milano Moda Donna Spring/Summer 2027",
                )
            elif s in brand_srcs and p == RDFS.label:
                supported = str(o) in brand_srcs[s]
            elif s in venue_srcs and p in (RDFS.label, SDO.streetAddress):
                supported = str(o) in venue_srcs[s]
            else:
                supported = None
        subj = str(s)
        if o == WD["Q193136"] or o == WD["Q130829"] or str(o).startswith(str(WD)):
            ent = "about_existing_entity"
        elif subj.startswith(str(EX) + "show/") or s == EDITION:
            ent = "about_new_entity"
        else:
            ent = "unchecked_entity"  # local brand/venue nodes: no Wikidata lookup/linking done (except Prada sameAs)
        rows.append((s, p, o, k, v, supported, ent))
        if supported is False:
            unsupported.append([str(s), str(p), str(o)])
    conforms, _ = shacl_validate(g)
    c = collections.Counter
    return {
        "total_triples": len(g),
        "shacl_conforms": conforms,
        "by_kind": c(r[3] for r in rows),
        "by_vocabulary": c(r[4] for r in rows),
        "by_kind_and_vocabulary": c(f"{r[3]}/{r[4]}" for r in rows),
        "by_entity_novelty_status": c(r[6] for r in rows),
        "factual_source_checks": c(
            "supported" if r[5] else "unsupported" if r[5] is False else "not_checked"
            for r in rows
            if r[3] == "factual"
        ),
        "unsupported": unsupported,
        "factual_triples_about_new_entities": sum(
            1 for r in rows if r[3] == "factual" and r[6] == "about_new_entity"
        ),
        "note": "novelty is relative to Wikidata label/EntitySearch evidence only (queries 04,06,09,12-15); other KGs unchecked; absence evidence is bounded, not proof",
    }


if __name__ == "__main__":
    a = audit()
    (ROOT / "rdf/out").mkdir(exist_ok=True)
    (ROOT / "rdf/out/audit.json").write_text(json.dumps(a, indent=1, default=dict))
    print(json.dumps(a, indent=1, default=dict))
