"""Gate between a finished REAL run and everything public (site, report, slides read results/metrics.json only).
Refuses mock data, incomplete runs, stale dataset/gold/prompt versions, and unequal cell sizes.
  python -m evaluation.publish outputs/real/metrics.json"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class PublishRefused(RuntimeError):
    pass


def problems(d: dict, analysis: dict | None = None) -> list[str]:
    from experiments import inputs as inp
    from experiments.config import PROMPT_VERSION

    cur = inp.build(write=False)["manifest"]
    meta = d.get("meta", {})
    out = []
    if d.get("is_mock") or any(c.get("is_mock") for c in d.get("cells", [])):
        out.append("mock results can never be published")
    if not meta.get("complete"):
        out.append(
            f"run incomplete: {meta.get('answered_rows')}/{meta.get('expected_rows')} answered, halted={meta.get('run_stats', {}).get('halted')}"
        )
    if meta.get("dataset_sha256") != cur["sha256"]["test_inputs.jsonl"]:
        out.append("dataset checksum differs from current data/experiment manifest")
    if meta.get("gold_sha256") != cur["gold_sha256"]:
        out.append("gold checksum differs from current gold manifest")
    if meta.get("prompt_version") != PROMPT_VERSION:
        out.append("prompt version differs from current")
    if analysis is None or analysis.get("is_mock"):
        out.append(
            "analysis.json missing next to metrics.json, or it is a mock analysis"
        )
    cells = d.get("cells", [])
    if len(cells) != 9:
        out.append(f"expected 9 model x technique cells, found {len(cells)}")
    if len({c["n_records"] for c in cells}) > 1 or any(
        c["n_records"] != cur["n_test"] for c in cells
    ):
        out.append("cells do not all cover the full test set")
    return out


def publish(
    metrics_path: str | Path, results_dir: str | Path = ROOT / "results"
) -> Path:
    src = Path(metrics_path)
    d = json.loads(src.read_text())
    ap = src.parent / "analysis.json"
    analysis = json.loads(ap.read_text()) if ap.exists() else None
    bad = problems(d, analysis)
    if bad:
        raise PublishRefused("; ".join(bad))
    out = Path(results_dir)
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, out / "metrics.json")
    shutil.copy(ap, out / "analysis.json")
    if (src.parent / "rdf").exists():
        shutil.rmtree(out / "rdf", ignore_errors=True)
        shutil.copytree(src.parent / "rdf", out / "rdf")
    return out / "metrics.json"


if __name__ == "__main__":
    print(publish(sys.argv[1]))
