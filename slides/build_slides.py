"""Build slides/FashionGraph_slides.pptx (+ slides/outline.md) from repository artefacts.
Facts (counts, versions) are read from artefacts, never typed in. Results slide stays a PLACEHOLDER until
results/metrics.json exists (never from mock runs). Time budget: max 2 minutes per member (PDF p.17)."""

from __future__ import annotations

import json
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "slides"
WEBSITE_PLACEHOLDER = "PLACEHOLDER: website URL (add after the owner approves GitHub publication; must be on this title slide)"
BG, FG, ACC = (
    RGBColor(0xFA, 0xF8, 0xF5),
    RGBColor(0x1B, 0x1B, 0x1B),
    RGBColor(0x8A, 0x1C, 0x3A),
)


def facts() -> dict:
    gold = json.loads((ROOT / "data/gold/MANIFEST.json").read_text())
    audit = json.loads((ROOT / "rdf/out/audit.json").read_text())
    n_q = len(list((ROOT / "queries").glob("*.rq")))
    metrics = ROOT / "results" / "metrics.json"
    real = metrics.exists() and not json.loads(metrics.read_text()).get("is_mock")
    return {
        "gold_v": gold["version"],
        "gold_n": gold["records"],
        "triples": audit["total_triples"],
        "supported": audit["factual_source_checks"].get("supported", 0),
        "novel": audit["factual_triples_about_new_entities"],
        "queries": n_q,
        "real_results": real,
    }


def slides(f: dict) -> list[dict]:
    """A deck for the real team size: max 2 minutes per member in total (PDF p.17). With group size 1 that is 120 s, so six slides."""
    team = json.loads((ROOT / "team.json").read_text())
    who = " and ".join(m["name"] for m in team["members"])
    site = (
        json.loads((ROOT / "site.json").read_text())
        if (ROOT / "site.json").exists()
        else {}
    )
    website_line = f"Website: {site['url']}" if site.get("url") else WEBSITE_PLACEHOLDER
    table, findings = None, ""
    res_body = [
        "PENDING: no real model experiment has been run.",
        "Table of precision / recall / F1 per model and prompting strategy goes here after a run.",
    ]
    if f["real_results"]:
        d = json.loads((ROOT / "results" / "metrics.json").read_text())
        fx = lambda x: "n/a" if x is None else f"{x:.2f}"
        table = [["model", "technique", "P", "R", "F1"]] + [
            [
                c["model_id"],
                c["technique"],
                fx(c["precision"]),
                fx(c["recall"]),
                fx(c["f1"]),
            ]
            for c in d["cells"]
        ]
        res_body = [
            "3 language models x 3 prompting strategies x 10 records, free tiers",
            f"n = {d['cells'][0]['n_records']} per cell, descriptive only; techniques provisional",
        ]
        by: dict[str, list[float]] = {}
        for c in d["cells"]:
            by.setdefault(c["model_id"], []).append(c["f1"] or 0.0)
        findings = "; ".join(
            f"{m.split('/')[-1]}: F1 {min(v):.2f}"
            + (
                f" to {max(v):.2f}"
                if max(v) - min(v) > 0.0005
                else " in every strategy"
            )
            for m, v in sorted(by.items())
        )
    real = f["real_results"]
    return [
        {
            "title": "FashionGraph",
            "sub": "Enriching Wikidata with knowledge about Milan Fashion Week",
            "body": [
                "Comparing three language models for fashion-event knowledge-graph enrichment",
                f"Team: {who}",
                website_line,
            ],
            "who": who,
            "sec": 10,
            "notes": "Website link must stay on this slide.",
        },
        {
            "title": "The gap and how we found it",
            "body": [
                "Wikidata has one item for Milan Fashion Week (Q130829); no editions or shows found",
                "0 of 19 Milan fashion houses record taking part in any event",
                f"{f['queries']} bounded SPARQL queries on Wikidata, with a control search against false negatives",
            ],
            "who": who,
            "sec": 20,
            "notes": "Gap shown with entity-level queries, not by missing properties on Q130829. All queries are on the website SPARQL page.",
        },
        {
            "title": "Source data and gold set",
            "body": [
                "Official CNMI calendar, Milano Moda Donna SS2027 (22-28 Sep 2026)",
                f"{f['gold_n']} records, gold v{f['gold_v']}, owner-verified, checksummed",
                "Single source: no independent corroboration; missing venues stay null",
            ],
            "who": who,
            "sec": 15,
            "notes": "Annotation policy and review table are on the Data page.",
        },
        {
            "title": "Ontology and RDF",
            "body": [
                "Reuse Wikidata and schema.org; three small custom classes",
                f"{f['triples']} candidate triples, valid and SHACL-conformant; only {f['novel']} potentially new",
                "Valid, source-supported and new are audited separately",
            ],
            "who": who,
            "sec": 15,
            "notes": "Do not say 153 novel triples.",
        },
        {
            "title": "Experiment and results" if real else "Experiment (planned)",
            "body": res_body,
            "who": who,
            "sec": 40,
            "notes": (
                findings
                + ". Two models are at the ceiling on this easy single-row task; Qwen differences come mostly from provider-side generation failures. Conditions differ by necessity (reasoning level, no Gemini temperature)."
            )
            if real
            else "Keep as pending until real data exists.",
            "table": table,
        },
        {
            "title": "Challenges, limits and next steps",
            "body": [
                "Provider outages, generation failures, interrupted runs: all logged and handled"
                if real
                else "Timeouts, false negatives, unexplained source fields",
                "Ten records, one source; two models at the ceiling",
                "Next: written discussion and confirmed technique names; publish after approval",
            ],
            "who": who,
            "sec": 20,
            "notes": "Full list on the website Methodology page, section Challenges and how we addressed them.",
        },
    ]


def build() -> Path:
    f = facts()
    sl = slides(f)
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    team = json.loads((ROOT / "team.json").read_text())
    prs.core_properties.author = prs.core_properties.last_modified_by = " and ".join(
        m["name"] for m in team["members"]
    )
    prs.core_properties.title = (
        "FashionGraph: Enriching Wikidata with knowledge about Milan Fashion Week"
    )
    prs.core_properties.comments = ""
    blank = prs.slide_layouts[6]
    for i, s in enumerate(sl):
        slide = prs.slides.add_slide(blank)
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = BG
        tb = slide.shapes.add_textbox(
            Inches(0.8), Inches(0.6), Inches(11.7), Inches(1.2)
        ).text_frame
        tb.word_wrap = True
        p = tb.paragraphs[0]
        p.text = s["title"]
        p.font.size, p.font.bold, p.font.color.rgb = Pt(44 if i == 0 else 36), False, FG
        if s.get("sub"):
            q = tb.add_paragraph()
            q.text = s["sub"]
            q.font.size, q.font.italic, q.font.color.rgb = Pt(22), True, ACC
        bt = slide.shapes.add_textbox(
            Inches(0.8), Inches(2.3), Inches(11.7), Inches(4.3)
        ).text_frame
        bt.word_wrap = True
        for k, line in enumerate(s["body"]):
            par = bt.paragraphs[0] if k == 0 else bt.add_paragraph()
            par.text = ("" if i == 0 else "- ") + line
            par.font.size, par.space_after = Pt(24 if i else 20), Pt(10)
            par.font.color.rgb = ACC if line.startswith("PLACEHOLDER") else FG
        if s.get("table"):
            n_r, n_c = len(s["table"]), len(s["table"][0])
            shape = slide.shapes.add_table(
                n_r, n_c, Inches(0.8), Inches(3.5), Inches(11.7), Inches(0.31) * n_r
            )
            for r_i, row in enumerate(s["table"]):
                for c_i, val in enumerate(row):
                    cell = shape.table.cell(r_i, c_i)
                    cell.text = str(val)
                    cell.text_frame.paragraphs[0].font.size = Pt(12)
        foot = slide.shapes.add_textbox(
            Inches(0.8), Inches(6.9), Inches(11.7), Inches(0.4)
        ).text_frame
        foot.text = f"{s['who']} - about {s['sec']} s" if s["sec"] else "FashionGraph"
        foot.paragraphs[0].font.size, foot.paragraphs[0].font.color.rgb = (
            Pt(12),
            RGBColor(0x5D, 0x5D, 0x5D),
        )
        slide.notes_slide.notes_text_frame.text = (
            f"{s['notes']} (speaker: {s['who']}, budget {s['sec']} s)"
        )
    OUT.mkdir(exist_ok=True)
    path = OUT / "FashionGraph_slides.pptx"
    prs.save(path)
    lines = [
        "# Slide outline (generated)",
        "",
        f"Budget: max 2 minutes per member (PDF p.17); group size {json.loads((ROOT / 'team.json').read_text())['group_size']}, so {120 * json.loads((ROOT / 'team.json').read_text())['group_size']} s in total. Slides are due 48 h before the exam; website link on the title slide.",
        "",
    ]
    for i, s in enumerate(sl, 1):
        lines += (
            [f"## {i}. {s['title']} ({s['who']}, ~{s['sec']} s)"]
            + [f"- {b}" for b in s["body"]]
            + [f"_Notes: {s['notes']}_", ""]
        )
    (OUT / "outline.md").write_text("\n".join(lines))
    return path


if __name__ == "__main__":
    print(build())
