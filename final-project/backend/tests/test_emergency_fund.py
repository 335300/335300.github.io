"""Emergency-fund tile: months covered and the red / amber / green status.

Uses the shared ``data`` fixture (conftest): 2026 tracked from March.
March: Rent 500, Food 250, Fun 120. April: Rent 500, Food 240.50.
"""

from __future__ import annotations

import pytest

from app.models import Contribution, SavingsGoal
from app.services import emergency

from .conftest import tx


def goal(saved: float, **kw) -> SavingsGoal:
    return SavingsGoal(
        id=1, name="Emergency fund", target_amount=4500, target_date="2027-12-31",
        created_date="2026-01-01", emergency_fund=True,
        contributions=[Contribution(id=1, date="2026-03-01", amount=saved)] if saved else [], **kw,
    )


def mark_essential(data, *names):
    for c in data.years["2026"].categories.expense:
        c.essential = c.name in names


@pytest.mark.parametrize("months,tone,word", [
    (0.0, "red", "Too thin"),
    (0.99, "red", "Too thin"),
    (1.0, "amber", "Building"),
    (2.99, "amber", "Building"),
    (3.0, "green", "Healthy"),
    (8.0, "green", "Healthy"),
])
def test_status_boundaries(months, tone, word):
    assert emergency.status_for(months) == (tone, word)


def test_needs_a_goal(data):
    mark_essential(data, "Rent")
    assert emergency.build(data, 2026, 4)["state"] == "no_goal"


def test_needs_essential_categories(data):
    data.goals = [goal(1000)]
    result = emergency.build(data, 2026, 4)
    assert result["state"] == "no_essentials" and result["saved"] == 1000


def test_months_covered_uses_the_median_of_earlier_months(data):
    """May: earlier months are March (500 + 250 = 750) and April (500 + 240.50 = 740.50).
    Median 745.25; 1,500 / 745.25 = 2.0 months -> "Building"."""
    mark_essential(data, "Rent", "Food")
    data.goals = [goal(1500)]
    result = emergency.build(data, 2026, 4)
    assert result["state"] == "ready"
    assert result["usual_essential_costs"] == 745.25 and result["costs_basis"] == "typical"
    assert result["months_covered"] == 2.0
    assert (result["tone"], result["status"]) == ("amber", "Building")
    assert result["essential_categories"] == ["Food", "Rent"]


def test_healthy_fund(data):
    mark_essential(data, "Rent")
    data.goals = [goal(1500)]  # 1,500 / 500 = 3 months
    result = emergency.build(data, 2026, 4)
    assert result["months_covered"] == 3.0 and result["status"] == "Healthy"


def test_first_month_uses_its_own_costs(data):
    mark_essential(data, "Rent", "Fun")
    data.goals = [goal(310)]  # March: rent 500 + fun 120 = 620 -> 0.5 months
    result = emergency.build(data, 2026, 2)
    assert result["costs_basis"] == "this_month" and result["months_covered"] == 0.5
    assert result["status"] == "Too thin"


def test_contributions_after_the_month_do_not_count(data):
    mark_essential(data, "Rent")
    g = goal(500)
    g.contributions.append(Contribution(id=2, date="2026-06-10", amount=1000))
    data.goals = [g]
    assert emergency.build(data, 2026, 4)["saved"] == 500
    assert emergency.build(data, 2026, 5)["saved"] == 1500


def test_a_stopped_goal_is_not_the_fund(data):
    mark_essential(data, "Rent")
    data.goals = [goal(1000, status="abandoned")]
    assert emergency.build(data, 2026, 4)["state"] == "no_goal"


def test_no_essential_costs_recorded(data):
    mark_essential(data, "Rent")
    data.years["2026"].transactions = [tx(1, "income", 2, 2000, "Salary")]
    data.goals = [goal(1000)]
    assert emergency.build(data, 2026, 3)["state"] == "no_costs"


def test_dashboard_carries_the_tile(data):
    from app.services import dashboard
    assert dashboard.build(data, 2026, 4)["emergency"]["state"] == "no_goal"
