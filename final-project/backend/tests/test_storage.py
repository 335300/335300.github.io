"""Storage: atomic writes, backups, schema guard, data location."""

from __future__ import annotations

import json

import pytest

from app import config
from app.models import YearData
from app.storage import Repository, StorageError


def test_save_and_reload(tmp_path):
    repo = Repository(path=tmp_path / "data.json")
    repo.data.years["2026"] = YearData(opening_balance=12.5)
    repo.save()
    again = Repository(path=tmp_path / "data.json")
    assert again.data.get_year(2026).opening_balance == 12.5
    assert not list(tmp_path.glob(".tmp-*"))  # no temp file left behind


def test_backups_rotate_to_retention_limit(tmp_path):
    repo = Repository(path=tmp_path / "data.json")
    for i in range(config.BACKUP_RETENTION + 5):
        repo.data.next_goal_id = i + 1
        repo.save()
    assert len(list((tmp_path / "backups").glob("data-*.json"))) == config.BACKUP_RETENTION


def test_newer_schema_is_refused(tmp_path):
    path = tmp_path / "data.json"
    path.write_text(json.dumps({"schema_version": config.SCHEMA_VERSION + 1}))
    with pytest.raises(StorageError):
        Repository(path=path).data


def test_corrupt_file_is_refused_not_overwritten(tmp_path):
    path = tmp_path / "data.json"
    path.write_text("{not json")
    with pytest.raises(StorageError):
        Repository(path=path).data
    assert path.read_text() == "{not json"


def test_data_file_lives_in_data_dir(isolated_data_dir):
    assert config.data_file() == isolated_data_dir / "data.json"
    assert Repository().path == isolated_data_dir / "data.json"


def test_profile_folders_are_separate(isolated_data_dir):
    assert config.profile_dir("personal") == isolated_data_dir
    assert config.profile_dir("joint") == isolated_data_dir / "joint"
    with pytest.raises(ValueError):
        config.profile_dir("../x")


def test_default_location_is_its_own_folder(monkeypatch):
    """Never the real app's folder ("Personal Centwise"), the course app's ("Centwise") or the v1 app's."""
    monkeypatch.delenv("CENTWISE_DATA_DIR")
    path = str(config.data_dir())
    assert path.endswith("Application Support/Centwise Final Project")
    assert not path.endswith("Application Support/Personal Centwise")
    assert not path.endswith("Application Support/Centwise")
    assert "Josus Finance" not in path


def test_older_file_loads_and_is_saved_under_the_current_schema(tmp_path):
    """A schema-1 file (no investments, no instalment counts) opens unchanged."""
    path = tmp_path / "data.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "years": {"2026": {
            "categories": {"expense": [{"name": "Rent", "kind": "fixed"}], "income": []},
            "transactions": [{"id": 1, "type": "expense", "date": "2026-03-05", "month": 2,
                              "amount": 500, "desc": "", "cat": "Rent"}],
            "next_id": 2,
        }},
    }))
    repo = Repository(path=path)
    assert repo.data.schema_version == config.SCHEMA_VERSION
    assert repo.data.investments == [] and repo.data.get_year(2026).transactions[0].installments is None
    repo.save()
    saved = json.loads(path.read_text())
    assert saved["schema_version"] == config.SCHEMA_VERSION and saved["investments"] == []


def test_schema_2_file_loads_with_phase_1_defaults(tmp_path):
    """A file from before the income calendar, import and rules opens unchanged."""
    path = tmp_path / "data.json"
    path.write_text(json.dumps({
        "schema_version": 2,
        "years": {"2026": {
            "categories": {"expense": [{"name": "Rent", "kind": "fixed"}], "income": []},
            "transactions": [{"id": 1, "type": "expense", "date": "2026-03-05", "month": 2,
                              "amount": 500, "desc": "", "cat": "Rent", "installments": None}],
            "next_id": 2,
        }},
        "goals": [{"id": 1, "name": "Buffer", "target_amount": 1000, "target_date": "2027-01-01",
                   "created_date": "2026-01-01"}],
        "next_goal_id": 2,
        "investments": [],
        "next_investment_id": 1,
    }))
    repo = Repository(path=path)
    data = repo.data
    assert data.income_plan is None and data.payee_rules == [] and data.dismissed_rule_suggestions == []
    year = data.get_year(2026)
    assert year.categories.expense[0].essential is False
    assert year.transactions[0].payee == "" and year.transactions[0].bank_ref is None
    assert data.goals[0].emergency_fund is False
    repo.save()
    saved = json.loads(path.read_text())
    assert saved["schema_version"] == config.SCHEMA_VERSION and saved["income_plan"] is None


def test_schema_3_file_loads_with_phase_2_defaults(tmp_path):
    path = tmp_path / "data.json"
    path.write_text(json.dumps({
        "schema_version": 3,
        "years": {"2026": {"transactions": [{"id": 1, "type": "expense", "date": "2026-03-05", "month": 2,
                                             "amount": 5, "desc": "", "cat": "X", "payee": "", "bank_ref": None}],
                           "next_id": 2}},
        "goals": [{"id": 1, "name": "Buffer", "target_amount": 1000, "target_date": "2027-01-01",
                   "created_date": "2026-01-01", "emergency_fund": True,
                   "contributions": [{"id": 1, "date": "2026-02-01", "amount": 100, "note": ""}]}],
        "income_plan": None, "payee_rules": [], "dismissed_rule_suggestions": [],
    }))
    repo = Repository(path=path)
    data = repo.data
    assert data.get_year(2026).transactions[0].one_off is False
    assert data.get_year(2026).transactions[0].link_id is None
    goal = data.goals[0]
    assert goal.goal_type == "one_time" and goal.contributions[0].withdrawal is False and goal.saved() == 100
    assert data.recurring_bills == [] and data.shared_expenses == [] and data.fair_share.name_a == "Josu"
    repo.save()
    assert json.loads(path.read_text())["schema_version"] == config.SCHEMA_VERSION


def test_schema_4_file_loads_with_phase_3_defaults(tmp_path):
    path = tmp_path / "data.json"
    path.write_text(json.dumps({
        "schema_version": 4,
        "years": {"2026": {"categories": {"expense": [{"name": "Rent", "kind": "fixed", "essential": True}], "income": []},
                           "transactions": [{"id": 1, "type": "expense", "date": "2026-03-05", "month": 2,
                                             "amount": 5, "desc": "", "cat": "Rent", "one_off": False, "link_id": None}],
                           "next_id": 2}},
        "investments": [{"id": 1, "name": "Plot", "category": "Land", "installment_amount": 10,
                         "total_installments": 5, "created_date": "2026-01-01"}],
        "recurring_bills": [], "shared_expenses": [], "settlements": [],
    }))
    repo = Repository(path=path)
    data = repo.data
    year = data.get_year(2026)
    assert year.categories.expense[0].tax_relevant is False and year.commute_days is None
    assert year.transactions[0].foreign_amount is None
    assert data.investments[0].market_value_local is None
    assert data.accounts == [] and data.exchange_rates == []
    repo.save()
    assert json.loads(path.read_text())["schema_version"] == config.SCHEMA_VERSION


def test_schema_7_file_loads_with_the_default_pay_day(tmp_path):
    """Schema 8 adds the income calendar's pay day; a schema-7 file gets the default, -1
    (the working day before the last one: how Josu is paid)."""
    path = tmp_path / "data.json"
    path.write_text(json.dumps({
        "schema_version": 7,
        "income_plan": {"enabled": True, "hourly_rate": 20, "salary_category": "Salary", "payslips": []},
    }))
    repo = Repository(path=path)
    assert repo.data.income_plan.pay_day == -1
    repo.save()
    saved = json.loads(path.read_text())
    assert saved["schema_version"] == config.SCHEMA_VERSION == 10 and saved["income_plan"]["pay_day"] == -1


def test_schema_8_file_loads_with_nothing_typed(tmp_path):
    """Schema 9 adds typed budget boxes, typed hours and vacations; a schema-8 file has none."""
    path = tmp_path / "data.json"
    path.write_text(json.dumps({
        "schema_version": 8,
        "years": {"2026": {"budgets": {"income": {"Salary": [1000] * 12}, "expense": {}}}},
        "income_plan": {"enabled": True, "hourly_rate": 20, "pay_day": -1, "payslips": []},
    }))
    repo = Repository(path=path)
    assert repo.data.get_year(2026).budgets.manual == {}
    assert repo.data.income_plan.hours_typed == {} and repo.data.income_plan.vacations == []
    repo.save()
    saved = json.loads(path.read_text())
    assert saved["schema_version"] == config.SCHEMA_VERSION == 10
