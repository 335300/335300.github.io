"""The rolling forecast: always the next 12 months, across year boundaries.

It starts the month after the last month with recorded transactions and runs
``FORECAST_MONTHS`` months. The last few recorded months come first, for
context, and use real figures.

For each planned month:

- **Costs and investments** come from the budget plan of that month's year. A
  year that is not set up yet borrows the same calendar month from the latest
  year that is (``budget_from`` says which).
- **Income** is the budgeted income. When the income calendar is on and has at
  least one payslip, the calendar's expected net pay replaces the budget of
  the salary category.
- Each **graduation scenario** is its own line: the student job stops on its
  end date, a new net salary starts after it (if entered), and from the month
  after the end the health-insurance category costs the employee rate.

Without scenarios (or without the income calendar) there is one line, "Plan".

**Savings goals** (see :mod:`goal_forecast`): a goal that is spent costs its
target in its deadline month, so the balance drops there (``goal_spend``).
Each month also gets ``free`` = balance − what is earmarked for goals by then
— the money no goal has a claim on. ``include_goals=False`` leaves purchases
out, to compare.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..config import FORECAST_CONTEXT_MONTHS, FORECAST_MONTHS
from ..models import AppData, GraduationScenario, IncomePlan, YearData
from . import goal_forecast
from . import income_calendar as ic
from .aggregation import balance_through, budget_kind_totals, budget_total, kind_totals, last_recorded_month, month_total
from .cashflow import months_back

YM = tuple[int, int]


def _round2(v: float) -> float:
    return round(v, 2)


def last_recorded(data: AppData) -> YM | None:
    """The latest month that holds a transaction, in any year.

    When nothing is recorded yet, the month before tracking starts in the
    first year (so the forecast starts with the first tracked month, even when
    a later year is already set up). ``None`` when no year exists.
    """
    years = data.year_numbers()
    if not years:
        return None
    for y in reversed(years):
        year = data.get_year(y)
        if year is not None and year.transactions:
            return y, last_recorded_month(year)
    first = years[0]
    return ic.ym_add((first, 0), data.years[str(first)].start_month)


def tracked_balance(data: AppData) -> float:
    """The tracked account's balance at the close of the last recorded month."""
    last = last_recorded(data)
    if last is None:
        return 0.0
    year = data.get_year(last[0])
    if year is None:  # the December before the first tracked year
        return data.years[str(last[0] + 1)].opening_balance
    return balance_through(year, last[1])


def budget_year(data: AppData, y: int) -> tuple[YearData, int] | None:
    """The year whose budget plans year ``y``: itself, else the latest before it,
    else the earliest after it."""
    found = data.get_year(y)
    if found is not None:
        return found, y
    years = data.year_numbers()
    earlier = [n for n in years if n < y]
    pick = earlier[-1] if earlier else (years[0] if years else None)
    return (data.years[str(pick)], pick) if pick is not None else None


def calendar_active(plan: IncomePlan | None) -> bool:
    """The calendar replaces the salary budget once it can give a net figure."""
    return bool(plan and plan.enabled and plan.hourly_rate > 0 and ic.has_net(plan, plan.payslips))


def _lines(plan: IncomePlan | None) -> list[dict[str, Any]]:
    if calendar_active(plan) and plan is not None and plan.scenarios:
        return [
            {"key": f"s{i}", "name": s.name, "scenario": s}
            for i, s in enumerate(plan.scenarios)
        ]
    return [{"key": "plan", "name": "Plan", "scenario": None}]


def _planned_month(
    data: AppData,
    ym: YM,
    plan: IncomePlan | None,
    scenario: GraduationScenario | None,
    paid: dict[YM, float],
) -> dict[str, Any]:
    y, m = ym
    source = budget_year(data, y)
    if source is None:
        return {"income": 0.0, "expenses": 0.0, "invested": 0.0, "budget_from": None}
    year, source_year = source
    kinds = dict(budget_kind_totals(year, m))
    income = budget_total(year, m, "income")

    # The calendar's pay replaces the salary budget — unless that box was typed by hand.
    typed = source_year == y and year.budgets.is_manual("income", plan.salary_category, m) if plan else False
    if calendar_active(plan) and plan is not None and not typed:
        income = income - year.budget_for("income", plan.salary_category, m) + paid.get(ym, 0.0)

        if scenario is not None and scenario.health_insurance_monthly is not None and plan.health_category:
            job_end = date.fromisoformat(scenario.job_end)
            if ic.ym_index(ym) > ic.ym_index(ic.ym_of(job_end)):
                kind = year.kind_of(plan.health_category)
                kinds[kind] += scenario.health_insurance_monthly - year.budget_for(
                    "expense", plan.health_category, m
                )

    return {
        "income": _round2(income),
        "expenses": _round2(kinds["fixed"] + kinds["variable"]),
        "invested": _round2(kinds["investment"]),
        "budget_from": source_year,
    }


def build(data: AppData, horizon: int = FORECAST_MONTHS, include_goals: bool = True) -> dict[str, Any]:
    last = last_recorded(data)
    plan = data.income_plan
    lines = _lines(plan)
    if last is None:
        return {"rows": [], "lines": [], "calendar_used": False, "start": None, "starting_balance": 0.0}

    first = ic.ym_add(last, 1)
    # Balance at the close of the last recorded month.
    ly, lm = last
    last_year = data.get_year(ly)
    if last_year is None:  # last is the December before the first tracked year
        start_balance = data.years[str(ly + 1)].opening_balance
    else:
        start_balance = balance_through(last_year, lm)

    rows: list[dict[str, Any]] = []

    # Recorded months for context (real figures, the same on every line).
    if last_year is not None:
        for y, m in months_back(data, ly, lm, FORECAST_CONTEXT_MONTHS):
            year = data.get_year(y)
            assert year is not None
            kinds = kind_totals(year, m)
            values = {
                "income": month_total(year, m, "income"),
                "expenses": _round2(kinds["fixed"] + kinds["variable"]),
                "invested": kinds["investment"],
            }
            values["savings"] = _round2(values["income"] - values["expenses"] - values["invested"])
            values["balance"] = balance_through(year, m)
            rows.append({
                "key": ic.ym_key((y, m)), "label": ic.ym_label((y, m)), "month_name": ic.ym_name((y, m)),
                "year": y, "month": m, "actual": True, "budget_from": None,
                "values": {line["key"]: values for line in lines},
            })

    # Planned months, one series per line.
    planned: list[dict[str, Any]] = [
        {
            "key": ic.ym_key(ym), "label": ic.ym_label(ym), "month_name": ic.ym_name(ym),
            "year": ym[0], "month": ym[1], "actual": False, "budget_from": None, "values": {},
        }
        for ym in (ic.ym_add(first, i) for i in range(horizon))
    ]
    spends = goal_forecast.purchases(data.goals, first, horizon) if include_goals else {}
    earmark = goal_forecast.earmarked(data.goals, first, horizon) if include_goals else [0.0] * horizon
    for row in planned:
        row["goals"] = spends.get((row["year"], row["month"]), [])
    summaries = []
    for line in lines:
        scenario: GraduationScenario | None = line["scenario"]
        job_end = date.fromisoformat(scenario.job_end) if scenario else None
        paid: dict[YM, float] = {}
        if calendar_active(plan) and plan is not None:
            paid = ic.paid_by_month(
                plan, plan.payslips, first, horizon, job_end,
                scenario.new_net_salary if scenario else None,
            )
        balance = start_balance
        kept = 0.0
        spent_on_goals = 0.0
        for i, row in enumerate(planned):
            ym = (row["year"], row["month"])
            month = _planned_month(data, ym, plan, scenario, paid)
            savings = _round2(month["income"] - month["expenses"] - month["invested"])
            goal_spend = _round2(sum(p["amount"] for p in row["goals"]))
            balance = _round2(balance + savings - goal_spend)
            kept = _round2(kept + savings)
            spent_on_goals = _round2(spent_on_goals + goal_spend)
            row["budget_from"] = month["budget_from"]
            row["values"][line["key"]] = {
                "income": month["income"],
                "expenses": month["expenses"],
                "invested": month["invested"],
                "savings": savings,
                "balance": balance,
                "salary": paid.get(ym) if paid else None,
                "goal_spend": goal_spend,
                "free": _round2(balance - earmark[i]) if include_goals else None,
            }
        lowest = min(planned, key=lambda r: r["values"][line["key"]]["balance"]) if planned else None
        lowest_free = (
            min(planned, key=lambda r: r["values"][line["key"]]["free"]) if planned and include_goals else None
        )
        summaries.append({
            "key": line["key"],
            "name": line["name"],
            "job_end": scenario.job_end if scenario else None,
            "end_balance": balance,
            "kept": kept,
            "average_kept": _round2(kept / len(planned)) if planned else 0.0,
            "lowest_balance": lowest["values"][line["key"]]["balance"] if lowest else start_balance,
            "lowest_label": lowest["month_name"] if lowest else None,
            "goes_negative": any(r["values"][line["key"]]["balance"] < 0 for r in planned),
            "spent_on_goals": spent_on_goals,
            "lowest_free": lowest_free["values"][line["key"]]["free"] if lowest_free else None,
            "lowest_free_label": lowest_free["month_name"] if lowest_free else None,
        })
    rows.extend(planned)

    borrowed = sorted({r["budget_from"] for r in planned if r["budget_from"] not in (None, r["year"])})
    return {
        "rows": rows,
        "lines": summaries,
        "calendar_used": calendar_active(plan),
        "start": ic.ym_key(first),
        "start_name": ic.ym_name(first),
        "end_name": ic.ym_name(ic.ym_add(first, horizon - 1)),
        "starting_balance": _round2(start_balance),
        "last_recorded_name": ic.ym_name(last) if last_year is not None else None,
        "borrowed_budget_years": borrowed,
        "include_goals": include_goals,
        "goals_spent": _round2(sum(p["amount"] for r in planned for p in r["goals"])),
    }


def expected_monthly_savings(data: AppData) -> float:
    """What goals can count on per month: the average a month keeps over the
    next 12 months (income − costs − investments). With several graduation
    scenarios the most careful one (the lowest average) is used."""
    lines = build(data, include_goals=False)["lines"]
    return min((line["average_kept"] for line in lines), default=0.0)


def goal_checks(data: AppData) -> dict[int, dict[str, Any]]:
    """Each goal seen through the forecast (with goal purchases).

    A goal that is spent: the balance at the end of its month, after this and
    every earlier purchase — ``affordable`` when it stays at or above zero.
    A goal that is kept (the emergency fund): ``affordable`` when the balance in
    its deadline month holds the target. With several scenarios the lowest
    line counts. Goals whose deadline lies after the 12 months shown get none.
    """
    forecast = build(data)
    planned = [r for r in forecast["rows"] if not r["actual"]]
    if not planned:
        return {}
    names = {line["key"]: line["name"] for line in forecast["lines"]}
    first_index = ic.ym_index((planned[0]["year"], planned[0]["month"]))
    out: dict[int, dict[str, Any]] = {}
    for g in data.goals:
        if g.status != "active":
            continue
        spends = g.spends_in_forecast()
        if spends:
            row = next((r for r in planned if any(p["goal_id"] == g.id for p in r["goals"])), None)
        else:
            due = ic.ym_index(ic.ym_of(date.fromisoformat(g.target_date)))
            row = planned[max(0, due - first_index)] if due - first_index < len(planned) else None
        if row is None:
            continue
        key, values = min(row["values"].items(), key=lambda kv: kv[1]["balance"])
        balance = values["balance"]
        out[g.id] = {
            "month": row["key"],
            "month_name": row["month_name"],
            "spent": spends,
            "balance": balance,
            "affordable": balance >= 0 if spends else balance >= g.target_amount,
            "line": names[key] if len(names) > 1 else None,
        }
    return out
