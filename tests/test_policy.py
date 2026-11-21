"""Tests for annotation-policy-v1 (docs/annotation-guidelines.md)."""

import json
from pathlib import Path

from rdflib import RDF, Literal

from evaluation.score import score_record
from rdf.gold_to_rdf import EX, SDO, gold_to_graph, load_gold

ROOT = Path(__file__).resolve().parent.parent
GOLD = load_gold(ROOT / "data/gold/gold_pilot.jsonl")
EXPECTED = {
    r["id"]: r["expected"]
    for r in map(
        json.loads, (ROOT / "data/experiment/expected.jsonl").read_text().splitlines()
    )
}
G = gold_to_graph(GOLD)


def show(r):
    return next(G.subjects(EX.cnmiEventId, Literal(r["cnmi_event_id"])))


def test_all_records_owner_verified_and_policy_tagged():
    assert all(
        g["human_verified"] is True
        and g["human_verified_by"].startswith("project owner")
        and g["annotation_policy"].startswith("annotation-policy-v1")
        for g in GOLD
    )


def test_policy1_asterisk_preserved_everywhere():
    starred = [g for g in GOLD if g["name_raw"].endswith("*")]
    assert len(starred) == 2
    for g in starred:
        assert "asterisk_suffix_unexplained_preserved" in g["ambiguities"]
        assert EXPECTED[g["gold_id"]]["show_name"] == g["name_raw"]
        assert (show(g), __import__("rdflib").RDFS.label, Literal(g["name_raw"])) in G


def test_policy2_vogue_kept_not_assumed_brand():
    (v,) = [g for g in GOLD if g["entry_kind"] == "unclassified_entry"]
    assert v["name_raw"] == "VOGUE WORLD: MILANO" and v["brand_raw"] is None
    assert (
        EXPECTED[v["gold_id"]]["_unscored"] == ["brand"]
        and EXPECTED[v["gold_id"]]["brand"] is None
    )
    org = next(G.objects(show(v), SDO.organizer))
    assert (org, RDF.type, SDO.Organization) in G and (
        org,
        RDF.type,
        SDO.Brand,
    ) not in G
    assert sum(1 for g in GOLD if g["entry_kind"] == "listed_show_entry") == 9


def test_policy3_null_venue_statuses_and_no_coordinates():
    assert {g["venue_status"] for g in GOLD if g["venue_address_raw"] is None} == {
        "unpublished",
        "invitation_only",
        "digital",
    }
    for g in GOLD:
        if g["venue_status"] != "address":
            assert (
                g["venue_address_raw"] is None
                and (show(g), SDO.location, None) not in G
            )
    assert not any(
        "lat" in json.dumps(g).lower() or "coordinates" in k for g in GOLD for k in g
    )
    assert any("map_coordinates_placeholder_ignored" in g["ambiguities"] for g in GOLD)


def test_policy4_local_time_no_timezone():
    for g in GOLD:
        assert "time_local_no_timezone_published" in g["ambiguities"]
        lit = str(next(G.objects(show(g), SDO.startDate)))
        assert (
            len(lit) == 19 and lit[-1].isdigit() and "Z" not in lit and "+" not in lit
        )


def test_policy5_corroboration_documented():
    reg = json.loads((ROOT / "data/source_register.jsonl").read_text())
    assert reg["corroboration"].startswith("none")


def test_scorer_skips_unscored_brand_and_flags_asterisk_loss():
    exp = {
        "show_name": "JIL SANDER *",
        "brand": None,
        "_unscored": ["brand"],
        "event_type": "fashion show",
        "date_time": None,
        "venue": None,
    }
    ev = {
        "show_name": "JIL SANDER",
        "brand": "Anything",
        "event_type": "fashion show",
        "date_time": None,
        "venue": None,
        "evidence_quote": "x",
    }
    s = score_record(exp, {"events": [ev]}, "JIL SANDER *")
    assert s["fp"] == 0 and s["tp"] == 2 and "asterisk_not_preserved" in s["errors"]
