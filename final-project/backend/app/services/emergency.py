"""Emergency-fund tile: how many months of essential costs the fund covers.

- **Emergency savings** = what is saved in the goal marked as the emergency
  fund, counting contributions up to the end of the month shown. A completed
  emergency fund still counts (the money is meant to stay); a stopped one not.
- **Usual essential costs** = the median, over the months before the one
  shown, of what the essential categories cost. Which categories are
  essential is taken from the year shown. Like the liquidity yardstick, the
  month's own figure stands in when no earlier month has essential costs.
- **Months covered** = savings ÷ usual essential costs, and a status:
  under 1 "Too thin" (red), 1 to under 3 "Building" (amber), 3 or more
  "Healthy" (green) — always a word as well as a colour.
"""

from __future__ import annotations

from statistics import median
from typing import Any

from ..config import EMERGENCY_THRESHOLDS
from ..models import AppData, SavingsGoal
from .cashflow import baseline_months, month_end


def _round2(v: float) -> float:
    return round(v, 2)


def status_for(months: float) -> tuple[str, str]:
    """(tone, word) for a number of months covered."""
    thin, healthy = EMERGENCY_THRESHOLDS
    if months < thin:
        return "red", "Too thin"
    if months < healthy:
        return "amber", "Building"
    return "green", "Healthy"


def fund_goal(data: AppData) -> SavingsGoal | None:
    for g in data.goals:
        if g.emergency_fund and g.status != "abandoned":
            return g
    return None


def essential_costs(data: AppData, y: int, m: int, names: set[str]) -> float:
    year = data.get_year(y)
    if year is None:
        return 0.0
    return _round2(sum(
        t.amount for t in year.transactions
        if t.type == "expense" and t.month == m and t.cat in names and not t.one_off
    ))


def build(data: AppData, year_num: int, month: int) -> dict[str, Any]:
    year = data.get_year(year_num)
    names = {c.name for c in year.categories.expense if c.essential} if year else set()
    goal = fund_goal(data)
    limit = month_end(year_num, month).isoformat()
    saved = _round2(sum(c.signed for c in goal.contributions if c.date <= limit)) if goal else 0.0

    usual: float | None = None
    basis = "none"
    if names:
        earlier = [essential_costs(data, y, m, names) for y, m in baseline_months(data, year_num, month)]
        if earlier and median(earlier) > 0:
            usual, basis = _round2(median(earlier)), "typical"
        else:
            this_month = essential_costs(data, year_num, month, names)
            if this_month > 0:
                usual, basis = this_month, "this_month"

    if goal is None:
        state = "no_goal"
    elif not names:
        state = "no_essentials"
    elif usual is None:
        state = "no_costs"
    else:
        state = "ready"

    months = round(saved / usual, 1) if state == "ready" and usual else None
    tone, word = status_for(saved / usual) if state == "ready" and usual else (None, None)
    return {
        "state": state,
        "goal_id": goal.id if goal else None,
        "goal_name": goal.name if goal else None,
        "target": goal.target_amount if goal else None,
        "saved": saved,
        "essential_categories": sorted(names),
        "usual_essential_costs": usual,
        "costs_basis": basis,
        "months_covered": months,
        "tone": tone,
        "status": word,
    }
