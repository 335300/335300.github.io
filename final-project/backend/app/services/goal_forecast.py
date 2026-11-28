"""Savings goals in the rolling forecast.

Putting money toward a goal only *earmarks* it — it stays in the account. The
balance moves when the goal is **spent**: the laptop is bought, the driving
school is paid. This module says when that happens and how much stays
earmarked along the way.

- :func:`purchases` — each active goal that is spent in the forecast
  (``SavingsGoal.spends_in_forecast``) costs its target in its deadline month;
  a sinking fund on every due date in the window. A deadline already passed
  falls in the first planned month (the purchase is still to come).
- :func:`earmarked` — what is set aside for goals at the end of each planned
  month, if each goal is saved for at its even pace (what is saved today, plus
  the rest spread over the months up to its deadline). A spent goal's money
  is gone after its month; a sinking fund then starts again from zero; a goal
  that is not spent (the emergency fund) stays at its target. A sinking fund
  always starts again after each due date — its bill is paid either by the
  forecast's purchase or by the budget line it usually has.

The forecast's **free to use** line is balance − earmarked: the money no goal
has a claim on.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..models import SavingsGoal
from . import income_calendar as ic

YM = tuple[int, int]


def _round2(v: float) -> float:
    return round(v + 0.0, 2)


def _due(goal: SavingsGoal) -> YM:
    return ic.ym_of(date.fromisoformat(goal.target_date))


def _active(goals: list[SavingsGoal]) -> list[SavingsGoal]:
    return [g for g in goals if g.status == "active"]


def purchases(goals: list[SavingsGoal], first: YM, horizon: int) -> dict[YM, list[dict[str, Any]]]:
    """``{month: [{goal_id, name, amount, overdue}]}`` for the planned months."""
    start, end = ic.ym_index(first), ic.ym_index(first) + horizon - 1
    out: dict[YM, list[dict[str, Any]]] = {}
    for g in _active(goals):
        if not g.spends_in_forecast():
            continue
        due = ic.ym_index(_due(g))
        step = g.repeat_months if g.goal_type == "sinking" and g.repeat_months else None
        months: list[tuple[int, bool]] = []
        if due < start:
            months.append((start, True))  # overdue: still to be paid, so in the first planned month
            if step:
                due += ((start - due) // step + 1) * step
        while due <= end:
            if due >= start:
                months.append((due, False))
            if not step:
                break
            due += step
        for index, overdue in months:
            ym = ic.ym_from_index(index)
            out.setdefault(ym, []).append(
                {"goal_id": g.id, "name": g.name, "amount": g.target_amount, "overdue": overdue}
            )
    return out


def earmarked(goals: list[SavingsGoal], first: YM, horizon: int) -> list[float]:
    """Money set aside for goals at the end of each planned month."""
    start = ic.ym_index(first)
    totals = [0.0] * horizon
    for g in _active(goals):
        saved = g.saved()
        target = g.target_amount
        t = ic.ym_index(_due(g)) - start           # months from the first planned month
        spends = g.spends_in_forecast()
        step = g.repeat_months if g.goal_type == "sinking" and g.repeat_months else None
        for i in range(horizon):
            if t < 0:
                if step:
                    # Overdue bill paid in the first month, then saving for the next one.
                    value = target * (i % step) / step
                else:
                    value = 0.0 if spends else max(saved, 0.0)
            elif i < t:
                value = saved + max(target - saved, 0.0) * (i + 1) / (t + 1)
            elif step:
                # A sinking fund pays its bill on the due date — from the forecast's
                # purchase, or from the budget line it already has — and starts again.
                value = target * ((i - t) % step) / step
            elif not spends:
                value = max(saved, target)
            else:
                value = 0.0
            totals[i] += value
    return [_round2(v) for v in totals]
