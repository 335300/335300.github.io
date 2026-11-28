"""Money dates for the Calendar tab: when money arrives, leaves or is due.

One list for a window of days (``start`` to ``end``, both included) of one
profile. Every item has a date, a kind, a name, an amount and a status.

**When the pay arrives.** The income calendar's *pay day* says it: 0 = the
last working day of the month, -1 = the working day before that (Josu's salary:
last working day Mon 30 Nov 2026 -> paid Fri 27 Nov), 1-31 = that day. A day
the month lacks becomes its last day, and a weekend moves back to the Friday
before (public holidays are not looked at). Each month M has one pay date (with pay day 1 or 2 it can
fall at the end of the month before).

**Budgets of a year not set up** are borrowed like the forecast does (the
latest earlier year, else the earliest one) — for the salary, the Personal
transfer budget and the Joint plan alike. The Joint plan's two parts are split
by :func:`joint.bill` (half-up to the cent, so they always add up).

Kinds:

- **salary** (Personal): the pay date of each month M. With a pay day at the
  end of the month (the working day before the last, the last working day, or
  the 25th or later) it is the salary of month **M + 1** — Josu's rule: salary
  paid 26th–30th counts for the following month, dated the 1st (18 Nov 2026).
  With an earlier pay day it is month M's. Done when salary is booked in that
  month (the amount booked); else expected: what the income calendar says
  arrives that month when it is on, otherwise the salary budget of that month.
- **transfer** (Personal): "Transfer to Joint" on the working day after the pay
  arrives, for month M + 1 when the pay day is late, else for month M. Done when
  a transfer is booked in that month; else due (overdue once its date passed),
  with Josu's part of the Joint plan of that month (or, without Joint data, the
  Personal "Transfer to Joint" budget).
- **contribution** (Joint): each person's money ("From <name>") on the same day
  as the transfer, for the same month. Done when booked; else expected, with
  that person's part of the Joint plan.
- **bill**: every due date of each recurring bill. Done when paid (with the
  payment date); else due, or overdue once the date passed.
- **goal** / **sinking**: the deadline of each savings goal (not abandoned).
  Done when completed; else due, or overdue once the date passed.

**A budget box typed by hand** (``YearBudgets.manual``) wins over the figure
that fills itself: a typed salary, Transfer to Joint or "From <name>" of that
month is the amount shown.

Items with no amount (0) are left out. ``due_total`` adds what is still to pay
(bills and transfers not done, overdue included); ``expected_total`` what is
still to come in (salary and contributions not done). Goals are in neither.

Pure functions: ``today`` comes in; nothing reads the clock or the disk.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any, Literal

from ..config import (
    LATE_PAYMENT_DAY,
    PAY_DAY_BEFORE_LAST_WORKING_DAY,
    PAY_DAY_LAST_WORKING_DAY,
    TRANSFER_PERSONAL_CATEGORY,
)
from ..models import AppData, IncomePlan, TxType
from . import income_calendar as ic
from . import joint, recurring
from .rolling_forecast import budget_year, calendar_active

YM = tuple[int, int]
Profile = Literal["personal", "joint"]

#: Order of items on the same day.
KIND_ORDER = {"salary": 0, "contribution": 1, "transfer": 2, "bill": 3, "goal": 4, "sinking": 5}


def _round2(v: float) -> float:
    return round(v, 2)


# -- days ------------------------------------------------------------------------------


def _weekend(d: date) -> bool:
    return d.weekday() >= 5


def pay_date(year: int, month: int, pay_day: int) -> date:
    """The day the pay arrives in ``month`` (0-11) of ``year``."""
    last = calendar.monthrange(year, month + 1)[1]
    day = last if pay_day <= PAY_DAY_LAST_WORKING_DAY else min(pay_day, last)
    d = date(year, month + 1, day)
    while _weekend(d):
        d -= timedelta(days=1)
    if pay_day == PAY_DAY_BEFORE_LAST_WORKING_DAY:  # one more working day back
        d -= timedelta(days=1)
        while _weekend(d):
            d -= timedelta(days=1)
    return d


def next_working_day(d: date) -> date:
    """The first Monday-Friday after ``d``."""
    d += timedelta(days=1)
    while _weekend(d):
        d += timedelta(days=1)
    return d


def late_pay_day(pay_day: int) -> bool:
    """A pay day at the end of the month: the last working day or the one before it
    (always the 25th or later), or a fixed day from the 25th on."""
    return pay_day <= PAY_DAY_LAST_WORKING_DAY or pay_day >= LATE_PAYMENT_DAY


def _paydays(start: date, end: date, pay_day: int) -> list[tuple[YM, date]]:
    """(month M, its pay date) from the month before ``start`` to the month after ``end``.

    The month before is included because its pay (or the transfer after it) can
    fall inside the window; the month after because an early pay day on a
    weekend moves back into the month before (1 Nov 2026 is a Sunday, so that
    pay arrives on Friday 30 Oct)."""
    out = []
    ym, last = ic.ym_add(ic.ym_of(start), -1), ic.ym_index(ic.ym_of(end)) + 1
    while ic.ym_index(ym) <= last:
        out.append((ym, pay_date(ym[0], ym[1], pay_day)))
        ym = ic.ym_add(ym, 1)
    return out


# -- amounts ---------------------------------------------------------------------------


def _booked(data: AppData, kind: TxType, category: str, ym: YM) -> float:
    """What is booked in ``category`` in month ``ym``."""
    year = data.get_year(ym[0])
    if year is None:
        return 0.0
    return _round2(sum(t.amount for t in year.transactions if t.type == kind and t.cat == category and t.month == ym[1]))


def _typed(data: AppData, kind: TxType, category: str, ym: YM) -> float | None:
    """The budget of month ``ym`` when that box was typed by hand, else None."""
    year = data.get_year(ym[0])
    if year is None or not year.budgets.is_manual(kind, category, ym[1]):
        return None
    return year.budget_for(kind, category, ym[1])


def _budget(data: AppData, kind: TxType, category: str, ym: YM) -> float:
    """The budget of month ``ym``; a year not set up borrows it like the forecast does."""
    source = budget_year(data, ym[0])
    return source[0].budget_for(kind, category, ym[1]) if source else 0.0


# -- items -----------------------------------------------------------------------------


def _item(*, key: str, day: date, kind: str, name: str, amount: float, status: str, direction: str,
          for_month: YM | None = None, paid_on: str | None = None, ref_id: int | None = None) -> dict[str, Any]:
    return {
        "key": key,
        "date": day.isoformat(),
        "kind": kind,
        "name": name,
        "amount": _round2(amount),
        "status": status,
        "done": status == "done",
        "direction": direction,
        "for_month": ic.ym_key(for_month) if for_month else None,
        "paid_on": paid_on,
        "ref_id": ref_id,
    }


def _salary(data: AppData, plan: IncomePlan, start: date, end: date) -> list[dict[str, Any]]:
    category = plan.salary_category
    next_month = late_pay_day(plan.pay_day)
    use_calendar = calendar_active(plan)
    items = []
    for month, arrives in _paydays(start, end, plan.pay_day):
        if not start <= arrives <= end:
            continue
        booked_in = ic.ym_add(month, 1) if next_month else month
        amount, status = _booked(data, "income", category, booked_in), "done"
        if amount <= 0:
            status = "expected"
            typed = _typed(data, "income", category, booked_in)
            if typed is not None:
                amount = typed
            elif use_calendar:
                amount = ic.paid_by_month(plan, plan.payslips, booked_in, 1).get(booked_in, 0.0)
            else:
                amount = _budget(data, "income", category, booked_in)
        if amount > 0:
            items.append(_item(key=f"salary/{ic.ym_key(booked_in)}", day=arrives, kind="salary", name=category,
                               amount=amount, status=status, direction="in", for_month=booked_in))
    return items


def _transfer_days(start: date, end: date, pay_day: int) -> list[tuple[YM, date]]:
    """(the month the money is for, the day) of each transfer inside the window."""
    out = []
    for month, arrives in _paydays(start, end, pay_day):
        day = next_working_day(arrives)
        if start <= day <= end:
            out.append((ic.ym_add(month, 1) if late_pay_day(pay_day) else month, day))
    return out


def _transfers(data: AppData, start: date, end: date, today: date, pay_day: int,
               shared: AppData | None) -> list[dict[str, Any]]:
    items = []
    for for_month, day in _transfer_days(start, end, pay_day):
        amount, status = _booked(data, "expense", TRANSFER_PERSONAL_CATEGORY, for_month), "done"
        if amount <= 0:
            status = "overdue" if day < today else "due"
            typed = _typed(data, "expense", TRANSFER_PERSONAL_CATEGORY, for_month)
            if typed is not None:
                amount = typed
            elif shared is not None:
                amount = joint.bill(shared, for_month, today)["a"]
            else:
                amount = _budget(data, "expense", TRANSFER_PERSONAL_CATEGORY, for_month)
        if amount > 0:
            items.append(_item(key=f"transfer/{ic.ym_key(for_month)}", day=day, kind="transfer",
                               name=TRANSFER_PERSONAL_CATEGORY, amount=amount, status=status, direction="out",
                               for_month=for_month))
    return items


def _contributions(data: AppData, start: date, end: date, today: date, pay_day: int) -> list[dict[str, Any]]:
    categories = joint.contribution_categories(data.fair_share)
    items = []
    for for_month, day in _transfer_days(start, end, pay_day):
        plan = joint.bill(data, for_month, today)
        for person in ("a", "b"):
            amount, status = _booked(data, "income", categories[person], for_month), "done"
            if amount <= 0:
                typed = _typed(data, "income", categories[person], for_month)
                amount, status = (plan[person] if typed is None else typed), "expected"
            if amount > 0:
                items.append(_item(key=f"from-{person}/{ic.ym_key(for_month)}", day=day, kind="contribution",
                                   name=categories[person], amount=amount, status=status, direction="in",
                                   for_month=for_month))
    return items


def _bills(data: AppData, start: date, end: date, today: date) -> list[dict[str, Any]]:
    items = []
    for bill in data.recurring_bills:
        for due, paid_on in recurring.bill_dates(data, bill, start, end):
            status = "done" if paid_on else ("overdue" if due < today else "due")
            items.append(_item(key=f"bill/{bill.id}/{due.isoformat()}", day=due, kind="bill", name=bill.name,
                               amount=bill.amount, status=status, direction="out", paid_on=paid_on, ref_id=bill.id))
    return items


def _goals(data: AppData, start: date, end: date, today: date) -> list[dict[str, Any]]:
    items = []
    for g in data.goals:
        deadline = date.fromisoformat(g.target_date)
        if g.status == "abandoned" or not start <= deadline <= end:
            continue
        status = "done" if g.status == "completed" else ("overdue" if deadline < today else "due")
        items.append(_item(key=f"goal/{g.id}", day=deadline, kind="sinking" if g.goal_type == "sinking" else "goal",
                           name=g.name, amount=g.target_amount, status=status, direction="goal", ref_id=g.id))
    return items


def money_dates(data: AppData, start: date, end: date, today: date, *, profile: Profile = "personal",
                pay_day: int | None = None, shared: AppData | None = None) -> dict[str, Any]:
    """The money dates of one profile from ``start`` to ``end``.

    ``pay_day``: the pay day to use; ``None`` = the one in ``data``'s income
    calendar (or the default). Joint has no income calendar, so its caller
    passes the owner's pay day from Personal. ``shared``: the Joint data, so a
    Personal transfer can show Josu's part of the Joint plan.
    """
    plan = data.income_plan or IncomePlan()
    day = plan.pay_day if pay_day is None else pay_day
    if profile == "personal":
        plan = plan.model_copy(update={"pay_day": day})
        items = _salary(data, plan, start, end) + _transfers(data, start, end, today, day, shared)
    else:
        items = _contributions(data, start, end, today, day)
    items += _bills(data, start, end, today) + _goals(data, start, end, today)
    items.sort(key=lambda i: (i["date"], KIND_ORDER[i["kind"]], i["name"]))
    return {
        "profile": profile,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "today": today.isoformat(),
        "pay_day": day,
        "items": items,
        "due_total": _round2(sum(i["amount"] for i in items if i["direction"] == "out" and not i["done"])),
        "expected_total": _round2(sum(i["amount"] for i in items if i["direction"] == "in" and not i["done"])),
    }
