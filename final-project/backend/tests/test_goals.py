"""Savings goals: months remaining, pace, status and the combined summary."""

from __future__ import annotations

from datetime import date

import pytest

from app.models import Contribution, SavingsGoal
from app.services import goals

from .conftest import TODAY


def make_goal(target=900.0, deadline="2027-03-31", saved=(), status="active", id=1) -> SavingsGoal:
    g = SavingsGoal(
        id=id, name=f"Goal {id}", target_amount=target, target_date=deadline,
        created_date="2026-01-01", status=status,
    )
    for amount in saved:
        g.contributions.append(Contribution(id=g.take_contribution_id(), date="2026-05-01", amount=amount))
    return g


@pytest.mark.parametrize(
    "deadline, expected",
    [
        (date(2027, 3, 31), 6),   # Oct, Nov, Dec, Jan, Feb, Mar
        (date(2026, 10, 31), 1),  # still this month
        (date(2026, 10, 21), 1),  # deadline is today
        (date(2026, 10, 20), 0),  # yesterday
        (date(2025, 1, 1), 0),
        (date(2027, 10, 1), 13),
    ],
)
def test_months_remaining(deadline, expected):
    assert goals.months_remaining(deadline, TODAY) == expected


def test_required_pace():
    assert goals.required_monthly_pace(400, 6) == 66.67
    assert goals.required_monthly_pace(0, 6) == 0.0
    assert goals.required_monthly_pace(-5, 6) == 0.0
    assert goals.required_monthly_pace(400, 0) is None  # never divides by zero


def test_zero_contributions_on_track():
    g = goals.build(make_goal(target=600, deadline="2027-03-31"), 150, TODAY)
    assert g["saved"] == 0 and g["remaining"] == 600
    assert g["required_monthly_pace"] == 100
    assert g["status"] == "on_track"
    assert g["shortfall"] == 0
    assert g["progress_pct"] == 0


def test_behind_reports_shortfall():
    g = goals.build(make_goal(target=900, saved=[300]), 60, TODAY)
    assert g["required_monthly_pace"] == 100  # 600 over 6 months
    assert g["status"] == "behind"
    assert g["shortfall"] == 40


def test_exactly_covered_is_on_track():
    assert goals.build(make_goal(target=900, saved=[300]), 100, TODAY)["status"] == "on_track"


def test_goal_met_early():
    g = goals.build(make_goal(target=500, saved=[300, 250]), 0, TODAY)
    assert g["status"] == "met"
    assert g["remaining"] == 0 and g["required_monthly_pace"] == 0
    assert g["progress_pct"] == 100.0  # capped even though 110% saved


def test_past_deadline_is_overdue_without_dividing_by_zero():
    g = goals.build(make_goal(target=500, deadline="2026-09-30", saved=[100]), 1000, TODAY)
    assert g["status"] == "overdue"
    assert g["months_remaining"] == 0
    assert g["required_monthly_pace"] is None


def test_met_beats_overdue():
    g = goals.build(make_goal(target=100, deadline="2026-01-31", saved=[100]), 0, TODAY)
    assert g["status"] == "met"


def test_negative_expected_savings_is_behind():
    assert goals.build(make_goal(), -50, TODAY)["status"] == "behind"


def test_user_status_wins():
    assert goals.build(make_goal(status="abandoned"), 1000, TODAY)["status"] == "abandoned"
    assert goals.build(make_goal(status="completed"), 0, TODAY)["status"] == "completed"


def test_contributions_newest_first():
    g = make_goal()
    g.contributions = [
        Contribution(id=1, date="2026-03-01", amount=10),
        Contribution(id=2, date="2026-06-01", amount=20),
    ]
    assert [c["id"] for c in goals.build(g, 0, TODAY)["contributions"]] == [2, 1]


def test_build_all_combined_summary():
    gs = [
        make_goal(id=1, target=600, deadline="2027-03-31"),            # pace 100
        make_goal(id=2, target=1200, deadline="2027-03-31", saved=[600]),  # pace 100
        make_goal(id=3, target=100, saved=[100]),                        # met
        make_goal(id=4, target=999, status="abandoned"),                 # ignored
    ]
    out = goals.build_all(gs, 150, TODAY)
    s = out["summary"]
    assert s["active_goals"] == 3
    assert s["open_goals"] == 2
    assert s["total_required_pace"] == 200
    assert s["expected_monthly_savings"] == 150
    assert s["combined_covered"] is False
    assert s["combined_shortfall"] == 50
    assert s["total_target"] == 1900 and s["total_saved"] == 700
    # Each goal alone is on track, even though together they are not.
    assert {g["id"]: g["status"] for g in out["goals"]} == {1: "on_track", 2: "on_track", 3: "met", 4: "abandoned"}
    assert out["goals"][-1]["id"] == 4


def test_build_all_empty():
    s = goals.build_all([], 100, TODAY)["summary"]
    assert s["total_required_pace"] == 0 and s["combined_covered"] is True


# -- unassigned savings ("Savings" tile) ----------------------------------------

def _contrib_goal(id, status, *items):
    g = make_goal(id=id, status=status)
    for d, amount in items:
        g.contributions.append(Contribution(id=g.take_contribution_id(), date=d, amount=amount))
    return g


def test_allocation_subtracts_this_years_contributions_to_active_goals():
    gs = [
        _contrib_goal(1, "active", ("2026-03-01", 200), ("2026-09-01", 100)),
        _contrib_goal(2, "active", ("2025-12-01", 500)),        # other year: not counted
        _contrib_goal(3, "completed", ("2026-05-01", 400)),     # released
        _contrib_goal(4, "abandoned", ("2026-05-01", 50)),      # released
    ]
    a = goals.allocation(gs, 1000, 2026)
    assert a == {"year": 2026, "saved_this_year": 1000, "assigned": 300, "unassigned": 700, "over_assigned": False}


def test_allocation_counts_met_goals_still_active():
    g = _contrib_goal(1, "active", ("2026-03-01", 900))
    g.target_amount = 900
    assert goals.allocation([g], 1000, 2026)["assigned"] == 900


def test_allocation_can_go_negative():
    a = goals.allocation([_contrib_goal(1, "active", ("2026-03-01", 300.5))], 100, 2026)
    assert a["unassigned"] == -200.5 and a["over_assigned"] is True


def test_allocation_without_goals():
    assert goals.allocation([], -50, 2026)["unassigned"] == -50
