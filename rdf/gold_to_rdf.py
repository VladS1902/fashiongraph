"""Deterministic gold records -> candidate RDF (no LLM). Only fields present in the record produce triples.
Entity links to Wikidata are asserted ONLY for items verified in docs/kg-evidence (see KNOWN_QIDS)."""

from __future__ import annotations

import json
from pathlib import Path

from rdflib import OWL, RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef

from rdf.convert import EX, PROV, SDO, new_graph, slug

WD = Namespace("http://www.wikidata.org/entity/")
SERIES = WD["Q130829"]  # Milan Fashion Week (verified, queries/01)
KNOWN_QIDS = {"PRADA": WD["Q193136"]}  # verified in queries/05
SOURCE_URL = "https://www.cameramoda.it/en/milano-moda-donna/calendar/"
EDITION = EX["edition/milano-moda-donna-ss2027"]


def gold_to_graph(records: list[dict]) -> Graph:
    g = new_graph()
    g.bind("wd", WD)
    g.add((EDITION, RDF.type, EX.FashionWeekEdition))
    g.add((EDITION, RDF.type, SDO.Event))
    g.add((EDITION, RDFS.label, Literal("Milano Moda Donna Spring/Summer 2027")))
    g.add((EDITION, SDO.superEvent, SERIES))
    g.add((EDITION, SDO.startDate, Literal("2026-09-22", datatype=XSD.date)))
    g.add((EDITION, SDO.endDate, Literal("2026-09-28", datatype=XSD.date)))
    g.add(
        (
            EDITION,
            EX.evidenceQuote,
            Literal("SPRING/SUMMER 2027 - 22-28 SEPTEMBER 2026"),
        )
    )
    g.add((EDITION, PROV.wasDerivedFrom, URIRef(SOURCE_URL)))
    for r in records:
        show = EX[f"show/{slug(r['name_raw'])}-{r['cnmi_event_id']}"]
        g.add((show, RDF.type, EX.FashionShow))
        g.add((show, RDF.type, SDO.Event))
        g.add(
            (show, RDFS.label, Literal(r["name_raw"]))
        )  # as published, incl. unexplained "*"
        g.add((show, SDO.superEvent, EDITION))
        g.add((show, EX.cnmiEventId, Literal(r["cnmi_event_id"])))
        g.add((show, EX.calendarTypeCode, Literal(r["event_type_code"])))
        if r.get("time") and r.get("date"):
            hh, mm = r["time"].split(":")
            g.add(
                (
                    show,
                    SDO.startDate,
                    Literal(
                        f"{r['date']}T{int(hh):02d}:{mm}:00", datatype=XSD.dateTime
                    ),
                )
            )
        if (
            r.get("entry_kind") == "unclassified_entry"
        ):  # policy 2: do not assume a fashion brand
            org = EX[f"org/{slug(r['name_raw'])}"]
            g.add((org, RDF.type, SDO.Organization))
            g.add((org, RDFS.label, Literal(r["name_raw"].rstrip(" *"))))
            g.add((show, SDO.organizer, org))
        else:
            brand = EX[f"brand/{slug(r['brand_raw'])}"]
            g.add((brand, RDF.type, SDO.Brand))
            g.add((brand, RDFS.label, Literal(r["brand_raw"])))
            g.add((show, SDO.organizer, brand))
            if r["brand_raw"].upper() in KNOWN_QIDS:
                g.add((brand, OWL.sameAs, KNOWN_QIDS[r["brand_raw"].upper()]))
        if r.get("venue_address_raw"):
            place = EX[f"venue/{slug(r['venue_address_raw'])}"]
            g.add((place, RDF.type, SDO.Place))
            g.add((place, RDFS.label, Literal(r["venue_address_raw"])))
            g.add((place, SDO.streetAddress, Literal(r["venue_address_raw"])))
            g.add((show, SDO.location, place))
        g.add((show, EX.evidenceQuote, Literal(r["evidence"])))
        g.add((show, PROV.wasDerivedFrom, URIRef(SOURCE_URL)))
    return g


def load_gold(path: str | Path) -> list[dict]:
    return [
        json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()
    ]
