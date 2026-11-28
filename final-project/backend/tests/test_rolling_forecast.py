"""Rolling 12-month forecast, across the year boundary, with graduation scenarios.

Made-up data: 2026 tracked from January, opening balance 1,000.
Budget every month: Salary 1,500 + Other income 100; Rent 500 (fixed),
Health 100 (fixed), Food 300 (variable) -> 700 kept a month.
Only October is recorded: salary 2,000, rent 500 -> balance 2,500 at its close.
"""

from __future__ import annotations

import pytest

from app.models import (
    AppData,
    Category,
    GraduationScenario,
    IncomePlan,
    LecturePeriod,
    Payslip,
    YearBudgets,
    YearCategories,
    YearData,
)
from app.services import rolling_forecast as rf

from .conftest import tx


@pytest.fixture
def data() -> AppData:
    year = YearData(
        opening_balance=1000,
        start_month=-1,
        categories=YearCategories(
            expense=[Category(name="Rent", kind="fixed"), Category(name="Health", kind="fixed"), Category(name="Food")],
            income=[Category(name="Salary"), Category(name="Other income")],
        ),
        budgets=YearBudgets(
            expense={"Rent": [500.0] * 12, "Health": [100.0] * 12, "Food": [300.0] * 12},
            income={"Salary": [1500.0] * 12, "Other income": [100.0] * 12},
        ),
        transactions=[tx(1, "income", 9, 2000, "Salary"), tx(2, "expense", 9, 500, "Rent")],
        next_id=3,
    )
    d = AppData()
    d.years["2026"] = year
    return d


def plan(**changes) -> IncomePlan:
    base = dict(
        hourly_rate=20,
        hours_lecture_week=20,
        hours_break_week=40,
        lecture_periods=[
            LecturePeriod(start="2026-10-01", end="2027-01-15"),
            LecturePeriod(start="2027-03-15", end="2027-07-09"),
            LecturePeriod(start="2027-10-01", end="2028-01-15"),
        ],
        salary_category="Salary",
        health_category="Health",
        net_method="payslips",
        payslips=[
            Payslip(id=1, month="2026-10", gross=1000, net=900),
            Payslip(id=2, month="2026-09", gross=3000, net=2100),
        ],
        scenarios=[
            GraduationScenario(name="Early end", job_end="2027-01-15", health_insurance_monthly=250),
            GraduationScenario(name="Late end", job_end="2027-08-31", health_insurance_monthly=250, new_net_salary=3000),
        ],
    )
    base.update(changes)
    return IncomePlan(**base)


def by_key(result, key):
    return next(r for r in result["rows"] if r["key"] == key)


def test_twelve_months_across_the_year_end_from_the_budget(data):
    result = rf.build(data)
    planned = [r for r in result["rows"] if not r["actual"]]
    assert len(planned) == 12
    assert planned[0]["key"] == "2026-11" and planned[-1]["key"] == "2027-10"
    assert result["start_name"] == "November 2026" and result["end_name"] == "October 2027"
    assert result["starting_balance"] == 2500
    # 2027 is not set up, so its months borrow the 2026 budget.
    assert result["borrowed_budget_years"] == [2026]
    assert by_key(result, "2027-03")["budget_from"] == 2026
    (line,) = result["lines"]
    assert line["key"] == "plan" and line["end_balance"] == 2500 + 12 * 700
    assert line["kept"] == 8400 and result["calendar_used"] is False


def test_recorded_months_come_first_for_context(data):
    result = rf.build(data)
    actual = [r for r in result["rows"] if r["actual"]]
    assert [r["key"] for r in actual] == ["2026-08", "2026-09", "2026-10"]
    assert actual[-1]["values"]["plan"]["balance"] == 2500
    assert actual[-1]["values"]["plan"]["income"] == 2000


def test_a_set_up_year_uses_its_own_budget(data):
    data.years["2027"] = data.years["2026"].model_copy(deep=True)
    data.years["2027"].transactions = []
    data.years["2027"].budgets.expense["Food"] = [400.0] * 12
    result = rf.build(data)
    assert result["borrowed_budget_years"] == []
    assert by_key(result, "2027-02")["values"]["plan"]["expenses"] == 1000


def test_one_line_per_scenario(data):
    data.income_plan = plan()
    result = rf.build(data)
    assert result["calendar_used"] is True
    assert [line["name"] for line in result["lines"]] == ["Early end", "Late end"]
    assert [line["key"] for line in result["lines"]] == ["s0", "s1"]


def test_calendar_pay_replaces_the_salary_budget(data):
    data.income_plan = plan()
    early = by_key(rf.build(data), "2027-02")["values"]["s0"]
    # Early end (15 Jan): February gets January's contract pay: 11 lecture days
    # x 4 h x 20 = 880 gross x 0.9 = 792 net. Plus the other income (100).
    assert early["salary"] == 792
    assert early["income"] == 100 + 792
    # March gets nothing from the student job any more.
    assert by_key(rf.build(data), "2027-03")["values"]["s0"]["income"] == 100


def test_health_insurance_switches_after_the_job_ends(data):
    data.income_plan = plan()
    result = rf.build(data)
    # Early end in January: from February, Health costs 250 instead of 100.
    assert by_key(result, "2027-01")["values"]["s0"]["expenses"] == 900
    assert by_key(result, "2027-02")["values"]["s0"]["expenses"] == 1050
    # Late end in August: still 100 in August, 250 from September.
    assert by_key(result, "2027-08")["values"]["s1"]["expenses"] == 900
    assert by_key(result, "2027-09")["values"]["s1"]["expenses"] == 1050


def test_new_salary_after_graduation(data):
    data.income_plan = plan()
    october = by_key(rf.build(data), "2027-10")["values"]["s1"]
    # The new job's September pay (3,000) arrives in October, with August's
    # extra hours (22 break days x 4 h x 20 = 1,760 gross x 0.7 = 1,232).
    assert october["income"] == 100 + 3000 + 1232


def test_lines_differ_only_where_the_scenarios_differ(data):
    data.income_plan = plan()
    nov = by_key(rf.build(data), "2026-11")["values"]
    assert nov["s0"] == nov["s1"]


def test_no_payslips_keeps_the_budget(data):
    data.income_plan = plan(payslips=[])
    result = rf.build(data)
    assert result["calendar_used"] is False
    assert [line["key"] for line in result["lines"]] == ["plan"]
    assert result["lines"][0]["end_balance"] == 2500 + 12 * 700


def test_switched_off_calendar_keeps_the_budget(data):
    data.income_plan = plan(enabled=False)
    assert rf.build(data)["calendar_used"] is False


def test_without_scenarios_the_job_just_goes_on(data):
    data.income_plan = plan(scenarios=[])
    result = rf.build(data)
    (line,) = result["lines"]
    assert line["name"] == "Plan" and result["calendar_used"] is True
    # December 2026 gets November's pay: a full lecture month,
    # 21 weekdays x 4 h x 20 = 1,680 gross; ratio 0.9 - 0.2 x 680/2,000 = 0.832.
    assert by_key(result, "2026-12")["values"]["plan"]["salary"] == 1397.76


def test_nothing_recorded_starts_with_the_first_tracked_month():
    d = AppData()
    d.years["2026"] = YearData(opening_balance=300, start_month=4)
    result = rf.build(d)
    assert result["start"] == "2026-06" and result["starting_balance"] == 300
    assert all(not r["actual"] for r in result["rows"])


def test_no_year_at_all():
    assert rf.build(AppData())["rows"] == []


def test_lowest_point_and_negative_flag(data):
    data.years["2026"].budgets.expense["Food"] = [2000.0] * 12
    line = rf.build(data)["lines"][0]
    # Each month now loses 1,000: 2,500 -> -9,500 after twelve months.
    assert line["goes_negative"] is True
    assert line["lowest_balance"] == 2500 - 12 * 1000
    assert line["lowest_label"] == "October 2027"


def test_tax_rules_switch_the_calendar_on_without_payslips():
    from app.services.rolling_forecast import calendar_active
    assert calendar_active(plan(net_method="tax_rules", payslips=[])) is True
    assert calendar_active(plan(net_method="payslips", payslips=[])) is False
    assert calendar_active(plan(net_method="tax_rules", payslips=[], hourly_rate=0)) is False


# --- Savings goals in the forecast --------------------------------------------
# Balance 2,500 at the close of October; 700 kept every planned month from November.

def _goal(id, name, amount, due, saved=0.0, **kw):
    from app.models import Contribution, SavingsGoal
    contributions = [Contribution(id=1, date="2026-10-10", amount=saved)] if saved else []
    return SavingsGoal(id=id, name=name, target_amount=amount, target_date=due, created_date="2026-10-01",
                       contributions=contributions, next_contribution_id=2, **kw)


def test_a_goal_is_spent_in_its_deadline_month(data):
    data.goals = [_goal(1, "Laptop", 1000, "2027-01-20", saved=200)]
    result = rf.build(data)
    jan = by_key(result, "2027-01")
    assert jan["goals"] == [{"goal_id": 1, "name": "Laptop", "amount": 1000, "overdue": False}]
    # Nov 3 200, Dec 3 900, Jan 4 600 − 1 000 = 3 600.
    assert by_key(result, "2026-12")["values"]["plan"]["balance"] == 3900
    assert jan["values"]["plan"]["balance"] == 3600 and jan["values"]["plan"]["goal_spend"] == 1000
    # Free to use: 200 saved + the other 800 spread over Nov, Dec, Jan; spent in January.
    assert by_key(result, "2026-11")["values"]["plan"]["free"] == round(3200 - (200 + 800 / 3), 2)
    assert jan["values"]["plan"]["free"] == 3600
    (line,) = result["lines"]
    assert line["end_balance"] == 2500 + 8400 - 1000 and line["spent_on_goals"] == 1000
    assert line["kept"] == 8400  # what a month keeps does not change; the purchase spends savings
    assert result["goals_spent"] == 1000


def test_goal_purchases_can_be_left_out(data):
    data.goals = [_goal(1, "Laptop", 1000, "2027-01-20")]
    result = rf.build(data, include_goals=False)
    assert by_key(result, "2027-01")["goals"] == [] and result["lines"][0]["end_balance"] == 2500 + 8400
    assert by_key(result, "2027-01")["values"]["plan"]["free"] is None


def test_the_emergency_fund_stays_and_sinking_funds_are_opt_in(data):
    data.goals = [
        _goal(1, "Emergency", 3000, "2027-03-31", emergency_fund=True),
        _goal(2, "Insurance", 300, "2027-02-01", goal_type="sinking", repeat_months=6),
        _goal(3, "Tuition", 600, "2027-02-01", goal_type="sinking", repeat_months=6, spend_in_forecast=True),
        _goal(4, "Old trip", 900, "2027-05-01", status="completed"),
    ]
    result = rf.build(data)
    spent = [(r["key"], p["name"]) for r in result["rows"] for p in r.get("goals", [])]
    assert spent == [("2027-02", "Tuition"), ("2027-08", "Tuition")]
    # The emergency fund is earmarked up to its target and stays there.
    oct27 = by_key(result, "2027-10")["values"]["plan"]
    # Both sinking funds are two months into their next six-month cycle.
    tuition_left = 600 * 2 / 6 + 300 * 2 / 6
    assert oct27["free"] == round(oct27["balance"] - 3000 - tuition_left, 2)


def test_an_overdue_goal_is_bought_in_the_first_planned_month(data):
    data.goals = [_goal(1, "Bike", 400, "2026-09-30")]
    nov = by_key(rf.build(data), "2026-11")
    assert nov["goals"][0]["overdue"] is True and nov["values"]["plan"]["balance"] == 2500 + 700 - 400


def test_goal_checks_and_expected_savings(data):
    data.goals = [
        _goal(1, "Laptop", 1000, "2027-01-20"),
        _goal(2, "House", 50_000, "2027-02-15"),
        _goal(3, "Emergency", 3000, "2027-03-31", emergency_fund=True),
        _goal(4, "Far away", 500, "2028-06-01"),
    ]
    checks = rf.goal_checks(data)
    assert checks[1] == {"month": "2027-01", "month_name": "January 2027", "spent": True, "balance": 3600,
                         "affordable": True, "line": None}
    assert checks[2]["affordable"] is False and checks[2]["balance"] == 2500 + 4 * 700 - 1000 - 50_000
    # Kept, not spent: March holds 2 500 + 5·700 − 1 000 − 50 000 < 3 000.
    assert checks[3]["spent"] is False and checks[3]["affordable"] is False
    assert 4 not in checks  # after the 12 months shown
    assert rf.expected_monthly_savings(data) == 700
