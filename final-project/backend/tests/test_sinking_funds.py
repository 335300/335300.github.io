"""Sinking funds: a goal for a bill that comes back, paid from the fund.

Uses the shared ``data`` fixture (2026 tracked from March, balance from
transactions in March and April). The fund: a semester fee of 220 every 6
months, next due 1 August 2026.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.models import Contribution, PayFromFundInput, SavingsGoal
from app.services import cashflow, goals, sinking
from app.services.dates import add_months


def fund(saved: float = 150, **kw) -> SavingsGoal:
    base = dict(
        id=1, name="Semester fee", target_amount=220, target_date="2026-08-01", created_date="2026-03-01",
        goal_type="sinking", repeat_months=6,
        contributions=[Contribution(id=1, date="2026-03-10", amount=saved)] if saved else [],
        next_contribution_id=2,
    )
    base.update(kw)
    return SavingsGoal(**base)


def pay(amount=220, when="2026-04-20", cat="Tuition"):
    return PayFromFundInput(date=when, amount=amount, category=cat)


@pytest.mark.parametrize("start,months,end", [
    (date(2026, 8, 1), 6, date(2027, 2, 1)),
    (date(2026, 1, 31), 1, date(2026, 2, 28)),
    (date(2027, 12, 15), 12, date(2028, 12, 15)),
])
def test_add_months(start, months, end):
    assert add_months(start, months) == end


def test_a_sinking_fund_needs_a_rhythm():
    with pytest.raises(ValueError):
        SavingsGoal(id=1, name="X", target_amount=10, target_date="2026-08-01", created_date="2026-01-01",
                    goal_type="sinking")


def test_monthly_set_aside():
    assert sinking.monthly_set_aside(fund()) == 36.67  # 220 / 6
    assert goals.build(fund(), 100, date(2026, 3, 15))["monthly_set_aside"] == 36.67


def test_pay_from_fund(data):
    g = fund()
    data.goals = [g]
    result = sinking.pay_from_fund(data, g, pay(amount=140))
    # The expense is real cash out...
    tx = result["transaction"]
    assert tx["amount"] == 140 and tx["cat"] == "Tuition" and tx["month"] == 3
    assert data.years["2026"].find_category("expense", "Tuition") is not None
    # ...and the fund paid it: 150 - 140 = 10 left; due date one cycle later.
    assert result["from_fund"] == 140 and result["from_free_money"] == 0
    assert g.saved() == 10
    assert g.target_date == "2027-02-01" and result["next_due"] == "2027-02-01"


def test_liquidity_does_not_dip(data):
    """Balance minus goal money stays the same: the bill was already put aside."""
    g = fund()
    data.goals = [g]
    upto = date(2026, 4, 30)
    before = cashflow.earmarked(data.goals, upto)
    sinking.pay_from_fund(data, g, pay(amount=140))
    after = cashflow.earmarked(data.goals, upto)
    assert before - after == 140  # exactly what the expense took from the balance


def test_a_bill_bigger_than_the_fund(data):
    g = fund(saved=150)
    data.goals = [g]
    result = sinking.pay_from_fund(data, g, pay(amount=220))
    assert result["from_fund"] == 150 and result["from_free_money"] == 70
    assert g.saved() == 0


def test_empty_fund_pays_nothing(data):
    g = fund(saved=0)
    data.goals = [g]
    result = sinking.pay_from_fund(data, g, pay())
    assert result["from_fund"] == 0 and g.contributions == []


def test_only_active_sinking_funds_pay(data):
    one_time = fund(goal_type="one_time", repeat_months=None)
    with pytest.raises(sinking.FundError):
        sinking.pay_from_fund(data, one_time, pay())
    with pytest.raises(sinking.FundError):
        sinking.pay_from_fund(data, fund(status="abandoned"), pay())


def test_untracked_month_is_refused(data):
    with pytest.raises(sinking.FundError, match="does not track"):
        sinking.pay_from_fund(data, fund(), pay(when="2026-02-10"))  # tracking starts in March
    with pytest.raises(sinking.FundError):
        sinking.pay_from_fund(data, fund(), pay(when="2025-12-10"))


def test_deleting_the_bill_gives_the_money_back(data):
    g = fund()
    data.goals = [g]
    tx = sinking.pay_from_fund(data, g, pay(amount=100))["transaction"]
    sinking.drop_withdrawals_for(data, 2026, tx["id"])
    assert g.saved() == 150


def test_paid_from_funds_in_a_month(data):
    g = fund()
    data.goals = [g]
    sinking.pay_from_fund(data, g, pay(amount=100))
    assert sinking.paid_from_funds(data.goals, 2026, 3) == {
        "total": 100, "items": [{"goal_id": 1, "name": "Semester fee", "amount": 100, "date": "2026-04-20"}],
    }
    assert sinking.paid_from_funds(data.goals, 2026, 2)["total"] == 0


def test_withdrawals_lower_the_month_put_toward_goals(data):
    g = fund()
    data.goals = [g]
    sinking.pay_from_fund(data, g, pay(amount=100))
    # April: nothing put in, 100 taken out.
    assert cashflow.contributions_in_month(data.goals, 2026, 3) == -100
