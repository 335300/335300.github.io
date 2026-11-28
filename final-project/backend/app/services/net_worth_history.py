"""Net worth over the last 12 months, month-end by month-end.

Each **point** is one month-end: ``own`` (the bar), ``owe`` and ``net_worth``
(the number on top), with the lines it is made of (``items``).

Where a month's figures come from (``source``):

- ``live``     — the month running now: exactly what the Net worth page shows
  (:func:`net_worth.build` for ``today``).
- ``snapshot`` — a past month for which the app kept a snapshot (written
  every time net worth was worked out while that month ran, see
  :func:`upsert_snapshot`). The accounts, the land and its debt are taken
  from the snapshot, as they were known then. The tracked account is always
  recalculated from the transactions, because statements are usually imported
  after the month ends.
- ``rebuilt``  — a past month without a snapshot, worked out from what is
  stored: the tracked account from its transactions; each account kept by
  hand at its latest value on or before the month-end; the land at its
  market value (or contract price) and its debt from the instalments paid
  up to the month-end; guaraníes at the rate entered on or before that day.

A point is ``estimated`` when part of it had to be assumed; the reasons are
listed in ``estimated_reasons``:

- ``carried_back``      — an account had no value yet at that month-end, so
  its earliest value was used (it may not have existed yet: check this).
- ``rate``              — no exchange rate on or before that day, so the first
  one entered was used.
- ``plan_before_added`` — the month is before the land plan was added; the
  instalments "paid before" are counted as already paid.
- ``land_value``        — the land's market value is only known for today.
- ``not_recorded``      — a past month with no transactions recorded yet (the
  tracked account then shows the last recorded balance).

The chart never goes back past the month-end before tracking started: before
that the tracked account's balance is unknown, so fewer months are returned
instead of invented ones.

**Split of the change** (``change``), from ``start`` to the last point:

- ``start`` is the month-end before the first bar (so 12 bars = 12 months of
  change), or the first bar when there is no earlier month-end.
- ``total``  = net worth at the end − at the start.
- ``saved``  = the sum of **wealth built** (cash in − costs, so money put into
  investments counts as saved) over the months after ``start`` up to the end.
- ``growth`` = ``total`` − ``saved``: everything that did not come from what
  was saved — accounts kept by hand earning or losing value, the land's value,
  exchange-rate moves, a payment that bought less debt than it cost, and
  money that moved without being recorded.
- ``saved_share_pct`` = saved ÷ total × 100 (only when the total went up);
  ``saved_of_10`` = that share in tenths, rounded half up ("about 9 of every
  10 euros"), only when 0 ≤ saved ≤ total.
"""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any

from ..config import MONTHS_SHORT, NET_WORTH_HISTORY_MONTHS
from ..models import AppData, NetWorthSnapshot
from . import net_worth
from .aggregation import balance_through, closing_balance, kind_totals, month_total
from .rolling_forecast import last_recorded

YM = tuple[int, int]


def _round2(v: float) -> float:
    return round(v + 0.0, 2)


def _index(ym: YM) -> int:
    return ym[0] * 12 + ym[1]


def _from_index(i: int) -> YM:
    return i // 12, i % 12


def _month_end(ym: YM) -> date:
    return date(ym[0], ym[1] + 1, calendar.monthrange(ym[0], ym[1] + 1)[1])


def _key(ym: YM) -> str:
    return f"{ym[0]}-{ym[1] + 1:02d}"


def tracked_at(data: AppData, ym: YM) -> float | None:
    """The tracked account's balance at the close of month ``ym``; ``None`` when
    it is not known (before tracking started, or a year that is missing)."""
    years = data.year_numbers()
    if not years:
        return None
    y, m = ym
    year = data.get_year(y)
    if year is not None:
        if m > year.start_month:
            return balance_through(year, m)
        if m == year.start_month:
            return _round2(year.opening_balance)
        return None
    following = data.get_year(y + 1)
    if following is not None and m == 11 and following.start_month == -1:
        return _round2(following.opening_balance)
    if y > years[-1]:
        return closing_balance(data.years[str(years[-1])])
    return None


def wealth_built(data: AppData, ym: YM) -> float:
    """Cash in − costs (fixed + variable) of one month; 0 when it is not tracked."""
    year = data.get_year(ym[0])
    if year is None or ym[1] <= year.start_month:
        return 0.0
    kinds = kind_totals(year, ym[1])
    return _round2(month_total(year, ym[1], "income") - kinds["fixed"] - kinds["variable"])


def _eur(amount: float, currency: str, data: AppData, day: str, reasons: set[str]) -> float | None:
    if currency == "EUR":
        return _round2(amount)
    rate = net_worth.rate_on(data.exchange_rates, currency, day)
    if rate is None:
        return None
    if rate.date > day:
        reasons.add("rate")
    return _round2(amount / rate.per_eur)


def _rebuilt_items(data: AppData, day: str, reasons: set[str]) -> list[dict[str, Any]]:
    """Accounts kept by hand and the land, as known at ``day`` (no tracked account)."""
    items: list[dict[str, Any]] = []
    for a in data.accounts:
        values = sorted(a.values, key=lambda v: v.date)
        if not values:
            continue
        before = [v for v in values if v.date <= day]
        value = before[-1] if before else values[0]
        if not before:
            reasons.add("carried_back")
        items.append({"kind": "account", "name": a.name, "side": "own", "account_id": a.id,
                      "eur": _eur(value.amount, a.currency, data, day, reasons)})
    for plan in data.investments:
        currency = net_worth.currency_of(plan.local_currency)
        if currency is None:
            continue  # like the Net worth page: an unknown currency cannot be valued
        if day < plan.created_date:
            reasons.add("plan_before_added")
        if plan.market_value_local:
            reasons.add("land_value")
        counted = sum(
            t.installments or 0
            for year in data.years.values() for t in year.transactions
            if t.type == "expense" and t.cat == plan.category and t.date <= day
        )
        remaining = plan.total_installments - min(plan.total_installments, plan.paid_before + counted)
        value = plan.market_value_local or plan.total_installments * plan.installment_amount
        items.append({"kind": "asset", "name": plan.name, "side": "own", "plan_id": plan.id,
                      "eur": _eur(value, currency, data, day, reasons)})
        if remaining > 0:
            items.append({"kind": "debt", "name": plan.name, "side": "owe", "plan_id": plan.id,
                          "eur": _eur(remaining * plan.installment_amount, currency, data, day, reasons)})
    return items


def _total(items: list[dict[str, Any]], side: str) -> float:
    return _round2(sum(i["eur"] for i in items if i["side"] == side and i["eur"] is not None))


def _slim(item: dict[str, Any]) -> dict[str, Any]:
    return {"kind": item["kind"], "name": item["name"], "side": item["side"], "eur": item["eur"],
            "account_id": item.get("account_id"), "plan_id": item.get("plan_id")}


def snapshot(data: AppData, today: date) -> dict[str, Any]:
    """This month's snapshot: what the Net worth page shows today."""
    live = net_worth.build(data, today)
    return {
        "month": _key((today.year, today.month - 1)),
        "taken": today.isoformat(),
        "own": live["own"],
        "owe": live["owe"],
        "net_worth": live["net_worth"],
        "items": [_slim(i) for i in live["items"]],
    }


def upsert_snapshot(data: AppData, today: date) -> bool:
    """Keep this month's snapshot current in ``data``. True if it changed
    (then the caller saves); unchanged figures are not rewritten. Before the
    first year is set up nothing is kept (a fresh install writes no file)."""
    if not data.years:
        return False
    new = NetWorthSnapshot(**snapshot(data, today))
    old = next((s for s in data.net_worth_snapshots if s.month == new.month), None)
    if old is not None and old.model_dump(exclude={"taken"}) == new.model_dump(exclude={"taken"}):
        return False
    data.net_worth_snapshots = sorted(
        [s for s in data.net_worth_snapshots if s.month != new.month] + [new], key=lambda s: s.month
    )
    return True


def _point(data: AppData, ym: YM, today: date, last: YM | None) -> dict[str, Any] | None:
    tracked = tracked_at(data, ym)
    current = ym == (today.year, today.month - 1)
    if tracked is None and not current:
        return None
    reasons: set[str] = set()
    if current:
        live = net_worth.build(data, today)
        items, source = [_slim(i) for i in live["items"]], "live"
    else:
        if last is None or _index(ym) > _index(last):
            reasons.add("not_recorded")
        tracked_item = {"kind": "tracked", "name": "Tracked account (from your transactions)", "side": "own",
                        "eur": tracked, "account_id": None, "plan_id": None}
        snap = next((s for s in data.net_worth_snapshots if s.month == _key(ym)), None)
        if snap is not None:
            others = [i.model_dump() for i in snap.items if i.kind != "tracked"]
            source = "snapshot"
        else:
            others = [_slim(i) for i in _rebuilt_items(data, _month_end(ym).isoformat(), reasons)]
            source = "rebuilt"
        items = [tracked_item, *others]
    own, owe = _total(items, "own"), _total(items, "owe")
    return {
        "month": _key(ym),
        "year": ym[0],
        "month_index": ym[1],
        "label": f"{MONTHS_SHORT[ym[1]]} {str(ym[0])[2:]}",
        "own": own,
        "owe": owe,
        "net_worth": _round2(own - owe),
        "estimated": bool(reasons),
        "estimated_reasons": sorted(reasons),
        "source": source,
        "items": items,
    }


def history(data: AppData, today: date, months: int = NET_WORTH_HISTORY_MONTHS) -> dict[str, Any]:
    """Up to ``months`` month-end points ending with the current month, the
    month-end before them (``start``) and the split of the change."""
    if not data.years:
        return {"points": [], "start": None, "change": None, "vs_previous_month": None}
    last = last_recorded(data)
    now = _index((today.year, today.month - 1))
    found: list[dict[str, Any]] = []
    for i in range(now, now - months - 1, -1):
        point = _point(data, _from_index(i), today, last)
        if point is None:
            break
        found.append(point)
    found.reverse()
    if not found:
        return {"points": [], "start": None, "change": None, "vs_previous_month": None}

    bars = found[-months:]
    start = found[0]
    window = found[1:]
    end = found[-1]
    change = None
    if window:
        total = _round2(end["net_worth"] - start["net_worth"])
        saved = _round2(sum(wealth_built(data, (p["year"], p["month_index"])) for p in window))
        share = saved / total if total > 0 else None
        change = {
            "from": start["month"],
            "to": end["month"],
            "months": len(window),
            "total": total,
            "saved": saved,
            "growth": _round2(total - saved),
            "saved_share_pct": _round2(share * 100) if share is not None else None,
            "saved_of_10": int(share * 10 + 0.5) if share is not None and 0 <= share <= 1 else None,
            "estimated": any(p["estimated"] for p in found),
        }
    return {
        "points": bars,
        "start": start,
        "change": change,
        "vs_previous_month": _round2(end["net_worth"] - found[-2]["net_worth"]) if len(found) > 1 else None,
    }
