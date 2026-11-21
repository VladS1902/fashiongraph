"""Static site generator (GitHub Pages compatible). Pages are rendered from repository artefacts:
docs/*.md, queries/*.rq (+ docs/kg-evidence/*.json), experiments/prompts/*.txt, data/, rdf/out/*.
No result numbers live in this file: results come only from results/metrics.json (never from mock runs)."""

from __future__ import annotations

import hashlib
import html
import importlib.util
import json
import re
import shutil
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "fg_viz", Path(__file__).with_name("viz.py")
)
viz = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(viz)
OUT = ROOT / "site" / "dist"
SITE_TITLE = "FashionGraph"
SUBTITLE = "Enriching Wikidata with Knowledge about Milan Fashion Week"
PAGES = [
    ("index", "Home"),
    ("context", "Context"),
    ("methodology", "Methodology"),
    ("gap", "Wikidata gap"),
    ("ontology", "Ontology"),
    ("sparql", "SPARQL"),
    ("data", "Data & gold"),
    ("models", "Models & prompts"),
    ("rdf", "RDF"),
    ("results", "Results"),
    ("references", "References"),
    ("team", "Team"),
]
DEKS = {
    "context": "A public calendar full of dated, structured facts that Wikidata does not hold.",
    "methodology": "Seven steps from a missing-knowledge question to a published, checkable result.",
    "gap": "What Wikidata holds about Milan Fashion Week, and the entity-level queries that show what it lacks.",
    "ontology": "Six concepts, mostly borrowed vocabulary, three small custom classes.",
    "sparql": "Seventeen queries, each with its recorded run and first result rows.",
    "data": "The official calendar, how rows became a verified gold set, and where it is still weak.",
    "models": "Three models, three prompting strategies, one fixed protocol and a hard spending cap.",
    "rdf": "Valid, supported and new are three different questions. Here is how the triples answer each.",
    "results": "Nothing here is a result until a validated run produces one.",
    "references": "Sources, tools and licensing notes.",
    "team": "Who did what, once the team confirms it.",
}
STATUS_BANNER = (
    "<b>Work in progress.</b> The gap analysis, source dataset, ontology and RDF pipeline exist; "
    "no real LLM experiment has been run yet, so no model results are shown."
)
MD = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists"])


def md(text: str) -> str:
    MD.reset()
    h = MD.convert(text)
    for n in range(5, 0, -1):  # demote headings: page title is the only h1
        h = h.replace(f"<h{n}>", f"<h{n + 1}>").replace(f"</h{n}>", f"</h{n + 1}>")
    h = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" rel="noopener"', h)
    return re.sub(r"<table>", '<div class="table-wrap"><table>', h).replace(
        "</table>", "</table></div>"
    )


def read(rel: str) -> str:
    return (ROOT / rel).read_text()


def load_results():
    """(metrics, analysis|None) for a genuine run in results/, else None. Mock data is refused, never shown."""
    mp = ROOT / "results" / "metrics.json"
    if not mp.exists():
        return None
    m = json.loads(mp.read_text())
    if m.get("is_mock"):
        raise RuntimeError("refusing to render mock metrics as results")
    ap = ROOT / "results" / "analysis.json"
    a = json.loads(ap.read_text()) if ap.exists() else None
    if a and a.get("is_mock"):
        raise RuntimeError("refusing to render a mock analysis as results")
    return m, a


def status_banner() -> str:
    try:
        res = load_results()
    except RuntimeError:
        res = None
    if res:
        n = sum(c["n_records"] for c in res[0]["cells"])
        return (
            f"<b>Experiment complete.</b> All {len(res[0]['cells'])} model cells ({n} answers) ran on free tiers and are scored on the "
            '<a href="results.html">Results</a> page. The prompting techniques are still provisional, each cell has only ten records, and the written discussion is pending.'
        )
    return STATUS_BANNER


def dek_for(slug: str) -> str:
    if slug == "results" and load_results():
        return "Ninety answers from three models under three prompting strategies: what came back, where it went wrong, and what it does not show."
    return DEKS[slug]


def research_note() -> str:
    if load_results():
        return (
            "<p class='note'>Questions 3 and 4 are answered descriptively on the <a href='results.html'>Results</a> page (ten records, one source, provisional techniques). "
            "Question 5 is partly answered: exactly-correct, valid predictions are counted there, and novelty against Wikidata is audited on the <a href='rdf.html'>RDF</a> page.</p>"
        )
    return research_note()


def model_triples_html() -> str:
    res = load_results()
    if not res or not res[1]:
        return ""
    vt = res[1].get("validated_triples", {})
    per = vt.get("per_cell", {})
    top = max(per.values()) if per else 0
    links = "".join(
        f'<li><a href="results-data/rdf/{html.escape(p.name)}">{html.escape(p.name)}</a></li>'
        for p in sorted((ROOT / "results" / "rdf").glob("*.ttl"))
    )
    return (
        "<h2>Triples produced by the models</h2>"
        "<p>Predictions that were exactly correct on every scored field, with verbatim evidence, were converted by the same deterministic code and checked with SHACL. "
        f"The files hold {vt.get('total', 0)} triples in total across {len(per)} model-and-strategy cells. These repeat the same ten shows' facts in every cell, so the number of distinct validated facts is about {top}, not {vt.get('total', 0)}. "
        "Wrong or unsupported predictions are never exported as knowledge.</p>"
        f"<ul class='qlist'>{links}</ul>"
    )


def css_version() -> str:
    h = hashlib.sha256()
    for n in ("style.css", "app.js"):
        h.update((ROOT / "site" / "assets" / n).read_bytes())
    return h.hexdigest()[:8]


def nav(current: str) -> str:
    items = "".join(
        f'<li><a href="{s}.html"{" aria-current=page" if s == current else ""}>{t}</a></li>'
        for s, t in PAGES
    )
    return (
        '<nav aria-label="Main menu"><button class="menu-btn" type="button" aria-expanded="false" aria-controls="menu">Menu</button>'
        f'<ul id="menu">{items}</ul></nav>'
    )


def page(slug: str, title: str, body: str, dek: str = "", hero: str = "") -> str:
    v = css_version()
    head = (
        ""
        if hero
        else f'<div class="page-head"><h1>{html.escape(title)}</h1><p class="dek">{html.escape(dek)}</p></div>'
    )
    mark = (
        '<svg viewBox="0 0 34 20" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8">'
        '<circle cx="5" cy="10" r="3.5" fill="currentColor"/><path d="M9 10h8" stroke-dasharray="2.5 2.5"/><circle cx="29" cy="10" r="3.5" stroke-dasharray="2.6 2"/></svg>'
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(title)} | {SITE_TITLE}</title>"
        f'<meta name="description" content="{html.escape(dek or SUBTITLE)}">'
        '<script>document.documentElement.className+=" js"</script>'
        f'<link rel="stylesheet" href="assets/style.css?v={v}"></head><body>'
        '<a class="skip" href="#main">Skip to content</a>'
        f'<header class="site-head"><div class="wrap"><a class="brand" href="index.html">{mark}{SITE_TITLE}</a>{nav(slug)}</div></header>'
        f'<div class="status" role="note"><div class="wrap">{status_banner()}</div></div>'
        f'<main id="main"><div class="wrap">{hero}{head}{body}</div></main>'
        f'<script src="assets/app.js?v={v}"></script></body></html>'
    )


def code(text: str) -> str:
    return f"<pre><code>{html.escape(text)}</code></pre>"


# ---- page bodies -------------------------------------------------------------------
def body_index() -> str:
    gold = json.loads(read("data/gold/MANIFEST.json"))
    n = gold["records"]
    res = load_results()
    goal = (
        "and compared three language models on extracting such facts."
        if res
        else "and are testing whether three language models can extract such facts reliably."
    )
    hero = (
        '<section class="hero" aria-labelledby="hero-h">'
        '<div><h1 id="hero-h">One node on Wikidata. A whole fashion week missing.</h1>'
        f'<p class="dek">Wikidata describes Milan Fashion Week as a single item. We checked the official September 2026 calendar, verified {n} shows against it, {goal}</p>'
        '<div class="cta"><a class="btn primary" href="gap.html">See the gap</a><a class="btn" href="results.html">See the results</a></div></div>'
        f'<div><figure class="stage" style="margin:0">{viz.hero_graph()}'
        f'<div class="stage-foot"><span class="count" id="hero-count">{n} of {n} shows verified from CNMI</span>'
        '<button class="replay" id="replay" type="button">Replay</button>'
        '<ul class="legend"><li><i></i>in Wikidata</li><li><i class="v"></i>verified at CNMI, not in Wikidata</li><li><i class="n"></i>verified, venue not published</li><li><i class="g"></i>missing</li></ul></div>'
        '<p class="swipe">Swipe the graph sideways to see every show.</p>'
        '<p id="node-detail" aria-live="polite">Hover or focus a show for its date, time and venue status.</p></figure></div></section>'
    )
    glance = ""
    if res and res[1]:
        glance = (
            "<h2>What the models did</h2><p>Ten verified shows, three language models, three prompting strategies, 90 answers. Everything below is computed from the scored answers.</p>"
            + '<ul class="findings">'
            + "".join(
                f"<li>{html.escape(s)}</li>" for s in viz.findings(res[0], res[1])
            )
            + "</ul>"
            + viz.results_matrix(res[0])
            + '<p><a href="results.html">Charts, every answer and the error examples</a></p>'
        )
    if res:
        step4 = (
            "Test three language models",
            f"{sum(c['n_records'] for c in res[0]['cells'])} answers from three models on free tiers, scored and analysed.",
            "done",
        )
        step5 = (
            "Publish and report",
            "This site and the report rebuild from the validated results. Deployment awaits approval.",
            "wip",
        )
    else:
        step4 = (
            "Test three language models",
            "Configured, costed and capped at EUR 5. Not run yet.",
            "pending",
        )
        step5 = (
            "Publish and report",
            "This site and the report rebuild themselves from validated results once they exist.",
            "wip",
        )
    tail = (
        " Three language models were then compared under three prompting strategies on the ten verified records, using only free-tier APIs. "
        + " ".join(viz.findings(res[0], res[1])[:3])
        + " The prompting techniques are provisional and the sample is small, so these are descriptive results, not significance claims."
        if res and res[1]
        else " The planned comparison of three language models under three prompting strategies is specified and tested on mock data only; it has not been run."
    )
    body = (
        "<h2>The gap</h2><p>The top-level item exists and is well described. Below it, Wikidata holds no edition, no shows, and no record of any Milan fashion house taking part. "
        "These counts come from the recorded query results, not from the missing properties of one page.</p>"
        + viz.gap_bars()
        + '<p><a href="gap.html">How we checked, with all queries</a></p>'
        + glance
        + "<h2>Where the project stands</h2>"
        + viz.care_label(res)
        + "<h2>How it works</h2>"
        + viz.timeline(
            [
                (
                    "Find the gap",
                    "Bounded SPARQL on Wikidata, with a control search to rule out false negatives.",
                    "done",
                ),
                (
                    "Verify the source",
                    "Parse the official CNMI calendar and check ten rows by two independent routes and by hand.",
                    "done",
                ),
                (
                    "Model the graph",
                    "Reuse schema.org and Wikidata; add three small classes; validate with SHACL.",
                    "done",
                ),
                step4,
                step5,
            ]
        )
        + '<h2>Abstract</h2><p>Wikidata describes <a href="https://www.wikidata.org/wiki/Q130829" rel="noopener">Milan Fashion Week</a> as a single item, '
        "but we found no items for its individual editions or shows, and none of 19 Milan fashion houses records participating in any event. "
        "This project identifies that gap with SPARQL, builds a provenance-rich gold dataset from the official "
        '<a href="https://www.cameramoda.it/en/milano-moda-donna/calendar/" rel="noopener">CNMI calendar</a> for Milano Moda Donna Spring/Summer 2027 (22-28 September 2026), '
        "defines a small ontology, and converts verified extractions into candidate RDF triples with deterministic code."
        + html.escape(tail)
        + "</p><h2>Team</h2><p>"
        + ", ".join(html.escape(n) for n, _ in TEAM)
        + '. See the <a href="team.html">Team</a> page.</p>'
    )
    return hero + body


def body_context() -> str:
    return (
        '<p><a href="https://www.wikidata.org/wiki/Q130829" rel="noopener">Milan Fashion Week</a> (Settimana della moda di Milano) is an Italian fashion trade event '
        'organised by the <a href="https://www.cameramoda.it/en/" rel="noopener">Camera Nazionale della Moda Italiana (CNMI)</a>. Wikidata records it as an instance of '
        "<em>fashion week</em> located in Milan, with inception 1958 and three significant places.</p>"
        "<p>The edition studied here is <strong>Milano Moda Donna Spring/Summer 2027, 22-28 September 2026</strong>. "
        "CNMI's calendar lists fashion shows, presentations, events and appointments; this pilot uses 63 fashion-show rows and a documented sample of 10.</p>"
        "<p>Why it matters for knowledge engineering: the calendar is public, structured and dated, yet its show-level facts (who showed, when, where) have no counterpart in Wikidata. "
        "That makes it a concrete test of whether language models can extract grounded facts that enrich an open knowledge graph.</p>"
        "<h2>Research questions</h2><ol>"
        "<li>What fashion-show knowledge is already in Wikidata for this edition?</li>"
        "<li>Which entity-level relations are demonstrably absent?</li>"
        "<li>How well do three language models extract correct show facts from the same official source text?</li>"
        "<li>How do three prompting strategies change precision, recall, validity and hallucination?</li>"
        "<li>How many correct, non-duplicate RDF triples result, and which are new to the graph?</li></ol>"
        "<p class='note'>Questions 3-5 are open: no model experiment has been run.</p>"
    )


def body_methodology() -> str:
    steps = [
        (
            "Requirements",
            "Mandatory rules from the course guidelines traced to evidence: SPARQL keywords, prompting techniques, model comparison, website.",
            "done",
        ),
        (
            "Feasibility",
            "Bounded SPARQL on the Wikidata Query Service with cached, timestamped responses. Result: go, narrowed to edition-level relations.",
            "done",
        ),
        (
            "Source data",
            "Parse the official CNMI calendar deterministically, record provenance, build a 10-record gold set under written annotation rules, verify by a second parsing route and by the project owner.",
            "done",
        ),
        (
            "Schema and RDF",
            "Reuse schema.org and Wikidata; add a minimal <code>ex:</code> extension; convert records to Turtle with code; validate syntax and SHACL; audit validity, source support and novelty separately.",
            "done",
        ),
        (
            "Experiment",
            "3 models x 3 prompting strategies x 10 records, identical inputs, checkpointed and resumable, under an enforced EUR 5 cap. Specified and tested on mock data; not yet run.",
            "pending",
        ),
        (
            "Evaluation",
            "Field-level precision, recall and F1, invalid-output rate, unsupported-assertion rate, RDF validity, error taxonomy. Implemented and unit-tested; no real data yet.",
            "ready",
        ),
        (
            "Website and report",
            "This site, generated from repository artefacts.",
            "wip",
        ),
    ]
    if load_results():
        done = {
            "Experiment": "3 models x 3 prompting strategies x 10 records = 90 calls on free tiers, checkpointed and resumable. It was interrupted and resumed several times without repeating a successful call.",
            "Evaluation": "Field-level precision, recall and F1, invalid-output rate, unsupported-assertion rate, RDF validity, an error taxonomy and a per-record outcome for every answer.",
        }
        steps = [(a, done.get(a, b), "done" if a in done else c) for a, b, c in steps]
    tools = [
        ("Wikidata Query Service", "https://query.wikidata.org/"),
        ("Python 3.12", "https://www.python.org/"),
        ("RDFLib", "https://rdflib.readthedocs.io/"),
        ("pySHACL", "https://github.com/RDFLib/pySHACL"),
        ("pytest", "https://docs.pytest.org/"),
        ("Ruff", "https://docs.astral.sh/ruff/"),
        ("Python-Markdown", "https://python-markdown.github.io/"),
    ]
    tl = "".join(f'<li><a href="{u}" rel="noopener">{n}</a></li>' for n, u in tools)
    return (
        "<h2>Steps</h2>"
        + viz.timeline(steps)
        + "<h2>How the gap was identified</h2><p>See <a href='gap.html'>Wikidata gap</a>: entity-level SPARQL queries (all on <a href='sparql.html'>SPARQL</a>) with a control search to rule out false negatives.</p>"
        + f"<h2>Tools</h2><ul>{tl}</ul>"
        + '<h2 id="challenges">Challenges and how we addressed them</h2>'
        + body_challenges()
        + "<h2>Reproduce</h2>"
        + code(
            "make all     # inputs, RDF, audit, mock pipeline, report, site, slides, lint, tests\nmake readiness   # pre-flight for the real run (no network, no paid calls)"
        )
    )


def body_sparql() -> str:
    qs = sorted((ROOT / "queries").glob("*.rq"))
    parts = [
        "<p>All queries run against the Wikidata Query Service. Together they use DISTINCT, OPTIONAL, UNION, FILTER, REGEX, LIMIT and ORDER BY (checked by an automated test). Each shows its recorded execution and first result rows.</p>",
        '<ul class="qlist">'
        + "".join(f'<li><a href="#{q.stem}">{html.escape(q.name)}</a></li>' for q in qs)
        + "</ul>",
    ]
    for q in qs:
        ev = ROOT / "docs" / "kg-evidence" / f"{q.stem}.json"
        meta = "<p class='note'>No successful execution is recorded for this query.</p>"
        if ev.exists():
            c = json.loads(ev.read_text())
            b = c["response"]["results"]["bindings"]
            vs = c["response"]["head"]["vars"]
            hdr = "".join(f"<th>{html.escape(v)}</th>" for v in vs)
            rows = "".join(
                "<tr>"
                + "".join(
                    f"<td>{html.escape(r.get(v, {}).get('value', '').split('/')[-1][:48])}</td>"
                    for v in vs
                )
                + "</tr>"
                for r in b[:4]
            )
            meta = (
                f"<p class='note'>Executed {c['timestamp_utc'][:19]}Z, HTTP {c['http_status']}, {len(b)} rows (first 4 shown).</p>"
                f"<div class='table-wrap'><table><thead><tr>{hdr}</tr></thead><tbody>{rows or '<tr><td>no rows (a recorded negative result)</td></tr>'}</tbody></table></div>"
            )
        parts.append(
            f"<h2 id='{q.stem}'>{html.escape(q.name)}</h2><pre><code>{viz.highlight_sparql(q.read_text())}</code></pre>{meta}"
        )
    return "".join(parts)


def body_data() -> str:
    return (
        '<figure class="viz-fig">'
        + viz.schedule_svg()
        + "<figcaption>The ten verified shows by day and time. Filled dots have a published street address; dashed dots have no published venue (by invitation, empty, or digital).</figcaption></figure>"
        + md(read("docs/data-coverage.md"))
        + "<h2>Annotation guidelines</h2>"
        + md(read("docs/annotation-guidelines.md"))
        + "<h2>Review table</h2>"
        + md(read("docs/gold-review.md"))
    )


def body_models() -> str:
    parts = [
        md(read("docs/experiment-protocol.md")),
        "<h2>Model selection</h2>" + md(read("docs/model-selection.md")),
        "<h2>Zero-cost alternative</h2>"
        + md(read("docs/free-tier-investigation.md"))
        + md(read("docs/free-tier-plan.md")),
        "<h2>All prompts (version v0.2-provisional)</h2>",
        "<p>Technique names are provisional until confirmed against the course materials.</p>",
    ]
    for n in ("system", "zero_shot", "few_shot", "step_by_step"):
        parts.append(f"<h3>{n}.txt</h3>{code(read(f'experiments/prompts/{n}.txt'))}")
    ex = "\n".join(
        json.dumps(json.loads(line), ensure_ascii=False, indent=1)
        for line in read("data/experiment/fewshot_train.jsonl").splitlines()
    )
    parts.append(
        "<h3>Few-shot examples inserted at {examples} (training split, disjoint from the evaluated records)</h3>"
        + code(ex)
    )
    return "".join(parts)


def body_rdf() -> str:
    ttl = "\n".join(read("rdf/out/gold_pilot.ttl").splitlines()[:70])
    return (
        viz.audit_bars()
        + md(read("docs/rdf-audit.md"))
        + "<h2>Example output</h2><p>The first 70 lines of the generated Turtle.</p>"
        + code(ttl)
        + model_triples_html()
    )


def body_gap() -> str:
    return viz.gap_bars() + md(read("docs/kg-feasibility.md"))


def body_ontology() -> str:
    return (
        '<figure class="viz-fig">'
        + viz.ontology_svg()
        + "<figcaption>How the six concepts connect. Solid outlines reuse existing vocabulary; dashed blue outlines are the custom classes, justified because Wikidata models no fashion-week editions.</figcaption></figure>"
        + md(read("docs/ontology.md"))
        + "<h2>Vocabulary file</h2>"
        + code(read("ontology/fashiongraph.ttl"))
        + "<h2>SHACL shapes</h2>"
        + code(read("rdf/shapes.ttl"))
    )


def body_results() -> str:
    res = load_results()
    if not res:
        return (
            "<p class='placeholder'><strong>Pending.</strong> No real model experiment has been run, so no quantitative results are shown. "
            "A deterministic mock run exists only to test the pipeline; its output is deliberately not displayed here. The <a href='report.md'>project report (Markdown)</a> is generated from the same artefacts.</p>"
            + viz.results_matrix(None)
            + "<h2>What will appear here</h2><ul><li>Precision, recall and F1 per model and prompting strategy (n = 10 records per cell, no significance claims).</li>"
            "<li>Invalid-output, unsupported-assertion and RDF-validity rates; error taxonomy counts.</li>"
            "<li>Validated novel triples after manual review.</li></ul>"
            "<h2>Differences in behaviour between models</h2><p class='placeholder'><strong>Pending.</strong> To be written from real outputs.</p>"
            "<h2>Effect of the prompting strategies</h2><p class='placeholder'><strong>Pending.</strong> To be written from real outputs.</p>"
        )
    d, an = res
    head = "<tr><th>model</th><th>technique</th><th>P</th><th>R</th><th>F1</th><th>invalid</th><th>unsupported</th><th>RDF conforms</th></tr>"

    def fx(x):
        return "n/a" if x is None else f"{x:.3f}"

    rows = "".join(
        f"<tr><td>{html.escape(c['model_id'])}</td><td>{html.escape(c['technique'])}</td><td>{fx(c['precision'])}</td><td>{fx(c['recall'])}</td><td>{fx(c['f1'])}</td><td>{fx(c['invalid_output_rate'])}</td><td>{fx(c['unsupported_assertion_rate'])}</td><td>{fx(c['rdf_conforms_rate'])}</td></tr>"
        for c in d["cells"]
    )
    table = f"<div class='table-wrap'><table><thead>{head}</thead><tbody>{rows}</tbody></table></div>"
    m = d.get("meta", {})
    note = f"Techniques: {html.escape(str(m.get('techniques_status')))}. Prompt version {html.escape(str(m.get('prompt_version')))}. Small n per cell: descriptive only, no significance claims."
    if (m.get("budget") or {}).get("mode") == "free":
        note += " Free-tier run: nothing was billed."
    elif m.get("budget"):
        note += f" Budget spent: EUR {m['budget']['spent_eur']:.4f} of EUR {m['budget']['cap_eur']}."
    out = ""
    if an:
        out += (
            '<ul class="findings">'
            + "".join(f"<li>{html.escape(s)}</li>" for s in viz.findings(d, an))
            + "</ul>"
        )
    out += (
        "<h2>F1 by model and strategy</h2>"
        + f'<figure class="viz-fig">{viz.f1_chart(d)}<figcaption>F1 per model under each prompting strategy, from the 10 records of each cell. F1 counts exact matches on the five scored fields; an invalid answer counts every expected field as missing.</figcaption></figure>'
        + viz.results_matrix(d)
        + "<h2>All metrics</h2>"
        + table
        + f"<p class='note'>{note}</p>"
    )
    if an:
        out += (
            (
                "<h2>Every answer</h2>" + viz.outcome_strips(an)
                if all("outcomes" in c for c in an["cells"].values())
                else ""
            )
            + "<h2>Differences in behaviour between models and prompting strategies</h2>"
            + viz.analysis_html(an)
            + "<h2>Conditions of the comparison</h2><p>The three models ran under comparable, not identical, conditions. Reasoning cannot be switched off the same way everywhere, and Gemini offers no temperature control, so differences in the table are not purely differences in model quality.</p>"
            + viz.conditions_table()
            + ("<h2>Compute used</h2>" + viz.usage_table(an) if an.get("usage") else "")
        )
    out += (
        "<h2>How the run went</h2>"
        + md(viz.run_record_md())
        + "<h2>What these results do not show</h2><ul>"
        "<li>The task is one structured calendar row per answer, so two of three models reach a ceiling and the comparison cannot separate them.</li>"
        "<li>Ten records from one edition and one source; the gold was derived from the same page the models read.</li>"
        "<li>The prompting techniques are provisional until confirmed against the course materials.</li>"
        "<li>Scoring is case-insensitive, so a changed capitalisation is not penalised.</li></ul>"
        "<h2>Data</h2><ul class='qlist'><li><a href='results-data/metrics.json'>metrics.json</a></li>"
        + (
            "<li><a href='results-data/analysis.json'>analysis.json</a></li>"
            if an
            else ""
        )
        + "<li><a href='report.md'>project report (Markdown)</a></li></ul>"
    )
    return out


def body_challenges() -> str:
    items = [
        (
            "Wikidata Query Service timeouts",
            "Broad scans and an unbounded predicate returned HTTP 504/502. Queries were narrowed with explicit property lists and class constraints, and results cached by query hash.",
        ),
        (
            "False negatives in 'not found' searches",
            "A first draft filtered on a label-service variable, which silently returned zero rows. It was rewritten with explicit labels, and a control search with a known answer was added.",
        ),
        (
            "'Missing property' is not 'missing knowledge'",
            "Q130829 lacks edition and show statements, but that alone proves nothing; the gap is shown through entity-level queries on editions, brands, venues and participation.",
        ),
        (
            "Unexplained or missing source fields",
            "CNMI rows carry an unexplained asterisk, empty addresses, 'Location in the invitation' and 'DIGITAL'. Written annotation rules keep them verbatim and map missing venues to null with distinct statuses.",
        ),
        (
            "Placeholder map coordinates",
            "Rows with undisclosed venues still carry map coordinates; these are ignored rather than treated as locations.",
        ),
        (
            "Extraction errors",
            "A second parsing route (DOM walk, embedded data, linearised text, live re-fetch) cross-checks the first parser. A mock-model parser bug on an empty address cell was caught by the end-to-end test.",
        ),
        (
            "Valid is not novel",
            "SHACL validity, source support and novelty relative to Wikidata are audited separately; only 39 of 153 triples are potentially new knowledge.",
        ),
        (
            "No independent corroboration",
            "CNMI's second domain was unavailable and no brand-site check was done, so the pilot rests on one official source.",
        ),
    ]
    res = load_results()
    if res:
        gen = 0
        if res[1]:
            gen = sum(
                1
                for c in res[1]["cells"].values()
                for o in c["outcomes"].values()
                if o.get("error_class") == "provider_generation_failure"
            )
        items = items + [
            (
                "The prompt and the gold disagreed",
                "The first live test calls showed all three models returning a null show name: the prompt said 'null when not stated' while the gold defines the show name as the row's title. The rule was stated explicitly (prompt v0.2) and the change was disclosed.",
            ),
            (
                "Free-tier outages",
                "Gemini repeatedly answered HTTP 503 (overloaded). Retries now wait longer, follow the provider's own retry guidance, and count against the quota, so an outage cannot silently burn the allowance.",
            ),
            (
                "Interrupted runs",
                "The laptop slept and the network dropped mid-run. Every cell is checkpointed, so resuming repeated no successful call and the quota ledger stayed correct.",
            ),
            (
                "Quota assumed, then measured",
                "Gemini's free limits are not published, so a deliberately low guess nearly stalled the run. The owner read the real limits from the account and the configuration was corrected; Groq's limits were verified from its documentation.",
            ),
            (
                "Models that cannot produce valid output",
                f"{gen} Qwen3.8-27B cells were rejected by Groq's constrained decoding ('Failed to generate JSON'). They are scored as invalid outputs and were not retried, because retrying until success would be cherry-picking.",
            ),
            (
                "A test deleted real results",
                "Found while reviewing: an older test cleaned up by deleting the results folder. The results were restored from the run's own outputs and the tests now move the real folder aside, so they cannot touch it.",
            ),
        ]
    rows = "".join(f"<tr><th scope='row'>{a}</th><td>{b}</td></tr>" for a, b in items)
    lim = (
        "<h2>Limitations</h2><ul><li>Ten records from one edition and one source; the task is a structured row, so ceiling effects are likely.</li>"
        "<li>Gold is derived from the same page the models read.</li><li>Prompting-technique names are provisional until confirmed with the course.</li>"
        "<li>Novelty is relative to bounded Wikidata searches; other knowledge graphs were not checked.</li><li>The comparison used free-tier APIs whose limits, availability and model versions can change; one of the three models is a Groq preview.</li></ul>"
    )
    return f"<div class='table-wrap'><table><tbody>{rows}</tbody></table></div>{lim}"


def body_references() -> str:
    refs = [
        (
            "Milan Fashion Week, Wikidata Q130829",
            "https://www.wikidata.org/wiki/Q130829",
        ),
        (
            "CNMI calendar, Milano Moda Donna SS 2027",
            "https://www.cameramoda.it/en/milano-moda-donna/calendar/",
        ),
        ("Camera Nazionale della Moda Italiana", "https://www.cameramoda.it/en/"),
        ("Wikidata Query Service", "https://query.wikidata.org/"),
        ("schema.org Event", "https://schema.org/Event"),
        ("W3C SHACL", "https://www.w3.org/TR/shacl/"),
        ("PROV-O", "https://www.w3.org/TR/prov-o/"),
    ]
    li = "".join(f'<li><a href="{u}" rel="noopener">{n}</a></li>' for n, u in refs)
    return f"<ul>{li}</ul><p>Source data licence: CNMI does not state one; only factual fields are stored and the raw page is not redistributed.</p>"


TEAM_FILE = json.loads((ROOT / "team.json").read_text())
TEAM = [
    (m["name"], m["contribution"] or "[to be added]") for m in TEAM_FILE["members"]
]  # contribution statements come from the members


def body_team() -> str:
    rows = "".join(
        f"<tr><th scope='row'>{html.escape(n)}</th><td>{html.escape(c)}</td></tr>"
        for n, c in TEAM
    )
    size = TEAM_FILE["group_size"]
    pending = [n for n, c in TEAM if c == "[to be added]"]
    note = (
        f"<p class='placeholder'><strong>Pending.</strong> Contribution statement still to be written by {html.escape(', '.join(pending))}. "
        "Each member must be able to discuss the whole project and one SPARQL, LLM or HTML task in detail.</p>"
        if pending
        else ""
    )
    return (
        f"<p>Group size: {size}."
        + (" The project was carried out by a single member." if size == 1 else "")
        + "</p>"
        + note
        + f"<div class='table-wrap'><table><thead><tr><th>Member</th><th>Contribution</th></tr></thead><tbody>{rows}</tbody></table></div>"
    )


BODIES = {
    "index": body_index,
    "context": body_context,
    "methodology": body_methodology,
    "gap": body_gap,
    "ontology": body_ontology,
    "sparql": body_sparql,
    "data": body_data,
    "models": body_models,
    "rdf": body_rdf,
    "results": body_results,
    "references": body_references,
    "team": body_team,
}


def build() -> list[str]:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.html"):  # no stale pages
        old.unlink()
    (OUT / "assets").mkdir(exist_ok=True)
    for n in ("style.css", "app.js"):
        shutil.copy(ROOT / "site" / "assets" / n, OUT / "assets" / n)
    (OUT / ".nojekyll").write_text("")
    if (ROOT / "reports" / "report.md").exists():
        shutil.copy(ROOT / "reports" / "report.md", OUT / "report.md")
    shutil.rmtree(OUT / "results-data", ignore_errors=True)
    if (ROOT / "results" / "metrics.json").exists():
        shutil.copytree(ROOT / "results", OUT / "results-data")
    for s, t in PAGES:
        body = BODIES[s]()
        if s == "index":
            hero, _, rest = body.partition("</section>")
            (OUT / f"{s}.html").write_text(page(s, t, rest, hero=hero + "</section>"))
        else:
            (OUT / f"{s}.html").write_text(page(s, t, body, dek=dek_for(s)))
    return [s for s, _ in PAGES]


if __name__ == "__main__":
    print("built", build())
