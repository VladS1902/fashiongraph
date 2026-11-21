"""Deterministic parser of the saved CNMI calendar HTML (data/raw/cnmi_calendar.html).
Extracts rows exactly as published; never infers missing fields. Output: data/cnmi_calendar_parsed.jsonl"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

DAY = re.compile(
    r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+(\d{1,2}) (September)"
)
ROW = re.compile(
    r'<div class="cal-table-row[^"]*"\s+data-id-event="(\d+)"\s*>(.*?)(?=<div class="cal-table-row|\Z)',
    re.DOTALL,
)


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def parse(text: str) -> list[dict]:
    # day markers: position of headings that precede row blocks
    days = [(m.start(), f"2026-09-{int(m.group(2)):02d}") for m in DAY.finditer(text)]
    out = []
    for m in ROW.finditer(text):
        body = m.group(2)
        cur = None
        for pos, d in days:
            if pos < m.start():
                cur = d
        typ = re.search(r'event-type">\s*(\w)\s*<', body)
        time = re.search(r'event-time">(.*?)</div>', body, re.DOTALL)
        title = re.search(r'event-title">(.*?)</div>', body, re.DOTALL)
        addr = re.search(r'event-address">(.*?)</div>', body, re.DOTALL)
        desc = re.search(r'event-desc[^"]*">(.*?)</div>', body, re.DOTALL)
        t = clean(time.group(1)) if time else ""
        tm = re.search(r"\b(\d{1,2}:\d{2})\b", t)
        out.append(
            {
                "cnmi_event_id": m.group(1),
                "day_heading_date": cur,
                "type": typ.group(1) if typ else None,
                "time_raw": t or None,
                "time": tm.group(1) if tm else None,
                "title": clean(title.group(1)) if title else None,
                "address": clean(addr.group(1)) or None if addr else None,
                "desc": clean(desc.group(1)) or None if desc else None,
            }
        )
    return out


if __name__ == "__main__":
    src = Path(sys.argv[1])
    rows = parse(src.read_text())
    Path(sys.argv[2]).write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    )
    print(len(rows), "rows")
