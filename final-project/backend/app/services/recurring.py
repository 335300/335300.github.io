"""Recurring bills: what comes back, when it is due next, and is the money ready.

A bill has an amount, a rhythm (every 1, 3, 6 or 12 months), a due date and a
``match`` text that identifies its payments (in the payee or description;
empty = any payment in its category).

- **Paid bills move on by themselves** (:func:`current_due`): starting from the
  stored due date, every due date with a matching payment within
  ``BILL_MATCH_DAYS`` days (amount within ``BILL_AMOUNT_TOLERANCE``) counts as
  paid, and the next one is due. Due dates are counted from the stored date
  (n × rhythm), so the 31st does not drift to the 28th for good. **One payment
  pays at most one bill**: when it fits two (same category, similar amounts),
  the best fit gets it (:func:`_walk_all`).
- **Upcoming** (:func:`upcoming`): unpaid due dates up to ``UPCOMING_DAYS``
  ahead (and any overdue one), each with a "money ready" verdict:
  a bill linked to a sinking fund is ready when the fund holds enough; any
  other bill when today's liquidity covers it plus the unlinked bills due
  before it.
- **Month calendar** (:func:`month_calendar`): the bills (paid and unpaid)
  and goal deadlines of one month, for the Overview calendar.
- **Detection** (:func:`suggestions`): the same payee at least
  ``BILL_MIN_PAYMENTS`` times, amounts within the tolerance of their median,
  and gaps that fit one rhythm (``BILL_RHYTHMS``).
"""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from statistics import median
from typing import Any

from ..config import (
    BILL_AMOUNT_TOLERANCE,
    BILL_MATCH_DAYS,
    BILL_MIN_PAYMENTS,
    BILL_RHYTHMS,
    UPCOMING_DAYS,
)
from ..models import AppData, RecurringBill, Transaction
from . import cashflow, rolling_forecast
from .dates import add_months
from .payee_rules import normalise, suggested_text

RHYTHM_WORD = {1: "monthly", 3: "every 3 months", 6: "every semester", 12: "yearly"}


def _round2(v: float) -> float:
    return round(v, 2)


def _expenses(data: AppData) -> list[Transaction]:
    return [t for year in data.years.values() for t in year.transactions if t.type == "expense"]


def matches(bill: RecurringBill, t: Transaction) -> bool:
    if t.type != "expense" or abs(t.amount - bill.amount) > bill.amount * BILL_AMOUNT_TOLERANCE + 1e-9:
        return False
    needle = normalise(bill.match)
    if needle:
        return needle in normalise(f"{t.payee} {t.desc}")
    return t.cat == bill.category


#: A walk stops after this many paid due dates (50 years of monthly bills).
_MAX_DUE_DATES = 600


def _walk_all(data: AppData, bills: list[RecurringBill]) -> dict[int, tuple[list[tuple[date, str]], date]]:
    """Walk all ``bills`` together, so that **one payment pays at most one bill**.

    One booking at a time: every bill still walking looks for the best unused
    payment for its next due date (it must :func:`match` and lie within
    ``BILL_MATCH_DAYS``); only the best fit of all bills is booked, then all
    bills look again. Best fit: a bill with
    its own match text before one matched by category, then the closest amount,
    then the closest date (then the earlier payment, the lower bill id). A bill
    with no payment left for its next due date stops: that is its next unpaid
    due date. Returns ``{bill id: ([(paid due date, payment date), …], next unpaid due date)}``.
    """
    expenses = _expenses(data)
    walks = {
        b.id: {
            "bill": b,
            "anchor": date.fromisoformat(b.next_due),
            "specific": 0 if normalise(b.match) else 1,
            "payments": [t for t in expenses if matches(b, t)],
            "paid": [],
            "walking": True,
        }
        for b in bills
    }
    used: set[int] = set()  # id() of the payments already booked to a bill
    while True:
        best = None
        for w in walks.values():
            if not w["walking"]:
                continue
            bill: RecurringBill = w["bill"]
            if len(w["paid"]) >= _MAX_DUE_DATES:  # pragma: no cover
                w["walking"] = False
                continue
            due = add_months(w["anchor"], len(w["paid"]) * bill.rhythm_months)
            pick = None
            for t in w["payments"]:
                days = abs((date.fromisoformat(t.date) - due).days)
                if id(t) in used or days > BILL_MATCH_DAYS:
                    continue
                score = (w["specific"], round(abs(t.amount - bill.amount), 2), days, t.date, bill.id)
                if pick is None or score < pick[0]:
                    pick = (score, t, due)
            if pick is None:
                w["walking"] = False  # payments only get fewer, so it stays stopped
            elif best is None or pick[0] < best[0]:
                best = (pick[0], w, pick[1], pick[2])
        if best is None:
            break
        _, w, payment, due = best
        used.add(id(payment))
        w["paid"].append((due, payment.date))
    return {
        bill_id: (w["paid"], add_months(w["anchor"], len(w["paid"]) * w["bill"].rhythm_months))
        for bill_id, w in walks.items()
    }


def _walk(data: AppData, bill: RecurringBill) -> tuple[list[tuple[date, str]], date]:
    """([(paid due date, payment date), …], the next unpaid due date) of one bill.

    The bill competes with the other saved bills for payments (see
    :func:`_walk_all`); a ``bill`` with the id of a saved one stands in for it.
    """
    others = [b for b in data.recurring_bills if b.id != bill.id]
    return _walk_all(data, [*others, bill])[bill.id]


def current_due(data: AppData, bill: RecurringBill) -> tuple[date, str | None]:
    """(the next unpaid due date, the date of the last payment found)."""
    paid_dates, due = _walk(data, bill)
    return due, (paid_dates[-1][1] if paid_dates else None)


def bill_dates(data: AppData, bill: RecurringBill, start: date, end: date) -> list[tuple[date, str | None]]:
    """Every due date of ``bill`` from ``start`` to ``end`` (both included).

    Each is ``(due date, payment date)``; the payment date is ``None`` while
    unpaid. Due dates are counted from the stored date (n × rhythm), like
    :func:`_walk`, so a bill on the 31st does not drift to the 28th.
    """
    anchor = date.fromisoformat(bill.next_due)
    paid_dates, _ = _walk(data, bill)
    out: list[tuple[date, str | None]] = [(due, paid_on) for due, paid_on in paid_dates if start <= due <= end]
    n = len(paid_dates)
    while True:
        due = add_months(anchor, n * bill.rhythm_months)
        if due > end:
            return out
        if due >= start:
            out.append((due, None))
        n += 1


def current_liquidity(data: AppData, today: date) -> float:
    """Balance at the close of the last recorded month, minus goal money up to today."""
    return _round2(rolling_forecast.tracked_balance(data) - cashflow.earmarked(data.goals, today))


def bill_view(data: AppData, bill: RecurringBill) -> dict[str, Any]:
    due, last_paid = current_due(data, bill)
    goal = data.find_goal(bill.goal_id) if bill.goal_id is not None else None
    return {
        **bill.model_dump(),
        "rhythm_word": RHYTHM_WORD[bill.rhythm_months],
        "due": due.isoformat(),
        "last_paid": last_paid,
        "goal_name": goal.name if goal else None,
        "monthly_cost": _round2(bill.amount / bill.rhythm_months),
    }


def _due_items(data: AppData, today: date, until: date, verdict_until: date) -> list[dict[str, Any]]:
    """Every unpaid due date up to ``until`` (overdue ones too), in date order.

    Due dates up to ``verdict_until`` get a "money ready" verdict; later ones
    have ``ready = None`` (too far ahead to judge on today's money).
    """
    items: list[dict[str, Any]] = []
    for bill in data.recurring_bills:
        due, _ = current_due(data, bill)
        k = 0
        while True:
            when = add_months(due, k * bill.rhythm_months)
            if when > until:
                break
            items.append({"bill": bill, "due": when})
            k += 1

    items.sort(key=lambda i: (i["due"], i["bill"].name))
    liquidity = current_liquidity(data, today)
    fund_left = {g.id: g.saved() for g in data.goals if g.status == "active"}
    free_needed = 0.0
    out = []
    for item in items:
        bill: RecurringBill = item["bill"]
        due: date = item["due"]
        goal = data.find_goal(bill.goal_id) if bill.goal_id is not None else None
        ready: bool | None = None
        short = 0.0
        if goal is not None and goal.id in fund_left:
            source = "fund"
            if due <= verdict_until:
                ready = fund_left[goal.id] >= bill.amount
                short = _round2(max(0.0, bill.amount - fund_left[goal.id]))
                fund_left[goal.id] = _round2(fund_left[goal.id] - bill.amount)
        else:
            source = "liquidity"
            if due <= verdict_until:
                free_needed = _round2(free_needed + bill.amount)
                ready = liquidity >= free_needed
                short = _round2(max(0.0, min(bill.amount, free_needed - liquidity)))
        out.append({
            "bill_id": bill.id,
            "name": bill.name,
            "amount": bill.amount,
            "category": bill.category,
            "due": due.isoformat(),
            "days_left": (due - today).days,
            "overdue": due < today,
            "source": source,
            "goal_name": goal.name if goal else None,
            "ready": ready,
            "short_by": short,
        })
    return out


def upcoming(data: AppData, today: date, days: int = UPCOMING_DAYS) -> dict[str, Any]:
    until = today + timedelta(days=days)
    out = _due_items(data, today, until, until)
    return {
        "items": out,
        "days": days,
        "total": _round2(sum(i["amount"] for i in out)),
        "liquidity": current_liquidity(data, today),
        "all_ready": all(i["ready"] for i in out),
    }


def month_calendar(data: AppData, year: int, month: int, today: date) -> dict[str, Any]:
    """One month of the Overview calendar (``month`` is 0-11).

    - **bills**: due dates in the month — paid ones (with the payment date) and
      unpaid ones (overdue ones on their own date). Unpaid bills up to
      ``UPCOMING_DAYS`` ahead carry the "money ready" verdict of :func:`upcoming`.
    - **goals**: goal deadlines (``target_date``) in the month.
    - **total_due**: what is still unpaid in the month.
    """
    first = date(year, month + 1, 1)
    last = add_months(first, 1) - timedelta(days=1)
    in_month = lambda d: first <= d <= last  # noqa: E731
    bills: list[dict[str, Any]] = []
    for bill in data.recurring_bills:
        for due, paid_on in _walk(data, bill)[0]:
            if in_month(due):
                bills.append({
                    "bill_id": bill.id, "name": bill.name, "amount": bill.amount, "category": bill.category,
                    "due": due.isoformat(), "paid": True, "paid_on": paid_on,
                    "overdue": False, "ready": True, "short_by": 0.0, "goal_name": None, "source": None,
                })
    verdict_until = today + timedelta(days=UPCOMING_DAYS)
    unpaid = [i for i in _due_items(data, today, last, verdict_until) if in_month(date.fromisoformat(i["due"]))]
    bills += [{**i, "paid": False, "paid_on": None} for i in unpaid]
    bills.sort(key=lambda b: (b["due"], b["name"]))
    goals = sorted(
        ({"goal_id": g.id, "name": g.name, "date": g.target_date, "status": g.status,
          "target_amount": g.target_amount}
         for g in data.goals if in_month(date.fromisoformat(g.target_date)) and g.status != "abandoned"),
        key=lambda g: (g["date"], g["name"]),
    )
    return {
        "year": year,
        "month": month,
        "today": today.isoformat(),
        "bills": bills,
        "goals": goals,
        "total_due": _round2(sum(b["amount"] for b in bills if not b["paid"])),
        "total_paid": _round2(sum(b["amount"] for b in bills if b["paid"])),
    }


def _key(t: Transaction) -> str:
    return suggested_text(t.payee or t.desc)


def suggestions(data: AppData, today: date) -> list[dict[str, Any]]:
    groups: dict[str, list[Transaction]] = {}
    for t in _expenses(data):
        key = _key(t)
        if key:
            groups.setdefault(key, []).append(t)

    dismissed = {normalise(d) for d in data.dismissed_bill_suggestions}
    out = []
    for key, txs in groups.items():
        if key in dismissed or len(txs) < BILL_MIN_PAYMENTS:
            continue
        typical = median(t.amount for t in txs)
        similar = sorted(
            (t for t in txs if abs(t.amount - typical) <= typical * BILL_AMOUNT_TOLERANCE + 1e-9),
            key=lambda t: t.date,
        )
        if len(similar) < BILL_MIN_PAYMENTS:
            continue
        dates = [date.fromisoformat(t.date) for t in similar]
        gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
        gap = median(gaps)
        rhythm = next((m for m, (lo, hi) in BILL_RHYTHMS.items() if lo <= gap <= hi), None)
        if rhythm is None:
            continue
        lo, hi = BILL_RHYTHMS[rhythm]
        if sum(lo <= g <= hi for g in gaps) * 3 < len(gaps) * 2:  # at least two thirds fit
            continue
        if (today - dates[-1]).days > 2 * hi:  # stopped long ago
            continue
        amount = _round2(median(t.amount for t in similar))
        if any(normalise(b.match) == key or matches(b, similar[-1]) for b in data.recurring_bills):
            continue
        category = Counter(t.cat for t in similar).most_common(1)[0][0]
        out.append({
            "key": key,
            "name": similar[-1].payee or similar[-1].desc,
            "amount": amount,
            "category": category,
            "rhythm_months": rhythm,
            "rhythm_word": RHYTHM_WORD[rhythm],
            "next_due": add_months(dates[-1], rhythm).isoformat(),
            "match": key,
            "payments": len(similar),
        })
    return sorted(out, key=lambda s: s["next_due"])
