import importlib.util
import json
import re
from pathlib import Path

from pptx import Presentation

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "slides_build", ROOT / "slides" / "build_slides.py"
)
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def deck(tmp_path, monkeypatch):
    monkeypatch.setattr(s, "OUT", tmp_path)
    path = s.build()
    return Presentation(path), (tmp_path / "outline.md").read_text()


def text(slide):
    return " ".join(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame)


def test_deck_structure_and_title_slide(tmp_path, monkeypatch):
    prs, outline = deck(tmp_path, monkeypatch)
    sl = list(prs.slides)
    assert len(sl) == 6
    url = json.loads((ROOT / "site.json").read_text())["url"]
    assert url in text(sl[0]) and "FashionGraph" in text(
        sl[0]
    )  # PDF p.17: the website link is on the title slide
    assert "Slide outline" in outline


def test_readable_and_budgeted(tmp_path, monkeypatch):
    prs, _ = deck(tmp_path, monkeypatch)
    for sl in prs.slides:
        assert 5 < len(text(sl).split()) <= 90
        assert sl.notes_slide.notes_text_frame.text
    secs = [
        int(m)
        for sl in prs.slides
        for m in re.findall(r"budget (\d+) s", sl.notes_slide.notes_text_frame.text)
    ]
    assert (
        sum(secs) <= 120 * json.loads((ROOT / "team.json").read_text())["group_size"]
    )  # PDF p.17: max 2 minutes per member


def test_results_slide_is_placeholder_and_facts_come_from_artefacts(
    tmp_path, monkeypatch
):
    prs, _ = deck(tmp_path, monkeypatch)
    res = text(list(prs.slides)[4])
    assert "PENDING" in res and not re.search(r"\b0\.\d{2,}\b", res)
    f = s.facts()
    all_text = " ".join(text(x) for x in prs.slides)
    assert (
        str(f["triples"]) in all_text
        and f"v{f['gold_v']}" in all_text
        and not f["real_results"]
    )


def test_deck_matches_the_real_team_and_time_limit(tmp_path, monkeypatch):
    team = json.loads((ROOT / "team.json").read_text())
    prs, outline = deck(tmp_path, monkeypatch)
    names = " and ".join(m["name"] for m in team["members"])
    for sl in prs.slides:
        notes = sl.notes_slide.notes_text_frame.text
        assert (
            f"speaker: {names}" in notes
        )  # every slide is attributed to the real member, not 'Member 1..5'
        assert "Member 1" not in text(sl) and "Member 2" not in notes
    assert f"group size {team['group_size']}" in outline and "templates" not in outline
    assert names in text(next(iter(prs.slides)))
