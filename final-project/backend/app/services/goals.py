"""Savings goals: pace, status and the combined picture.

Pure functions. ``today`` is always passed in — nothing here reads the clock —
so deadline logic is deterministic and testable.

Status values:
- ``met``       — saved at least the target.
- ``overdue``   — deadline passed, target not reached.
- ``on_track``  — the forecast's expected monthly savings cover the required pace.
- ``behind``    — they don't; ``shortfall`` says by how much per month.
- ``completed`` / ``abandoned`` — set by the user; excluded from the summary.

v1 simplification (shown in the UI): each goal is checked against the full
expected savings independently; the summary adds up the required pace of all
active goals so the honest combined picture is visible too.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..models import SavingsGoal


def _round2(v: float) -> float:
    return round(v, 2)


def months_remaining(target_date: date, today: date) -> int:
    """Calendar months left to save, counting the current month.

    Today 21 Oct, deadline 31 Mar next year → Oct, Nov, Dec, Jan, Feb, Mar = 6.
    A deadline in the past gives 0.
    """
    if target_date < today:
        return 0
    return (target_date.year - today.year) * 12 + (target_date.month - today.month) + 1


def required_monthly_pace(remaining: float, months: int) -> float | None:
    """What still needs saving per month; ``None`` when no month is left."""
    if remaining <= 0:
        return 0.0
    if months <= 0:
        return None
    return _round2(remaining / months)


def on_track(pace: float | None, expected_monthly_savings: float) -> bool:
    return pace is not None and expected_monthly_savings >= pace


def build(goal: SavingsGoal, expected_monthly_savings: float, today: date) -> dict[str, Any]:
    """One goal with its progress and status."""
    saved = goal.saved()
    target = goal.target_amount
    remaining = _round2(max(0.0, target - saved))
    deadline = date.fromisoformat(goal.target_date)
    months = months_remaining(deadline, today)
    pace = required_monthly_pace(remaining, months)

    if goal.status != "active":
        status = goal.status
    elif saved >= target:
        status = "met"
    elif deadline < today:
        status = "overdue"
    elif on_track(pace, expected_monthly_savings):
        status = "on_track"
    else:
        status = "behind"

    shortfall = (
        _round2(pace - expected_monthly_savings)
        if status == "behind" and pace is not None
        else 0.0
    )
    return {
        "id": goal.id,
        "name": goal.name,
        "notes": goal.notes,
        "emergency_fund": goal.emergency_fund,
        "goal_type": goal.goal_type,
        "repeat_months": goal.repeat_months,
        "monthly_set_aside": (
            round(goal.target_amount / goal.repeat_months, 2)
            if goal.goal_type == "sinking" and goal.repeat_months else None
        ),
        "target_amount": target,
        "target_date": goal.target_date,
        "created_date": goal.created_date,
        "user_status": goal.status,
        "saved": saved,
        "remaining": remaining,
        "progress_pct": min(100.0, _round2(saved / target * 100)),
        "months_remaining": months,
        "required_monthly_pace": pace,
        "expected_monthly_savings": _round2(expected_monthly_savings),
        "spend_in_forecast": goal.spend_in_forecast,
        "spends_in_forecast": goal.spends_in_forecast(),
        "shortfall": shortfall,
        "status": status,
        "contributions": [
            {**c.model_dump(), "signed": c.signed}
            for c in sorted(goal.contributions, key=lambda c: (c.date, c.id), reverse=True)
        ],
    }


def build_all(
    goals: list[SavingsGoal], expected_monthly_savings: float, today: date
) -> dict[str, Any]:
    """Every goal plus the combined summary across active, unfinished goals."""
    built = [build(g, expected_monthly_savings, today) for g in goals]
    # Active ones first (by deadline), finished/abandoned at the end.
    order = {"overdue": 0, "behind": 1, "on_track": 2, "met": 3, "completed": 4, "abandoned": 5}
    built.sort(key=lambda g: (order[g["status"]], g["target_date"], g["id"]))

    open_goals = [g for g in built if g["status"] in ("on_track", "behind")]
    total_pace = _round2(sum(g["required_monthly_pace"] or 0.0 for g in open_goals))
    counted = [g for g in built if g["user_status"] == "active"]
    return {
        "goals": built,
        "summary": {
            "active_goals": len(counted),
            "open_goals": len(open_goals),
            "total_target": _round2(sum(g["target_amount"] for g in counted)),
            "total_saved": _round2(sum(g["saved"] for g in counted)),
            "total_required_pace": total_pace,
            "expected_monthly_savings": _round2(expected_monthly_savings),
            "combined_covered": expected_monthly_savings >= total_pace,
            "combined_shortfall": _round2(max(0.0, total_pace - expected_monthly_savings)),
        },
    }


def allocation(goals: list[SavingsGoal], saved_this_year: float, year: int) -> dict[str, Any]:
    """How much of this year's savings is not yet assigned to a goal.

    - Starts from what was actually saved in ``year`` (income − expenses of the
      recorded months, without the opening balance) — the owner's choice.
    - Subtracts contributions *dated in that year* to goals that still hold the
      money: ``active`` goals, including ones already met. A goal marked
      ``completed`` (the purchase is then a transaction) or ``abandoned``
      releases its money.
    - ``unassigned`` can go negative: assigning more than was saved is allowed
      (the UI warns) — e.g. money from the opening balance.
    """
    prefix = f"{year}-"
    assigned = _round2(
        sum(
            c.signed
            for g in goals
            if g.status == "active"
            for c in g.contributions
            if c.date.startswith(prefix)
        )
    )
    unassigned = _round2(saved_this_year - assigned)
    return {
        "year": year,
        "saved_this_year": _round2(saved_this_year),
        "assigned": assigned,
        "unassigned": unassigned,
        "over_assigned": unassigned < 0,
    }


def suggest(built: list[dict[str, Any]], available: float) -> list[dict[str, Any]]:
    """A starting point for distributing ``available`` across open goals.

    Goals are served in the order :func:`build_all` returns them — overdue
    first, then by deadline — each getting its required monthly pace (everything
    still missing when the deadline has passed) until the money runs out. The
    owner edits the amounts; nothing is saved here.
    """
    left = max(0.0, available)
    out = []
    for g in built:
        if g["user_status"] != "active" or g["remaining"] <= 0:
            continue
        pace = g["required_monthly_pace"]
        want = g["remaining"] if pace is None else min(pace, g["remaining"])
        amount = _round2(min(want, left))
        left = _round2(left - amount)
        out.append(
            {
                "goal_id": g["id"],
                "name": g["name"],
                "remaining": g["remaining"],
                "required_monthly_pace": pace,
                "status": g["status"],
                "suggested": amount,
            }
        )
    return out
