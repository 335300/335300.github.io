"""Budgets that follow income.

Two kinds of budget cells are kept up to date automatically:

1. **The salary row follows the income calendar.** When the calendar is on,
   the salary budget of every month that is not recorded yet (from the current
   month on) is set to the net pay the calendar expects to arrive that month —
   the same figure the forecast uses, so budget, "Kept" row, planned split and
   forecast all agree.
2. **The investment budget follows its plan.** An investment plan with a euro
   cost per instalment fills its category's budget in every month that is not
   recorded yet (from the current month on): one instalment a month at that
   cost, until the last one, then nothing.
3. **Linked % budgets.** A cash-out cell can be linked to a % of the month's
   planned income. Its euro amount is recalculated from the month's income
   every time :func:`sync` runs.

:func:`sync` is called after every change that can move a month's income
(a budget edit, calendar settings, payslips, a new year) and when the budget
plan is read. It only touches the cells described above, and never a box
typed by hand (``YearBudgets.manual``).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..models import AppData, YearData
from . import income_calendar as ic
from .aggregation import budget_total, last_recorded_month


def _round2(v: float) -> float:
    return round(v + 0.0, 2)


def calendar_months(data: AppData, year_num: int, today: date) -> list[bool]:
    """Which months of ``year_num`` take their salary budget from the calendar."""
    from .rolling_forecast import calendar_active  # local import: rolling_forecast imports this module's peers

    plan = data.income_plan
    year = data.get_year(year_num)
    if year is None or not calendar_active(plan) or plan is None:
        return [False] * 12
    if year.find_category("income", plan.salary_category) is None:
        return [False] * 12
    recorded = last_recorded_month(year)
    now = ic.ym_index(ic.ym_of(today))
    return [ic.ym_index((year_num, m)) >= now and m > recorded for m in range(12)]


def open_month(year: YearData, year_num: int, m: int, today: date) -> bool:
    """A month derived budgets may fill: not recorded yet, from the current month on."""
    return ic.ym_index((year_num, m)) >= ic.ym_index(ic.ym_of(today)) and m > last_recorded_month(year)


def _plans_with_cost(data: AppData) -> list:
    return [p for p in data.investments if p.cost_per_installment]


def plan_months(data: AppData, year_num: int, today: date) -> dict[str, list[bool]]:
    """``{category: [12 flags]}``: months whose budget comes from an investment plan."""
    year = data.get_year(year_num)
    out: dict[str, list[bool]] = {}
    if year is None:
        return out
    for plan in _plans_with_cost(data):
        if year.find_category("expense", plan.category) is None:
            continue
        out[plan.category] = [open_month(year, year_num, m, today) for m in range(12)]
    return out


def _sync_plans(data: AppData, today: date) -> bool:
    from .investments import build as plan_progress

    changed = False
    for plan in _plans_with_cost(data):
        remaining = plan_progress(plan, data, today.year, today.month - 1, today)["remaining"]
        cost = _round2(plan.cost_per_installment or 0.0)
        for y in data.year_numbers():
            year = data.years[str(y)]
            if year.find_category("expense", plan.category) is None:
                continue
            row = year.budgets.expense.setdefault(plan.category, [0.0] * 12)
            for m in range(12):
                if not open_month(year, y, m, today) or year.budgets.is_manual("expense", plan.category, m):
                    continue  # a box typed by hand keeps its value (and takes no instalment)
                value = cost if remaining > 0 else 0.0
                remaining = max(0, remaining - 1)
                if row[m] != value:
                    row[m] = value
                    changed = True
    return changed


def _sync_salary(data: AppData, today: date) -> bool:
    plan = data.income_plan
    years = data.year_numbers()
    if plan is None or not years:
        return False
    first = ic.ym_of(today)
    count = ic.ym_index((max(years), 11)) - ic.ym_index(first) + 1
    if count <= 0:
        return False
    flags = {y: calendar_months(data, y, today) for y in years}
    if not any(any(f) for f in flags.values()):
        return False
    paid = ic.paid_by_month(plan, plan.payslips, first, count)
    changed = False
    for y in years:
        year = data.years[str(y)]
        row = year.budgets.income.setdefault(plan.salary_category, [0.0] * 12)
        for m, follows in enumerate(flags[y]):
            if follows and not year.budgets.is_manual("income", plan.salary_category, m):
                value = _round2(paid.get((y, m), 0.0))
                if row[m] != value:
                    row[m] = value
                    changed = True
    return changed


def apply_shares(year: YearData) -> bool:
    """Recalculate every linked cell of one year from its month's planned income."""
    changed = False
    for name, shares in year.budgets.shares.items():
        if year.find_category("expense", name) is None:
            continue
        row = year.budgets.expense.setdefault(name, [0.0] * 12)
        for m, pct in enumerate(shares):
            if pct is None or year.budgets.is_manual("expense", name, m):
                continue  # no link, or a box typed by hand
            value = _round2(budget_total(year, m, "income") * pct / 100)
            if row[m] != value:
                row[m] = value
                changed = True
    return changed


def sync(data: AppData, today: date) -> bool:
    """Bring the salary row and every linked % budget up to date. True if anything changed."""
    changed = _sync_salary(data, today)
    changed = _sync_plans(data, today) or changed
    for year in data.years.values():
        changed = apply_shares(year) or changed
    return changed


def open_months(year: YearData) -> list[int]:
    """Months a "whole row" % applies to: the ones not recorded yet."""
    recorded = last_recorded_month(year)
    return [m for m in range(12) if m > recorded]


def describe(data: AppData, year_num: int, today: date) -> dict[str, Any]:
    plan = data.income_plan
    return {
        "salary_category": plan.salary_category if plan else None,
        "calendar_months": calendar_months(data, year_num, today),
        "open_months": open_months(data.years[str(year_num)]),
        "plan_months": plan_months(data, year_num, today),
        "plans": {
            p.category: {"name": p.name, "unit": p.unit, "cost": p.cost_per_installment}
            for p in _plans_with_cost(data)
        },
        "panel": share_panel(data.years[str(year_num)]),
    }


def _range(values: list[float]) -> dict[str, float] | None:
    return {"min": _round2(min(values)), "max": _round2(max(values))} if values else None


def share_panel(year: YearData) -> dict[str, Any]:
    """The "variable costs by % of income" panel, over the months not recorded yet.

    Fixed costs and investments stay fixed euro amounts; the panel shows what
    share of income they take. Each variable category shows the % it is linked
    to in every open month (``percent``; ``mixed`` when the months differ) and
    the euro range that gives. Shares are only taken in months with planned
    income. ``savings`` is what the plan leaves over, as a share of income.
    """
    from .aggregation import budget_kind_totals
    from ..config import DISTRIBUTION_GUIDE

    months = open_months(year)
    incomes = {m: budget_total(year, m, "income") for m in months}
    kinds = {m: budget_kind_totals(year, m) for m in months}
    paid = [m for m in months if incomes[m] > 0]

    def share_range(amount_of) -> dict[str, float] | None:
        return _range([amount_of(m) / incomes[m] * 100 for m in paid])

    def block(kind: str) -> dict[str, Any]:
        return {
            "amount": _range([kinds[m][kind] for m in months]),
            "share": share_range(lambda m: kinds[m][kind]),
        }

    rows = []
    for c in year.categories.expense:
        if c.kind != "variable":
            continue
        links = year.budgets.share_row(c.name)
        values = [links[m] for m in months]
        common = values[0] if values and all(v is not None and v == values[0] for v in values) else None
        budget = year.budget_row("expense", c.name)
        rows.append(
            {
                "cat": c.name,
                "percent": common,
                "mixed": common is None and any(v is not None for v in values),
                "amount": _range([budget[m] for m in months]),
            }
        )

    def saved(m: int) -> float:
        k = kinds[m]
        return incomes[m] - k["fixed"] - k["variable"] - k["investment"]

    return {
        "months": months,
        "income": _range([incomes[m] for m in months]),
        "fixed": block("fixed"),
        "investment": block("investment"),
        "variable": block("variable"),
        "savings": {"share": share_range(saved), "guide_min": DISTRIBUTION_GUIDE["savings"][0]},
        "rows": rows,
    }
