"""Prompt loading/rendering. Templates live in experiments/prompts/."""

from __future__ import annotations

import json
from pathlib import Path

PROMPT_DIR = Path(__file__).parent / "prompts"
FEW_SHOT_IS_PLACEHOLDER = (
    False  # examples come from data/experiment/fewshot_train.jsonl (train split only)
)
EXAMPLES_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "experiment"
    / "fewshot_train.jsonl"
)
FALLBACK_EXAMPLES = 'TEXT: Example Label presented at Example Hall.\n{"events":[]}  [PLACEHOLDER - NOT FROM TEST SET]'


def load_examples() -> str:
    if not EXAMPLES_PATH.exists():
        return FALLBACK_EXAMPLES
    out = []
    for line in EXAMPLES_PATH.read_text().splitlines():
        ex = json.loads(line)
        out.append(
            f"TEXT:\n{ex['text']}\n{json.dumps(ex['output'], ensure_ascii=False)}"
        )
    return "\n\n".join(out)


def load_system() -> str:
    return (PROMPT_DIR / "system.txt").read_text().strip()


def render(technique: str, text: str) -> tuple[str, str]:
    path = PROMPT_DIR / f"{technique}.txt"
    if not path.exists():
        raise ValueError(f"unknown technique {technique}")
    # Use replace (not format): templates contain literal JSON braces.
    tpl = path.read_text()
    if "{examples}" in tpl:
        tpl = tpl.replace("{examples}", load_examples())
    return load_system(), tpl.replace("{text}", text)
