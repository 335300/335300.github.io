"""Calculation layer: aggregation, Overview (dashboard) and Forecast (projection)."""

from __future__ import annotations

import pytest

from app.models import AppData, YearData
from app.services import aggregation, dashboard, projection

from .conftest import tx


# -- aggregation ------------------------------------------------------------

def test_month_totals(year):
    assert aggregation.month_total(year, 2, "income") == 2000
    assert aggregation.month_total(year, 2, "expense") == 870
    assert aggregation.month_total(year, 3, "expense") == 740.5
    assert aggregation.month_total(year, 7, "expense") == 0


def test_category_totals_group_by_category(year):
    assert aggregation.category_totals(year, 2, "expense") == {"Rent": 500, "Food": 250, "Fun": 120}


def test_balance_starts_after_start_month(year):
    # Opening 1000 at close of Feb; + March 1130 + April 1259.5
    assert aggregation.balance_through(year, 1) == 1000
    assert aggregation.balance_through(year, 2) == 2130
    assert aggregation.balance_through(year, 3) == 3389.5
    # No transactions after April: balance stays flat.
    assert aggregation.closing_balance(year) == 3389.5


def test_last_recorded_month(year):
    assert aggregation.last_recorded_month(year) == 3
    assert aggregation.last_recorded_month(YearData(start_month=4)) == 4


def test_opening_balance_for_month(data):
    assert aggregation.opening_balance_for_month(data, 2026, 2) == 1000  # first tracked month
    assert aggregation.opening_balance_for_month(data, 2026, 3) == 2130
    assert aggregation.opening_balance_for_month(data, 1999, 3) == 0.0


def test_opening_balance_reaches_into_previous_year(data):
    data.years["2027"] = YearData(opening_balance=0.0, start_month=-1)
    assert aggregation.opening_balance_for_month(data, 2027, 0) == 3389.5


def test_float_noise_is_rounded():
    y = YearData(transactions=[tx(i, "expense", 0, 0.1, "X") for i in range(1, 4)])
    assert aggregation.month_total(y, 0, "expense") == 0.3


# -- Overview ---------------------------------------------------------------

def test_kpis(data):
    k = dashboard.kpis(data, data.get_year(2026), 2026, 2)
    assert k["balance_last_month"] == 1000
    assert k["current_balance"] == 2130
    assert k["income"] == 2000 and k["income_budget"] == 2000
    assert k["spent"] == 870 and k["spent_budget"] == 900
    assert k["savings"] == 1130
    assert k["savings_rate"] == 56.5
    assert k["savings_vs_budget"] == 1100
    assert k["negative_balance"] is False


def test_savings_rate_without_income_is_zero(year):
    d = AppData()
    d.years["2026"] = year
    k = dashboard.kpis(d, year, 2026, 9)
    assert k["income"] == 0 and k["savings_rate"] == 0.0


def test_fixed_plus_variable_equals_spent(data, year):
    costs = dashboard.cost_split(year, 2)
    assert costs["fixed"]["total"] == 500
    assert costs["variable"]["total"] == 370
    assert costs["fixed"]["total"] + costs["variable"]["total"] == costs["month_spend"]
    assert costs["month_spend"] == dashboard.kpis(data, year, 2026, 2)["spent"]
    assert [r["cat"] for r in costs["ranked"]] == ["Rent", "Food", "Fun"]
    assert costs["ranked"][0]["width"] == 100.0
    assert costs["ranked"][1]["width"] == 50.0


def test_deleted_category_spending_counts_as_variable(year):
    year.transactions.append(tx(99, "expense", 2, 30, "Old category"))
    costs = dashboard.cost_split(year, 2)
    assert costs["variable"]["total"] == 400
    assert any(r["cat"] == "Old category" for r in costs["ranked"])


def test_budget_vs_real_total_equals_spent(data, year):
    bvr = dashboard.budget_vs_real(year, 2)
    assert bvr["total"]["real"] == dashboard.kpis(data, year, 2026, 2)["spent"]
    assert bvr["total"]["budget"] == 900
    rows = {r["cat"]: r for r in bvr["rows"]}
    assert rows["Fun"]["status"] == "over" and rows["Fun"]["progress"] == 100.0
    assert rows["Fun"]["used_pct"] == 120.0
    assert rows["Food"]["status"] == "warning"  # 250 / 300 = 83% >= 80%
    assert rows["Rent"]["status"] == "on_budget"


@pytest.mark.parametrize(
    "budget, actual, fixed, expected",
    [
        (100, 79.99, False, "under"),
        (100, 80, False, "warning"),  # owner's threshold: 80%
        (100, 100, False, "on_budget"),
        (100, 100.01, False, "over"),
        (500, 250, True, "on_budget"),  # a fixed cost paid is never a warning
        (500, 510, True, "over"),
        (0, 20, False, "unbudgeted"),
        (0, 0, False, "under"),
    ],
)
def test_budget_status(budget, actual, fixed, expected):
    assert dashboard.budget_status(budget, actual, "expense", fixed=fixed) == expected


def test_income_is_never_over():
    assert dashboard.budget_status(100, 500, "income") == "under"


def test_budget_vs_real_includes_unbudgeted(year):
    year.transactions.append(tx(99, "expense", 2, 45, "Gift"))
    rows = {r["cat"]: r for r in dashboard.budget_vs_real(year, 2)["rows"]}
    assert rows["Gift"]["status"] == "unbudgeted"
    assert rows["Gift"]["used_pct"] is None


def test_trend_covers_recorded_months(year):
    t = dashboard.trend(year)
    assert [r["month"] for r in t] == [2, 3]
    assert t[0] == {
        "month": 2, "month_name": "Mar", "income": 2000, "expenses": 870, "invested": 0.0, "savings": 1130,
    }


def test_dashboard_build_unknown_year(data):
    with pytest.raises(KeyError):
        dashboard.build(data, 1999, 0)


# -- Forecast ---------------------------------------------------------------

def test_projection_blends_actual_and_budget(year):
    p = projection.build(year, 2026)
    rows = p["rows"]
    assert [r["month"] for r in rows] == list(range(2, 12))
    assert rows[0]["actual"] and rows[1]["actual"] and not rows[2]["actual"]
    # Budgeted months: 2000 income - 900 expenses = 1100
    assert rows[2]["savings"] == 1100
    assert rows[1]["balance"] == 3389.5
    assert rows[-1]["balance"] == 3389.5 + 8 * 1100

    s = p["summary"]
    assert s["actual_savings"] == 2389.5 and s["actual_months"] == 2
    assert s["planned_savings"] == 8800 and s["planned_months"] == 8
    assert s["year_end_savings"] == 11189.5
    assert s["year_end_balance"] == 12189.5
    assert s["average_planned_savings"] == 1100
    assert s["average_monthly_savings"] == round(11189.5 / 10, 2)
    assert s["last_actual_month"] == 3
    assert s["goes_negative"] is False


def test_projection_flags_negative_months(year):
    year.budgets.expense["Rent"] = [3000.0] * 12
    p = projection.build(year, 2026)
    assert p["summary"]["goes_negative"] is True
    first_negative = next(r for r in p["rows"] if r["negative"])
    assert first_negative["balance"] < 0
    assert p["summary"]["lowest_balance"] == min(r["balance"] for r in p["rows"])


def test_expected_monthly_savings_uses_remaining_months(year):
    s = projection.build(year, 2026)["summary"]
    assert projection.expected_monthly_savings(s) == 1100


def test_expected_monthly_savings_falls_back_when_year_is_recorded(year):
    year.transactions.append(tx(50, "income", 11, 100, "Salary"))
    s = projection.build(year, 2026)["summary"]
    assert s["planned_months"] == 0
    assert projection.expected_monthly_savings(s) == s["average_monthly_savings"]


def test_empty_year_projection():
    p = projection.build(YearData(opening_balance=50), 2026)
    assert len(p["rows"]) == 12
    assert p["summary"]["year_end_balance"] == 50
    assert p["summary"]["last_actual_month"] is None


def test_savings_by_month(year):
    s = aggregation.savings_by_month(year)
    # Plan: 2000 income - (500 + 300 + 100) = 1100 every month.
    assert s["planned"] == [1100.0] * 12 and s["planned_total"] == 13200
    # Tracking starts in March; March and April are recorded.
    assert s["actual"][:2] == [None, None]
    assert s["actual"][2:4] == [1130, 1259.5]
    assert s["actual"][4:] == [None] * 8
    assert s["actual_total"] == 2389.5


def test_savings_by_month_negative_plan():
    y = YearData(budgets={"expense": {"Rent": [300.0] * 12}, "income": {}})
    s = aggregation.savings_by_month(y)
    assert s["planned"][0] == -300 and s["actual"] == [None] * 12 and s["actual_total"] == 0


def test_budget_kind_rows_split_the_cash_out(year):
    """Fixture budgets: Rent 500 (fixed), Food 300 + Fun 100 (variable), every month."""
    from app.services.aggregation import budget_kind_rows, budget_total
    rows = budget_kind_rows(year)
    assert rows["fixed"]["monthly"] == [500.0] * 12 and rows["fixed"]["total"] == 6000
    assert rows["variable"]["monthly"] == [400.0] * 12 and rows["variable"]["total"] == 4800
    assert rows["investment"]["total"] == 0
    # Together they are the plan's cash-out total for each month.
    assert all(rows["fixed"]["monthly"][m] + rows["variable"]["monthly"][m] == budget_total(year, m, "expense") for m in range(12))


def test_budget_of_a_removed_category_counts_as_variable(year):
    from app.services.aggregation import budget_kind_rows
    year.budgets.expense["Old gym"] = [30.0] + [0.0] * 11
    assert budget_kind_rows(year)["variable"]["monthly"][0] == 430


# --- Planned split of income (Forecast tab's budget plan) ------------------

def _blocks(split):
    return {b["key"]: b for b in split["blocks"]}


def test_budget_allocation_splits_planned_income(year):
    """Fixture plan: income 2000; Rent 500 fixed, Food 300 + Fun 100 variable.
    -> fixed 25 %, variable 20 %, investment 0 %, savings 1100 = 55 %."""
    from app.services.cashflow import budget_allocation
    alloc = budget_allocation(year)
    may = alloc["months"][4]
    assert may["income"] == 2000 and may["cash_out"] == 900 and may["shortfall"] == 0
    b = _blocks(may)
    assert [b[k]["share"] for k in ("fixed", "variable", "investment", "savings")] == [25, 20, 0, 55]
    assert b["savings"]["amount"] == 1100
    # The guide: fixed below 50 % is fine; investing below 10 % deserves attention.
    assert b["fixed"]["status"] == "below" and not b["fixed"]["attention"]
    assert b["variable"]["status"] == "within"
    assert b["investment"]["status"] == "below" and b["investment"]["attention"]
    assert may["attention"] == 1
    # Bar widths follow the shares when the plan earns more than it spends.
    assert [b[k]["width"] for k in ("fixed", "variable", "investment", "savings")] == [25, 20, 0, 55]
    # The year adds the twelve months.
    y = _blocks(alloc["year"])
    assert alloc["year"]["income"] == 24000 and y["savings"]["amount"] == 13200 and y["savings"]["share"] == 55


def test_budget_allocation_counts_investment_categories(year):
    from app.models import Category
    from app.services.cashflow import budget_allocation
    year.categories.expense.append(Category(name="ETF", kind="investment"))
    year.budgets.expense["ETF"] = [300.0] * 12
    b = _blocks(budget_allocation(year)["months"][0])
    assert b["investment"]["amount"] == 300 and b["investment"]["share"] == 15
    assert b["investment"]["status"] == "within" and not b["investment"]["attention"]
    assert b["savings"]["amount"] == 800 and b["savings"]["share"] == 40


def test_budget_allocation_when_the_plan_spends_more_than_it_earns(year):
    from app.services.cashflow import budget_allocation
    year.budgets.income["Salary"][6] = 600.0
    july = budget_allocation(year)["months"][6]
    b = _blocks(july)
    assert b["savings"]["amount"] == -300 and july["shortfall"] == 300
    # The bar is as long as the cash out (900); negative savings take no room.
    assert b["fixed"]["width"] == round(500 / 900 * 100, 2) and b["savings"]["width"] == 0


def test_budget_allocation_month_without_income(year):
    from app.services.cashflow import budget_allocation
    year.budgets.income["Salary"][11] = 0.0
    dec = budget_allocation(year)["months"][11]
    assert dec["income"] == 0 and dec["shortfall"] == 900
    assert all(b["share"] == 0 and b["status"] is None for b in dec["blocks"])


def test_budget_shares_and_amount_from_share(year):
    from app.services.cashflow import amount_from_share, budget_shares
    year.budgets.income["Salary"][3] = 0.0
    shares = budget_shares(year, year.budgets.expense["Food"])
    assert shares[0] == 15 and shares[3] is None
    assert amount_from_share(year, 0, 12.5) == 250
    assert amount_from_share(year, 0, 33.333) == 666.66
    with pytest.raises(ValueError):
        amount_from_share(year, 3, 10)
