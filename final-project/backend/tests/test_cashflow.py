"""Cash in / cash out, investments, the income distribution and cost history."""

from __future__ import annotations

from datetime import date

import pytest

from app.models import AppData, Category, Contribution, InvestmentPlan, SavingsGoal, YearCategories, YearData
from app.services import aggregation, cashflow, dashboard, investments, projection
from app.services import goals as goals_service

from .conftest import TODAY, tx


def with_land(year: YearData) -> YearData:
    """The conftest year plus an investment category: 300 in March (1 cuota), 300 in April (2 cuotas)."""
    year.categories.expense.append(Category(name="Land", kind="investment"))
    year.budgets.expense["Land"] = [300.0] * 12
    a = tx(20, "expense", 2, 300, "Land")
    a.installments = 1
    b = tx(21, "expense", 3, 300, "Land")
    b.installments = 2
    year.transactions += [a, b]
    return year


def land_plan(**changes) -> InvestmentPlan:
    fields = dict(
        id=1, name="Land", category="Land", unit="cuota", local_currency="Gs", installment_amount=2_170_000,
        total_installments=130, paid_before=15, cost_per_installment=340, created_date="2026-01-01",
    )
    return InvestmentPlan(**{**fields, **changes})


def goal(saved=(), status="active", id=1, target=900.0, deadline="2027-03-31") -> SavingsGoal:
    g = SavingsGoal(id=id, name=f"Goal {id}", target_amount=target, target_date=deadline,
                    created_date="2026-01-01", status=status)
    for when, amount in saved:
        g.contributions.append(Contribution(id=g.take_contribution_id(), date=when, amount=amount))
    return g


# -- investment is cash out, not spending -------------------------------------

def test_kind_totals_add_up_to_all_cash_out(year):
    with_land(year)
    assert aggregation.kind_totals(year, 2) == {"fixed": 500, "variable": 370, "investment": 300}
    assert sum(aggregation.kind_totals(year, 2).values()) == aggregation.month_total(year, 2, "expense")
    assert aggregation.budget_kind_totals(year, 2) == {"fixed": 500, "variable": 400, "investment": 300}


def test_kpis_separate_investment_from_spending(data, year):
    with_land(year)
    k = dashboard.kpis(data, year, 2026, 2)
    assert k["cash_in"] == 2000
    assert k["spent"] == 870 and k["invested"] == 300 and k["cash_out"] == 1170
    assert k["savings"] == 830 and k["savings_rate"] == 41.5
    assert k["wealth_built"] == 1130 and k["wealth_rate"] == 56.5
    assert k["spent_budget"] == 900 and k["invested_budget"] == 300 and k["cash_out_budget"] == 1200
    # The balance still follows every euro that left the account.
    assert k["current_balance"] == 1000 + 830


def test_cost_split_leaves_investment_out(year):
    with_land(year)
    costs = dashboard.cost_split(year, 2)
    assert costs["month_spend"] == 870
    assert "Land" not in [r["cat"] for r in costs["ranked"]]


def test_budget_vs_real_keeps_investment_row_as_planned_cash_out(year):
    with_land(year)
    rows = {r["cat"]: r for r in dashboard.budget_vs_real(year, 2)["rows"]}
    assert rows["Land"]["kind"] == "investment" and rows["Land"]["status"] == "on_budget"
    assert dashboard.budget_vs_real(year, 2)["total"]["real"] == 1170


def test_projection_splits_invested_from_expenses(year):
    with_land(year)
    p = projection.build(year, 2026)
    assert p["rows"][0]["expenses"] == 870 and p["rows"][0]["invested"] == 300 and p["rows"][0]["savings"] == 830
    # A budgeted month: 2000 - 900 costs - 300 invested.
    assert p["rows"][2]["invested"] == 300 and p["rows"][2]["savings"] == 800
    s = p["summary"]
    assert s["actual_invested"] == 600 and s["planned_invested"] == 8 * 300
    assert s["year_end_invested"] == 3000


def test_free_balance_is_balance_minus_earmarked(data, year):
    data.goals = [
        goal(saved=[("2026-03-10", 200), ("2026-04-02", 50)]),
        goal(saved=[("2026-03-15", 999)], status="abandoned", id=2),  # gives its money back
    ]
    march = dashboard.kpis(data, year, 2026, 2)
    assert march["earmarked"] == 200 and march["free_balance"] == march["current_balance"] - 200
    assert dashboard.kpis(data, year, 2026, 3)["earmarked"] == 250


# -- where the income went ----------------------------------------------------

def test_distribution_blocks_and_segments(year):
    with_land(year)
    goals = [goal(saved=[("2026-03-31", 200), ("2026-04-01", 70)])]
    d = cashflow.distribution(year, 2026, 2, goals)
    assert d["income"] == 2000 and d["cash_out"] == 1170
    assert {b["key"]: (b["amount"], b["share"]) for b in d["blocks"]} == {
        "fixed": (500, 25.0), "variable": (370, 18.5), "investment": (300, 15.0), "savings": (830, 41.5),
    }
    assert d["saved"] == 830 and d["to_goals"] == 200 and d["left_to_assign"] == 630
    assert d["shortfall"] == 0 and d["over_assigned"] is False
    assert [(s["key"], s["amount"], s["width"]) for s in d["segments"]] == [
        ("fixed", 500, 25.0), ("variable", 370, 18.5), ("investment", 300, 15.0),
        ("goals", 200, 10.0), ("unassigned", 630, 31.5),
    ]
    assert round(sum(s["width"] for s in d["segments"]), 2) == 100.0


def test_distribution_guide_status(year):
    with_land(year)
    blocks = {b["key"]: b for b in cashflow.distribution(year, 2026, 2, [])["blocks"]}
    # Costs below their range are fine; investing and saving inside theirs too.
    assert blocks["fixed"]["status"] == "below" and blocks["fixed"]["attention"] is False
    assert blocks["investment"]["status"] == "within" and blocks["savings"]["status"] == "within"
    assert (blocks["fixed"]["guide_min"], blocks["fixed"]["guide_max"]) == (50.0, 60.0)

    year.transactions.append(tx(30, "expense", 2, 900, "Rent"))      # fixed 1400 of 2000 = 70 %
    blocks = {b["key"]: b for b in cashflow.distribution(year, 2026, 2, [])["blocks"]}
    assert blocks["fixed"]["status"] == "above" and blocks["fixed"]["attention"] is True
    assert blocks["savings"]["share"] == -3.5 and blocks["savings"]["attention"] is True


def test_distribution_when_more_went_out_than_came_in(year):
    year.transactions.append(tx(30, "expense", 5, 100, "Food"))  # June: no income
    d = cashflow.distribution(year, 2026, 5, [goal(saved=[("2026-06-10", 40)])])
    assert d["saved"] == -100 and d["shortfall"] == 100 and d["left_to_assign"] == 0
    assert d["over_assigned"] is True
    assert all(b["status"] is None for b in d["blocks"])
    assert {s["key"]: s["amount"] for s in d["segments"]}["goals"] == 0


def test_suggest_serves_goals_by_deadline_until_the_money_runs_out():
    built = goals_service.build_all(
        [goal(id=1, target=600, deadline="2027-03-31"),          # 6 months -> 100 a month
         goal(id=2, target=500, deadline="2026-12-31"),          # 3 months -> 166.67 a month
         goal(id=3, target=50, deadline="2026-01-31"),           # overdue -> everything
         goal(id=4, status="completed")],
        expected_monthly_savings=1000, today=TODAY,
    )["goals"]
    out = goals_service.suggest(built, 250)
    assert [(s["goal_id"], s["suggested"]) for s in out] == [(3, 50), (2, 166.67), (1, 33.33)]
    assert round(sum(s["suggested"] for s in out), 2) == 250
    assert goals_service.suggest(built, 0)[0]["suggested"] == 0


# -- cost history -------------------------------------------------------------

def two_years() -> AppData:
    """2025 tracked from October; variable costs 100, 200, 300, then 400, 500, 600 in 2026."""
    cats = YearCategories(expense=[Category(name="Rent", kind="fixed"), Category(name="Food")])
    y25 = YearData(start_month=8, categories=cats.model_copy(deep=True))
    y26 = YearData(categories=cats.model_copy(deep=True))
    for i, m in enumerate((9, 10, 11)):
        y25.transactions += [tx(1 + i, "expense", m, 100 * (i + 1), "Food", year=2025),
                             tx(10 + i, "expense", m, 300, "Rent", year=2025)]
    for i, m in enumerate((0, 1, 2)):
        y26.transactions += [tx(1 + i, "expense", m, 100 * (i + 4), "Food"),
                             tx(10 + i, "expense", m, 300, "Rent")]
    d = AppData()
    d.years["2025"], d.years["2026"] = y25, y26
    return d


def test_months_back_crosses_years_and_stops_where_tracking_began():
    d = two_years()
    assert cashflow.months_back(d, 2026, 2, 12) == [(2025, 9), (2025, 10), (2025, 11), (2026, 0), (2026, 1), (2026, 2)]
    assert cashflow.months_back(d, 2026, 2, 2) == [(2026, 1), (2026, 2)]
    # A month with nothing recorded is only included when it is the selected one.
    assert cashflow.months_back(d, 2026, 5, 3) == [(2026, 1), (2026, 2), (2026, 5)]
    assert cashflow.months_back(d, 2026, 5, 3, include_selected=False) == [(2026, 0), (2026, 1), (2026, 2)]
    assert cashflow.months_back(d, 1999, 0, 3) == []


def test_history_compares_the_month_with_the_months_before_it():
    h = cashflow.history(two_years(), 2026, 2)
    assert [r["label"] for r in h["rows"]] == ["Oct 25", "Nov 25", "Dec 25", "Jan 26", "Feb 26", "Mar 26"]
    assert [r["variable_avg3"] for r in h["rows"]] == [None, None, 200, 300, 400, 500]
    v = h["variable"]
    assert v["current"] == 600
    assert v["avg_3m"] == 400            # Dec, Jan, Feb
    assert v["avg_6m"] == 300            # only five earlier months exist
    assert v["median_6m"] == 300 and v["months"] == 5
    assert v["vs_avg_pct"] == 100.0
    assert v["trend_pct"] is None        # needs six earlier months
    assert h["fixed"]["current"] == 300 and h["fixed"]["avg_6m"] == 300 and h["fixed"]["vs_avg_pct"] == 0.0


def test_history_trend_and_median_shrug_off_a_one_off():
    d = two_years()
    y26 = d.get_year(2026)
    for i, m in enumerate((3, 4, 5, 6)):   # Apr-Jul: 100, 100, 100, then a 5000 one-off in July
        y26.transactions.append(tx(40 + i, "expense", m, 5000 if m == 6 else 100, "Food"))
    y26.transactions.append(tx(50, "expense", 7, 150, "Food"))
    v = cashflow.history(d, 2026, 7)["variable"]     # August against Feb..Jul
    assert v["avg_6m"] == round((500 + 600 + 100 + 100 + 100 + 5000) / 6, 2)
    assert v["median_6m"] == 300.0                   # middle of 100,100,100,500,600,5000
    assert v["trend_pct"] == round(((100 + 100 + 5000) / 3 - 400) / 400 * 100, 2)  # May-Jul vs Feb-Apr


def test_history_of_a_single_month_has_no_yardstick(year):
    d = AppData()
    d.years["2026"] = year
    v = cashflow.history(d, 2026, 2)["variable"]
    assert v["current"] == 370 and v["avg_6m"] is None and v["vs_avg_pct"] is None and v["months"] == 0


def test_category_baselines_count_empty_months_as_zero():
    d = two_years()
    d.get_year(2026).transactions.append(tx(60, "expense", 1, 90, "Fun"))
    months = cashflow.baseline_months(d, 2026, 2)
    assert months == [(2025, 9), (2025, 10), (2025, 11), (2026, 0), (2026, 1)]
    base = cashflow.category_baselines(d, months)
    # The median of five months: Fun was bought once (90, 0, 0, 0, 0) -> a usual month costs 0.
    assert base == {"Food": 300.0, "Rent": 300.0, "Fun": 0.0}
    assert cashflow.category_baselines(d, []) == {}
    assert cashflow.recent_months(d, 2026, 3, skip=(2026, 2)) == [(2025, 11), (2026, 0), (2026, 1)]


def test_costs_with_usual():
    d = two_years()
    costs = dashboard.costs_with_usual(d, d.get_year(2026), 2026, 2)
    food = next(r for r in costs["ranked"] if r["cat"] == "Food")
    assert food["amount"] == 600 and food["usual"] == 300 and food["vs_usual_pct"] == 100.0
    assert costs["usual_months"] == 5


# -- investment plans ---------------------------------------------------------

def test_plan_progress(data, year):
    with_land(year)
    data.investments = [land_plan()]
    p = investments.build(data.investments[0], data, 2026, 2, TODAY)
    assert p["paid"] == 18 and p["remaining"] == 112        # 15 before + 1 + 2
    assert p["progress_pct"] == 13.85
    assert p["paid_local"] == 18 * 2_170_000 and p["total_local"] == 130 * 2_170_000
    assert p["value_at_cost"] == 18 * 340 and p["remaining_cost"] == 112 * 340
    assert p["recorded_total"] == 600 and p["invested_year"] == 600
    assert p["invested_month"] == 300 and p["installments_month"] == 1
    assert p["paid_this_month"] is False
    assert p["expected_end"] == "2036-01"                    # Oct 2026 + 111 months
    assert [x["installments"] for x in p["payments"]] == [2, 1]


def test_plan_counts_only_payments_that_say_so(data, year):
    with_land(year)
    year.transactions.append(tx(22, "expense", 9, 332, "Land", day=20))   # no instalment count
    data.investments = [land_plan(cost_per_installment=None)]
    p = investments.build(data.investments[0], data, 2026, 9, TODAY)
    assert p["paid"] == 18 and p["recorded_total"] == 932
    assert p["paid_this_month"] is True and p["expected_end"] == "2036-02"  # next cuota in November
    assert p["value_at_cost"] is None and p["remaining_cost"] is None


@pytest.mark.parametrize(
    "remaining, paid_this_month, expected",
    [(0, False, None), (1, False, "2026-10"), (1, True, "2026-11"), (3, True, "2027-01"), (115, True, "2036-05")],
)
def test_expected_end(remaining, paid_this_month, expected):
    assert investments.expected_end(remaining, paid_this_month, TODAY) == expected


def test_plan_never_exceeds_its_total(data, year):
    with_land(year)
    data.investments = [land_plan(total_installments=16)]
    p = investments.build(data.investments[0], data, 2026, 2, TODAY)
    assert p["paid"] == 16 and p["remaining"] == 0 and p["status"] == "completed" and p["expected_end"] is None


def test_build_all_totals_cover_every_investment_category(data, year):
    with_land(year)
    year.categories.expense.append(Category(name="ETF", kind="investment"))
    year.transactions.append(tx(23, "expense", 2, 50, "ETF"))
    data.investments = [land_plan()]
    out = investments.build_all(data, 2026, 2, TODAY)
    assert out["invested_month"] == 350 and out["invested_year"] == 650
    assert len(out["plans"]) == 1 and out["value_at_cost"] == 18 * 340


def test_dashboard_carries_the_new_sections(data, year):
    with_land(year)
    data.investments = [land_plan()]
    data.goals = [goal()]
    d = dashboard.build(data, 2026, 2, date(2026, 3, 31))
    assert d["distribution"]["left_to_assign"] == 830
    assert d["distribution"]["suggested"][0]["goal_id"] == 1
    assert d["investments"]["plans"][0]["paid"] == 18
    assert d["goals"]["goals"][0]["name"] == "Goal 1" and "built" not in d["goals"]
    assert d["history"]["rows"][-1]["label"] == "Mar 26"
    assert d["kpis"]["invested"] == 300


# -- liquidity ----------------------------------------------------------------

def test_position_splits_what_you_own_by_how_free_it_is():
    p = cashflow.position(balance=5000, set_aside=1500, invested_value=5100, usual_costs=1400)
    assert p["liquidity"] == 3500 and p["balance"] == 5000 and p["total"] == 10100
    assert [(x["key"], x["amount"], x["width"]) for x in p["parts"]] == [
        ("liquid", 3500, 34.65), ("goals", 1500, 14.85), ("investments", 5100, 50.5),
    ]
    assert p["runway_months"] == 2.5 and p["over_earmarked"] is False


def test_position_when_goals_hold_more_than_the_account():
    p = cashflow.position(balance=1000, set_aside=1200, invested_value=0, usual_costs=500)
    assert p["liquidity"] == -200 and p["over_earmarked"] is True and p["runway_months"] == 0
    assert {x["key"]: x["width"] for x in p["parts"]} == {"liquid": 0.0, "goals": 100.0, "investments": 0.0}
    assert cashflow.position(100, 0, 0, None)["runway_months"] is None
    assert cashflow.position(100, 0, 0, None)["costs_basis"] == "none"
    assert cashflow.position(100, 0, 0, 0)["runway_months"] is None


def test_typical_costs_is_the_median_of_the_months_before():
    d = two_years()                                    # costs incl. 300 rent: 400, 500, 600, 700, 800, then 900
    assert cashflow.typical_costs(d, 2026, 2) == 600   # middle of Oct-Feb
    assert cashflow.typical_costs(d, 2025, 9) is None  # nothing before the first tracked month


def test_costs_yardstick_falls_back_to_the_month_itself():
    d = two_years()
    assert cashflow.costs_yardstick(d, 2026, 2) == (600, "typical")
    # First tracked month: nothing before it, so its own costs stand in.
    assert cashflow.costs_yardstick(d, 2025, 9) == (400, "this_month")


def test_costs_yardstick_without_any_costs():
    d = AppData()
    d.years["2026"] = YearData(start_month=8)          # a new profile, nothing recorded yet
    assert cashflow.costs_yardstick(d, 2026, 9) == (None, "none")


def test_dashboard_liquidity(data, year):
    with_land(year)
    data.investments = [land_plan()]
    data.goals = [goal(saved=[("2026-03-10", 200)])]
    d = dashboard.build(data, 2026, 3, date(2026, 4, 30))      # April
    balance = d["kpis"]["current_balance"]
    assert d["kpis"]["liquidity"] == balance - 200 == d["position"]["liquidity"]
    assert d["position"]["invested_value"] == 18 * 340 and d["position"]["total"] == balance + 18 * 340
    # One earlier month (March: 870 of living costs) is the yardstick.
    assert d["position"]["usual_costs"] == 870
    assert d["position"]["runway_months"] == round((balance - 200) / 870, 1)
