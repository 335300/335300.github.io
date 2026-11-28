"""Recurring bills: paid bills move on, upcoming with "money ready", detection.

Made-up data, 2026 tracked from January with an opening balance of 1,000.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.models import AppData, Contribution, RecurringBill, SavingsGoal, Transaction, YearData
from app.services import recurring

TODAY = date(2026, 4, 10)


@pytest.fixture
def data() -> AppData:
    d = AppData()
    d.years["2026"] = YearData(opening_balance=1000)
    return d


def pay(data: AppData, when: str, amount: float, payee: str = "", desc: str = "", cat: str = "Bills") -> None:
    year = data.years.setdefault(when[:4], YearData())
    d = date.fromisoformat(when)
    year.transactions.append(Transaction(id=year.take_id(), type="expense", date=when, month=d.month - 1,
                                         amount=amount, cat=cat, payee=payee, desc=desc))


def bill(**kw) -> RecurringBill:
    base = dict(id=1, name="Phone", amount=22, category="Bills", rhythm_months=1, next_due="2026-01-15", match="vodafone")
    base.update(kw)
    return RecurringBill(**base)


def test_rhythm_must_be_known():
    with pytest.raises(ValueError):
        bill(rhythm_months=2)


def test_paid_due_dates_move_on(data):
    pay(data, "2026-01-14", 22, payee="Vodafone GmbH")
    pay(data, "2026-02-16", 22, payee="Vodafone GmbH")
    pay(data, "2026-03-15", 23, payee="VODAFONE")  # within 10%
    due, last = recurring.current_due(data, bill())
    assert due == date(2026, 4, 15) and last == "2026-03-15"


def test_a_payment_too_far_from_the_due_date_does_not_count(data):
    pay(data, "2026-01-23", 22, payee="Vodafone")  # 8 days late
    assert recurring.current_due(data, bill())[0] == date(2026, 1, 15)


def test_a_different_amount_is_not_the_bill(data):
    pay(data, "2026-01-15", 30, payee="Vodafone")  # +36%
    assert recurring.current_due(data, bill())[0] == date(2026, 1, 15)


def test_without_match_text_the_category_decides(data):
    pay(data, "2026-01-15", 22, desc="phone", cat="Phone & Internet")
    b = bill(match="", category="Phone & Internet")
    assert recurring.current_due(data, b)[0] == date(2026, 2, 15)
    assert recurring.current_due(data, bill(match="", category="Other"))[0] == date(2026, 1, 15)


def test_month_end_due_dates_do_not_drift(data):
    pay(data, "2026-01-31", 22, payee="Vodafone")
    pay(data, "2026-02-28", 22, payee="Vodafone")
    due, _ = recurring.current_due(data, bill(next_due="2026-01-31"))
    assert due == date(2026, 3, 31)  # not the 28th


def test_semester_rhythm(data):
    pay(data, "2026-02-14", 220, payee="Hochschule Beispiel")
    due, _ = recurring.current_due(data, bill(amount=220, rhythm_months=6, next_due="2026-02-15", match="hochschule"))
    assert due == date(2026, 8, 15)


def test_upcoming_with_money_ready(data):
    # Balance at the end of March: 1,000 - 22 - 22 - 23 = 933.
    for when in ("2026-01-15", "2026-02-15", "2026-03-15"):
        pay(data, when, 22 if when < "2026-03" else 23, payee="Vodafone")
    data.goals = [SavingsGoal(id=7, name="Semester fee", target_amount=220, target_date="2026-04-20",
                              created_date="2026-01-01", goal_type="sinking", repeat_months=6,
                              contributions=[Contribution(id=1, date="2026-01-31", amount=150)])]
    data.recurring_bills = [
        bill(),
        bill(id=2, name="Semester fee", amount=220, rhythm_months=6, next_due="2026-04-20", match="hochschule", goal_id=7),
        bill(id=3, name="Rent", amount=900, next_due="2026-05-01", match="landlord"),
    ]
    up = recurring.upcoming(data, TODAY)
    # Liquidity today: 933 - 150 saved for the goal = 783.
    assert up["liquidity"] == 783
    names = [(i["name"], i["due"]) for i in up["items"]]
    assert names == [("Phone", "2026-04-15"), ("Semester fee", "2026-04-20"), ("Rent", "2026-05-01")]
    phone, fee, rent = up["items"]
    assert phone["ready"] is True and phone["days_left"] == 5 and phone["source"] == "liquidity"
    assert fee["source"] == "fund" and fee["ready"] is False and fee["short_by"] == 70
    # Rent: 22 (phone) + 900 = 922 needed from 783 -> 139 short.
    assert rent["ready"] is False and rent["short_by"] == 139
    assert up["total"] == 22 + 220 + 900 and up["all_ready"] is False


def test_overdue_bills_are_listed(data):
    data.recurring_bills = [bill(next_due="2026-03-01")]
    items = recurring.upcoming(data, TODAY)["items"]
    assert items[0]["overdue"] is True and items[0]["days_left"] == -40
    # Also every later due date inside the 30 days: 1 April and 1 May... 1 May is day 21.
    assert [i["due"] for i in items] == ["2026-03-01", "2026-04-01", "2026-05-01"]


def test_bill_view(data):
    view = recurring.bill_view(data, bill(amount=220, rhythm_months=6))
    assert view["rhythm_word"] == "every semester" and view["monthly_cost"] == 36.67
    assert view["due"] == "2026-01-15" and view["last_paid"] is None


# -- detection ------------------------------------------------------------------

def streaming(data):
    for when, amount in (("2026-01-03", 9.99), ("2026-02-03", 9.99), ("2026-03-04", 10.49)):
        pay(data, when, amount, payee="Streaming Dienst GmbH", cat="Subscriptions")


def test_detects_a_monthly_bill(data):
    streaming(data)
    (s,) = recurring.suggestions(data, TODAY)
    assert s["key"] == "streaming dienst" and s["rhythm_months"] == 1
    assert s["amount"] == 9.99 and s["category"] == "Subscriptions"
    assert s["next_due"] == "2026-04-04" and s["payments"] == 3


def test_detects_a_semester_bill_across_years(data):
    for when in ("2025-02-15", "2025-08-14", "2026-02-16"):
        pay(data, when, 220, payee="Hochschule Beispiel")
    (s,) = recurring.suggestions(data, TODAY)
    assert s["rhythm_months"] == 6 and s["next_due"] == "2026-08-16"


def test_two_payments_are_not_enough(data):
    pay(data, "2026-01-03", 9.99, payee="Streaming Dienst")
    pay(data, "2026-02-03", 9.99, payee="Streaming Dienst")
    assert recurring.suggestions(data, TODAY) == []


def test_irregular_gaps_are_not_a_bill(data):
    for when in ("2026-01-03", "2026-01-20", "2026-03-30"):
        pay(data, when, 9.99, payee="Kiosk")
    assert recurring.suggestions(data, TODAY) == []


def test_stopped_long_ago_is_not_suggested(data):
    streaming(data)
    assert recurring.suggestions(data, date(2026, 8, 1)) == []


def test_known_or_dismissed_bills_are_not_suggested(data):
    streaming(data)
    data.recurring_bills = [bill(name="Streaming", amount=9.99, match="streaming")]
    assert recurring.suggestions(data, TODAY) == []
    data.recurring_bills = []
    data.dismissed_bill_suggestions = ["streaming dienst"]
    assert recurring.suggestions(data, TODAY) == []


def test_month_calendar_shows_paid_and_unpaid_bills_and_goal_deadlines(data):
    pay(data, "2026-03-15", 22, payee="Vodafone")
    data.goals = [
        SavingsGoal(id=7, name="Laptop", target_amount=900, target_date="2026-04-28", created_date="2026-01-01"),
        SavingsGoal(id=8, name="Old trip", target_amount=300, target_date="2026-04-02", created_date="2026-01-01",
                    status="abandoned"),
    ]
    data.recurring_bills = [bill(next_due="2026-03-15"), bill(id=3, name="Rent", amount=900, next_due="2026-04-01", match="landlord")]

    march = recurring.month_calendar(data, 2026, 2, TODAY)
    assert [(b["name"], b["due"], b["paid"], b["paid_on"]) for b in march["bills"]] == [("Phone", "2026-03-15", True, "2026-03-15")]
    assert march["total_due"] == 0 and march["total_paid"] == 22

    april = recurring.month_calendar(data, 2026, 3, TODAY)
    # Rent on the 1st is unpaid and overdue on TODAY (10 April); the phone is due on the 15th.
    assert [(b["name"], b["due"], b["paid"]) for b in april["bills"]] == [("Rent", "2026-04-01", False), ("Phone", "2026-04-15", False)]
    rent, phone = april["bills"]
    assert rent["overdue"] is True and phone["overdue"] is False
    # Liquidity 1,000 - 22 = 978 covers rent (900) and then rent + phone (922).
    assert rent["ready"] is True and phone["ready"] is True
    assert april["total_due"] == 922
    # Only goals that are not abandoned show their deadline.
    assert [(g["name"], g["date"]) for g in april["goals"]] == [("Laptop", "2026-04-28")]


def test_month_calendar_far_ahead_has_no_money_verdict(data):
    data.recurring_bills = [bill(next_due="2026-04-15")]
    july = recurring.month_calendar(data, 2026, 6, TODAY)
    assert [(b["due"], b["ready"]) for b in july["bills"]] == [("2026-07-15", None)]
    assert july["total_due"] == 22


def test_upcoming_is_unchanged_by_the_calendar_refactor(data):
    data.recurring_bills = [bill(next_due="2026-04-15")]
    up = recurring.upcoming(data, TODAY)
    assert [(i["due"], i["ready"]) for i in up["items"]] == [("2026-04-15", True)]


# -- one payment pays at most one bill (found by the blind check, 18 Nov 2026) ------------


def policies(data: AppData) -> list[RecurringBill]:
    """Two yearly policies in one category, no match text: B (52 €, 22 Mar) has the lower id."""
    data.recurring_bills = [
        RecurringBill(id=1, name="Policy B", amount=52, category="Insurance", rhythm_months=12, next_due="2026-03-22"),
        RecurringBill(id=2, name="Policy A", amount=50, category="Insurance", rhythm_months=12, next_due="2026-03-20"),
    ]
    return data.recurring_bills


def test_one_payment_pays_only_one_bill(data):
    """One 50 € payment on 20 Mar fits both (52 − 50 = 2 ≤ 10 % of 52; 2 days from 22 Mar).
    Policy A gets it: exact amount (difference 0 < 2). Policy B stays unpaid: due 22 Mar 2026."""
    b, a = policies(data)
    pay(data, "2026-03-20", 50, cat="Insurance")
    assert recurring.current_due(data, a) == (date(2027, 3, 20), "2026-03-20")
    assert recurring.current_due(data, b) == (date(2026, 3, 22), None)


def test_two_payments_pay_both_bills(data):
    """50 € on 20 Mar and 52 € on 22 Mar: each policy gets its own payment."""
    b, a = policies(data)
    pay(data, "2026-03-20", 50, cat="Insurance")
    pay(data, "2026-03-22", 52, cat="Insurance")
    assert recurring.current_due(data, a) == (date(2027, 3, 20), "2026-03-20")
    assert recurring.current_due(data, b) == (date(2027, 3, 22), "2026-03-22")


def test_a_bill_with_its_own_match_text_is_served_first(data):
    """Both 30 € on 15 Mar in category Insurance; the payment says "Allianz". The bill
    with match text "allianz" gets it although the other bill has the lower id."""
    data.recurring_bills = [
        RecurringBill(id=1, name="Any insurance", amount=30, category="Insurance", rhythm_months=12,
                      next_due="2026-03-15"),
        RecurringBill(id=2, name="Allianz", amount=30, category="Insurance", rhythm_months=12,
                      next_due="2026-03-15", match="allianz"),
    ]
    pay(data, "2026-03-15", 30, payee="Allianz SE", cat="Insurance")
    anyone, allianz = data.recurring_bills
    assert recurring.current_due(data, allianz)[0] == date(2027, 3, 15)
    assert recurring.current_due(data, anyone)[0] == date(2026, 3, 15)


def test_the_overview_lists_show_the_unpaid_policy(data):
    """Today 10 Apr 2026: Policy B (22 Mar) is overdue in the due-soon list and unpaid in
    the March calendar, where only Policy A is paid. Still due in March: 52."""
    policies(data)
    pay(data, "2026-03-20", 50, cat="Insurance")
    overdue = [(i["name"], i["due"], i["overdue"]) for i in recurring.upcoming(data, TODAY)["items"]]
    assert overdue == [("Policy B", "2026-03-22", True)]
    march = recurring.month_calendar(data, 2026, 2, TODAY)
    assert [(x["name"], x["paid"]) for x in march["bills"]] == [("Policy A", True), ("Policy B", False)]
    assert march["total_due"] == 52
