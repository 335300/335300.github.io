"""Sinking funds: goals for a known bill that comes back.

A sinking fund is a goal with ``goal_type == "sinking"``: ``target_amount`` is
one bill, ``target_date`` the next due date, ``repeat_months`` the rhythm.

**Paying from the fund** (:func:`pay_from_fund`) does three things at once:

1. records the bill as an ordinary expense transaction (it is real cash out);
2. takes the same amount out of the fund as a *withdrawal* — at most what the
   fund holds; anything above that is paid from free money;
3. moves the due date on by one cycle.

Because the withdrawal lowers the money earmarked for goals by what the
expense lowered the balance, the **liquidity does not dip** — the bill was
already put aside. :func:`paid_from_funds` reports what each month paid this way.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..models import AppData, Category, Contribution, PayFromFundInput, SavingsGoal, Transaction
from .dates import add_months


def _round2(v: float) -> float:
    return round(v, 2)


class FundError(ValueError):
    pass


def monthly_set_aside(goal: SavingsGoal) -> float | None:
    """The steady amount that covers the bill each cycle (€220 every 6 months → €36.67)."""
    if goal.goal_type != "sinking" or not goal.repeat_months:
        return None
    return _round2(goal.target_amount / goal.repeat_months)


def pay_from_fund(data: AppData, goal: SavingsGoal, payment: PayFromFundInput) -> dict[str, Any]:
    if goal.goal_type != "sinking" or not goal.repeat_months:
        raise FundError(f"{goal.name!r} is not a sinking fund")
    if goal.status != "active":
        raise FundError(f"{goal.name!r} is not active")
    d = date.fromisoformat(payment.date)
    year = data.get_year(d.year)
    if year is None or d.month - 1 <= year.start_month:
        raise FundError(f"{payment.date} is in a month the app does not track")

    tx = Transaction(
        id=year.take_id(), type="expense", date=payment.date, month=d.month - 1, amount=payment.amount,
        desc=payment.desc or f"{goal.name} (paid from fund)", cat=payment.category,
    )
    if year.find_category("expense", payment.category) is None:
        year.categories.expense.append(Category(name=payment.category))
        year.budgets.expense.setdefault(payment.category, [0.0] * 12)
    year.transactions.append(tx)

    from_fund = _round2(min(payment.amount, max(0.0, goal.saved())))
    if from_fund > 0:
        goal.contributions.append(Contribution(
            id=goal.take_contribution_id(), date=payment.date, amount=from_fund,
            note=f"Paid: {tx.desc}", withdrawal=True, tx_year=d.year, tx_id=tx.id,
        ))
    old_due = goal.target_date
    goal.target_date = add_months(date.fromisoformat(goal.target_date), goal.repeat_months).isoformat()
    return {
        "transaction": tx.model_dump(),
        "from_fund": from_fund,
        "from_free_money": _round2(payment.amount - from_fund),
        "old_due": old_due,
        "next_due": goal.target_date,
    }


def drop_withdrawals_for(data: AppData, year: int, tx_id: int) -> None:
    """A deleted bill gives its money back to the fund."""
    for g in data.goals:
        g.contributions = [
            c for c in g.contributions if not (c.withdrawal and c.tx_year == year and c.tx_id == tx_id)
        ]


def paid_from_funds(goals: list[SavingsGoal], year_num: int, month: int) -> dict[str, Any]:
    """Bills of one month that sinking funds paid."""
    prefix = f"{year_num}-{month + 1:02d}-"
    items = [
        {"goal_id": g.id, "name": g.name, "amount": c.amount, "date": c.date}
        for g in goals
        for c in g.contributions
        if c.withdrawal and c.date.startswith(prefix)
    ]
    return {"total": _round2(sum(i["amount"] for i in items)), "items": items}
