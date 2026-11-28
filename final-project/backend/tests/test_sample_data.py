"""The sample-data generator (scripts/2026-11-28-make-sample-data.py) still works
with the current app: it fills both profiles, the files load under the current
schema, and the Joint links line up."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app.config import SCHEMA_VERSION
from app.models import AppData

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "2026-11-28-make-sample-data.py"


def run(folder: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-W", "ignore", str(SCRIPT), str(folder), *extra],
                          capture_output=True, text=True, timeout=120)


def load(path: Path) -> AppData:
    return AppData.model_validate(json.loads(path.read_text()))


def test_generator_fills_both_profiles(tmp_path):
    folder = tmp_path / "sample"
    result = run(folder)
    assert result.returncode == 0, result.stderr

    personal = load(folder / "data.json")
    joint = load(folder / "joint" / "data.json")
    assert personal.schema_version == joint.schema_version == SCHEMA_VERSION

    p_year, j_year = personal.years["2026"], joint.years["2026"]
    assert len(p_year.transactions) > 150 and len(j_year.transactions) > 80
    assert {g.name for g in personal.goals} == {"Emergency fund", "Semester fee", "New laptop", "Trip to Paraguay"}
    assert [g.name for g in joint.goals] == ["Holiday in Italy"]
    assert personal.investments[0].name == "Plot of land"
    assert len(personal.income_plan.payslips) == 11
    assert joint.fair_share.name_a == "Josu" and joint.fair_share.name_b == "Isa"

    # Every Transfer to Joint has its linked twin on the Joint side.
    p_links = {t.link_id for t in p_year.transactions if t.link_id}
    j_links = {t.link_id for t in j_year.transactions if t.link_id}
    assert len(p_links) == 11 and p_links == j_links

    # No step backups are left behind.
    assert not (folder / "backups").exists() and not (folder / "joint" / "backups").exists()


def test_generator_is_repeatable_and_needs_force(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    assert run(first).returncode == 0 and run(second).returncode == 0
    strip = lambda p: [t.model_dump(exclude={"link_id"}) for t in load(p).years["2026"].transactions]  # noqa: E731
    assert strip(first / "data.json") == strip(second / "data.json")

    again = run(first)
    assert again.returncode != 0 and "--force" in again.stderr
    assert run(first, "--force").returncode == 0
