"""Forecast ranges: how far the real balance may drift from the forecast.

A simple model — "the spread of your past months, growing with time":

1. **Most likely** balance = the forecast's own line (Personal: the first line
   of :mod:`rolling_forecast`; Joint: the shared pot of
   :func:`joint.bill_forecast`). This module never changes those numbers.
2. **How much a month usually wobbles** = ``sigma``, the sample standard
   deviation of the monthly *kept* amount (cash in − cash out) over the
   finished months: up to ``RANGE_HISTORY_MONTHS``, never the month still in
   progress, transactions tagged one-off left out (like every "usual" figure).
   With fewer than ``RANGE_MIN_HISTORY_MONTHS`` months there are no ranges.
3. Wobbles add up, so the band grows with the square root of the months
   ahead: half-width = z × sigma × √h, with z = ``RANGE_Z50`` for the band that
   holds half of the likely futures and ``RANGE_Z80`` for eight in ten.

From the bands come the sentences on screen: ``floor_80`` (the lowest 80 %
low across the horizon, rounded *down* to a round figure — "In 8 of 10 likely
futures you stay above …") and ``likely_end_about`` ("Most likely balance in
May: about …"). ``first_6`` gives the same for the Overview's 6-month card.

Everything is computed unrounded and rounded to cents only in the output.
"""

from __future__ import annotations

import math
from datetime import date
from statistics import stdev
from typing import Any

from ..config import (
    MONTHS,
    OVERVIEW_FORECAST_MONTHS,
    RANGE_ABOUT_STEP,
    RANGE_FLOOR_BIG_STEP,
    RANGE_FLOOR_SMALL_STEP,
    RANGE_FLOOR_SWITCH,
    RANGE_HISTORY_MONTHS,
    RANGE_MIN_HISTORY_MONTHS,
    RANGE_Z50,
    RANGE_Z80,
)
from ..models import AppData
from . import income_calendar as ic
from . import rolling_forecast
from .cashflow import months_back

YM = tuple[int, int]


def _round2(v: float) -> float:
    return round(v, 2)


# ---------------------------------------------------------------------------
# Small pieces
# ---------------------------------------------------------------------------

def sample_sigma(values: list[float]) -> float:
    """Sample standard deviation (divides by n − 1). Needs at least 2 values."""
    return float(stdev(values))


def nice_floor(value: float) -> float:
    """Round *down* to a round figure: to 100 € below 5 000 €, to 500 € from there."""
    step = RANGE_FLOOR_SMALL_STEP if value < RANGE_FLOOR_SWITCH else RANGE_FLOOR_BIG_STEP
    return float(math.floor(value / step) * step)


def about(value: float) -> float:
    """Round to the nearest 50 € (halves go up) — for "about 4 050 €"."""
    return float(math.floor(value / RANGE_ABOUT_STEP + 0.5) * RANGE_ABOUT_STEP)


def _month_kept(data: AppData, ym: YM) -> float:
    """Cash in − cash out of one month, one-off transactions left out."""
    year = data.get_year(ym[0])
    if year is None:
        return 0.0
    total = 0.0
    for t in year.transactions:
        if t.month == ym[1] and not t.one_off:
            total += t.amount if t.type == "income" else -t.amount
    return _round2(total)


def kept_history(data: AppData, today: date, limit: int = RANGE_HISTORY_MONTHS) -> list[float]:
    """The kept amount of each finished month, oldest first (at most ``limit``).

    Finished = recorded and before today's month, so the month in progress
    never counts. Months walk back across year ends like the "usual" figures
    (:func:`cashflow.months_back`); a tracked month with nothing recorded counts 0.
    """
    last = rolling_forecast.last_recorded(data)
    if last is None:
        return []
    end = min(last, ic.ym_add(ic.ym_of(today), -1), key=ic.ym_index)
    return [_month_kept(data, ym) for ym in months_back(data, end[0], end[1], limit, include_selected=False)]


# ---------------------------------------------------------------------------
# The bands
# ---------------------------------------------------------------------------

def _summary(rows: list[dict[str, Any]], low80: list[float]) -> dict[str, Any]:
    end = rows[-1]
    ym = (end["year"], end["month"])
    return {
        "floor_80": nice_floor(min(low80)),
        "horizon_end_name": ic.ym_name(ym),
        "horizon_end_month": MONTHS[ym[1]],
        "likely_end": _round2(end["balance"]),
        "likely_end_about": about(end["balance"]),
    }


def build(likely: list[dict[str, Any]], kept: list[float]) -> dict[str, Any] | None:
    """The 50 % and 80 % bands around ``likely``.

    ``likely``: the forecast months in order, each ``{year, month, balance}``
    (month 0–11); the first is one month ahead of the last known balance.
    ``kept``: the history from :func:`kept_history`.
    ``None`` when there is no forecast month or too little history.
    """
    if not likely or len(kept) < RANGE_MIN_HISTORY_MONTHS:
        return None
    sigma = sample_sigma(kept)
    months: list[dict[str, Any]] = []
    low80: list[float] = []
    for h, row in enumerate(likely, start=1):
        ym = (row["year"], row["month"])
        mid = row["balance"]
        half50 = RANGE_Z50 * sigma * math.sqrt(h)
        half80 = RANGE_Z80 * sigma * math.sqrt(h)
        low80.append(mid - half80)
        months.append({
            "key": ic.ym_key(ym),
            "month_name": ic.ym_name(ym),
            "months_ahead": h,
            "likely": _round2(mid),
            "low50": _round2(mid - half50),
            "high50": _round2(mid + half50),
            "low80": _round2(mid - half80),
            "high80": _round2(mid + half80),
        })
    n = min(OVERVIEW_FORECAST_MONTHS, len(likely))
    return {
        "months": months,
        "sigma": _round2(sigma),
        "history_months": len(kept),
        **_summary(likely, low80),
        "first_6": _summary(likely[:n], low80[:n]),
    }


# ---------------------------------------------------------------------------
# Glue for the two forecasts
# ---------------------------------------------------------------------------

def for_rolling(forecast: dict[str, Any], data: AppData, today: date) -> dict[str, Any] | None:
    """Ranges for the Personal rolling forecast (the output of
    :func:`rolling_forecast.build`), around its first line ("Plan", or the
    first graduation scenario). ``line_key`` says which line."""
    if not forecast.get("lines"):
        return None
    key = forecast["lines"][0]["key"]
    likely = [
        {"year": r["year"], "month": r["month"], "balance": r["values"][key]["balance"]}
        for r in forecast["rows"] if not r["actual"]
    ]
    result = build(likely, kept_history(data, today))
    return {**result, "line_key": key} if result else None


def for_joint(bill: dict[str, Any], data: AppData, today: date) -> dict[str, Any] | None:
    """Ranges for the Joint Forecast (the output of :func:`joint.bill_forecast`),
    around the shared pot. ``data`` is the Joint profile."""
    likely = [{"year": r["year"], "month": r["month"], "balance": r["pot"]} for r in bill.get("rows", [])]
    result = build(likely, kept_history(data, today))
    return {**result, "line_key": None} if result else None
