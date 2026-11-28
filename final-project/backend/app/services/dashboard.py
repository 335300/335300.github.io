"""Everything the Overview tab renders, in one payload.

The KPI tiles (balance, cash in, cash out, kept, wealth built), where the
month's income went, the fixed/variable cost split with each category against
its usual month, budget vs real, costs over time, investment plans and goals.

Vocabulary used throughout:

- **cash in**  — all income of the month.
- **cash out** — everything that left the account: living costs (``spent``:
  fixed + variable) plus investments (``invested``).
- **savings**  — cash in minus cash out: what stayed in the account.
- **wealth built** — savings plus investments: income not consumed.
- **liquidity** — the balance minus what is saved for goals: money with no job
  yet. Investments are not part of it — they already left the account.
"""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any

from ..config import BUDGET_WARNING_PCT, MONTHS, MONTHS_SHORT, UNUSUAL_FACTOR, UNUSUAL_MIN_EUR
from ..models import AppData, TxType, YearData
from . import cashflow, emergency, investments, kpi_compare, projection, recurring, sinking
from . import goals as goals_service
from .aggregation import (
    balance_through,
    budget_kind_totals,
    budget_total,
    category_totals,
    kind_totals,
    last_recorded_month,
    month_total,
    opening_balance_for_month,
)


def _round2(v: float) -> float:
    return round(v, 2)


def _pct(part: float, whole: float) -> float:
    return _round2(part / whole * 100) if whole else 0.0


def kpis(data: AppData, year: YearData, year_num: int, month: int) -> dict[str, Any]:
    """The headline tiles, as plain numbers (the UI only formats them)."""
    income = month_total(year, month, "income")
    kinds = kind_totals(year, month)
    spent = _round2(kinds["fixed"] + kinds["variable"])
    invested = kinds["investment"]
    cash_out = _round2(spent + invested)
    savings = _round2(income - cash_out)
    planned = budget_kind_totals(year, month)
    cash_out_budget = budget_total(year, month, "expense")
    current = balance_through(year, month)
    set_aside = cashflow.earmarked(data.goals, cashflow.month_end(year_num, month))
    wealth_built = _round2(income - spent)
    return {
        "balance_last_month": opening_balance_for_month(data, year_num, month),
        "current_balance": current,
        # Goal money stays in the account: part of the balance already has a job.
        # What is left is the liquidity — money free to use.
        "earmarked": set_aside,
        "free_balance": _round2(current - set_aside),
        "liquidity": _round2(current - set_aside),
        "income": income,
        "income_budget": budget_total(year, month, "income"),
        "cash_in": income,
        "cash_out": cash_out,
        "cash_out_budget": cash_out_budget,
        # Living costs only — investments are cash out, but not spending.
        "spent": spent,
        "spent_budget": _round2(planned["fixed"] + planned["variable"]),
        "invested": invested,
        "invested_budget": planned["investment"],
        "savings": savings,
        "savings_rate": _pct(savings, income),
        "wealth_built": wealth_built,
        "wealth_rate": _pct(wealth_built, income),
        # "If I stick to plan, what is left over?" — real income minus all budgeted cash out.
        "savings_vs_budget": _round2(income - cash_out_budget),
        "negative_balance": current < 0,
    }


def cost_split(year: YearData, month: int) -> dict[str, Any]:
    """Split the month's living costs into fixed and variable.

    Membership comes from each category's editable ``kind`` flag. A category
    with spending that is no longer in the category list falls into
    ``variable``, so no money silently disappears from the view. Investment
    categories are left out: they are cash out, not costs.
    """
    real = {
        cat: amount
        for cat, amount in category_totals(year, month, "expense").items()
        if year.kind_of(cat) != "investment"
    }
    month_spend = _round2(sum(real.values()))

    ranked = [
        {"cat": cat, "amount": amount, "kind": year.kind_of(cat)}
        for cat, amount in real.items()
        if amount > 0
    ]
    ranked.sort(key=lambda r: (-r["amount"], r["cat"]))
    peak = ranked[0]["amount"] if ranked else 0.0
    for row in ranked:
        row["share"] = _pct(row["amount"], month_spend)
        # Bar width relative to the largest category.
        row["width"] = _pct(row["amount"], peak)

    fixed = _round2(sum(r["amount"] for r in ranked if r["kind"] == "fixed"))
    variable = _round2(sum(r["amount"] for r in ranked if r["kind"] == "variable"))
    return {
        "month_spend": month_spend,
        "fixed": {"total": fixed, "share": _pct(fixed, month_spend)},
        "variable": {"total": variable, "share": _pct(variable, month_spend)},
        "ranked": ranked,
    }


def budget_status(budget: float, actual: float, kind: TxType = "expense", fixed: bool = False) -> str:
    """Traffic-light state of one budget line.

    - ``under``      (teal)  — comfortably within budget.
    - ``on_budget``  (teal ✓) — exactly the budgeted amount, or a fixed cost paid
      as planned. Paying the rent is not a warning sign.
    - ``warning``    (amber) — a variable cost has used BUDGET_WARNING_PCT or more.
    - ``over``       (red)   — only once the budget is actually exceeded.
    - ``unbudgeted``         — money spent where no budget was set.

    Income lines are never "over" — earning more than planned is good news.
    """
    if budget <= 0:
        return "unbudgeted" if actual > 0 else "under"
    if kind == "income":
        return "under"
    if round(actual, 2) > round(budget, 2):
        return "over"
    if round(actual, 2) == round(budget, 2) or (fixed and actual > 0):
        return "on_budget"
    if actual / budget * 100 >= BUDGET_WARNING_PCT:
        return "warning"
    return "under"


def budget_vs_real(year: YearData, month: int, kind: TxType = "expense") -> dict[str, Any]:
    """Per-category budget / real / difference for one month.

    Rows cover the union of budgeted categories and categories that actually saw
    activity, so an uncategorised or deleted category is never hidden. For
    expenses a positive ``diff`` means under budget. The expense table is the
    whole planned cash out, so investment rows are part of it; like a fixed
    cost, an investment paid as planned is "on budget", not a warning.
    """
    real = category_totals(year, month, kind)
    grid = getattr(year.budgets, kind)

    def row_kind(name: str) -> str:
        return year.kind_of(name) if kind == "expense" else "variable"
    names = list(dict.fromkeys([*year.category_names(kind), *grid.keys(), *real.keys()]))

    rows: list[dict[str, Any]] = []
    total_budget = total_real = 0.0
    for name in names:
        budget = year.budget_for(kind, name, month)
        actual = real.get(name, 0.0)
        if budget == 0 and actual == 0:
            continue
        total_budget += budget
        total_real += actual
        used = _pct(actual, budget) if budget > 0 else None
        rows.append(
            {
                "cat": name,
                "budget": _round2(budget),
                "real": _round2(actual),
                "diff": _round2(budget - actual),
                "used_pct": used,
                # Bar fill, capped at 100%.
                "progress": min(100.0, used) if used is not None else (100.0 if actual > 0 else 0.0),
                "kind": row_kind(name),
                "status": budget_status(budget, actual, kind, fixed=row_kind(name) != "variable"),
            }
        )

    rows.sort(key=lambda r: (-r["real"], r["cat"]))
    return {
        "warning_pct": BUDGET_WARNING_PCT,
        "rows": rows,
        "total": {
            "budget": _round2(total_budget),
            "real": _round2(total_real),
            "diff": _round2(total_budget - total_real),
            # The total mixes fixed and variable costs, so it only says over / within.
            "status": "over" if kind == "expense" and _round2(total_real) > _round2(total_budget) else "under",
        },
    }


def budget_usual(
    data: AppData, year_num: int, month: int, bvr: dict[str, Any], today: date
) -> dict[str, Any]:
    """Budget vs real, with each row's usual month and a footer for the variable budgets.

    Adds to every row of ``bvr`` (the result of :func:`budget_vs_real`):

    - ``usual`` — the category's usual month: the median of the months before
      this one, one-offs left out (same rule as :func:`costs_with_usual`).
      ``None`` when there is no earlier month, or when none of the earlier
      months holds a non-one-off transaction (:func:`cashflow.months_with_data`
      = 0, e.g. a fresh profile) — empty months are no usual month.
    - ``usual_pct`` — usual ÷ budget × 100, 2 decimals (the │ marker on the bar).
      ``None`` when the row has no budget or no usual.

    And next to the rows, ``variable_totals``: ``spent`` and ``budget`` summed
    over the variable rows (unbudgeted variable rows add their spending), and
    ``days_left`` = days in the month − today's day, only for the current
    month (else ``None``). No existing figure changes.
    """
    months = cashflow.baseline_months(data, year_num, month)
    has_usual = cashflow.months_with_data(data, months) > 0
    usual = cashflow.category_baselines(data, months)
    spent = budget = 0.0
    for row in bvr["rows"]:
        base = usual.get(row["cat"], 0.0) if has_usual else None
        row["usual"] = base
        row["usual_pct"] = _round2(base / row["budget"] * 100) if base is not None and row["budget"] > 0 else None
        if row["kind"] == "variable":
            spent += row["real"]
            budget += row["budget"]
    current = (year_num, month) == (today.year, today.month - 1)
    days = calendar.monthrange(year_num, month + 1)[1]
    bvr["variable_totals"] = {
        "spent": _round2(spent),
        "budget": _round2(budget),
        "days_left": days - today.day if current else None,
    }
    return bvr


def trend(year: YearData) -> list[dict[str, Any]]:
    """Cash in vs cash out for every month recorded so far this year."""
    last = last_recorded_month(year)
    out = []
    for m in range(year.start_month + 1, last + 1):
        income = month_total(year, m, "income")
        kinds = kind_totals(year, m)
        expenses = _round2(kinds["fixed"] + kinds["variable"])
        out.append(
            {
                "month": m,
                "month_name": MONTHS_SHORT[m],
                "income": income,
                "expenses": expenses,
                "invested": kinds["investment"],
                "savings": _round2(income - expenses - kinds["investment"]),
            }
        )
    return out


def costs_with_usual(data: AppData, year: YearData, year_num: int, month: int) -> dict[str, Any]:
    """The cost split, with each category next to what it costs in a usual month.

    ``usual`` is the category's median over the months before this one
    (:func:`cashflow.baseline_months`), without one-offs; ``vs_usual_pct`` is
    how far this month is from it. Both are ``None`` when there is no earlier
    month to compare with. ``one_off`` is the part of this month tagged one-off.

    ``unusual`` lists categories that cost at least ``UNUSUAL_FACTOR`` times
    their usual month *and* ``UNUSUAL_MIN_EUR`` more — one-offs excluded, as
    they are expected. Categories with a usual month of 0 are never listed
    (a yearly bill is not a surprise).

    ``usual_months`` is how many earlier months the usual is built from;
    ``usual_months_with_data`` how many of them hold a non-one-off transaction
    (0 on a fresh profile: the screen then shows no usual month).
    """
    costs = cost_split(year, month)
    months = cashflow.baseline_months(data, year_num, month)
    usual = cashflow.category_baselines(data, months)
    regular = category_totals(year, month, "expense", skip_one_off=True)
    unusual = []
    for row in costs["ranked"]:
        base = usual.get(row["cat"], 0.0) if months else None
        row["usual"] = base
        row["vs_usual_pct"] = _round2((row["amount"] - base) / base * 100) if base else None
        row["one_off"] = _round2(row["amount"] - regular.get(row["cat"], 0.0))
        now = regular.get(row["cat"], 0.0)
        if base and now >= base * UNUSUAL_FACTOR and now - base >= UNUSUAL_MIN_EUR:
            unusual.append({"cat": row["cat"], "amount": now, "usual": base, "over": _round2(now - base)})
    costs["usual_months"] = len(months)
    costs["usual_months_with_data"] = cashflow.months_with_data(data, months)
    costs["unusual"] = sorted(unusual, key=lambda u: -u["over"])
    return costs


def goals_overview(data: AppData, year: YearData, year_num: int, month: int, today: date) -> dict[str, Any]:
    """Active goals for the Overview: progress, pace, and this month's share."""
    from . import rolling_forecast  # local: rolling_forecast imports cashflow, which this module uses too

    built = goals_service.build_all(data.goals, rolling_forecast.expected_monthly_savings(data), today)
    prefix = f"{year_num}-{month + 1:02d}-"
    rows = [
        {
            "id": g["id"],
            "name": g["name"],
            "saved": g["saved"],
            "target_amount": g["target_amount"],
            "remaining": g["remaining"],
            "progress_pct": g["progress_pct"],
            "target_date": g["target_date"],
            "months_remaining": g["months_remaining"],
            "required_monthly_pace": g["required_monthly_pace"],
            "status": g["status"],
            "added_this_month": _round2(sum(c["signed"] for c in g["contributions"] if c["date"].startswith(prefix))),
        }
        for g in built["goals"]
        if g["user_status"] == "active"
    ]
    return {"goals": rows, "summary": built["summary"], "built": built["goals"]}


def build(data: AppData, year_num: int, month: int, today: date | None = None) -> dict[str, Any]:
    """Assemble the whole Overview payload in a single response.

    ``today`` drives goal deadlines and the investment timeline; without it the
    first day of the selected month stands in, so the result stays deterministic.
    """
    year = data.get_year(year_num)
    if year is None:
        raise KeyError(year_num)
    today = today or date(year_num, month + 1, 1)
    goals = goals_overview(data, year, year_num, month, today)
    built = goals.pop("built")
    spread = cashflow.distribution(year, year_num, month, data.goals)
    spread["suggested"] = goals_service.suggest(built, spread["left_to_assign"])
    tiles = kpis(data, year, year_num, month)
    plans = investments.build_all(data, year_num, month, today)
    return {
        "year": year_num,
        "month": month,
        "month_name": MONTHS[month],
        "kpis": tiles,
        # Each tile against a usual month, in euros (services/kpi_compare.py).
        "vs_usual": kpi_compare.vs_usual(data, year_num, month),
        "position": cashflow.position(
            tiles["current_balance"],
            tiles["earmarked"],
            plans["value_at_cost"],
            *cashflow.costs_yardstick(data, year_num, month),
        ),
        "emergency": emergency.build(data, year_num, month),
        "paid_from_funds": sinking.paid_from_funds(data.goals, year_num, month),
        "upcoming": recurring.upcoming(data, today),
        "distribution": spread,
        "costs": costs_with_usual(data, year, year_num, month),
        # Each row also gets its usual month (│ marker) + a variable-budgets footer.
        "budget_vs_real": budget_usual(data, year_num, month, budget_vs_real(year, month, "expense"), today),
        "history": cashflow.history(data, year_num, month),
        "investments": plans,
        "goals": goals,
        "trend": trend(year),
    }
