"""Second-pass review of gold records using a DIFFERENT extraction path than data/scripts/parse_cnmi.py:
 (1) stdlib html.parser DOM walk (not regex over raw HTML) over the saved HTML;
 (2) cross-check each id's type against the page's embedded JS event array (`id/type/name`);
 (3) cross-check against the linearised visible text ('F 14:00 live TITLE ADDRESS');
 (4) map coordinates presence for rows with a published address;
 (5) LIVE re-fetch of the official page and drift comparison.
Writes data/review/second_pass.json. This reduces extraction-error risk; it is NOT human adjudication."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
URL = "https://www.cameramoda.it/en/milano-moda-donna/calendar/"
MONTHS = ("September",)


class Walker(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.day = None
        self.rows = []
        self.row = None
        self.cell = None
        self.in_h2 = False
        self.h2buf = ""
        self.depth_stack = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        c = a.get("class", "") or ""
        if tag == "h2":
            self.in_h2, self.h2buf = True, ""
        if tag == "div" and "cal-table-row" in c and "data-id-event" in a:
            self.row = {
                "id": a["data-id-event"],
                "day": self.day,
                "cls": c,
                "type": "",
                "time": "",
                "title": "",
                "address": "",
                "lat": None,
                "lng": None,
            }
            self.rows.append(self.row)
            self.cell = None
        elif self.row is not None and tag == "div":
            for key in ("event-type", "event-time", "event-title", "event-address"):
                if key in c.split():
                    self.cell = key.split("-")[1]
            if "map" in c.split() and "data-lat" in a:
                self.row["lat"], self.row["lng"] = a["data-lat"], a["data-lng"]

    def handle_endtag(self, tag):
        if tag == "h2":
            self.in_h2 = False
            m = re.fullmatch(r"\s*\w+day\s+(\d{1,2})\s+September\s*", self.h2buf)
            if m:
                self.day = f"2026-09-{int(m.group(1)):02d}"
        if tag == "div":
            self.cell = None

    def handle_data(self, d):
        if self.in_h2:
            self.h2buf += d
        if self.row is not None and self.cell:
            self.row[self.cell] = (self.row[self.cell] + " " + d.strip()).strip()


def walk(html: str):
    w = Walker()
    w.feed(html)
    return {r["id"]: r for r in w.rows}


def js_types(html: str):
    return {
        m.group(1): (m.group(2), m.group(3))
        for m in re.finditer(
            r'id:\s*"(\d+)",\s*type:\s*"(\w)",\s*name:\s*"([^"]*)"', html
        )
    }


def linear(html: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.DOTALL)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))


def main():
    gold = [
        json.loads(line)
        for line in (ROOT / "data/gold/gold_pilot.jsonl").read_text().splitlines()
    ]
    saved = (ROOT / "data/raw/cnmi_calendar.html").read_text()
    dom, js, lin = walk(saved), js_types(saved), linear(saved)
    live = requests.get(
        URL,
        headers={"User-Agent": "Mozilla/5.0 FashionGraphStudentProject/0.1"},
        timeout=30,
    ).text
    live_dom = walk(live)
    out = {
        "live_sha256": hashlib.sha256(live.encode()).hexdigest(),
        "saved_sha256": hashlib.sha256(saved.encode()).hexdigest(),
        "records": [],
    }
    for g in gold:
        i = g["cnmi_event_id"]
        d = dom.get(i)
        checks = {}
        checks["dom_found"] = d is not None
        if d:
            t = re.search(r"\d{1,2}:\d{2}", d["time"])
            checks["dom_title_eq"] = d["title"] == g["name_raw"]
            checks["dom_day_eq"] = d["day"] == g["date"]
            checks["dom_time_eq"] = (t.group(0) if t else None) == g["time"]
            checks["dom_address_eq"] = d["address"] == (
                g["venue_address_published_as"] or ""
            )
            checks["dom_type_F"] = d["type"] == "F"
            has_addr = g["venue_status"] == "address"
            checks["coords_consistent_with_status"] = (
                (d["lat"] not in (None, "")) if has_addr else True
            )  # coords on non-address rows are informational only
        jt = js.get(i)
        checks["js_type_F"] = bool(jt) and jt[0] == "F"
        checks["js_name_eq_title_sans_star"] = bool(jt) and jt[1].strip() == g[
            "name_raw"
        ].rstrip(" *")
        pat = re.escape(g["name_raw"])
        checks["linear_text_has_row"] = bool(
            re.search(rf"F\s+{re.escape(g['time'])}(?: live)?\s+{pat}(?=\s)", lin)
        )
        ld = live_dom.get(i)
        checks["live_same_as_saved"] = (
            bool(ld) and all(ld[k] == d[k] for k in ("day", "time", "title", "address"))
            if d
            else False
        )
        info = {
            "coords_on_nonaddress_row": bool(d)
            and g["venue_status"] != "address"
            and d["lat"] not in (None, "")
        }
        out["records"].append(
            {
                "gold_id": g["gold_id"],
                "checks": checks,
                "info": info,
                "all_ok": all(checks.values()),
            }
        )
    (ROOT / "data/review").mkdir(exist_ok=True)
    (ROOT / "data/review/second_pass.json").write_text(json.dumps(out, indent=1))
    for r in out["records"]:
        bad = [k for k, v in r["checks"].items() if not v]
        print(r["gold_id"], "OK" if r["all_ok"] else f"DISCREPANCY {bad}")
    print(
        "live==saved bytes:",
        out["live_sha256"] == out["saved_sha256"],
        "| dom rows:",
        len(dom),
        "live rows:",
        len(live_dom),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
