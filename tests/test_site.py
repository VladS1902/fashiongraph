import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("site_build", ROOT / "site" / "build.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


@pytest.fixture(scope="module")
def dist(tmp_path_factory):
    out = tmp_path_factory.mktemp("dist")
    old = b.OUT
    b.OUT = out
    try:
        slugs = b.build()
    finally:
        b.OUT = old
    return out, slugs, {s: (out / f"{s}.html").read_text() for s in slugs}


def test_pages_and_homepage(dist):
    out, slugs, pages = dist
    assert len(slugs) == 12 and (out / "index.html").exists()
    home = pages["index"]
    assert "Abstract" in home and "Team" in home and "FashionGraph" in home


def test_same_menu_everywhere_and_current_marked(dist):
    navs = set()
    for s, h in dist[2].items():
        nav = re.search(r"<nav.*?</nav>", h, re.DOTALL).group(0)
        assert (
            nav.count("aria-current=page") == 1
            and f'href="{s}.html" aria-current=page' in nav
        )
        navs.add(nav.replace(" aria-current=page", ""))
    assert len(navs) == 1  # PDF p.16: menu always the same, same position


def test_structure_accessibility_offline(dist):
    titles = set()
    for h in dist[2].values():
        assert (
            len(re.findall(r"<h1[ >]", h)) == 1
            and '<html lang="en">' in h
            and 'name="viewport"' in h
            and 'class="skip"' in h
        )
        scripts = re.findall(r"<script[^>]*>", h)
        assert scripts == [
            "<script>",
            re.search(r'<script src="assets/app\.js\?v=[0-9a-f]{8}">', h).group(0),
        ]  # inline js-class flag + local app.js only
        assert 'rel="stylesheet" href="assets/style.css?v=' in h
        assert not re.search(
            r'<(?:link|script|img|iframe)[^>]+(?:src|href)="(?:https?:)?//', h
        )  # no third-party requests (offline, privacy)
        titles.add(re.search(r"<title>(.*?)</title>", h).group(1))
        for m in re.finditer(r'<a href="(https?://[^"]+)"([^>]*)>', h):
            assert "noopener" in m.group(2), m.group(1)
    assert len(titles) == 12


def test_internal_links_and_anchors_resolve(dist):
    out, _, pages = dist
    for s, h in pages.items():
        for href in re.findall(r'href="([^"]+)"', h):
            if href.startswith(("http", "mailto")):
                continue
            path, _, frag = href.partition("#")
            path = path.partition("?")[0]
            target = out / (path or f"{s}.html")
            assert target.exists(), (s, href)
            if frag:
                assert (
                    f'id="{frag}"' in target.read_text()
                    or f"id='{frag}'" in target.read_text()
                ), (s, href)


def strip_tags(h):
    import html

    return html.unescape(re.sub(r"<[^>]+>", "", h))


def test_all_sparql_queries_and_all_prompts_published(dist):
    pages = dist[2]
    import html

    for q in (ROOT / "queries").glob("*.rq"):
        assert q.read_text().strip() in strip_tags(pages["sparql"]), q.name
    for p in (ROOT / "experiments/prompts").glob("*.txt"):
        assert html.escape(p.read_text()) in pages["models"], p.name


def test_gold_review_and_docs_rendered(dist):
    data = dist[2]["data"]
    for i in (
        "13639",
        "13700",
        "13645",
        "13646",
        "13685",
        "13691",
        "13669",
        "13659",
        "13652",
        "13648",
    ):
        assert i in data
    assert "annotation-policy-v1" in data and "ontology" in dist[2]["ontology"].lower()
    assert "GO" in dist[2]["gap"]


def test_no_results_without_real_metrics_and_placeholders_marked(dist):
    r = dist[2]["results"]
    assert (
        "Pending." in r
        and r.count("cell pending") == 9
        and "<b>" not in r.split("What will appear")[0].split("matrix")[1]
    )
    assert "Pending." in dist[2]["team"]
    assert not (ROOT / "results" / "metrics.json").exists()


def test_mock_metrics_refused_and_real_metrics_rendered(tmp_path, monkeypatch):
    (tmp_path / "results").mkdir()
    cell = {
        "model_id": "m",
        "technique": "t",
        "precision": 0.5,
        "recall": 0.25,
        "f1": 0.333,
        "invalid_output_rate": 0.0,
        "unsupported_assertion_rate": None,
        "rdf_conforms_rate": 1.0,
    }
    monkeypatch.setattr(b, "ROOT", tmp_path)
    (tmp_path / "results" / "metrics.json").write_text(
        json.dumps({"is_mock": True, "cells": [cell]})
    )
    with pytest.raises(RuntimeError):
        b.body_results()
    (tmp_path / "results" / "metrics.json").write_text(
        json.dumps({"is_mock": False, "cells": [cell]})
    )
    html_ = b.body_results()
    assert (
        "0.333" in html_ and "n/a" in html_ and "Pending." not in html_.split("<h")[0]
    )


def test_assets_are_self_contained_and_motion_is_respectful():
    css = (ROOT / "site/assets/style.css").read_text()
    js = (ROOT / "site/assets/app.js").read_text()
    assert (
        "@import" not in css
        and "url(http" not in css
        and "fetch(" not in js
        and "XMLHttpRequest" not in js
    )
    assert (
        "prefers-reduced-motion" in css and "prefers-reduced-motion" in js
    )  # both layers honour it
    assert ":focus-visible" in css and "prefers-color-scheme:dark" in css


def test_visuals_are_built_from_real_artefacts(dist):
    import json

    pages = dist[2]
    gold = [
        json.loads(x)
        for x in (ROOT / "data/gold/gold_pilot.jsonl").read_text().splitlines()
    ]
    home = pages["index"]
    assert len(re.findall(r'class="node show', home)) == 10 == len(gold)
    for g in gold:
        assert g["name_raw"].rstrip(" *") in home
    assert "Q130829" in home and 'id="node-detail"' in home and 'id="replay"' in home
    assert pages["data"].count('class="mark') == 10
    audit = json.loads((ROOT / "rdf/out/audit.json").read_text())
    assert str(audit["total_triples"]) in pages["rdf"]
    seg_values = [
        int(v)
        for v in re.findall(r'class="seg s\d"[^>]*><span>(\d+)</span>', pages["rdf"])
    ]
    assert (
        sum(seg_values) == 3 * audit["total_triples"]
    )  # three stacked bars, each summing to all triples
    assert (
        "0 of 28" in pages["gap"] and "0 of 19" in pages["gap"]
    )  # recorded zero counts, from the evidence files
    for slug in ("ontology", "data", "gap", "rdf", "results"):
        assert (
            "<svg" in pages[slug] or "brow" in pages[slug] or "matrix" in pages[slug]
        ), slug


# ---- results state: the whole site must describe the real comparison, never the old "not run" text ------------------
@pytest.fixture()
def with_results(tmp_path):
    """Synthetic but complete non-mock results published into the (isolated, see conftest) results/ folder, built into tmp."""
    from evaluation.publish import publish
    from tests.test_budget import synthetic_real_metrics

    f = synthetic_real_metrics(tmp_path)
    an = json.loads((tmp_path / "analysis.json").read_text())
    ids = [f"mfw-ss27-{g['cnmi_event_id']}" for g in b.viz.gold_rows()]
    base = an["cells"]["a | zero_shot"]
    an["cells"] = {
        f"{m} | {tq}": json.loads(json.dumps(base))
        for m in ("a", "b", "c")
        for tq in ("zero_shot", "few_shot", "step_by_step")
    }
    for c in an["cells"].values():
        c["outcomes"] = {
            rid: {
                "kind": "exact" if i % 4 else "invalid",
                "n_diffs": 0,
                "error_class": "provider_generation_failure" if i % 4 == 0 else None,
            }
            for i, rid in enumerate(ids)
        }
    an["usage"] = {
        m: {"answered": 30, "input_tokens": 1000, "output_tokens": 200}
        for m in ("a", "b", "c")
    }
    (tmp_path / "analysis.json").write_text(json.dumps(an))
    publish(f, ROOT / "results")
    out = tmp_path / "dist"
    old = b.OUT
    b.OUT = out
    try:
        slugs = b.build()
        yield out, {s: (out / f"{s}.html").read_text() for s in slugs}
    finally:
        b.OUT = old
        import shutil

        shutil.rmtree(
            ROOT / "results", ignore_errors=True
        )  # synthetic: never leave it behind


def test_results_state_has_no_stale_not_run_claims(with_results):
    _, pages = with_results
    stale = (
        "no real LLM experiment has been run",
        "Not run yet",
        "has not been run",
        "0 of 9 cells run",
        "Nothing here is a result until",
        "not yet been run",
    )
    for slug, h in pages.items():
        for s in stale:
            assert s not in h, (slug, s)
    assert (
        "Experiment complete." in pages["index"]
        and "Experiment complete." in pages["results"]
    )


def test_results_page_shows_chart_strips_conditions_usage_and_run_record(with_results):
    _, pages = with_results
    r = pages["results"]
    assert (
        'class="viz chart' in r
        and r.count('class="gbar') == 9
        and r.count('class="sq ') >= 90
    )
    for needle in (
        "Every answer",
        "Conditions of the comparison",
        "Compute used",
        "How the run went",
        "What these results do not show",
        "Example errors",
    ):
        assert needle in r, needle
    assert (
        "reasoning effort low" in r and "not sent (deprecated" in r
    )  # the real, per-model conditions from the config
    assert (
        'class="findings"' in r and r.count("<li>") >= 5
    )  # the findings sentences are computed from the data


def test_results_state_updates_home_methodology_challenges_and_downloads(with_results):
    out, pages = with_results
    assert (
        "What the models did" in pages["index"] and 'class="findings"' in pages["index"]
    )
    assert (
        "Test three language models" in pages["index"]
        and "scored and analysed" in pages["index"]
    )
    assert (
        "built, not run" not in pages["methodology"]
        and "interrupted and resumed" in pages["methodology"]
    )
    assert (
        "A test deleted real results" in pages["methodology"]
        and "Free-tier outages" in pages["methodology"]
    )
    assert "Triples produced by the models" in pages["rdf"]
    for f in ("results-data/metrics.json", "results-data/analysis.json"):
        assert (out / f).exists()


def test_pending_state_unchanged_without_results(dist):
    assert (
        "no real LLM experiment has been run" in dist[2]["index"]
        and "Pending." in dist[2]["results"]
    )


# ---- reviewer feedback (Vlad, 2026-11-20): removals and additions --------------------------------------------------------
def test_footer_text_removed_from_every_page(dist):
    for slug, h in dist[2].items():
        assert (
            "<footer" not in h
            and "Every page is generated" not in h
            and "nothing on it is typed in" not in h
        ), slug
        assert "Knowledge Engineering and Computation for the Humanities" not in h, slug


def test_cost_estimate_section_removed_from_models_page(dist):
    m = dist[2]["models"]
    assert (
        "Cost estimate" not in m
        and "Model selection" in m
        and "Zero-cost alternative" in m
    )


def test_challenges_is_not_a_menu_item_but_its_content_is_kept(dist):
    out, slugs, pages = dist
    assert "challenges" not in slugs and not (out / "challenges.html").exists()
    for slug, h in pages.items():
        nav = re.search(r"<nav.*?</nav>", h, re.DOTALL).group(0)
        assert "challenges.html" not in nav and ">Challenges<" not in nav, slug
        assert "challenges.html" not in h, slug  # nothing links to the removed page
    meth = pages["methodology"]
    # PDF p.4 #5 and p.16 make the discussion of challenges and how they were addressed MANDATORY: it stays, as a section here
    assert 'id="challenges"' in meth and "Challenges and how we addressed them" in meth
    assert "Wikidata Query Service timeouts" in meth and "Limitations" in meth


def test_course_unit_reference_removed(dist):
    ref = dist[2]["references"]
    assert (
        "Course unit page" not in ref
        and "unibo.it" not in ref
        and "Wikidata Q130829" in ref
    )


def test_team_lists_vlad_sapytskii_without_inventing_a_contribution(dist):
    team, home = dist[2]["team"], dist[2]["index"]
    assert (
        "Vlad Sapytskii" in team and "Vlad Sapytskii" in home
    )  # PDF p.16: the homepage must list the team
    row = re.search(r"Vlad Sapytskii</th><td>(.*?)</td>", team).group(1)
    assert (
        row == "[to be added]"
    )  # contribution statements are written by the member, never invented
