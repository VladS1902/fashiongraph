"""Response schema and strict validation (no jsonschema dependency available)."""

from __future__ import annotations

import json
import re

FIELDS = ("show_name", "brand", "event_type", "date_time", "venue", "evidence_quote")

# Documentation form of the schema (draft-07 compatible).
RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["events"],
    "additionalProperties": False,
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "required": list(FIELDS),
                "additionalProperties": False,
                "properties": {f: {"type": ["string", "null"]} for f in FIELDS},
            },
        }
    },
}


class ValidationError(ValueError):
    pass


def extract_json(text: str):
    """Parse JSON from model text, tolerating a markdown code fence only."""
    t = text.strip()
    m = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", t, re.DOTALL)
    if m:
        t = m.group(1)
    try:
        return json.loads(t)
    except json.JSONDecodeError as e:
        raise ValidationError(f"invalid JSON: {e}") from e


def validate_response(obj) -> dict:
    if not isinstance(obj, dict) or set(obj) != {"events"}:
        raise ValidationError("top level must be object with only 'events'")
    if not isinstance(obj["events"], list):
        raise ValidationError("'events' must be a list")
    for i, ev in enumerate(obj["events"]):
        if not isinstance(ev, dict):
            raise ValidationError(f"events[{i}] not an object")
        if set(ev) != set(FIELDS):
            raise ValidationError(f"events[{i}] keys must be exactly {FIELDS}")
        for k, v in ev.items():
            if v is not None and not isinstance(v, str):
                raise ValidationError(f"events[{i}].{k} must be string or null")
    return obj


def parse_and_validate(text: str) -> dict:
    return validate_response(extract_json(text))
