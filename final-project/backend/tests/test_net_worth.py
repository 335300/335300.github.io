"""Net worth with EUR/PYG: accounts, the land as asset and debt, exchange cost.

Made-up data: 2026 opening balance 1,000; one land payment of €300 on 5 March
(1 cuota; 2,000,000 Gs arrived). Plan: 100 cuotas of 2,000,000 Gs, 10 paid
before -> 11 paid, 89 to go. Rates: 7,000 Gs/€ on 1 March, 8,000 on 1 October.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.models import Account, AccountValue, AppData, Category, ExchangeRate, InvestmentPlan, Transaction, YearCategories, YearData
from app.services import net_worth

TODAY = date(2026, 10, 21)


@pytest.fixture
def data() -> AppData:
    d = AppData()
    d.years["2026"] = YearData(
        opening_balance=1000,
        categories=YearCategories(expense=[Category(name="Land", kind="investment")]),
        transactions=[Transaction(id=1, type="expense", date="2026-03-05", month=2, amount=300, cat="Land",
                                  installments=1, foreign_amount=2_000_000, foreign_currency="PYG", desc="Cuota")],
        next_id=2,
    )
    d.investments = [InvestmentPlan(id=1, name="Plot", category="Land", unit="cuota", local_currency="Gs",
                                    installment_amount=2_000_000, total_installments=100, paid_before=10,
                                    created_date="2026-01-01")]
    d.exchange_rates = [ExchangeRate(per_eur=7000, date="2026-03-01"), ExchangeRate(per_eur=8000, date="2026-10-01")]
    d.accounts = [
        Account(id=1, name="Tagesgeld", values=[AccountValue(date="2026-09-01", amount=4000),
                                                AccountValue(date="2026-11-01", amount=4500)]),
        Account(id=2, name="Cuenta PY", currency="PYG", values=[AccountValue(date="2026-06-01", amount=8_000_000)]),
    ]
    return d


def item(result, kind, name_start=""):
    return next(i for i in result["items"] if i["kind"] == kind and i["name"].startswith(name_start))


def test_rate_on_a_day(data):
    assert net_worth.rate_on(data.exchange_rates, "PYG", "2026-06-15").per_eur == 7000
    assert net_worth.rate_on(data.exchange_rates, "PYG", "2026-10-01").per_eur == 8000
    assert net_worth.rate_on(data.exchange_rates, "PYG", "2026-01-01").per_eur == 7000  # before the first: the first
    assert net_worth.rate_on(data.exchange_rates, "PYG").per_eur == 8000
    assert net_worth.rate_on([], "PYG") is None


def test_currency_labels():
    assert net_worth.currency_of("Gs") == "PYG" and net_worth.currency_of("€") == "EUR"
    assert net_worth.currency_of("USD") is None


def test_net_worth(data):
    r = net_worth.build(data, TODAY)
    assert item(r, "tracked")["eur"] == 700                       # 1,000 - 300
    tagesgeld = item(r, "account", "Tagesgeld")
    assert tagesgeld["eur"] == 4000 and tagesgeld["as_of"] == "2026-09-01"   # November's value is in the future
    assert item(r, "account", "Cuenta PY")["eur"] == 1000          # 8,000,000 / 8,000
    land = item(r, "asset")
    assert land["eur"] == 25000 and land["basis"] == "full contract price"   # 100 x 2,000,000 / 8,000
    assert item(r, "debt")["eur"] == 22250                          # 89 x 2,000,000 / 8,000
    assert (r["own"], r["owe"], r["net_worth"]) == (30700, 22250, 8450)
    assert r["in_pyg"] == 1000 + 25000 - 22250 and r["missing_rate"] == []


def test_market_value_replaces_the_contract_price(data):
    data.investments[0].market_value_local = 240_000_000
    land = item(net_worth.build(data, TODAY), "asset")
    assert land["eur"] == 30000 and land["basis"] == "market value"


def test_a_paid_off_plan_has_no_debt(data):
    data.investments[0].paid_before = 99
    assert not [i for i in net_worth.build(data, TODAY)["items"] if i["kind"] == "debt"]


def test_without_a_rate_guaranies_are_not_counted(data):
    data.exchange_rates = []
    r = net_worth.build(data, TODAY)
    assert r["missing_rate"] == ["PYG"] and item(r, "asset")["eur"] is None
    assert r["net_worth"] == 700 + 4000


def test_exchange_cost_of_a_payment(data):
    (p,) = net_worth.exchange_costs(data)["payments"]
    # €300 bought 2,000,000 Gs (6,666.67 Gs/€); at the rate of the day (7,000) that is €285.71.
    assert p["rate_got"] == 6666.67 and p["rate_reference"] == 7000
    assert p["fair_eur"] == 285.71 and p["cost"] == 14.29 and p["cost_pct"] == 4.76
    assert net_worth.exchange_costs(data)["total_cost"] == 14.29


def test_payments_without_a_foreign_amount_are_not_listed(data):
    data.years["2026"].transactions[0].foreign_amount = None
    assert net_worth.exchange_costs(data)["payments"] == []
