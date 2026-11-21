"""Assemble reports/report.md (the project report) from repository artefacts. Results come ONLY from results/metrics.json
(never mock). Missing results render an explicit placeholder. All SPARQL queries and all prompts are included verbatim."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports"


def results_section() -> str:
    f = ROOT / "results" / "metrics.json"
    if not f.exists():
        return "**PLACEHOLDER: no real model experiment has been run; no quantitative results are reported.**\n"
    d = json.loads(f.read_text())
    if d.get("is_mock"):
        raise RuntimeError("refusing to report mock metrics")
    fx = lambda x: "n/a" if x is None else f"{x:.3f}"
    rows = [
        "| model | technique | P | R | F1 | invalid | unsupported | RDF conforms |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for c in d["cells"]:
        rows.append(
            f"| {c['model_id']} | {c['technique']} | {fx(c['precision'])} | {fx(c['recall'])} | {fx(c['f1'])} | {fx(c['invalid_output_rate'])} | {fx(c['unsupported_assertion_rate'])} | {fx(c['rdf_conforms_rate'])} |"
        )
    m = d.get("meta", {})
    note = f"\nTechniques: {m.get('techniques_status')}. Prompt version {m.get('prompt_version')}. n = {d['cells'][0]['n_records']} per cell; descriptive only."
    if m.get("budget"):
        if m["budget"].get("mode") == "free":
            note += " Free-tier run: nothing was billed."
        else:
            note += f" Budget spent: EUR {m['budget']['spent_eur']:.4f} of EUR {m['budget']['cap_eur']}."
    return "\n".join(rows) + "\n" + note + "\n"


def analysis_section() -> str:
    f = ROOT / "results" / "analysis.json"
    if not f.exists():
        return "**PLACEHOLDER** until a real run exists.\n"
    an = json.loads(f.read_text())
    if an.get("is_mock"):
        raise RuntimeError("refusing to report a mock analysis")
    fx = lambda x: "n/a" if x is None else f"{x:.3f}"
    errs = lambda s: (
        ", ".join(f"{e}: {n}" for e, n in s["top_errors"].items()) or "none"
    )
    out = [
        "Descriptive means over cells; n is small, no significance claims. The interpretation is written by the team.\n",
        "| model | mean F1 | mean P | mean R | invalid | most common errors |",
        "|---|---|---|---|---|---|",
    ]
    for k, s in an["by_model"].items():
        out.append(
            f"| {k} | {fx(s['mean_f1'])} | {fx(s['mean_precision'])} | {fx(s['mean_recall'])} | {fx(s['mean_invalid_output_rate'])} | {errs(s)} |"
        )
    out += [
        "",
        "| technique | mean F1 | mean P | mean R | invalid | most common errors |",
        "|---|---|---|---|---|---|",
    ]
    for k, s in an["by_technique"].items():
        out.append(
            f"| {k} | {fx(s['mean_f1'])} | {fx(s['mean_precision'])} | {fx(s['mean_recall'])} | {fx(s['mean_invalid_output_rate'])} | {errs(s)} |"
        )
    out += [
        "",
        f"Validated triples from exactly-correct, SHACL-valid predictions: {an.get('validated_triples', {}).get('total', 0)}.",
        "",
    ]
    for cell, c in an["cells"].items():
        for e in c["examples"]:
            for d in e["diffs"]:
                out.append(
                    f"- {cell}, `{e['record']}` {d['field']}: expected `{d['expected']}`, got `{d['predicted']}` ({d['error']})"
                )
    return "\n".join(out) + "\n"


def build() -> Path:
    r = lambda p: (ROOT / p).read_text()
    gold = json.loads(r("data/gold/MANIFEST.json"))
    parts = [
        "# FashionGraph: Enriching Wikidata with Knowledge about Milan Fashion Week\n",
        "*A comparative study of three language models for fashion-event knowledge-graph enrichment.* Status: work in progress; see the Results section.\n",
        f"Gold dataset v{gold['version']} (sha256 `{gold['sha256'][:16]}...`), {gold['records']} CNMI calendar records, owner-verified, single source.\n",
        "## 1. Topic, gap and feasibility\n"
        + r("docs/kg-feasibility.md").replace("# ", "### ", 1),
        "## 2. Source data and annotation\n"
        + r("docs/data-coverage.md")
        + "\n"
        + r("docs/annotation-guidelines.md").replace("# ", "### ", 1),
        "## 3. Ontology\n" + r("docs/ontology.md").replace("# ", "### ", 1),
        "## 4. SPARQL queries (all)\n"
        + "\n".join(
            f"### {q.name}\n```sparql\n{q.read_text()}```\n"
            for q in sorted((ROOT / "queries").glob("*.rq"))
        ),
        "## 5. Models, cost and protocol\n"
        + r("docs/experiment-protocol.md").replace("# ", "### ", 1)
        + "\n"
        + r("docs/cost-estimate.md").replace("# ", "### ", 1),
        "## 6. Prompts (all)\n"
        + "\n".join(
            f"### {n}\n```\n{r(f'experiments/prompts/{n}.txt')}```\n"
            for n in ("system", "zero_shot", "few_shot", "step_by_step")
        ),
        "## 7. RDF enrichment and audit\n"
        + r("docs/rdf-audit.md").replace("# ", "### ", 1),
        "## 8. Results\n" + results_section(),
        "## 9. Differences between models and prompting effects\n" + analysis_section(),
        "## 10. Challenges and limitations\nSee the website Methodology page, section 'Challenges and how we addressed them' (generated from the same repository).\n",
    ]
    OUT.mkdir(exist_ok=True)
    p = OUT / "report.md"
    p.write_text("\n".join(parts))
    return p


if __name__ == "__main__":
    print(build())
