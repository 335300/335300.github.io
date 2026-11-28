"""Net worth: everything you own minus what you still owe, in euros.

- **Tracked account**: the balance the app calculates from your transactions.
- **Other accounts** (Tagesgeld, ETF depot, cash, an account in Paraguay):
  their latest value entered by hand, up to today.
- **Investment plans** (the land): an **asset** worth its market value if
  entered, otherwise its full contract price; the instalments still to pay
  are a **debt**.
- Amounts in guaraníes are converted with the latest **exchange rate** entered
  by hand (guaraníes per euro).

**Exchange cost of a payment**: a payment that also records what arrived in
the other currency (``foreign_amount``) shows the rate you really got against
the rate entered for that day — the difference in euros is what the transfer
cost (fees plus a worse rate).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..models import Account, AppData, ExchangeRate
from . import investments as investments_service
from .rolling_forecast import tracked_balance

#: Labels an investment plan may use for its currency.
CURRENCY_LABELS = {"€": "EUR", "eur": "EUR", "gs": "PYG", "gs.": "PYG", "pyg": "PYG", "₲": "PYG", "guaraní": "PYG", "guarani": "PYG"}


def _round2(v: float) -> float:
    return round(v, 2)


def currency_of(label: str) -> str | None:
    return CURRENCY_LABELS.get(label.strip().lower())


def rate_on(rates: list[ExchangeRate], currency: str, day: str | None = None) -> ExchangeRate | None:
    """The latest rate for ``currency`` on or before ``day`` (any day: the latest).
    Before the first rate, the first one is used."""
    mine = sorted((r for r in rates if r.currency == currency), key=lambda r: r.date)
    if not mine:
        return None
    if day is None:
        return mine[-1]
    before = [r for r in mine if r.date <= day]
    return before[-1] if before else mine[0]


def to_eur(amount: float, currency: str, rates: list[ExchangeRate], day: str | None = None) -> float | None:
    if currency == "EUR":
        return _round2(amount)
    rate = rate_on(rates, currency, day)
    return _round2(amount / rate.per_eur) if rate else None


def latest_value(account: Account, today: date) -> tuple[float, str] | None:
    values = sorted((v for v in account.values if v.date <= today.isoformat()), key=lambda v: v.date)
    return (values[-1].amount, values[-1].date) if values else None


def exchange_costs(data: AppData) -> dict[str, Any]:
    rows = []
    for y, year in data.years.items():
        for t in year.transactions:
            if not t.foreign_amount or not t.foreign_currency or t.foreign_currency == "EUR":
                continue
            ref = rate_on(data.exchange_rates, t.foreign_currency, t.date)
            got = t.foreign_amount / t.amount
            fair = _round2(t.foreign_amount / ref.per_eur) if ref else None
            cost = _round2(t.amount - fair) if fair is not None else None
            rows.append({
                "year": int(y), "id": t.id, "date": t.date, "desc": t.desc, "cat": t.cat,
                "eur_paid": t.amount, "foreign_amount": t.foreign_amount, "currency": t.foreign_currency,
                "rate_got": round(got, 2),
                "rate_reference": ref.per_eur if ref else None,
                "fair_eur": fair,
                "cost": cost,
                "cost_pct": _round2(cost / t.amount * 100) if cost is not None else None,
            })
    rows.sort(key=lambda r: (r["date"], r["id"]), reverse=True)
    priced = [r for r in rows if r["cost"] is not None]
    return {
        "payments": rows,
        "total_cost": _round2(sum(r["cost"] for r in priced)),
        "total_paid": _round2(sum(r["eur_paid"] for r in priced)),
    }


def build(data: AppData, today: date) -> dict[str, Any]:
    rates = data.exchange_rates
    items: list[dict[str, Any]] = []
    missing_rate: set[str] = set()

    def add(kind: str, name: str, amount_local: float, currency: str, side: str, as_of: str | None, extra=None) -> None:
        eur = to_eur(amount_local, currency, rates)
        if eur is None:
            missing_rate.add(currency)
        items.append({
            "kind": kind, "name": name, "side": side, "currency": currency,
            "amount_local": _round2(amount_local), "eur": eur, "as_of": as_of, **(extra or {}),
        })

    add("tracked", "Tracked account (from your transactions)", tracked_balance(data), "EUR", "own", None)
    for a in data.accounts:
        latest = latest_value(a, today)
        if latest is not None:
            add("account", a.name, latest[0], a.currency, "own", latest[1], {"account_id": a.id, "account_kind": a.kind})

    year = today.year if data.get_year(today.year) else (max(data.year_numbers()) if data.years else today.year)
    for plan in data.investments:
        view = investments_service.build(plan, data, year, 0, today)
        currency = currency_of(plan.local_currency)
        if currency is None:
            missing_rate.add(plan.local_currency)
            continue
        value = plan.market_value_local or view["total_local"]
        basis = "market value" if plan.market_value_local else "full contract price"
        add("asset", plan.name, value, currency, "own", None, {"plan_id": plan.id, "basis": basis})
        if view["remaining_local"] > 0:
            add("debt", f"{plan.name}: {view['remaining']} {plan.unit}s still to pay", view["remaining_local"], currency,
                "owe", None, {"plan_id": plan.id})

    def total(side: str) -> float:
        return _round2(sum(i["eur"] for i in items if i["side"] == side and i["eur"] is not None))

    own, owe = total("own"), total("owe")
    in_pyg = _round2(sum((i["eur"] or 0.0) * (1 if i["side"] == "own" else -1) for i in items if i["currency"] == "PYG"))
    rate = rate_on(rates, "PYG")
    net = _round2(own - owe)
    return {
        "items": items,
        "own": own,
        "owe": owe,
        "net_worth": net,
        "in_pyg": in_pyg,
        "in_pyg_pct": _round2(in_pyg / net * 100) if net else None,
        "rate": rate.model_dump() if rate else None,
        "rates": [r.model_dump() for r in sorted(rates, key=lambda r: r.date, reverse=True)],
        "missing_rate": sorted(missing_rate),
        "accounts": [
            {**a.model_dump(), "values": sorted((v.model_dump() for v in a.values), key=lambda v: v["date"])}
            for a in data.accounts
        ],
        "exchange": exchange_costs(data),
    }
