import pytest
from rdflib import RDF, Graph

from rdf.convert import EX, SDO, events_to_graph, slug
from rdf.validate import parse_turtle, serialize, shacl_validate

EV = {
    "show_name": "Test Show",
    "brand": "Test Brand",
    "event_type": "runway show",
    "date_time": "2026-09-23",
    "venue": "Test Venue",
    "evidence_quote": "quote",
}


def test_slug():
    assert slug("Dolce & Gabbana") == "dolce-gabbana"
    assert slug("Ermenegildo Zégna") == "ermenegildo-zegna"


def test_deterministic_and_roundtrip():
    a = serialize(events_to_graph({"events": [EV]}))
    b = serialize(events_to_graph({"events": [EV]}))
    assert a == b
    g = parse_turtle(a)
    assert len(list(g.subjects(RDF.type, SDO.Event))) == 1


def test_valid_conforms():
    ok, rep = shacl_validate(events_to_graph({"events": [EV]}))
    assert ok, rep


def test_missing_evidence_fails_shacl():
    ev = dict(EV, evidence_quote=None)
    ok, _ = shacl_validate(events_to_graph({"events": [ev]}))
    assert not ok


def test_bad_date_fails_shacl():
    ok, _ = shacl_validate(
        events_to_graph({"events": [dict(EV, date_time="late September")]})
    )
    assert not ok


def test_no_name_skipped():
    g = events_to_graph({"events": [dict(EV, show_name=None)]})
    assert len(g) == 0


def test_bad_turtle_raises():
    with pytest.raises(Exception, match="."):
        parse_turtle("this is not turtle")


def test_dedup_same_event():
    g = events_to_graph({"events": [EV, EV]})
    assert len(list(g.subjects(RDF.type, SDO.Event))) == 1
    assert isinstance(g, Graph) and EX
