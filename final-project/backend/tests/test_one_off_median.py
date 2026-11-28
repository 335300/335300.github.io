"""One-off transactions and median "usual" figures.

Made-up year 2026, tracked from January. Every month January–June:
Rent 500 (fixed), Food 200 (variable), Salary 2,000. In March a one-off
wedding (Food, 1,000) is recorded on top.
"""

from __future__ import annotations

import pytest

from app.models import AppData, Category, Contribution, SavingsGoal, Transaction, YearCategories, YearData
from app.services import cashflow, dashboard, emergency


def t(id, kind, month, amount, cat, one_off=False, day=5) -> Transaction:
    return Transaction(id=id, type=kind, date=f"2026-{month + 1:02d}-{day:02d}", month=month,
                       amount=amount, cat=cat, one_off=one_off)


@pytest.fixture
def data() -> AppData:
    txs, n = [], 1
    for m in range(6):
        for kind, amount, cat in (("income", 2000, "Salary"), ("expense", 500, "Rent"), ("expense", 200, "Food")):
            txs.append(t(n, kind, m, amount, cat))
            n += 1
    txs.append(t(n, "expense", 2, 1000, "Food", one_off=True))
    year = YearData(
        categories=YearCategories(
            expense=[Category(name="Rent", kind="fixed", essential=True), Category(name="Food", essential=True),
                     Category(name="Fun")],
            income=[Category(name="Salary")],
        ),
        transactions=txs, next_id=n + 1,
    )
    d = AppData()
    d.years["2026"] = year
    return d


def add(data, kind, month, amount, cat, one_off=False):
    year = data.years["2026"]
    year.transactions.append(t(year.take_id(), kind, month, amount, cat, one_off))


def test_usual_category_leaves_the_one_off_out(data):
    months = cashflow.baseline_months(data, 2026, 6)
    assert len(months) == 6
    assert cashflow.category_baselines(data, months) == {"Rent": 500, "Food": 200}


def test_median_ignores_a_single_big_month(data):
    # Without tagging: one month of Food at 1,200 still leaves the usual month at 200.
    data.years["2026"].transactions[-1].one_off = False
    months = cashflow.baseline_months(data, 2026, 6)
    assert cashflow.category_baselines(data, months)["Food"] == 200


def test_typical_costs_leave_the_one_off_out(data):
    assert cashflow.typical_costs(data, 2026, 6) == 700


def test_history_yardsticks_leave_the_one_off_out(data):
    add(data, "expense", 6, 200, "Food")
    variable = cashflow.history(data, 2026, 6)["variable"]
    assert variable["median_6m"] == 200 and variable["avg_6m"] == 200
    assert variable["vs_avg_pct"] == 0.0


def test_vs_usual_leaves_this_months_one_off_out(data):
    add(data, "expense", 6, 300, "Food")
    add(data, "expense", 6, 900, "Food", one_off=True)
    variable = cashflow.history(data, 2026, 6)["variable"]
    assert variable["current"] == 1200 and variable["one_off"] == 900
    assert variable["vs_usual_pct"] == 50.0  # 300 against the usual 200
    # The chart rows still show what really happened in March.
    march = next(r for r in cashflow.history(data, 2026, 6)["rows"] if r["month"] == 2)
    assert march["variable"] == 1200 and march["variable_regular"] == 200


def test_unusual_this_month(data):
    add(data, "expense", 6, 500, "Rent")
    add(data, "expense", 6, 350, "Food")  # 1.75x usual and +150 -> unusual
    add(data, "expense", 6, 90, "Fun")    # usual month 0 -> never listed
    costs = dashboard.costs_with_usual(data, data.years["2026"], 2026, 6)
    assert costs["unusual"] == [{"cat": "Food", "amount": 350, "usual": 200, "over": 150}]


def test_small_or_tagged_differences_are_not_unusual(data):
    add(data, "expense", 6, 225, "Food")                  # +25: under the €30 minimum
    add(data, "expense", 6, 400, "Food", one_off=True)    # tagged, so expected
    costs = dashboard.costs_with_usual(data, data.years["2026"], 2026, 6)
    assert costs["unusual"] == []
    food = next(r for r in costs["ranked"] if r["cat"] == "Food")
    assert food["amount"] == 625 and food["one_off"] == 400


@pytest.mark.parametrize("now,listed", [(300, True), (299.99, False)])
def test_unusual_needs_one_and_a_half_times(data, now, listed):
    add(data, "expense", 6, now, "Food")
    costs = dashboard.costs_with_usual(data, data.years["2026"], 2026, 6)
    assert bool(costs["unusual"]) is listed


def test_emergency_fund_leaves_the_one_off_out(data):
    data.goals = [SavingsGoal(id=1, name="Fund", target_amount=5000, target_date="2027-01-01",
                              created_date="2026-01-01", emergency_fund=True,
                              contributions=[Contribution(id=1, date="2026-01-10", amount=2100)])]
    tile = emergency.build(data, 2026, 6)
    assert tile["usual_essential_costs"] == 700 and tile["months_covered"] == 3.0
