"""Cash in, cash out and how they move over time.

Three views the Overview needs, all pure functions:

- :func:`history`      — the last months (across year boundaries) with fixed
  costs, variable costs, investments and cash in, plus what is "usual".
- :func:`distribution` — where one month's income went: fixed costs, variable
  costs, investment, savings — against the planning guide.
- :func:`category_baselines` — each category's usual monthly amount.

And one for the Forecast tab's budget plan:

- :func:`budget_allocation` — how the plan splits planned income into the same
  four jobs, per month and for the year (with :func:`budget_shares` and
  :func:`amount_from_share` for the % view of single budget lines).

"Usual" figures are always taken from the months *before* the one being looked
at, so a month is never compared with itself (and a month still in progress
cannot pull its own yardstick down). They leave out transactions tagged
**one-off** and use the **median** (the middle value), so a wedding or a
late double salary does not move them for half a year.
"""

from __future__ import annotations

import calendar
from datetime import date
from statistics import median
from typing import Any

from ..config import (
    BASELINE_MONTHS,
    DISTRIBUTION_GUIDE,
    HISTORY_MONTHS,
    MONTHS,
    MONTHS_SHORT,
    SHORT_BASELINE_MONTHS,
)
from ..models import AppData, SavingsGoal, TxType, YearData
from .aggregation import budget_kind_totals, budget_total, kind_totals, last_recorded_month, month_total


def _round2(v: float) -> float:
    return round(v, 2)


def _pct(part: float, whole: float) -> float:
    return _round2(part / whole * 100) if whole else 0.0


def _mean(values: list[float]) -> float | None:
    return _round2(sum(values) / len(values)) if values else None


def _change_pct(now: float, before: float | None) -> float | None:
    """Percent change against a yardstick; ``None`` when there is none."""
    if not before:
        return None
    return _round2((now - before) / before * 100)


def month_end(year_num: int, month: int) -> date:
    return date(year_num, month + 1, calendar.monthrange(year_num, month + 1)[1])


# ---------------------------------------------------------------------------
# Walking back through months, across years
# ---------------------------------------------------------------------------

def months_back(
    data: AppData, year_num: int, month: int, limit: int, include_selected: bool = True
) -> list[tuple[int, int]]:
    """Up to ``limit`` tracked months ending at (``year_num``, ``month``), oldest first.

    A month counts when its year tracks it (it is after ``start_month``) and it
    is not later than that year's last recorded month — an empty future month
    must never drag an average down. The selected month itself is included even
    when nothing is recorded in it yet (``include_selected``). The walk stops at
    a year whose tracking began mid-year, or at a year that does not exist.
    """
    out: list[tuple[int, int]] = []
    y, top, first = year_num, month, True
    while len(out) < limit:
        year = data.get_year(y)
        if year is None:
            break
        last = last_recorded_month(year)
        for m in range(top, year.start_month, -1):
            if len(out) >= limit:
                break
            if m <= last or (first and include_selected and m == month):
                out.append((y, m))
        if year.start_month != -1:
            break
        y, top, first = y - 1, 11, False
    return list(reversed(out))


def _month_row(data: AppData, y: int, m: int) -> dict[str, Any]:
    year = data.get_year(y)
    assert year is not None
    kinds = kind_totals(year, m)
    regular = kind_totals(year, m, skip_one_off=True)
    income = month_total(year, m, "income")
    expenses = _round2(kinds["fixed"] + kinds["variable"])
    cash_out = _round2(expenses + kinds["investment"])
    return {
        # Without one-offs — what the "usual" figures are built from.
        "fixed_regular": regular["fixed"],
        "variable_regular": regular["variable"],
        "expenses_regular": _round2(regular["fixed"] + regular["variable"]),
        "year": y,
        "month": m,
        "month_name": MONTHS_SHORT[m],
        "label": f"{MONTHS_SHORT[m]} {str(y)[2:]}",
        "income": income,
        "fixed": kinds["fixed"],
        "variable": kinds["variable"],
        "invested": kinds["investment"],
        "expenses": expenses,
        "cash_out": cash_out,
        "net": _round2(income - cash_out),
    }


# ---------------------------------------------------------------------------
# Cost history
# ---------------------------------------------------------------------------

def history(data: AppData, year_num: int, month: int, window: int = HISTORY_MONTHS) -> dict[str, Any]:
    """The last ``window`` months up to the selected one, and what is usual.

    ``rows`` feed the charts; each carries ``variable_avg3``, the average of its
    own and the two preceding months' variable costs (``None`` until three
    months exist). ``fixed`` / ``variable`` compare the selected month with the
    months before it:

    - ``avg_3m`` / ``avg_6m`` — mean of the previous 3 / 6 months;
    - ``median_6m`` — the typical month: half of the previous six were below
      it, half above, so one big one-off barely moves it;
    - ``vs_avg_pct`` — the selected month against ``avg_6m``;
    - ``vs_usual_pct`` — the selected month *without one-offs* against
      ``median_6m``: the "vs usual" figure the Overview shows;
    - ``one_off`` — the part of the selected month tagged one-off;
    - ``trend_pct`` — the previous 3 months against the 3 before those.
    """
    extra = max(BASELINE_MONTHS, 2)
    months = months_back(data, year_num, month, window + extra)
    rows = [_month_row(data, y, m) for y, m in months]
    for i, row in enumerate(rows):
        row["variable_avg3"] = _mean([r["variable"] for r in rows[i - 2 : i + 1]]) if i >= 2 else None

    has_current = bool(rows) and (rows[-1]["year"], rows[-1]["month"]) == (year_num, month)
    current = rows[-1] if has_current else None
    prior = rows[:-1] if has_current else rows

    def stats(key: str) -> dict[str, Any]:
        usual_key = f"{key}_regular"  # yardsticks leave one-offs out
        long = [r[usual_key] for r in prior[-BASELINE_MONTHS:]]
        short = [r[usual_key] for r in prior[-SHORT_BASELINE_MONTHS:]]
        earlier = [r[usual_key] for r in prior[-2 * SHORT_BASELINE_MONTHS : -SHORT_BASELINE_MONTHS]]
        now = current[key] if current else 0.0
        now_regular = current[usual_key] if current else 0.0
        median_long = _round2(median(long)) if long else None
        avg_long = _mean(long)
        full_short = len(short) == SHORT_BASELINE_MONTHS
        return {
            "current": now,
            "avg_3m": _mean(short) if full_short else None,
            "avg_6m": avg_long,
            "median_6m": median_long,
            "months": len(long),
            "vs_avg_pct": _change_pct(now, avg_long),
            "vs_usual_pct": _change_pct(now_regular, median_long),
            "one_off": _round2(now - now_regular),
            "trend_pct": (
                _change_pct(_mean(short) or 0.0, _mean(earlier))
                if full_short and len(earlier) == SHORT_BASELINE_MONTHS
                else None
            ),
        }

    return {
        "rows": rows[-window:],
        "fixed": stats("fixed"),
        "variable": stats("variable"),
        "baseline_months": BASELINE_MONTHS,
    }


def baseline_months(
    data: AppData, year_num: int, month: int, n: int = BASELINE_MONTHS, skip: tuple[int, int] | None = None
) -> list[tuple[int, int]]:
    """The ``n`` recorded months before (``year_num``, ``month``).

    ``skip`` leaves one month out — the calendar month still in progress, when
    the yardstick should only use finished months.
    """
    months = months_back(data, year_num, month, n + 2, include_selected=False)
    months = [ym for ym in months if ym != (year_num, month) and ym != skip]
    return months[-n:]


def months_with_data(data: AppData, months: list[tuple[int, int]]) -> int:
    """How many of ``months`` hold at least one transaction that is not one-off.

    A "usual" figure built only from empty months is 0 by accident, not a real
    usual month; the screens use this count to say "no usual yet" instead.
    One-off transactions do not count — they are left out of every usual.
    """
    count = 0
    for y, m in months:
        year = data.get_year(y)
        if year is not None and any(t.month == m and not t.one_off for t in year.transactions):
            count += 1
    return count


def recent_months(
    data: AppData, year_num: int, n: int = BASELINE_MONTHS, skip: tuple[int, int] | None = None
) -> list[tuple[int, int]]:
    """The last ``n`` recorded months up to the end of ``year_num`` (reaching
    into earlier years), again without the month in ``skip``."""
    months = months_back(data, year_num, 11, n + 1, include_selected=False)
    return [ym for ym in months if ym != skip][-n:]


def category_baselines(data: AppData, months: list[tuple[int, int]], kind: TxType = "expense") -> dict[str, float]:
    """``{category: usual month}`` over the given months — the median.

    A month in which a category saw nothing counts as zero, so the result is
    "what this category costs in a usual month", not "per month it was used"
    (a yearly bill has a usual month of 0). One-off transactions are left out.
    """
    if not months:
        return {}
    index = {ym: i for i, ym in enumerate(months)}
    per_month: dict[str, list[float]] = {}
    for y in {ym[0] for ym in months}:
        year = data.get_year(y)
        if year is None:
            continue
        for t in year.transactions:
            i = index.get((y, t.month))
            if t.type == kind and i is not None and not t.one_off:
                per_month.setdefault(t.cat, [0.0] * len(months))[i] += t.amount
    return {cat: _round2(median(values)) for cat, values in per_month.items()}


def typical_costs(data: AppData, year_num: int, month: int) -> float | None:
    """Living costs (fixed + variable) of a typical month before this one.

    The median of the previous months, so a one-off does not distort it.
    ``None`` when there is no earlier month to go by.
    """
    months = baseline_months(data, year_num, month)
    if not months:
        return None
    return _round2(median(_month_row(data, y, m)["expenses_regular"] for y, m in months))


def costs_yardstick(data: AppData, year_num: int, month: int) -> tuple[float | None, str]:
    """The monthly living costs to measure the liquidity against, and where they come from.

    - ``"typical"``    — the median of the months before (``typical_costs``);
    - ``"this_month"`` — no earlier month has any costs yet (the first tracked
      month), so the selected month's own costs stand in;
    - ``"none"``       — no costs recorded at all; ``None`` as the amount.
    """
    typical = typical_costs(data, year_num, month)
    if typical and typical > 0:
        return typical, "typical"
    this_month = _month_row(data, year_num, month)["expenses"]
    if this_month > 0:
        return _round2(this_month), "this_month"
    return None, "none"


# ---------------------------------------------------------------------------
# Liquidity: where the money is
# ---------------------------------------------------------------------------

def position(
    balance: float,
    set_aside: float,
    invested_value: float,
    usual_costs: float | None,
    costs_basis: str = "typical",
) -> dict[str, Any]:
    """What you own, by how freely you can use it.

    - ``liquid``      — money in the account that has no job yet: the balance
      minus what is saved for goals. This is the **liquidity**.
    - ``goals``       — in the account too, but earmarked for a goal.
    - ``investments`` — already turned into an asset (valued at what it cost);
      not money that can be spent.

    ``runway_months`` is how many months of ``usual_costs`` the liquidity covers
    (0 when there is no liquidity; ``None`` only when no costs are known).
    ``costs_basis`` says where ``usual_costs`` comes from (see
    ``costs_yardstick``). ``over_earmarked`` flags goals holding more than the
    account has.
    """
    liquid = _round2(balance - set_aside)
    total = _round2(balance + invested_value)
    parts = [
        ("liquid", "Liquid", liquid),
        ("goals", "Saved for goals", _round2(set_aside)),
        ("investments", "Investments", _round2(invested_value)),
    ]
    drawn = sum(max(0.0, amount) for _, _, amount in parts)
    return {
        "liquidity": liquid,
        "balance": _round2(balance),
        "earmarked": _round2(set_aside),
        "invested_value": _round2(invested_value),
        "total": total,
        "parts": [
            {"key": key, "label": label, "amount": amount, "width": _pct(max(0.0, amount), drawn)}
            for key, label, amount in parts
        ],
        "usual_costs": usual_costs if usual_costs and usual_costs > 0 else None,
        "costs_basis": costs_basis if usual_costs and usual_costs > 0 else "none",
        "runway_months": (
            round(max(0.0, liquid) / usual_costs, 1) if usual_costs and usual_costs > 0 else None
        ),
        "over_earmarked": liquid < 0 <= balance,
    }


# ---------------------------------------------------------------------------
# Where the income went
# ---------------------------------------------------------------------------

def contributions_in_month(goals: list[SavingsGoal], year_num: int, month: int) -> float:
    """Money put toward goals that still hold it, dated in that month."""
    prefix = f"{year_num}-{month + 1:02d}-"
    return _round2(
        sum(c.signed for g in goals if g.status == "active" for c in g.contributions if c.date.startswith(prefix))
    )


def earmarked(goals: list[SavingsGoal], upto: date) -> float:
    """Money set aside for active goals up to and including ``upto``.

    Goal money stays in the same account, so this is the part of the balance
    that already has a job. Completed or stopped goals release theirs.
    """
    limit = upto.isoformat()
    return _round2(
        sum(c.signed for g in goals if g.status == "active" for c in g.contributions if c.date <= limit)
    )


def _guide_status(key: str, share: float, income: float) -> tuple[str | None, bool]:
    """Where a share sits against its planning range, and whether to point it out.

    Costs deserve attention above their range; investing and saving below theirs.
    """
    if income <= 0:
        return None, False
    low, high = DISTRIBUTION_GUIDE[key]
    if low is not None and share < low:
        return "below", key in ("investment", "savings")
    if high is not None and share > high:
        return "above", key in ("fixed", "variable")
    return "within", False


JOB_LABELS = {
    "fixed": "Fixed costs",
    "variable": "Variable costs",
    "investment": "Investment",
    "savings": "Savings",
}


def _job_blocks(income: float, amounts: dict[str, float]) -> list[dict[str, Any]]:
    """The four jobs money can have, each with its share of income and where
    it sits against the planning guide (shared by the real month and the plan)."""
    blocks = []
    for key, label in JOB_LABELS.items():
        share = _pct(amounts[key], income)
        status, attention = _guide_status(key, share, income)
        low, high = DISTRIBUTION_GUIDE[key]
        blocks.append(
            {
                "key": key,
                "label": label,
                "amount": amounts[key],
                "share": share,
                "guide_min": low,
                "guide_max": high,
                "status": status,
                "attention": attention,
            }
        )
    return blocks


def distribution(year: YearData, year_num: int, month: int, goals: list[SavingsGoal]) -> dict[str, Any]:
    """How one month's income was distributed.

    ``blocks`` are the four jobs money can have — fixed costs, variable costs,
    investment, savings — each with its share of income and the planning range.
    Savings (what stayed in the account) are then split into what was put
    toward goals and what is still unassigned. ``segments`` draw the bar: when
    more went out than came in, the bar is as long as the cash out and
    ``shortfall`` says how much came from the existing balance.
    """
    income = month_total(year, month, "income")
    kinds = kind_totals(year, month)
    fixed, variable, invested = kinds["fixed"], kinds["variable"], kinds["investment"]
    saved = _round2(income - fixed - variable - invested)
    to_goals = contributions_in_month(goals, year_num, month)
    unassigned = _round2(saved - to_goals)
    left = max(0.0, unassigned)

    blocks = _job_blocks(income, {"fixed": fixed, "variable": variable, "investment": invested, "savings": saved})

    goals_part = min(to_goals, max(saved, 0.0))
    parts = [
        ("fixed", "Fixed costs", fixed),
        ("variable", "Variable costs", variable),
        ("investment", "Investment", invested),
        ("goals", "Put toward goals", _round2(goals_part)),
        ("unassigned", "Not assigned yet", _round2(left)),
    ]
    bar_total = _round2(sum(amount for _, _, amount in parts))
    segments = [
        {"key": key, "label": label, "amount": amount, "share": _pct(amount, income), "width": _pct(amount, bar_total)}
        for key, label, amount in parts
    ]
    return {
        "year": year_num,
        "month": month,
        "month_name": MONTHS[month],
        "income": income,
        "cash_out": _round2(fixed + variable + invested),
        "blocks": blocks,
        "segments": segments,
        "saved": saved,
        "to_goals": to_goals,
        "left_to_assign": _round2(left),
        "shortfall": _round2(max(0.0, -saved)),
        "over_assigned": unassigned < 0 and to_goals > 0,
    }


def _planned_split(income: float, fixed: float, variable: float, invested: float) -> dict[str, Any]:
    """One planned split: the four jobs as € and % of planned income.

    ``width`` sizes each part of the bar. When the plan spends more than it
    earns, savings are negative: the bar is then as long as the cash out and
    ``shortfall`` says how much would have to come from the balance.
    """
    cash_out = _round2(fixed + variable + invested)
    savings = _round2(income - cash_out)
    blocks = _job_blocks(income, {"fixed": fixed, "variable": variable, "investment": invested, "savings": savings})
    bar_total = max(income, cash_out)
    for b in blocks:
        b["width"] = _pct(max(b["amount"], 0.0), bar_total)
    return {
        "income": _round2(income),
        "cash_out": cash_out,
        "blocks": blocks,
        "shortfall": _round2(max(0.0, -savings)),
        "attention": sum(1 for b in blocks if b["attention"]),
    }


def budget_allocation(year: YearData) -> dict[str, Any]:
    """How the budget plan splits planned income, month by month and for the year.

    Uses the income and cash-out budgets of the plan (the same figures as its
    "Planned" kept row). Savings are what the plan leaves over:
    planned income − fixed − variable − investment, so the four shares add up to
    100 % whenever the plan does not spend more than it earns.
    A month without planned income has shares of 0 and no guide status.
    """
    months = []
    sums = {"income": 0.0, "fixed": 0.0, "variable": 0.0, "investment": 0.0}
    for m in range(12):
        income = budget_total(year, m, "income")
        kinds = budget_kind_totals(year, m)
        months.append(
            {"month": m, "name": MONTHS[m], **_planned_split(income, kinds["fixed"], kinds["variable"], kinds["investment"])}
        )
        sums["income"] += income
        for key in ("fixed", "variable", "investment"):
            sums[key] += kinds[key]
    total = {k: _round2(v) for k, v in sums.items()}
    return {
        "months": months,
        "year": _planned_split(total["income"], total["fixed"], total["variable"], total["investment"]),
    }


def budget_shares(year: YearData, values: list[float]) -> list[float | None]:
    """Each month's budget as a % of that month's planned income (``None`` when
    no income is planned that month, so no share can be given)."""
    shares: list[float | None] = []
    for m, value in enumerate(values[:12]):
        income = budget_total(year, m, "income")
        shares.append(_pct(value, income) if income > 0 else None)
    return shares


def amount_from_share(year: YearData, month: int, percent: float) -> float:
    """The euro budget that is ``percent`` % of the month's planned income.

    Raises ``ValueError`` when the month has no planned income to take a share of.
    """
    income = budget_total(year, month, "income")
    if income <= 0:
        raise ValueError(f"{MONTHS[month]} has no planned income yet, so a % cannot be turned into euros")
    return _round2(income * percent / 100)
