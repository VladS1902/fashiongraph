import json
from pathlib import Path

from rdflib import OWL, RDF, URIRef

from data.scripts.parse_cnmi import parse
from data.validate_register import check_record
from rdf.gold_to_rdf import EX, SDO, WD, gold_to_graph, load_gold
from rdf.validate import parse_turtle, serialize, shacl_validate

ROOT = Path(__file__).resolve().parent.parent
GOLD = load_gold(ROOT / "data/gold/gold_pilot.jsonl")
PARSED = {
    r["cnmi_event_id"]: r
    for r in map(
        json.loads, (ROOT / "data/cnmi_calendar_parsed.jsonl").read_text().splitlines()
    )
}

FIXTURE = """<h2 class="title">Tuesday 22 September</h2>
<div class="cal-table-row sfilata" data-id-event="1" >
 <div class="event-type">F</div><div class="event-time"><strong>14:00<br/><span class="live">live</span></strong></div>
 <div class="event-title">PRADA *</div><div class="event-address">Via Lorenzini, 14</div></div>
<h2 class="title">Wednesday 23 September</h2>
<div class="cal-table-row sfilata" data-id-event="2" >
 <div class="event-type">F</div><div class="event-time"><strong>9:30</strong></div>
 <div class="event-title">X</div><div class="event-address">Location In The Invitation</div></div>"""


def test_parser_fixture():
    a, b = parse(FIXTURE)
    assert (a["day_heading_date"], a["time"], a["title"], a["address"]) == (
        "2026-09-22",
        "14:00",
        "PRADA *",
        "Via Lorenzini, 14",
    )
    assert b["day_heading_date"] == "2026-09-23" and b["time"] == "9:30"


def test_gold_size_and_fields_verbatim_from_source():
    assert len(GOLD) == 10 and len({g["gold_id"] for g in GOLD}) == 10
    for g in GOLD:
        s = PARSED[g["cnmi_event_id"]]
        assert (
            g["name_raw"] == s["title"]
            and g["date"] == s["day_heading_date"]
            and g["time"] == s["time"]
        )
        assert g["venue_address_published_as"] == s["address"]
        assert g["split"] is None  # must be assigned deliberately before experiments


def test_status_consistent_with_missing_fields():
    for g in GOLD:
        assert (g["status"] == "confirmed") == (g["missing_fields"] == [])
        assert (g["status"] == "confirmed_no_venue") == (
            g["missing_fields"] == ["address"]
        )
        assert (g["venue_status"] == "address") == (g["venue_address_raw"] is not None)
    assert {g["venue_status"] for g in GOLD} == {
        "address",
        "invitation_only",
        "digital",
        "unpublished",
    }


def test_source_register_valid():
    rec = json.loads((ROOT / "data/source_register.jsonl").read_text())
    assert check_record(rec) == []
    assert {g["source_id"] for g in GOLD} == {rec["source_id"]}


def test_rdf_roundtrip_and_shacl_conforms():
    g = gold_to_graph(GOLD)
    assert len(parse_turtle(serialize(g))) == len(g)
    ok, rep = shacl_validate(g)
    assert ok, rep


def test_withheld_venue_gives_no_location_and_no_invented_links():
    g = gold_to_graph(GOLD)
    for r in GOLD:
        show = next(
            g.subjects(EX.cnmiEventId, __import__("rdflib").Literal(r["cnmi_event_id"]))
        )
        has_loc = (show, SDO.location, None) in g
        assert has_loc == (r["venue_status"] == "address")
    links = list(g.subject_objects(OWL.sameAs))
    assert len(links) == 1 and links[0][1] == WD["Q193136"]  # only verified Prada link


def test_shacl_has_teeth():
    g = gold_to_graph(GOLD)
    show = next(g.subjects(RDF.type, EX.FashionShow))
    g.remove((show, SDO.organizer, None))
    assert not shacl_validate(g)[0]
    g2 = gold_to_graph(GOLD)
    s2 = next(g2.subjects(RDF.type, EX.FashionShow))
    g2.add(
        (s2, SDO.superEvent, URIRef("https://example.org/fashiongraph/edition/other"))
    )
    assert not shacl_validate(g2)[0]
