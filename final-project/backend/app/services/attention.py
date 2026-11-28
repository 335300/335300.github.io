"""The Overview's "Worth a look" banner: the one variable budget that needs a look.

Only for the month that is running now (``today``); any other month gives
``None`` — a finished month cannot be steered any more.

For every **variable** cost category with a budget this month:

- **pace** = spent so far ÷ days so far (today counts) × days in the month:
  where the month ends if spending goes on like this.
- It is a candidate when it is **over** its budget, or its pace is over the
  budget (**pace**), or at least ``BUDGET_WARNING_PCT`` % of it is used
  (**close**) — in that order of seriousness for ``reason``.
- The flagged category is the candidate with the highest spent ÷ budget (ties:
  by name). Nothing flagged -> ``status: "all_clear"``.
- **left** = budget − spent (negative once over); **over** = spent − budget
  when the budget is exceeded (a positive amount, for "12,40 € over"), else ``None``.
- **needed** = pace − budget, never below 0, rounded **up** to whole 5 €.
- **source** = the other variable budget with the most room (budget − pace),
  if that room is at least ``needed``; none -> no move suggestion.
- **can_move** only when there is something to move, a source, and both boxes
  are plain euro budgets: not linked to a % of income (``YearBudgets.shares``)
  and not filled by itself (``locked``: the route passes the categories that
  follow the Joint plan, the income calendar or an investment plan this month).

Spending counts in full (one-offs too): the budget is used either way.
Money is rounded to cents like the rest of the Overview.
"""

from __future__ import annotations

import calendar
import math
from datetime import date
from typing import Any

from ..config import BUDGET_WARNING_PCT
from ..models import AppData, YearData
from .aggregation import category_totals


def _round2(v: float) -> float:
    return round(v + 0.0, 2)


def round_up_5(value: float) -> float:
    """Round up to whole 5 € (0 and less -> 0). Cents first, so 35.00 stays 35."""
    cents = round(value * 100)
    if cents <= 0:
        return 0
    return math.ceil(cents / 500) * 5


def _reason(spent: float, budget: float, pace: float) -> str | None:
    if spent > budget:
        return "over"
    if pace > budget:
        return "pace"
    if spent / budget * 100 >= BUDGET_WARNING_PCT:
        return "close"
    return None


def build(
    data: AppData, year_num: int, month: int, today: date, locked: set[str] | frozenset[str] = frozenset()
) -> dict[str, Any] | None:
    """The banner for (``year_num``, ``month``), or ``None`` when it is not the current month."""
    year = data.get_year(year_num)
    if year is None or (year_num, month) != (today.year, today.month - 1):
        return None
    days = calendar.monthrange(year_num, month + 1)[1]
    elapsed = today.day
    real = category_totals(year, month, "expense")

    rows = []
    for c in year.categories.expense:
        budget = _round2(year.budget_for("expense", c.name, month))
        if c.kind != "variable" or budget <= 0:
            continue
        spent = _round2(real.get(c.name, 0.0))
        pace = _round2(spent / elapsed * days)
        rows.append({"cat": c.name, "budget": budget, "spent": spent, "pace": pace,
                     "used": spent / budget, "reason": _reason(spent, budget, pace)})

    out: dict[str, Any] = {
        "status": "all_clear", "year": year_num, "month": month,
        "day": elapsed, "days_in_month": days, "days_left": days - elapsed,
        "checked": len(rows),
        "category": None, "reason": None, "spent": None, "budget": None, "left": None, "over": None,
        "used_pct": None, "pace": None, "needed": 0,
        "source": None, "source_budget": None, "source_spent": None, "source_pace": None,
        "can_move": False, "cannot_move_reason": None,
    }
    candidates = [r for r in rows if r["reason"]]
    if not candidates:
        return out
    flagged = sorted(candidates, key=lambda r: (-r["used"], r["cat"]))[0]
    needed = round_up_5(flagged["pace"] - flagged["budget"])
    roomy = [
        r for r in rows
        if r["cat"] != flagged["cat"] and needed > 0 and _round2(r["budget"] - r["pace"]) >= needed
    ]
    source = sorted(roomy, key=lambda r: (-(r["budget"] - r["pace"]), r["cat"]))[0] if roomy else None

    if needed <= 0:
        why = "nothing_needed"
    elif source is None:
        why = "no_room"
    elif {flagged["cat"], source["cat"]} & set(locked):
        why = "fills_itself"
    elif any(year.budgets.share_row(name)[month] is not None for name in (flagged["cat"], source["cat"])):
        why = "linked"
    else:
        why = None

    out.update({
        "status": "problem",
        "category": flagged["cat"],
        "reason": flagged["reason"],
        "spent": flagged["spent"],
        "budget": flagged["budget"],
        "left": _round2(flagged["budget"] - flagged["spent"]),
        "over": _round2(flagged["spent"] - flagged["budget"]) if flagged["spent"] > flagged["budget"] else None,
        "used_pct": _round2(flagged["used"] * 100),
        "pace": flagged["pace"],
        "needed": needed,
        "source": source["cat"] if source else None,
        "source_budget": source["budget"] if source else None,
        "source_spent": source["spent"] if source else None,
        "source_pace": source["pace"] if source else None,
        "can_move": why is None,
        "cannot_move_reason": why,
    })
    return out


def move_budget(year: YearData, month: int, source: str, target: str, amount: float) -> dict[str, float]:
    """Move ``amount`` € of one month's budget from ``source`` to ``target``.
    The month's total budget stays the same. Returns both new values."""
    grid = year.budgets.expense
    for name in (source, target):
        grid.setdefault(name, [0.0] * 12)
    grid[source][month] = _round2(grid[source][month] - amount)
    grid[target][month] = _round2(grid[target][month] + amount)
    return {source: grid[source][month], target: grid[target][month]}
