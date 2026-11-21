"""Syntax + SHACL validation of generated RDF."""

from __future__ import annotations

from pathlib import Path

from pyshacl import validate
from rdflib import Graph

SHAPES = Path(__file__).with_name("shapes.ttl")


def parse_turtle(text: str) -> Graph:
    return Graph().parse(data=text, format="turtle")  # raises on bad syntax


def shacl_validate(g: Graph) -> tuple[bool, str]:
    conforms, _, report = validate(g, shacl_graph=str(SHAPES), inference="none")
    return bool(conforms), report


def serialize(g: Graph) -> str:
    return g.serialize(format="turtle")
