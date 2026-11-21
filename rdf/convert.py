"""Deterministic JSON (experiments/schema.py events) -> RDF graph. No LLM involved.

Vocabulary is PROVISIONAL (pending KG feasibility memo): schema.org for reuse,
`ex:` for the minimal extension. Candidate triples only; not verified facts.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

from rdflib import RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef

EX = Namespace("https://example.org/fashiongraph/")
SDO = Namespace("https://schema.org/")
PROV = Namespace("http://www.w3.org/ns/prov#")


def slug(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-") or "unnamed"


def _iri(kind: str, label: str) -> URIRef:
    return EX[f"{kind}/{slug(label)}"]


def new_graph() -> Graph:
    g = Graph()
    g.bind("ex", EX)
    g.bind("schema", SDO)
    g.bind("prov", PROV)
    g.bind("rdfs", RDFS)
    return g


def _date_literal(s: str) -> Literal:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return Literal(s, datatype=XSD.date)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?", s):
        if len(s) == 16:  # xsd:dateTime requires seconds
            s += ":00"
        return Literal(s, datatype=XSD.dateTime)
    return Literal(s)  # unparsed: kept as plain literal, flagged by validation


def add_event(
    g: Graph, ev: dict, source_url: str | None = None, run_id: str | None = None
) -> URIRef | None:
    """Add one extracted event. Returns subject IRI, or None if no show name."""
    name = ev.get("show_name")
    if not name:
        return None
    key = "|".join(str(ev.get(k) or "") for k in ("show_name", "brand", "date_time"))
    subj = EX[f"show/{slug(name)}-{hashlib.sha1(key.encode()).hexdigest()[:8]}"]
    g.add((subj, RDF.type, SDO.Event))
    g.add((subj, RDFS.label, Literal(name)))
    if ev.get("event_type"):
        g.add((subj, EX.eventType, Literal(ev["event_type"])))
    if ev.get("brand"):
        b = _iri("brand", ev["brand"])
        g.add((b, RDF.type, SDO.Brand))
        g.add((b, RDFS.label, Literal(ev["brand"])))
        g.add((subj, SDO.organizer, b))
    if ev.get("venue"):
        v = _iri("venue", ev["venue"])
        g.add((v, RDF.type, SDO.Place))
        g.add((v, RDFS.label, Literal(ev["venue"])))
        g.add((subj, SDO.location, v))
    if ev.get("date_time"):
        g.add((subj, SDO.startDate, _date_literal(ev["date_time"])))
    if ev.get("evidence_quote"):
        g.add((subj, EX.evidenceQuote, Literal(ev["evidence_quote"])))
    if source_url:
        g.add((subj, PROV.wasDerivedFrom, URIRef(source_url)))
    if run_id:
        g.add((subj, EX.extractionRun, Literal(run_id)))
    return subj


def events_to_graph(
    obj: dict, source_url: str | None = None, run_id: str | None = None
) -> Graph:
    g = new_graph()
    for ev in obj["events"]:
        add_event(g, ev, source_url, run_id)
    return g
