"""Month-by-month forecast for one year.

Months that already hold transactions use **real** figures; every later month
uses the **budget**. So the year-end number answers the question directly: "if I
keep to the plan for the rest of the year, where will I be?"
"""

from __future__ import annotations

from typing import Any

from ..config import MONTHS, MONTHS_SHORT
from ..models import YearData
from .aggregation import budget_kind_totals, budget_total, kind_totals, last_recorded_month, month_total


def _round2(v: float) -> float:
    return round(v, 2)


def build(year: YearData, year_num: int) -> dict[str, Any]:
    last_actual = last_recorded_month(year)

    rows: list[dict[str, Any]] = []
    balance = year.opening_balance
    cumulative = actual_savings = planned_savings = 0.0
    actual_invested = planned_invested = 0.0

    for month in range(year.start_month + 1, 12):
        is_actual = month <= last_actual
        if is_actual:
            income = month_total(year, month, "income")
            kinds = kind_totals(year, month)
        else:
            income = budget_total(year, month, "income")
            kinds = budget_kind_totals(year, month)
        # Living costs and investments both leave the account; only the first
        # are expenses. What is left after both is the month's savings.
        expenses = _round2(kinds["fixed"] + kinds["variable"])
        invested = kinds["investment"]

        savings = _round2(income - expenses - invested)
        cumulative = _round2(cumulative + savings)
        balance = _round2(balance + savings)
        if is_actual:
            actual_savings = _round2(actual_savings + savings)
            actual_invested = _round2(actual_invested + invested)
        else:
            planned_savings = _round2(planned_savings + savings)
            planned_invested = _round2(planned_invested + invested)

        rows.append(
            {
                "month": month,
                "month_name": MONTHS[month],
                "month_short": MONTHS_SHORT[month],
                "income": income,
                "expenses": expenses,
                "invested": invested,
                "savings": savings,
                "cumulative": cumulative,
                "balance": balance,
                "actual": is_actual,
                # The chart puts a red marker only where this is true.
                "negative": balance < 0,
            }
        )

    actual_months = sum(1 for r in rows if r["actual"])
    planned_months = len(rows) - actual_months
    lowest = min(rows, key=lambda r: r["balance"]) if rows else None

    return {
        "year": year_num,
        "rows": rows,
        "summary": {
            "opening_balance": _round2(year.opening_balance),
            "actual_savings": actual_savings,
            "actual_months": actual_months,
            "planned_savings": planned_savings,
            "planned_months": planned_months,
            "year_end_savings": _round2(actual_savings + planned_savings),
            "actual_invested": actual_invested,
            "planned_invested": planned_invested,
            "year_end_invested": _round2(actual_invested + planned_invested),
            "year_end_balance": _round2(balance),
            "average_monthly_savings": (
                _round2((actual_savings + planned_savings) / len(rows)) if rows else 0.0
            ),
            "average_actual_savings": (
                _round2(actual_savings / actual_months) if actual_months else 0.0
            ),
            "average_planned_savings": (
                _round2(planned_savings / planned_months) if planned_months else 0.0
            ),
            "lowest_balance": lowest["balance"] if lowest else _round2(year.opening_balance),
            "lowest_balance_month": lowest["month"] if lowest else None,
            "goes_negative": any(r["negative"] for r in rows),
            "last_actual_month": last_actual if last_actual >= 0 else None,
            "last_actual_month_name": MONTHS[last_actual] if last_actual >= 0 else None,
        },
    }


def expected_monthly_savings(summary: dict[str, Any]) -> float:
    """What the forecast expects you to save per month from here on.

    Goals are forward-looking, so they are checked against the average of the
    *remaining* (budgeted) months. When no month is left to plan (December is
    already recorded), it falls back to the whole-year average.
    """
    if summary["planned_months"]:
        return summary["average_planned_savings"]
    return summary["average_monthly_savings"]
