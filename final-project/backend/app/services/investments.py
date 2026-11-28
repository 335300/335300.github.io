"""Investment plans: an asset paid for in instalments, and its progress.

A plan's payments are the expense transactions in its category, in any year.
Each payment says how many instalments it covered; ``paid_before`` covers what
was paid before the plan was added. Pure functions — ``today`` is passed in.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..models import AppData, InvestmentPlan
from .aggregation import kind_totals


def _round2(v: float) -> float:
    return round(v, 2)


def _add_months(year: int, month: int, n: int) -> tuple[int, int]:
    """(year, 1-based month) moved ``n`` months on."""
    index = year * 12 + (month - 1) + n
    return index // 12, index % 12 + 1


def payments(plan: InvestmentPlan, data: AppData) -> list[dict[str, Any]]:
    """Every payment into the plan's category, newest first."""
    out = [
        {
            "year": int(y),
            "id": t.id,
            "date": t.date,
            "amount": t.amount,
            "desc": t.desc,
            "installments": t.installments or 0,
            "foreign_amount": t.foreign_amount,
            "foreign_currency": t.foreign_currency,
        }
        for y, year in data.years.items()
        for t in year.transactions
        if t.type == "expense" and t.cat == plan.category
    ]
    out.sort(key=lambda p: (p["date"], p["id"]), reverse=True)
    return out


def expected_end(remaining: int, paid_this_month: bool, today: date) -> str | None:
    """``YYYY-MM`` of the last instalment at one a month, ``None`` when done.

    The next instalment falls in the current month if nothing was paid in it
    yet, otherwise next month.
    """
    if remaining <= 0:
        return None
    first = 1 if paid_this_month else 0
    y, m = _add_months(today.year, today.month, first + remaining - 1)
    return f"{y}-{m:02d}"


def build(plan: InvestmentPlan, data: AppData, year_num: int, month: int, today: date) -> dict[str, Any]:
    """One plan with its progress, seen from the selected month."""
    paid_rows = payments(plan, data)
    counted = sum(p["installments"] for p in paid_rows)
    paid = min(plan.total_installments, plan.paid_before + counted)
    remaining = plan.total_installments - paid
    this_month = f"{today.year}-{today.month:02d}-"
    paid_this_month = any(p["date"].startswith(this_month) for p in paid_rows)
    selected = f"{year_num}-{month + 1:02d}-"
    cost = plan.cost_per_installment
    return {
        "id": plan.id,
        "name": plan.name,
        "category": plan.category,
        "unit": plan.unit,
        "local_currency": plan.local_currency,
        "installment_amount": plan.installment_amount,
        "total_installments": plan.total_installments,
        "paid_before": plan.paid_before,
        "cost_per_installment": cost,
        "market_value_local": plan.market_value_local,
        "notes": plan.notes,
        "created_date": plan.created_date,
        "paid": paid,
        "remaining": remaining,
        "progress_pct": _round2(paid / plan.total_installments * 100),
        "paid_local": _round2(paid * plan.installment_amount),
        "total_local": _round2(plan.total_installments * plan.installment_amount),
        "remaining_local": _round2(remaining * plan.installment_amount),
        # Euro estimates, only when the owner gave a cost per instalment.
        "value_at_cost": _round2(paid * cost) if cost else None,
        "remaining_cost": _round2(remaining * cost) if cost else None,
        # Real euros recorded in the app (may cover only part of what was paid).
        "recorded_total": _round2(sum(p["amount"] for p in paid_rows)),
        "invested_year": _round2(sum(p["amount"] for p in paid_rows if p["year"] == year_num)),
        "invested_month": _round2(sum(p["amount"] for p in paid_rows if p["date"].startswith(selected))),
        "installments_month": sum(p["installments"] for p in paid_rows if p["date"].startswith(selected)),
        "paid_this_month": paid_this_month,
        "expected_end": expected_end(remaining, paid_this_month, today),
        "status": "completed" if remaining == 0 else "active",
        "payments": paid_rows[:8],
    }


def build_all(data: AppData, year_num: int, month: int, today: date) -> dict[str, Any]:
    """Every plan, plus what was invested in the selected month and year
    (all investment categories, with or without a plan)."""
    year = data.get_year(year_num)
    invested_month = kind_totals(year, month)["investment"] if year else 0.0
    invested_year = _round2(sum(kind_totals(year, m)["investment"] for m in range(12))) if year else 0.0
    plans = [build(p, data, year_num, month, today) for p in data.investments]
    plans.sort(key=lambda p: (p["status"] != "active", p["id"]))
    return {
        "plans": plans,
        "invested_month": invested_month,
        "invested_year": invested_year,
        "value_at_cost": _round2(sum(p["value_at_cost"] or 0.0 for p in plans)),
    }
