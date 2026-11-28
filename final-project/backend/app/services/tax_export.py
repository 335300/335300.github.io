"""Yearly tax export: everything in tax-relevant categories, plus the commute.

- Every transaction of the year in a category marked **tax-relevant** (in
  that year's category list), with totals per category.
- The **commute estimate** (Entfernungspauschale): office days × one-way km ×
  ``COMMUTE_RATE_PER_KM`` — only when both numbers are entered.

It is a list to take to the Lohnsteuerhilfeverein, not a tax calculation.
"""

from __future__ import annotations

from typing import Any

from ..config import APP_NAME, COMMUTE_RATE_PER_KM
from ..models import AppData
from . import csv_format


def _round2(v: float) -> float:
    return round(v, 2)


def build(data: AppData, year_num: int) -> dict[str, Any]:
    year = data.get_year(year_num)
    if year is None:
        raise KeyError(year_num)
    relevant = {
        (kind, c.name)
        for kind in ("expense", "income")
        for c in getattr(year.categories, kind)
        if c.tax_relevant
    }
    rows = sorted(
        (t for t in year.transactions if (t.type, t.cat) in relevant),
        key=lambda t: (t.date, t.id),
    )
    totals: dict[tuple[str, str], float] = {}
    for t in rows:
        totals[(t.type, t.cat)] = totals.get((t.type, t.cat), 0.0) + t.amount

    commute = None
    if year.commute_days and year.commute_km:
        commute = {
            "days": year.commute_days,
            "km": year.commute_km,
            "rate": COMMUTE_RATE_PER_KM,
            "amount": _round2(year.commute_days * year.commute_km * COMMUTE_RATE_PER_KM),
        }
    expenses = _round2(sum(v for (kind, _), v in totals.items() if kind == "expense"))
    return {
        "year": year_num,
        "categories": sorted(name for _, name in relevant),
        "rows": [
            {"date": t.date, "type": t.type, "cat": t.cat, "desc": t.desc, "amount": t.amount, "one_off": t.one_off}
            for t in rows
        ],
        "totals": [
            {"type": kind, "cat": cat, "amount": _round2(v), "count": sum(1 for t in rows if (t.type, t.cat) == (kind, cat))}
            for (kind, cat), v in sorted(totals.items(), key=lambda kv: (kv[0][0], kv[0][1]))
        ],
        "expenses_total": expenses,
        "income_total": _round2(sum(v for (kind, _), v in totals.items() if kind == "income")),
        "commute": commute,
        "commute_days": year.commute_days,
        "commute_km": year.commute_km,
        "work_costs_total": _round2(expenses + (commute["amount"] if commute else 0.0)),
    }


def to_csv(view: dict[str, Any]) -> bytes:
    n = csv_format.number
    out: list[list[str]] = [
        [f"Tax export {view['year']} — {APP_NAME}"],
        ["A list for the tax return (estimate, not tax advice)."],
        [],
        ["Date", "Type", "Category", "Description", "Amount (EUR)"],
    ]
    for r in view["rows"]:
        out.append([csv_format.day(r["date"]), "Expense" if r["type"] == "expense" else "Income", r["cat"], r["desc"],
                    n(r["amount"])])
    out += [[], ["Totals by category"], ["Type", "Category", "Transactions", "Amount (EUR)"]]
    for t in view["totals"]:
        out.append(["Expense" if t["type"] == "expense" else "Income", t["cat"], str(t["count"]), n(t["amount"])])
    c = view["commute"]
    if c:
        out += [[], ["Commute (Entfernungspauschale, estimate)"],
                ["Office days", "Km one way", "EUR per km", "Amount (EUR)"],
                [str(c["days"]), n(c["km"]), n(c["rate"]), n(c["amount"])]]
    out += [[], ["Work-related costs incl. commute (EUR)", n(view["work_costs_total"])]]
    return csv_format.write(out)
