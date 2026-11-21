"""Original visuals for the site, generated at build time from repository artefacts (no hardcoded results).
Visual grammar (explained in the legend on the home page): solid = present in Wikidata or verified from CNMI;
dashed = missing / modelled-but-empty / pending. Nothing here invents data."""

from __future__ import annotations

import html
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _jl(rel: str) -> list[dict]:
    return [json.loads(x) for x in (ROOT / rel).read_text().splitlines() if x.strip()]


def gold_rows() -> list[dict]:
    return sorted(
        _jl("data/gold/gold_pilot.jsonl"), key=lambda r: (r["date"], r["time"])
    )


def clean_name(r: dict) -> str:
    return r["name_raw"].rstrip(" *").strip()


def evidence(name: str) -> dict:
    return json.loads((ROOT / "docs" / "kg-evidence" / f"{name}.json").read_text())


# ---------------------------------------------------------------- hero graph ----
W, H = 760, 520
MFW, EDN = (70, 260), (250, 260)


def _show_pos(i: int, n: int) -> tuple[float, float]:
    th = math.radians(-62 + 124 * i / (n - 1))
    return 250 + 250 * math.cos(th), 260 + 250 * math.sin(th)


STATUS_TEXT = {
    "address": "street address published",
    "invitation_only": "venue: by invitation (not published)",
    "digital": "digital show, no venue",
    "unpublished": "venue not published",
}


def hero_graph() -> str:
    rows = gold_rows()
    n = len(rows)
    nodes, ghosts, edges = [], [], []
    ghosts.append(
        f'<path class="ghost-edge" d="M{MFW[0] + 18} {MFW[1]} L{EDN[0] - 15} {EDN[1]}"/>'
    )
    edges.append(
        f'<path class="edge" pathLength="1" d="M{MFW[0] + 18} {MFW[1]} L{EDN[0] - 15} {EDN[1]}" data-i="-1"/>'
    )
    for i, r in enumerate(rows):
        x, y = _show_pos(i, n)
        d = f"M{EDN[0] + 15} {EDN[1]} Q{(EDN[0] + x) / 2 + 10:.1f} {(EDN[1] + y) / 2:.1f} {x - 9:.1f} {y:.1f}"
        ghosts.append(f'<path class="ghost-edge" d="{d}"/>')
        edges.append(f'<path class="edge" pathLength="1" d="{d}" data-i="{i}"/>')
        nm = clean_name(r)
        detail = f"{nm}: {r['date'][8:]} September {r['time']}, {STATUS_TEXT[r['venue_status']]}."
        if r["name_raw"].endswith("*"):
            detail += " Title carries an unexplained asterisk on the CNMI page."
        if r["entry_kind"] == "unclassified_entry":
            detail += " Listed by CNMI; not assumed to be a fashion brand."
        if nm == "PRADA":
            detail += " Prada exists in Wikidata as Q193136; the show does not."
        dashed = " nov" if r["venue_status"] != "address" else ""
        nodes.append(
            f'<g class="node show{dashed}" tabindex="0" role="button" data-i="{i}" data-detail="{html.escape(detail, quote=True)}" aria-label="{html.escape(detail, quote=True)}">'
            f'<circle class="ghost" cx="{x:.1f}" cy="{y:.1f}" r="9"/><circle class="fill" cx="{x:.1f}" cy="{y:.1f}" r="9"/>'
            f'<text class="label" x="{x + 17:.1f}" y="{y + 4:.1f}">{html.escape(nm)}</text></g>'
        )
    mfw = (
        f'<g class="node root"><circle class="fill" cx="{MFW[0]}" cy="{MFW[1]}" r="18"/>'
        f'<text class="label strong" x="{MFW[0]}" y="{MFW[1] + 40}" text-anchor="middle">Milan Fashion Week</text>'
        f'<text class="label sub" x="{MFW[0]}" y="{MFW[1] + 56}" text-anchor="middle">Wikidata Q130829</text></g>'
    )
    edn = (
        f'<g class="node edition" data-i="-1"><circle class="ghost" cx="{EDN[0]}" cy="{EDN[1]}" r="14"/><circle class="fill" cx="{EDN[0]}" cy="{EDN[1]}" r="14"/>'
        f'<text class="label sub" x="{EDN[0]}" y="{EDN[1] + 36}" text-anchor="middle">Spring/Summer 2027</text>'
        f'<text class="label sub" x="{EDN[0]}" y="{EDN[1] + 51}" text-anchor="middle">edition</text></g>'
    )
    return (
        f'<svg class="graph" viewBox="0 0 {W} {H}" role="group" aria-label="Graph of the pilot dataset: one Wikidata node and ten verified shows">'
        f"{''.join(ghosts)}{''.join(edges)}{mfw}{edn}{''.join(nodes)}</svg>"
    )


# ------------------------------------------------------------- schedule viz ----
def schedule_svg() -> str:
    rows = gold_rows()
    days = [f"2026-09-{d}" for d in range(22, 29)]
    x0, colw, y0, y1 = 64, 108, 40, 330
    t0, t1 = 9, 21
    ys = lambda t: y0 + (t - t0) / (t1 - t0) * (y1 - y0)
    out = [
        '<svg class="viz schedule" viewBox="0 0 840 380" role="img" aria-label="Schedule of the ten verified shows across 22 to 28 September 2026">'
    ]
    for h in range(9, 22, 3):
        out.append(
            f'<line class="grid" x1="{x0 - 8}" x2="{x0 + 7 * colw}" y1="{ys(h):.1f}" y2="{ys(h):.1f}"/><text class="tick" x="{x0 - 14}" y="{ys(h) + 4:.1f}" text-anchor="end">{h:02d}:00</text>'
        )
    for k, d in enumerate(days):
        cx = x0 + k * colw + colw / 2
        wd = ["Tue", "Wed", "Thu", "Fri", "Sat", "Sun", "Mon"][k]
        out.append(
            f'<line class="col" x1="{x0 + k * colw}" x2="{x0 + k * colw}" y1="{y0 - 8}" y2="{y1 + 6}"/><text class="tick" x="{cx:.1f}" y="{y1 + 26}" text-anchor="middle">{wd} {int(d[8:])}</text>'
        )
    out.append(
        f'<line class="col" x1="{x0 + 7 * colw}" x2="{x0 + 7 * colw}" y1="{y0 - 8}" y2="{y1 + 6}"/>'
    )
    seen: dict[tuple[str, int], int] = {}
    for i, r in enumerate(rows):
        k = days.index(r["date"])
        hh, mm = (int(v) for v in r["time"].split(":"))
        y = ys(hh + mm / 60)
        slot = seen.get((r["date"], round(y / 10)), 0)
        seen[(r["date"], round(y / 10))] = slot + 1
        cx = x0 + k * colw + 22 + slot * 0
        cls = "mark" if r["venue_status"] == "address" else "mark nov"
        nm = clean_name(r)
        if (
            len(nm) > 12 and " " in nm
        ):  # wrap long names on two lines instead of truncating them
            words = nm.split(" ")
            cut = min(
                range(1, len(words)),
                key=lambda k: abs(len(" ".join(words[:k])) - len(" ".join(words[k:]))),
            )
            lines = [" ".join(words[:cut]), " ".join(words[cut:])]
        else:
            lines = [nm]
        tspans = "".join(
            f'<tspan x="{cx + 12}" dy="{0 if j == 0 else 11}">{html.escape(ln)}</tspan>'
            for j, ln in enumerate(lines)
        )
        y_text = y + (4 if len(lines) == 1 else -1)
        out.append(
            f'<g class="{cls}" style="--d:{i * 70}ms"><title>{html.escape(nm)}, {r["time"]}, {STATUS_TEXT[r["venue_status"]]}</title>'
            f'<circle cx="{cx}" cy="{y:.1f}" r="7"/><text x="{cx + 12}" y="{y_text:.1f}">{tspans}</text></g>'
        )
    out.append("</svg>")
    return "".join(out)


# ----------------------------------------------------------------- ontology ----
def ontology_svg() -> str:
    def box(x, y, w, title, sub, cls):
        return (
            f'<g class="onode {cls}"><rect x="{x}" y="{y}" width="{w}" height="58" rx="4"/>'
            f'<text class="t" x="{x + w / 2}" y="{y + 25}" text-anchor="middle">{title}</text><text class="s" x="{x + w / 2}" y="{y + 44}" text-anchor="middle">{sub}</text></g>'
        )

    def edge(x1, y1, x2, y2, label, cls="", lx=None, ly=None, anchor="middle"):
        lx = (x1 + x2) / 2 if lx is None else lx
        ly = (y1 + y2) / 2 - 7 if ly is None else ly
        return f'<path class="oedge {cls}" d="M{x1} {y1} L{x2} {y2}" marker-end="url(#arr)"/><text class="el" x="{lx}" y="{ly}" text-anchor="{anchor}">{label}</text>'

    parts = [
        '<svg class="viz ontology" viewBox="0 0 840 360" role="img" aria-label="Ontology: fashion week, edition, show, brand, venue and collection and how they connect">',
        '<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="currentColor"/></marker></defs>',
        edge(250, 155, 150, 155, "superEvent", "", 200, 146),
        edge(500, 155, 400, 155, "superEvent", "", 450, 146),
        edge(610, 140, 690, 88, "organizer", "", 638, 100, "end"),
        edge(610, 155, 690, 175, "location", "", 650, 156),
        edge(600, 184, 700, 262, "presentsCollection", "dash", 650, 238, "end"),
        box(10, 126, 140, "Fashion week", "wd:Q130829", "reuse"),
        box(250, 126, 150, "Edition", "ex:FashionWeekEdition", "custom"),
        box(500, 126, 110, "Show", "ex:FashionShow", "custom"),
        box(690, 56, 140, "Brand", "schema:Brand", "reuse"),
        box(690, 146, 140, "Venue", "schema:Place", "reuse"),
        box(690, 236, 140, "Collection", "ex:FashionCollection", "empty"),
    ]
    parts.append(
        '<g class="olegend" transform="translate(10 318)"><rect class="reuse-k" x="0" y="0" width="22" height="12" rx="2"/><text x="30" y="10">reused vocabulary or existing Wikidata item</text>'
        '<rect class="custom-k" x="360" y="0" width="22" height="12" rx="2"/><text x="390" y="10">custom class (no Wikidata equivalent)</text>'
        '<rect class="empty-k" x="0" y="22" width="22" height="12" rx="2"/><text x="30" y="32">modelled, no data yet (CNMI rows do not name collections)</text></g>'
    )
    parts.append("</svg>")
    return "".join(parts)


# -------------------------------------------------------------------- bars ----
def _bar(label: str, n: int, total: int, note: str = "") -> str:
    pct = 0 if total == 0 else n / total * 100
    zero = " zero" if n == 0 else ""
    return (
        f'<div class="brow{zero}"><div class="bl">{html.escape(label)}</div><div class="bar" role="img" aria-label="{n} of {total}"><span style="--w:{pct:.1f}%"></span></div>'
        f'<div class="bv">{n} of {total}{(" " + html.escape(note)) if note else ""}</div></div>'
    )


def gap_bars() -> str:
    fw = evidence("09_fashion_weeks_structure")["response"]["results"]["bindings"]
    total = len(fw)
    c = {k: sum(1 for b in fw if k in b) for k in ("start", "loc", "edition", "partOf")}
    hs = evidence("08_milan_houses_coverage")["response"]["results"]["bindings"][0]
    g = lambda k: int(hs[k]["value"])
    return (
        f'<div class="bars"><h3>The {total} fashion weeks in Wikidata</h3>'
        + _bar("have a start date", c["start"], total)
        + _bar("have a location", c["loc"], total)
        + _bar("have edition items", c["edition"], total)
        + _bar("are part of something", c["partOf"], total)
        + f"<h3>The {g('houses')} fashion houses based in Milan</h3>"
        + _bar("have a website", g("withWebsite"), g("houses"))
        + _bar("have an inception date", g("withInception"), g("houses"))
        + _bar("record taking part in any event", g("withParticipantIn"), g("houses"))
        + "</div>"
    )


def audit_bars() -> str:
    a = json.loads((ROOT / "rdf/out/audit.json").read_text())

    def stack(title: str, data: dict, labels: dict) -> str:
        tot = sum(data.values())
        segs = "".join(
            f'<div class="seg s{i}" style="--w:{v / tot * 100:.2f}%" title="{html.escape(labels.get(k, k))}: {v}"><span>{v}</span></div>'
            for i, (k, v) in enumerate(data.items())
        )
        key = "".join(
            f'<li><i class="k s{i}"></i>{html.escape(labels.get(k, k))} <b>{v}</b></li>'
            for i, (k, v) in enumerate(data.items())
        )
        return f'<div class="stack"><h3>{html.escape(title)}</h3><div class="sbar">{segs}</div><ul class="skey">{key}</ul></div>'

    return (
        f'<div class="stacks"><p class="note">{a["total_triples"]} generated triples, shown three separate ways. Valid RDF, source support and novelty are different questions.</p>'
        + stack(
            "What the triples are",
            a["by_kind"],
            {
                "structural": "structural",
                "factual": "source-checkable facts",
                "provenance": "provenance",
                "link": "link to Wikidata",
            },
        )
        + stack(
            "Where they come from",
            a["by_vocabulary"],
            {"reused": "reused vocabulary", "custom": "custom ex: terms"},
        )
        + stack(
            "Who they are about",
            a["by_entity_novelty_status"],
            {
                "about_new_entity": "new local entities (edition, shows)",
                "unchecked_entity": "local brand and venue nodes, not linked",
                "about_existing_entity": "existing Wikidata items",
            },
        )
        + "</div>"
    )


# ---------------------------------------------------------- timeline / label ----
def timeline(steps: list[tuple[str, str, str]]) -> str:
    li = "".join(
        f'<li class="{st}"><i></i><div><b>{html.escape(t)}</b><p>{d}</p><span class="chip {st}">{lab}</span></div></li>'
        for t, d, st, lab in [
            (
                a,
                b,
                c,
                {
                    "done": "done",
                    "pending": "pending",
                    "ready": "built, not run",
                    "wip": "in progress",
                }[c],
            )
            for a, b, c in steps
        ]
    )
    return f'<ol class="timeline">{li}</ol>'


def care_label(res=None) -> str:
    gold = json.loads((ROOT / "data/gold/MANIFEST.json").read_text())
    audit = json.loads((ROOT / "rdf/out/audit.json").read_text())
    nq = len(list((ROOT / "queries").glob("*.rq")))
    rows = [
        ("Gap in Wikidata", f"found at edition level, {nq} queries", "done"),
        (
            "Gold dataset",
            f"v{gold['version']}, {gold['records']} of {gold['records']} records owner-verified",
            "done",
        ),
        (
            "Candidate RDF",
            f"{audit['total_triples']} triples, SHACL valid, {audit['factual_triples_about_new_entities']} potentially new",
            "done",
        ),
    ]
    if res:
        metrics, _ = res
        cells = metrics["cells"]
        f1 = [c["f1"] or 0.0 for c in cells]
        free = (metrics.get("meta", {}).get("budget") or {}).get("mode") == "free"
        rows += [
            (
                "Models compared",
                ", ".join(
                    sorted(short_model(m) for m in {c["model_id"] for c in cells})
                ),
                "done",
            ),
            (
                "Model results",
                f"{len(cells)} of 9 cells run ({sum(c['n_records'] for c in cells)} answers); F1 from {min(f1):.2f} to {max(f1):.2f}",
                "done",
            ),
            (
                "Cost",
                "free tiers only, nothing billed" if free else "see the Results page",
                "done",
            ),
            (
                "Still open",
                "course technique names (results stay provisional), written discussion, team details",
                "pending",
            ),
        ]
    else:
        models = [
            m["model_id"]
            for m in json.loads((ROOT / "models.json").read_text())["models"]
        ]
        cost = re.search(
            r"Total expected:\*\* \$[\d.]+ \(EUR ([\d.]+)\)",
            (ROOT / "docs/cost-estimate.md").read_text(),
        )
        rows += [
            ("Models configured", ", ".join(models), "ready"),
            ("Model results", "0 of 9 cells run", "pending"),
            (
                "Spending cap",
                f"EUR 5 enforced; expected about EUR {cost.group(1) if cost else '?'}",
                "ready",
            ),
        ]
    li = "".join(
        f'<div class="crow {st}"><dt>{html.escape(a)}</dt><dd>{html.escape(b)}</dd></div>'
        for a, b, st in rows
    )
    return f'<dl class="care">{li}</dl>'


def results_matrix(metrics: dict | None) -> str:
    techs = ["zero_shot", "few_shot", "step_by_step"]
    if metrics:
        models = sorted({c["model_id"] for c in metrics["cells"]})
        by = {(c["model_id"], c["technique"]): c for c in metrics["cells"]}
    else:
        models = [
            m["model_id"]
            for m in json.loads((ROOT / "models.json").read_text())["models"]
        ]
        by = {}
    head = "".join(f"<th scope='col'>{t.replace('_', ' ')}</th>" for t in techs)
    body = ""
    for m in models:
        tds = ""
        for t in techs:
            c = by.get((m, t))
            if c is None:
                tds += '<td class="cell pending"><span>pending</span></td>'
            else:
                f1 = c["f1"]
                tds += f'<td class="cell" style="--v:{(f1 or 0) * 100:.0f}%"><b>{"n/a" if f1 is None else f"{f1:.2f}"}</b><small>F1</small></td>'
        body += f"<tr><th scope='row'>{html.escape(m)}</th>{tds}</tr>"
    cap = (
        "F1 per model and prompting strategy"
        if metrics
        else "Nine cells, none run yet. Each cell fills in only from a validated real run."
    )
    return f'<div class="table-wrap"><table class="matrix"><caption>{cap}</caption><thead><tr><th></th>{head}</tr></thead><tbody>{body}</tbody></table></div>'


# --------------------------------------------------------------- highlighting ----
KW = r"SELECT|DISTINCT|WHERE|OPTIONAL|UNION|FILTER|REGEX|LIMIT|ORDER BY|GROUP BY|VALUES|SERVICE|BIND|COUNT|AS|ASK|IN|LANG|STR|BOUND|DESC"


def highlight_sparql(text: str) -> str:
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            out.append(f'<span class="c">{html.escape(line)}</span>')
            continue
        esc = html.escape(line)
        esc = re.sub(
            r"(&quot;[^&]*?&quot;(?:@\w+)?)", r'<span class="s">\1</span>', esc
        )
        esc = re.sub(rf"\b({KW})\b", r'<span class="k">\1</span>', esc)
        esc = re.sub(r"(\?\w+)", r'<span class="v">\1</span>', esc)
        esc = re.sub(
            r"\b((?:wd|wdt|wikibase|rdfs|schema|bd|mwapi):[\w\-]*)",
            r'<span class="p">\1</span>',
            esc,
        )
        out.append(esc)
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------ analysis ----
def analysis_html(an: dict) -> str:
    """Tables from results/analysis.json (genuine runs only). Descriptive: the interpretation is written by people."""
    fx = lambda x: "n/a" if x is None else f"{x:.3f}"

    def tab(title, key, first):
        rows = "".join(
            f"<tr><th scope='row'>{html.escape(k)}</th><td>{fx(s['mean_f1'])}</td><td>{fx(s['mean_precision'])}</td><td>{fx(s['mean_recall'])}</td><td>{fx(s['mean_invalid_output_rate'])}</td>"
            f"<td>{html.escape(', '.join(f'{e}: {n}' for e, n in s['top_errors'].items()) or 'none')}</td></tr>"
            for k, s in an[key].items()
        )
        return f"<h3>{title}</h3><div class='table-wrap'><table><thead><tr><th>{first}</th><th>mean F1</th><th>mean P</th><th>mean R</th><th>invalid</th><th>most common errors</th></tr></thead><tbody>{rows}</tbody></table></div>"

    ex = []
    for cell, c in an["cells"].items():
        if c["examples"]:
            items = "".join(
                f"<li><code>{html.escape(e['record'])}</code> {html.escape(d['field'])}: expected <code>{html.escape(str(d['expected']))}</code>, got <code>{html.escape(str(d['predicted']))}</code> ({html.escape(d['error'])})</li>"
                for e in c["examples"]
                for d in e["diffs"]
            )
            ex.append(
                f"<h3>{html.escape(cell)}</h3><p class='note'>{c['exact_records']} of {c['n_records']} records exactly correct.</p><ul>{items}</ul>"
            )
    vt = an.get("validated_triples", {})
    return (
        tab("By model (mean over its three techniques)", "by_model", "model")
        + tab(
            "By prompting technique (mean over its three models)",
            "by_technique",
            "technique",
        )
        + f"<p class='note'>{html.escape(an['note'])} Validated triples exported from exactly-correct, SHACL-valid predictions: {vt.get('total', 0)}.</p>"
        + "<h2>Example errors</h2>"
        + ("".join(ex) or "<p>No errors were recorded.</p>")
        + "<p class='placeholder'><strong>Pending.</strong> The written discussion of what these differences mean is added by the team; none is generated automatically.</p>"
    )


# ================================================================ real results ====
TECH_LABEL = {
    "zero_shot": "zero-shot",
    "few_shot": "few-shot",
    "step_by_step": "step-by-step",
}
TECHS = ("zero_shot", "few_shot", "step_by_step")


def load_real_results() -> tuple[dict, dict] | None:
    """(metrics, analysis) from results/ for a genuine, non-mock run; None otherwise."""
    m, a = ROOT / "results" / "metrics.json", ROOT / "results" / "analysis.json"
    if not (m.exists() and a.exists()):
        return None
    md, an = json.loads(m.read_text()), json.loads(a.read_text())
    if md.get("is_mock") or an.get("is_mock"):
        raise RuntimeError("refusing to display mock results")
    return md, an


def short_model(mid: str) -> str:
    return mid.split("/")[-1]


def findings(metrics: dict, analysis: dict) -> list[str]:
    """Plain descriptive sentences computed from the numbers. No interpretation is generated."""
    cells = metrics["cells"]
    by: dict[str, dict] = {}
    for c in cells:
        by.setdefault(c["model_id"], {})[c["technique"]] = c
    out = []
    for mid, ts in by.items():
        f1 = {t: (c["f1"] or 0.0) for t, c in ts.items()}
        lo, hi = min(f1, key=f1.get), max(f1, key=f1.get)
        inv = sum(round(c["invalid_output_rate"] * c["n_records"]) for c in ts.values())
        n = sum(c["n_records"] for c in ts.values())
        gen = sum(
            1
            for k, v in analysis["cells"].items()
            if k.startswith(mid + " |")
            for o in v.get("outcomes", {}).values()
            if o.get("error_class") == "provider_generation_failure"
        )
        if abs(f1[hi] - f1[lo]) < 0.0005:
            s = f"{short_model(mid)} scored F1 {f1[hi]:.2f} under all three prompting strategies"
        else:
            s = f"{short_model(mid)} scored F1 from {f1[lo]:.2f} ({TECH_LABEL[lo]}) to {f1[hi]:.2f} ({TECH_LABEL[hi]})"
        s += (
            f", with {inv} of {n} answers invalid"
            + (f" ({gen} of them provider-side generation failures)" if gen else "")
            + "."
            if inv
            else ", with no invalid answers."
        )
        out.append(s)
    varied = [
        short_model(m)
        for m, ts in by.items()
        if max(c["f1"] or 0 for c in ts.values())
        - min(c["f1"] or 0 for c in ts.values())
        >= 0.0005
    ]
    tot_exact = sum(c["exact_records"] for c in analysis["cells"].values())
    tot = sum(c["n_records"] for c in analysis["cells"].values())
    out.append(
        f"{tot_exact} of {tot} answers were exactly correct on every scored field and valid RDF."
    )
    out.append(
        "The prompting strategy changed the score of "
        + (", ".join(varied) if varied else "no model")
        + (" only." if len(varied) == 1 else ".")
    )
    return out


def f1_chart(metrics: dict) -> str:
    cells = metrics["cells"]
    models = sorted({c["model_id"] for c in cells})
    by = {(c["model_id"], c["technique"]): c["f1"] or 0.0 for c in cells}
    x0, gw, bw, gap, y0, h = 56, 232, 58, 10, 24, 230
    out = [
        '<svg class="viz chart" viewBox="0 0 800 340" role="img" aria-label="F1 score for each model under each prompting strategy">'
    ]
    for i in range(6):
        v = i / 5
        y = y0 + h - v * h
        out.append(
            f'<line class="grid" x1="{x0 - 6}" x2="780" y1="{y:.1f}" y2="{y:.1f}"/><text class="tick" x="{x0 - 12}" y="{y + 4:.1f}" text-anchor="end">{v:.1f}</text>'
        )
    for g, m in enumerate(models):
        gx = x0 + 30 + g * gw
        for t_i, t in enumerate(TECHS):
            v = by.get((m, t), 0.0)
            bh = max(v * h, 1.5)
            bx = gx + t_i * (bw + gap)
            out.append(
                f'<g class="gbar t{t_i}"><title>{html.escape(short_model(m))}, {TECH_LABEL[t]}: F1 {v:.3f}</title>'
                f'<rect x="{bx}" y="{y0 + h - bh:.1f}" width="{bw}" height="{bh:.1f}"/>'
                f'<text class="val" x="{bx + bw / 2}" y="{y0 + h - bh - 6:.1f}" text-anchor="middle">{v:.2f}</text></g>'
            )
        out.append(
            f'<text class="mname" x="{gx + (3 * bw + 2 * gap) / 2}" y="{y0 + h + 28}" text-anchor="middle">{html.escape(short_model(m))}</text>'
        )
    lx = x0 + 6
    for t_i, t in enumerate(TECHS):
        out.append(
            f'<rect class="lk t{t_i}" x="{lx + t_i * 150}" y="312" width="14" height="14"/><text class="tick" x="{lx + t_i * 150 + 22}" y="324">{TECH_LABEL[t]}</text>'
        )
    out.append("</svg>")
    return "".join(out)


def outcome_strips(analysis: dict) -> str:
    gold = {f"mfw-ss27-{g['cnmi_event_id']}": g for g in gold_rows()}
    order = [f"mfw-ss27-{g['cnmi_event_id']}" for g in gold_rows()]
    models = sorted({k.split(" | ")[0] for k in analysis["cells"]})
    blocks = []
    for m in models:
        rows = ""
        for t in TECHS:
            c = analysis["cells"][f"{m} | {t}"]["outcomes"]
            sq = ""
            for rid in order:
                o = c[rid]
                nm = clean_name(gold[rid])
                lab = {
                    "exact": "exactly correct",
                    "errors": f"{o['n_diffs']} field error(s)",
                    "invalid": "no valid output"
                    + (
                        " (provider generation failure)" if o.get("error_class") else ""
                    ),
                }[o["kind"]]
                sq += f'<i class="sq {o["kind"]}" title="{html.escape(nm)}: {lab}" role="img" aria-label="{html.escape(nm)}: {lab}"></i>'
            rows += f'<div class="srow"><span class="st">{TECH_LABEL[t]}</span><span class="sqs">{sq}</span></div>'
        blocks.append(
            f'<div class="sblock"><h3>{html.escape(short_model(m))}</h3>{rows}</div>'
        )
    legend = '<ul class="legend slegend"><li><i class="sq exact"></i>exactly correct</li><li><i class="sq errors"></i>valid answer with field errors</li><li><i class="sq invalid"></i>no valid output</li></ul>'
    return f'<div class="strips" aria-label="Outcome of each of the 90 answers, in show order">{"".join(blocks)}{legend}<p class="note">Each square is one record, in schedule order (the same order as the Data page). Hover or focus a square for the show and what happened.</p></div>'


def usage_table(analysis: dict) -> str:
    rows = "".join(
        f"<tr><th scope='row'>{html.escape(m)}</th><td>{u['answered']}</td><td>{u['input_tokens']:,}</td><td>{u['output_tokens']:,}</td></tr>"
        for m, u in sorted(analysis["usage"].items())
    )
    return f"<div class='table-wrap'><table><thead><tr><th>model</th><th>answers</th><th>input tokens</th><th>output tokens (incl. any reasoning)</th></tr></thead><tbody>{rows}</tbody></table></div>"


def conditions_table() -> str:
    raw = json.loads((ROOT / "models.free.json").read_text())["models"]
    temp = {"gemini": "not sent (deprecated for Gemini 3.x)", "groq": "0"}
    think = {
        "gemini-3.5-flash-lite": "thinking level MINIMAL",
        "openai/gpt-oss-120b": "reasoning effort low (its minimum), reasoning excluded from the answer",
        "qwen/qwen3.8-27b": "reasoning effort none (instruct mode)",
    }
    rows = "".join(
        f"<tr><th scope='row'>{html.escape(m['model_id'])}</th><td>{'Google AI Studio' if m['provider'] == 'gemini' else 'GroqCloud'}, free tier</td><td>{html.escape(think[m['model_id']])}</td><td>{temp[m['provider']]}</td><td>{m['max_output_tokens']}</td></tr>"
        for m in raw
    )
    return f"<div class='table-wrap'><table><thead><tr><th>model</th><th>access</th><th>reasoning</th><th>temperature</th><th>output cap (tokens)</th></tr></thead><tbody>{rows}</tbody></table></div>"


def run_record_md() -> str:
    t = (ROOT / "docs" / "experiment-protocol.md").read_text()
    i = t.find("## Run log")
    return (
        t[i:].replace("## Run log: free-tier experiment (2026-11-19)", "").strip()
        if i >= 0
        else ""
    )
