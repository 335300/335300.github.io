"""The Overview's KPI tiles next to a usual month, in euros.

For each tile (balance, cash in, cash out, kept, wealth built) this returns
how far the month shown is from a **usual** month:

- **usual** = the median (middle value) of the same figure over the recorded
  months *before* the one shown (``cashflow.baseline_months``: up to 6, across
  the year end). Months after it never count.
- Money flows (cash in, cash out, kept, wealth built) leave **one-off**
  transactions out, in the earlier months *and* in the month shown — the same
  rule as the "vs usual" % of the cost history. ``current`` is still the full
  tile figure; ``one_off`` is the part of it tagged one-off, and
  ``current_regular`` = ``current`` − ``one_off`` is what is compared.
- The balance has no one-offs: it is the month-end balance, compared with the
  median of the earlier month-ends.
- ``diff`` = ``current_regular`` − ``usual`` (positive: more than usual);
  ``pct`` = ``diff`` ÷ ``usual`` × 100 (``None`` when usual is 0).
- ``direction``: ``"same"`` while |diff| is less than
  max(``SAME_AS_USUAL_EUR``, ``SAME_AS_USUAL_PCT`` % of |usual|), otherwise
  ``"up"`` or ``"down"``. Whether up is good news depends on the tile (more
  cash out is not), so the screen picks the colour.

Everything is ``None`` when there is no earlier month to compare with — and
also when none of the earlier months holds a transaction that is not one-off
(``months_with_data`` = 0, e.g. a fresh profile): empty months are no usual month.
"""

from __future__ import annotations

from statistics import median
from typing import Any

from ..config import SAME_AS_USUAL_EUR, SAME_AS_USUAL_PCT
from ..models import AppData
from .aggregation import balance_through, kind_totals
from .cashflow import baseline_months, months_with_data


def _round2(v: float) -> float:
    return round(v + 0.0, 2)


def direction(diff: float | None, usual: float | None) -> str | None:
    """'up' / 'down' / 'same' (about the same as usual), ``None`` without a usual."""
    if diff is None or usual is None:
        return None
    if abs(diff) < max(SAME_AS_USUAL_EUR, abs(usual) * SAME_AS_USUAL_PCT / 100):
        return "same"
    return "up" if diff > 0 else "down"


def _income(data: AppData, y: int, m: int, skip_one_off: bool) -> float:
    year = data.get_year(y)
    return _round2(sum(
        t.amount for t in year.transactions
        if t.type == "income" and t.month == m and not (skip_one_off and t.one_off)
    ))


def month_figures(data: AppData, y: int, m: int, skip_one_off: bool) -> dict[str, float]:
    """One month's tile figures (``skip_one_off``: without one-off transactions)."""
    year = data.get_year(y)
    income = _income(data, y, m, skip_one_off)
    kinds = kind_totals(year, m, skip_one_off=skip_one_off)
    costs = kinds["fixed"] + kinds["variable"]
    cash_out = costs + kinds["investment"]
    return {
        "balance": balance_through(year, m),
        "cash_in": income,
        "cash_out": _round2(cash_out),
        "kept": _round2(income - cash_out),
        "wealth_built": _round2(income - costs),
    }


def vs_usual(data: AppData, year_num: int, month: int) -> dict[str, Any]:
    """``{tile: {current, current_regular, one_off, usual, diff, pct, direction}}``
    plus ``months`` (how many earlier months the usual is built from),
    ``months_with_data`` (how many of them hold a non-one-off transaction) and the
    "about the same" rule (``same_within``)."""
    months = baseline_months(data, year_num, month)
    with_data = months_with_data(data, months)
    full = month_figures(data, year_num, month, skip_one_off=False)
    regular = month_figures(data, year_num, month, skip_one_off=True)
    regular["balance"] = full["balance"]
    # Earlier months that are all empty give no usual month (not a usual of 0).
    earlier = [month_figures(data, y, m, skip_one_off=True) for y, m in months] if with_data else []

    out: dict[str, Any] = {
        "months": len(months),
        "months_with_data": with_data,
        "same_within": {"eur": SAME_AS_USUAL_EUR, "pct": SAME_AS_USUAL_PCT},
    }
    for key in ("balance", "cash_in", "cash_out", "kept", "wealth_built"):
        usual = _round2(median(e[key] for e in earlier)) if earlier else None
        diff = _round2(regular[key] - usual) if usual is not None else None
        out[key] = {
            "current": full[key],
            "current_regular": regular[key],
            "one_off": _round2(full[key] - regular[key]),
            "usual": usual,
            "diff": diff,
            "pct": _round2(diff / usual * 100) if usual else None,
            "direction": direction(diff, usual),
        }
    return out
