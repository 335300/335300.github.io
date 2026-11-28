"""Shared test setup. Every test runs against a throwaway data folder."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import (  # noqa: E402
    AppData,
    Category,
    Transaction,
    YearBudgets,
    YearCategories,
    YearData,
)

TODAY = date(2026, 10, 21)


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Point the app at a temp folder so tests can never touch real data."""
    monkeypatch.setenv("CENTWISE_DATA_DIR", str(tmp_path / "appdata"))
    monkeypatch.delenv("CENTWISE_TOKEN", raising=False)
    yield tmp_path / "appdata"


def tx(id: int, type: str, month: int, amount: float, cat: str, day: int = 5, year: int = 2026) -> Transaction:
    return Transaction(
        id=id, type=type, date=f"{year}-{month + 1:02d}-{day:02d}", month=month,
        amount=amount, cat=cat, desc="",
    )


@pytest.fixture
def year() -> YearData:
    """A small, hand-checkable year: tracking starts in March (start_month=1).

    Budgets: Rent 500 (fixed), Food 300, Fun 100; Salary 2000.
    March: salary 2000, rent 500, food 250, fun 120  -> spent 870, net 1130
    April: salary 2000, rent 500, food 240.5          -> spent 740.5, net 1259.5
    """
    budgets = YearBudgets(
        expense={"Rent": [500.0] * 12, "Food": [300.0] * 12, "Fun": [100.0] * 12},
        income={"Salary": [2000.0] * 12},
    )
    cats = YearCategories(
        expense=[Category(name="Rent", kind="fixed"), Category(name="Food"), Category(name="Fun")],
        income=[Category(name="Salary")],
    )
    txs = [
        tx(1, "income", 2, 2000, "Salary"),
        tx(2, "expense", 2, 500, "Rent"),
        tx(3, "expense", 2, 200, "Food"),
        tx(4, "expense", 2, 50, "Food"),
        tx(5, "expense", 2, 120, "Fun"),
        tx(6, "income", 3, 2000, "Salary"),
        tx(7, "expense", 3, 500, "Rent"),
        tx(8, "expense", 3, 240.5, "Food"),
    ]
    return YearData(
        opening_balance=1000.0, start_month=1, categories=cats, budgets=budgets,
        transactions=txs, next_id=9,
    )


@pytest.fixture
def data(year) -> AppData:
    d = AppData()
    d.years["2026"] = year
    return d
