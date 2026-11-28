"""Totals and running balances (ported from the v1 app)."""

from __future__ import annotations

from ..models import AppData, TxType, YearData


def _round2(v: float) -> float:
    return round(v, 2)


def month_total(year: YearData, month: int, kind: TxType) -> float:
    """Recorded income or expenses for one month."""
    return _round2(
        sum(t.amount for t in year.transactions if t.month == month and t.type == kind)
    )


def category_totals(year: YearData, month: int, kind: TxType, skip_one_off: bool = False) -> dict[str, float]:
    """``{category: amount}`` actually recorded in one month.

    ``skip_one_off`` leaves out transactions tagged one-off (for "usual" figures).
    """
    totals: dict[str, float] = {}
    for t in year.transactions:
        if t.month == month and t.type == kind and not (skip_one_off and t.one_off):
            totals[t.cat] = totals.get(t.cat, 0.0) + t.amount
    return {k: _round2(v) for k, v in totals.items()}


def kind_totals(year: YearData, month: int, skip_one_off: bool = False) -> dict[str, float]:
    """One month's recorded cash out, split by what it was for.

    ``fixed`` and ``variable`` are living costs; ``investment`` is money that
    left the account to build an asset. The three add up to
    ``month_total(year, month, "expense")`` (unless ``skip_one_off`` leaves
    one-off transactions out, for "usual" figures).
    """
    totals = {"fixed": 0.0, "variable": 0.0, "investment": 0.0}
    for t in year.transactions:
        if t.month == month and t.type == "expense" and not (skip_one_off and t.one_off):
            totals[year.kind_of(t.cat)] += t.amount
    return {k: _round2(v) for k, v in totals.items()}


def budget_kind_totals(year: YearData, month: int) -> dict[str, float]:
    """The same split for one month's budget."""
    totals = {"fixed": 0.0, "variable": 0.0, "investment": 0.0}
    for name, row in year.budgets.expense.items():
        if month < len(row):
            totals[year.kind_of(name)] += row[month]
    return {k: _round2(v) for k, v in totals.items()}


def budget_kind_rows(year: YearData) -> dict[str, dict]:
    """The expense budget summed per kind, for the budget plan's subtotal rows.

    ``{"fixed" | "variable" | "investment": {"monthly": [12 amounts], "total": year}}``.
    A budget row whose category no longer exists counts as variable (like
    :func:`budget_kind_totals`), so the three add up to the plan's cash-out total.
    """
    months = [budget_kind_totals(year, m) for m in range(12)]
    return {
        kind: {"monthly": [m[kind] for m in months], "total": _round2(sum(m[kind] for m in months))}
        for kind in ("fixed", "variable", "investment")
    }


def month_net(year: YearData, month: int) -> float:
    """Cash in minus all cash out (costs and investments) for one month — what
    stayed in the account: the month's savings."""
    return _round2(month_total(year, month, "income") - month_total(year, month, "expense"))


def budget_total(year: YearData, month: int, kind: TxType) -> float:
    """Budgeted income or expenses for one month, across all categories."""
    grid = getattr(year.budgets, kind)
    return _round2(sum(row[month] for row in grid.values() if month < len(row)))


def balance_through(year: YearData, month: int) -> float:
    """Running balance at the close of ``month``.

    Starts from the year's opening balance and applies every month after
    ``start_month`` up to and including ``month``.
    """
    balance = year.opening_balance
    for m in range(year.start_month + 1, month + 1):
        balance += month_net(year, m)
    return _round2(balance)


def closing_balance(year: YearData) -> float:
    """Balance at the close of December."""
    return balance_through(year, 11)


def last_recorded_month(year: YearData) -> int:
    """Index of the latest month holding any transaction, else ``start_month``."""
    if not year.transactions:
        return year.start_month
    return max(t.month for t in year.transactions)


def opening_balance_for_month(data: AppData, year_num: int, month: int) -> float:
    """Balance at the *start* of ``month`` — i.e. the close of the month before.

    For the first tracked month this reaches back into the previous year's
    December, falling back to this year's opening balance when the previous
    year is not tracked.
    """
    year = data.get_year(year_num)
    if year is None:
        return 0.0

    if month > year.start_month + 1:
        return balance_through(year, month - 1)

    previous = data.get_year(year_num - 1)
    if previous is not None and year.start_month == -1:
        return closing_balance(previous)
    return _round2(year.opening_balance)


def savings_by_month(year: YearData) -> dict:
    """The "Saved" rows under the budget plan.

    - ``planned``: budgeted income − budgeted expenses, every month (the plan).
    - ``actual``: recorded income − expenses for tracked months up to the last
      recorded one; ``None`` for months not tracked or not recorded yet.
    Totals add up each row (``actual_total`` over recorded months only).
    """
    last = last_recorded_month(year)
    planned = [
        _round2(budget_total(year, m, "income") - budget_total(year, m, "expense")) for m in range(12)
    ]
    actual = [month_net(year, m) if year.start_month < m <= last else None for m in range(12)]
    return {
        "planned": planned,
        "planned_total": _round2(sum(planned)),
        "actual": actual,
        "actual_total": _round2(sum(v for v in actual if v is not None)),
    }


def day_totals(transactions: list) -> dict[str, dict[str, float]]:
    """Cash in and cash out per date ("YYYY-MM-DD") for the Transactions calendar."""
    out: dict[str, dict[str, float]] = {}
    for t in transactions:
        day = out.setdefault(t.date, {"income": 0.0, "expense": 0.0})
        day[t.type] = _round2(day[t.type] + t.amount)
    return out
