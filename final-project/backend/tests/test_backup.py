"""Encrypted backups: make, verify, restore. Small scrypt cost keeps tests fast."""

from __future__ import annotations

import json

import pytest

from app.models import AppData, Contribution, SavingsGoal, Transaction, YearData
from app.services import backup
from app.storage import Repository

PASSWORD = "correct horse battery"
FAST = 2**12


def profile(amount: float) -> AppData:
    d = AppData()
    d.years["2026"] = YearData(opening_balance=100, transactions=[
        Transaction(id=1, type="income", date="2026-03-01", month=2, amount=2000, cat="Salary"),
        Transaction(id=2, type="expense", date="2026-03-02", month=2, amount=amount, cat="Rent"),
    ], next_id=3)
    d.goals = [SavingsGoal(id=1, name="Fund", target_amount=500, target_date="2027-01-01", created_date="2026-01-01",
                           contributions=[Contribution(id=1, date="2026-03-05", amount=50)])]
    return d


@pytest.fixture
def profiles() -> dict[str, AppData]:
    return {"personal": profile(700), "joint": profile(400)}


def make(profiles, **kw):
    return backup.make(profiles, PASSWORD, created="2026-11-13T10:00:00", n=FAST, **kw)


def test_round_trip_keeps_both_profiles_apart(profiles):
    raw = make(profiles)
    header, payload = backup.read(raw, PASSWORD)
    assert header["profiles"] == ["joint", "personal"] and header["cipher"] == "AES-256-GCM"
    assert payload["profiles"]["personal"]["years"]["2026"]["transactions"][1]["amount"] == 700
    assert payload["profiles"]["joint"]["years"]["2026"]["transactions"][1]["amount"] == 400


def test_nothing_readable_without_the_password(profiles):
    raw = make(profiles)
    assert b"Salary" not in raw and b"Rent" not in raw
    with pytest.raises(backup.BackupError, match="Wrong password"):
        backup.read(raw, "wrong password!!")


def test_a_short_password_is_refused(profiles):
    with pytest.raises(backup.BackupError, match="at least 10"):
        backup.make(profiles, "short", created="x", n=FAST)


def test_a_changed_byte_is_detected(profiles):
    doc = json.loads(make(profiles))
    ct = bytearray(backup._unb64(doc["ciphertext"]))
    ct[10] ^= 1
    doc["ciphertext"] = backup._b64(bytes(ct))
    with pytest.raises(backup.BackupError, match="changed or damaged"):
        backup.read(json.dumps(doc).encode(), PASSWORD)


def test_a_changed_header_is_detected(profiles):
    doc = json.loads(make(profiles))
    doc["created"] = "2020-01-01T00:00:00"
    with pytest.raises(backup.BackupError, match="changed or damaged"):
        backup.read(json.dumps(doc).encode(), PASSWORD)


def test_other_files_are_refused():
    with pytest.raises(backup.BackupError, match="not a Personal Centwise backup"):
        backup.read(b"hello", PASSWORD)
    with pytest.raises(backup.BackupError, match="not a Personal Centwise backup"):
        backup.read(json.dumps({"format": "other", "ciphertext": ""}).encode(), PASSWORD)


def test_a_newer_backup_is_refused(profiles):
    doc = json.loads(make(profiles))
    doc["schema_version"] = 999
    with pytest.raises(backup.BackupError, match="newer version"):
        backup.read(json.dumps(doc).encode(), PASSWORD)


def test_checksheet(profiles):
    sheet = backup.checksheet(profiles)
    assert sheet["personal"]["years"]["2026"] == {
        "transactions": 2, "income": 2000, "expenses": 700, "closing_balance": 100 + 2000 - 700,
    }
    assert sheet["joint"]["goal_money"] == 50 and sheet["personal"]["transactions"] == 2


def test_verify_passes(profiles):
    result = backup.verify(make(profiles), PASSWORD)
    assert result["ok"] is True and result["problems"] == []
    assert [s["label"] for s in result["summary"]] == ["Joint", "Personal"]
    assert result["summary"][1] == {"profile": "personal", "label": "Personal", "years": [2026], "transactions": 2, "goals": 1}
    assert isinstance(result["profiles"]["personal"], AppData)


def test_verify_catches_totals_that_do_not_match(profiles, monkeypatch):
    real = backup.checksheet
    def fudged(p):
        sheet = real(p)
        sheet["personal"]["years"]["2026"]["expenses"] = 1
        return sheet
    monkeypatch.setattr(backup, "checksheet", fudged)
    raw = make(profiles)
    monkeypatch.setattr(backup, "checksheet", real)
    result = backup.verify(raw, PASSWORD)
    assert result["ok"] is False
    assert result["problems"] == ["Personal 2026: the totals do not match the check sheet."]


def test_restore_keeps_a_safety_copy(tmp_path, profiles):
    repo = Repository(path=tmp_path / "data.json")
    repo.data.years["2026"] = YearData(opening_balance=5)
    repo.save()
    safety = repo.replace(backup.verify(make(profiles), PASSWORD)["profiles"]["personal"])
    assert safety is not None and safety.name.startswith("data-before-restore-")
    assert json.loads(safety.read_text())["years"]["2026"]["opening_balance"] == 5
    again = Repository(path=tmp_path / "data.json")
    assert again.data.get_year(2026).transactions[1].amount == 700
