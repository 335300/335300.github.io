"""Budget vs real with each category's usual month (services/dashboard.py → budget_usual).

Made-up year 2026, tracking from September (start_month=7).
Budgets every month: Rent 500 (fixed), Food 400, Fun 90, Books 50 (variable),
Land 200 (investment). Gifts (variable) has no budget.

| month | Rent | Food                  | Fun | Gifts | Books | Land |
|-------|------|-----------------------|-----|-------|-------|------|
| Sep   | 500  | 300 + 1,000 one-off   | 60  | –     | –     | 200  |
| Oct   | 500  | 340                   | –   | 50    | –     | 200  |
| Nov   | 500  | 200                   | 50  | 30    | 20    | 200  |

Usual = median of the months before the one shown, one-offs left out,
a month with nothing counts as 0.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.models import AppData, Category, Transaction, YearBudgets, YearCategories, YearData
from app.services import dashboard


def t(id: int, month: int, amount: float, cat: str, one_off: bool = False, year: int = 2026) -> Transaction:
    return Transaction(id=id, type="expense", date=f"{year}-{month + 1:02d}-10", month=month,
                       amount=amount, cat=cat, one_off=one_off)


def cats() -> YearCategories:
    return YearCategories(
        expense=[
            Category(name="Rent", kind="fixed"),
            Category(name="Food"),
            Category(name="Fun"),
            Category(name="Gifts"),
            Category(name="Books"),
            Category(name="Land", kind="investment"),
        ],
        income=[Category(name="Salary")],
    )


def budgets() -> YearBudgets:
    return YearBudgets(expense={
        "Rent": [500.0] * 12, "Food": [400.0] * 12, "Fun": [90.0] * 12,
        "Books": [50.0] * 12, "Land": [200.0] * 12,
    })


@pytest.fixture
def autumn() -> AppData:
    txs = [
        t(1, 8, 500, "Rent"), t(2, 8, 300, "Food"), t(3, 8, 1000, "Food", one_off=True),
        t(4, 8, 60, "Fun"), t(5, 8, 200, "Land"),
        t(6, 9, 500, "Rent"), t(7, 9, 340, "Food"), t(8, 9, 50, "Gifts"), t(9, 9, 200, "Land"),
        t(10, 10, 500, "Rent"), t(11, 10, 200, "Food"), t(12, 10, 50, "Fun"), t(13, 10, 30, "Gifts"),
        t(14, 10, 20, "Books"), t(15, 10, 200, "Land"),
    ]
    d = AppData()
    d.years["2026"] = YearData(opening_balance=1000.0, start_month=7, categories=cats(), budgets=budgets(),
                               transactions=txs, next_id=16)
    return d


def bvr(data: AppData, year_num: int, month: int, today: date) -> dict:
    return dashboard.build(data, year_num, month, today)["budget_vs_real"]


def by_cat(block: dict) -> dict[str, dict]:
    return {r["cat"]: r for r in block["rows"]}


def test_usual_and_usual_pct_in_november(autumn):
    """November, earlier months Sep + Oct (2 months -> median = mean of the two):

    - Rent  500, 500           -> usual 500 ; 500 / 500 x 100 = 100.00 %
    - Food  300, 340 (the 1,000 one-off is left out) -> 320 ; 320 / 400 x 100 = 80.00 %
    - Fun    60,   0           -> 30  ; 30 / 90 x 100 = 33.333... -> 33.33 %
    - Gifts   0,  50           -> 25  ; no budget -> usual_pct None
    - Books   0,   0           -> 0   ; 0 / 50 x 100 = 0.00 %
    - Land  200, 200           -> 200 ; 200 / 200 x 100 = 100.00 %
    """
    rows = by_cat(bvr(autumn, 2026, 10, date(2026, 11, 20)))
    expected = {
        "Rent": (500, 100.0), "Food": (320, 80.0), "Fun": (30, 33.33),
        "Gifts": (25, None), "Books": (0, 0.0), "Land": (200, 100.0),
    }
    assert {cat: (r["usual"], r["usual_pct"]) for cat, r in rows.items()} == expected


def test_variable_totals_current_month(autumn):
    """Variable rows in November: Food 200/400, Fun 50/90, Gifts 30/0 (no budget), Books 20/50.

    spent  = 200 + 50 + 30 + 20 = 300
    budget = 400 + 90 + 0 + 50  = 540
    Rent (fixed) and Land (investment) are not variable, so they are left out.
    today = 20 Nov; November has 30 days -> days_left = 30 - 20 = 10.
    """
    block = bvr(autumn, 2026, 10, date(2026, 11, 20))
    assert block["variable_totals"] == {"spent": 300, "budget": 540, "days_left": 10}


def test_variable_spent_matches_variable_costs(autumn):
    """The footer's spent equals the variable cost total of the cost split (same month): 300."""
    dash = dashboard.build(autumn, 2026, 10, date(2026, 11, 20))
    assert dash["budget_vs_real"]["variable_totals"]["spent"] == dash["costs"]["variable"]["total"] == 300


def test_first_tracked_month_has_no_usual(autumn):
    """September is the first tracked month: no earlier month -> usual and usual_pct are None.

    Variable rows: Food 1,300/400 (the one-off is real spending this month), Fun 60/90, Books 0/50.
    spent = 1,300 + 60 + 0 = 1,360 ; budget = 400 + 90 + 50 = 540.
    today = 30 Sep (last day) -> days_left = 30 - 30 = 0.
    """
    block = bvr(autumn, 2026, 8, date(2026, 9, 30))
    assert all(r["usual"] is None and r["usual_pct"] is None for r in block["rows"])
    assert block["variable_totals"] == {"spent": 1360, "budget": 540, "days_left": 0}


def test_past_month_uses_only_months_before_it(autumn):
    """October looked at on 20 Nov. Only September counts (November is later):

    - Food  300 (one-off left out) -> 300 / 400 x 100 = 75.00 %
    - Fun    60                    -> 60 / 90 x 100 = 66.666... -> 66.67 %
    - Gifts   0, no budget         -> usual 0, usual_pct None
    - Books   0                    -> 0 / 50 x 100 = 0.00 %
    Not the current month -> days_left None.
    Variable: spent 340 + 0 + 50 + 0 = 390 ; budget 400 + 90 + 0 + 50 = 540.
    """
    block = bvr(autumn, 2026, 9, date(2026, 11, 20))
    rows = by_cat(block)
    assert (rows["Food"]["usual"], rows["Food"]["usual_pct"]) == (300, 75.0)
    assert (rows["Fun"]["usual"], rows["Fun"]["usual_pct"]) == (60, 66.67)
    assert (rows["Gifts"]["usual"], rows["Gifts"]["usual_pct"]) == (0, None)
    assert (rows["Books"]["usual"], rows["Books"]["usual_pct"]) == (0, 0.0)
    assert block["variable_totals"] == {"spent": 390, "budget": 540, "days_left": None}


def test_existing_figures_unchanged(autumn):
    """Every key budget_vs_real already sent keeps its value; only usual / usual_pct are added."""
    year = autumn.get_year(2026)
    before = dashboard.budget_vs_real(year, 10, "expense")
    after = bvr(autumn, 2026, 10, date(2026, 11, 20))
    assert after["total"] == before["total"]
    assert after["warning_pct"] == before["warning_pct"]
    assert [{k: v for k, v in r.items() if k not in ("usual", "usual_pct")} for r in after["rows"]] == before["rows"]


def test_usual_reaches_back_across_the_year_end():
    """January 2027 (tracked from January) looks back into Nov + Dec 2026:

    Food 100, 300 -> usual 200 ; 200 / 400 x 100 = 50.00 %.
    today = 10 Jan 2027; January has 31 days -> days_left = 31 - 10 = 21.
    Variable: Food 50/400 + Fun 0/90 + Books 0/50 -> spent 50, budget 540.
    """
    d = AppData()
    d.years["2026"] = YearData(start_month=9, categories=cats(), budgets=budgets(),
                               transactions=[t(1, 10, 100, "Food"), t(2, 11, 300, "Food")], next_id=3)
    d.years["2027"] = YearData(start_month=-1, categories=cats(), budgets=budgets(),
                               transactions=[t(3, 0, 50, "Food", year=2027)], next_id=4)
    block = bvr(d, 2027, 0, date(2027, 1, 10))
    food = by_cat(block)["Food"]
    assert (food["usual"], food["usual_pct"]) == (200, 50.0)
    assert block["variable_totals"] == {"spent": 50, "budget": 540, "days_left": 21}


def test_no_rows_gives_zero_totals():
    """A month with no budgets and no spending: no rows, totals 0 / 0."""
    d = AppData()
    d.years["2026"] = YearData(start_month=7, categories=cats(), budgets=YearBudgets(), transactions=[], next_id=1)
    block = bvr(d, 2026, 8, date(2026, 9, 15))
    assert block["rows"] == []
    assert block["variable_totals"] == {"spent": 0, "budget": 0, "days_left": 15}


def test_no_earlier_month_with_data_gives_no_usual():
    """A fresh profile: 2026 tracked from January, only May holds transactions
    (Rent 500, Food 200). January–April are the 4 baseline months, all empty.
    Before: usual 0 and usual_pct 0.00 on every row. Now both are None, and the
    cost card says 0 of its 4 usual months have data (usual_months stays 4)."""
    d = AppData()
    d.years["2026"] = YearData(categories=cats(), budgets=budgets(),
                               transactions=[t(1, 4, 500, "Rent"), t(2, 4, 200, "Food")], next_id=3)
    dash = dashboard.build(d, 2026, 4, date(2026, 5, 20))
    rows = dash["budget_vs_real"]["rows"]
    assert rows and all(r["usual"] is None and r["usual_pct"] is None for r in rows)
    assert (dash["costs"]["usual_months"], dash["costs"]["usual_months_with_data"]) == (4, 0)


def test_usual_months_with_data_in_november(autumn):
    """November: baseline Sep + Oct, both hold transactions -> 2 of 2."""
    costs = dashboard.build(autumn, 2026, 10, date(2026, 11, 20))["costs"]
    assert (costs["usual_months"], costs["usual_months_with_data"]) == (2, 2)
