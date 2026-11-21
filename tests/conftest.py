"""Test isolation: some tests publish synthetic results into results/ and then clean up. The REAL results/ folder is moved
aside for the whole session and restored afterwards (also recovered after an interrupted session), so tests can never
delete or overwrite genuine experimental results."""

import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session", autouse=True)
def _protect_real_results():
    real, bak = ROOT / "results", ROOT / ".pytest_results_backup"
    if (
        bak.exists() and not real.exists()
    ):  # a previous session was interrupted: restore first
        shutil.move(str(bak), str(real))
    moved = False
    if real.exists():
        shutil.move(str(real), str(bak))
        moved = True
    try:
        yield
    finally:
        shutil.rmtree(real, ignore_errors=True)  # anything left by tests is synthetic
        if moved and bak.exists():
            shutil.move(str(bak), str(real))
