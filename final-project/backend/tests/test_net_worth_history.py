"""Net worth over 12 months (services/net_worth_history.py) and month-end snapshots.

Made-up data. Tracking starts January 2026, opening balance 1,000 (= end of Dec 2025).
Today: 20 May 2026 (May has nothing recorded yet).

| month | Salary | Rent | Food | Land (1 cuota) | wealth built | tracked balance |
|-------|--------|------|------|----------------|--------------|-----------------|
| Dec 25| -      | -    | -    | -              | -            | 1,000 (opening) |
| Jan   | 2,000  | 800  | 200  |                | 1,000        | 2,000           |
| Feb   | 2,000  | 800  | 200  | 500 on 5 Feb   | 1,000        | 2,500           |
| Mar   | 2,000  | 800  | 400  |                | 800          | 3,300           |
| Apr   | 2,000  | 800  | 200  |                | 1,000        | 4,300           |
| May   | -      | -    | -    |                | 0            | 4,300           |

Tagesgeld (kept by hand): 3,000 on 1 Feb, 3,400 on 15 Apr. Before 1 Feb its first value
is carried back (estimated).
Land plan "Plot": 10 cuotas of 1,000,000 Gs, 2 paid before, added 10 Jan 2026 -> contract
price 10,000,000 Gs. Rates: 5,000 Gs/EUR from 1 Jan, 4,000 from 1 Apr (Dec 2025 has no rate
yet: the first one is used, estimated).

| month-end | tracked | Tagesgeld | land asset          | debt (cuotas left)   | own    | owe   | net worth |
|-----------|---------|-----------|---------------------|----------------------|--------|-------|-----------|
| Dec 25    | 1,000   | 3,000 (c) | 10M/5,000 = 2,000   | 8M/5,000 = 1,600     | 6,000  | 1,600 | 4,400 est.|
| Jan       | 2,000   | 3,000 (c) | 2,000               | 1,600                | 7,000  | 1,600 | 5,400 est.|
| Feb       | 2,500   | 3,000     | 2,000               | 7M/5,000 = 1,400     | 7,500  | 1,400 | 6,100     |
| Mar       | 3,300   | 3,000     | 2,000               | 1,400                | 8,300  | 1,400 | 6,900     |
| Apr       | 4,300   | 3,400     | 10M/4,000 = 2,500   | 7M/4,000 = 1,750     | 10,200 | 1,750 | 8,450     |
| May (now) | 4,300   | 3,400     | 2,500               | 1,750                | 10,200 | 1,750 | 8,450     |

Change Dec 25 -> May = 8,450 − 4,400 = 4,050 over 5 months.
Saved = wealth built Jan..May = 1,000 + 1,000 + 800 + 1,000 + 0 = 3,800.
Growth = 4,050 − 3,800 = 250 (Tagesgeld +400, the rate +150, the land payment −300:
500 € paid for 1 cuota = 200 € of debt at 5,000 Gs/EUR).
Saved share = 3,800 ÷ 4,050 = 93.83 % -> about 9 of every 10 euros.
"""

from __future__ import annotations

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import config
from app.api.deps import get_today
from app.app import create_app
from app.models import (
    Account, AccountValue, AppData, Category, ExchangeRate, InvestmentPlan, Transaction, YearCategories, YearData,
)
from app.services import net_worth_history as nwh
from app.storage import Repository

TODAY = date(2026, 5, 20)


def t(id: int, type: str, month: int, amount: float, cat: str, day: int = 10, year: int = 2026, **extra) -> Transaction:
    return Transaction(id=id, type=type, date=f"{year}-{month + 1:02d}-{day:02d}", month=month, amount=amount,
                       cat=cat, **extra)


def cats() -> YearCategories:
    return YearCategories(
        expense=[Category(name="Rent", kind="fixed"), Category(name="Food"), Category(name="Land", kind="investment")],
        income=[Category(name="Salary")],
    )


@pytest.fixture
def data() -> AppData:
    txs = []
    for m, food in enumerate([200, 200, 400, 200]):
        txs += [t(len(txs) + 1, "income", m, 2000, "Salary"), t(len(txs) + 2, "expense", m, 800, "Rent"),
                t(len(txs) + 3, "expense", m, food, "Food")]
    txs.append(t(len(txs) + 1, "expense", 1, 500, "Land", day=5, installments=1))
    d = AppData()
    d.years["2026"] = YearData(opening_balance=1000, categories=cats(), transactions=txs, next_id=len(txs) + 1)
    d.accounts = [Account(id=1, name="Tagesgeld", values=[AccountValue(date="2026-02-01", amount=3000),
                                                          AccountValue(date="2026-04-15", amount=3400)])]
    d.investments = [InvestmentPlan(id=1, name="Plot", category="Land", unit="cuota", local_currency="Gs",
                                    installment_amount=1_000_000, total_installments=10, paid_before=2,
                                    created_date="2026-01-10")]
    d.exchange_rates = [ExchangeRate(per_eur=5000, date="2026-01-01"), ExchangeRate(per_eur=4000, date="2026-04-01")]
    return d


def nets(points):
    return [(p["month"], p["own"], p["owe"], p["net_worth"]) for p in points]


def test_month_end_net_worth(data):
    """See the second table in the module docstring."""
    r = nwh.history(data, TODAY)
    assert nets(r["points"]) == [
        ("2025-12", 6000, 1600, 4400), ("2026-01", 7000, 1600, 5400), ("2026-02", 7500, 1400, 6100),
        ("2026-03", 8300, 1400, 6900), ("2026-04", 10200, 1750, 8450), ("2026-05", 10200, 1750, 8450),
    ]
    est = {p["month"]: p["estimated_reasons"] for p in r["points"]}
    assert est["2025-12"] == ["carried_back", "plan_before_added", "rate"]
    assert est["2026-01"] == ["carried_back"]
    assert all(est[m] == [] for m in ("2026-02", "2026-03", "2026-04", "2026-05"))
    assert [p["estimated"] for p in r["points"]] == [True, True, False, False, False, False]
    assert r["points"][-1]["source"] == "live" and r["points"][0]["source"] == "rebuilt"
    assert r["points"][-1]["label"] == "May 26"


def test_the_last_point_is_the_net_worth_page(data):
    from app.services import net_worth

    live = net_worth.build(data, TODAY)
    last = nwh.history(data, TODAY)["points"][-1]
    assert (last["own"], last["owe"], last["net_worth"]) == (live["own"], live["owe"], live["net_worth"])


def test_split_of_the_change(data):
    """4,050 up in 5 months: 3,800 from what was saved, 250 growth; 93.83 % -> 9 of 10."""
    r = nwh.history(data, TODAY)
    assert r["change"] == {
        "from": "2025-12", "to": "2026-05", "months": 5, "total": 4050, "saved": 3800, "growth": 250,
        "saved_share_pct": 93.83, "saved_of_10": 9, "estimated": True,   # Dec 25 and Jan are estimated
    }
    assert r["vs_previous_month"] == 0      # May = April (nothing recorded in May yet)


def test_saved_more_than_the_change(data):
    """Tagesgeld 3,100 in April instead of 3,400: change 3,750, saved 3,800, growth −50.
    No "x of every 10" sentence then (it only works for 0 <= saved <= change)."""
    data.accounts[0].values[1].amount = 3100
    c = nwh.history(data, TODAY)["change"]
    assert (c["total"], c["saved"], c["growth"], c["saved_of_10"]) == (3750, 3800, -50, None)
    assert c["saved_share_pct"] == 101.33


def test_twelve_bars_and_the_month_before_as_start():
    """2025 + 2026 Jan–May, 100 € salary every month, nothing else; today 20 May 2026.
    Bars: Jun 2025 .. May 2026 (12). Start: end of May 2025 (balance 500).
    Change 1,700 − 500 = 1,200 over 12 months, all saved -> 10 of 10."""
    d = AppData()
    d.years["2025"] = YearData(categories=cats(), transactions=[t(m + 1, "income", m, 100, "Salary", year=2025)
                                                                 for m in range(12)], next_id=13)
    d.years["2026"] = YearData(opening_balance=1200, categories=cats(),
                               transactions=[t(m + 1, "income", m, 100, "Salary") for m in range(5)], next_id=6)
    r = nwh.history(d, TODAY)
    assert len(r["points"]) == 12 and r["points"][0]["month"] == "2025-06" and r["start"]["month"] == "2025-05"
    assert r["start"]["net_worth"] == 500 and r["points"][-1]["net_worth"] == 1700
    c = r["change"]
    assert (c["months"], c["total"], c["saved"], c["growth"], c["saved_of_10"]) == (12, 1200, 1200, 0, 10)


def test_no_months_before_tracking_starts():
    """Tracking starts in May (start_month 3 = April is the opening): points Apr, May, Jun only."""
    d = AppData()
    d.years["2026"] = YearData(opening_balance=500, start_month=3, categories=cats(),
                               transactions=[t(1, "income", 4, 100, "Salary")], next_id=2)
    r = nwh.history(d, date(2026, 6, 15))
    assert [p["month"] for p in r["points"]] == ["2026-04", "2026-05", "2026-06"]
    assert [p["net_worth"] for p in r["points"]] == [500, 600, 600]
    assert r["change"]["months"] == 2 and r["change"]["saved"] == 100


def test_a_past_month_not_recorded_yet_is_estimated(data):
    """Today 20 June: May (past) has no transactions yet -> estimated, reason not_recorded."""
    r = nwh.history(data, date(2026, 6, 20))
    may = next(p for p in r["points"] if p["month"] == "2026-05")
    assert may["estimated"] and may["estimated_reasons"] == ["not_recorded"]


def test_no_data():
    r = nwh.history(AppData(), TODAY)
    assert r["points"] == [] and r["start"] is None and r["change"] is None and r["vs_previous_month"] is None
    assert nwh.upsert_snapshot(AppData(), TODAY) is False    # a fresh install writes nothing


# -- snapshots -------------------------------------------------------------------

def test_snapshot_keeps_what_was_known_then(data):
    """Snapshot taken 20 May. In June the land gets a market value of 12,000,000 Gs (3,000 €) and a
    May salary of 2,000 (25 May) is imported.
    May from the snapshot: tracked recomputed 4,300 + 2,000 = 6,300; Tagesgeld 3,400 and land 2,500 /
    debt 1,750 as they were -> own 12,200, owe 1,750, net 10,450, not estimated.
    April has no snapshot: rebuilt with today's market value -> land 3,000, estimated (land_value).
    June (live): 6,300 + 3,400 + 3,000 = 12,700, owe 1,750 -> 10,950."""
    assert nwh.upsert_snapshot(data, TODAY) is True
    assert nwh.upsert_snapshot(data, TODAY) is False                  # same figures: nothing to write
    snap = data.net_worth_snapshots[0]
    assert (snap.month, snap.taken, snap.own, snap.owe, snap.net_worth) == ("2026-05", "2026-05-20", 10200, 1750, 8450)

    data.investments[0].market_value_local = 12_000_000
    data.years["2026"].transactions.append(t(99, "income", 4, 2000, "Salary", day=25))
    r = nwh.history(data, date(2026, 6, 10))
    by = {p["month"]: p for p in r["points"]}
    assert (by["2026-05"]["own"], by["2026-05"]["owe"], by["2026-05"]["net_worth"]) == (12200, 1750, 10450)
    assert by["2026-05"]["source"] == "snapshot" and by["2026-05"]["estimated"] is False
    assert by["2026-04"]["net_worth"] == 4300 + 3400 + 3000 - 1750 and by["2026-04"]["estimated_reasons"] == ["land_value"]
    assert (by["2026-06"]["own"], by["2026-06"]["net_worth"]) == (12700, 10950)


def test_snapshot_is_replaced_within_the_month(data):
    nwh.upsert_snapshot(data, TODAY)
    data.accounts[0].values.append(AccountValue(date="2026-05-20", amount=3500))
    assert nwh.upsert_snapshot(data, date(2026, 5, 21)) is True
    assert len(data.net_worth_snapshots) == 1
    assert (data.net_worth_snapshots[0].taken, data.net_worth_snapshots[0].own) == ("2026-05-21", 10300)


def test_schema_9_file_loads_without_snapshots(tmp_path):
    path = tmp_path / "data.json"
    path.write_text(json.dumps({"schema_version": 9, "years": {"2026": {"opening_balance": 100}}}), encoding="utf-8")
    repo = Repository(path=path)
    assert repo.data.net_worth_snapshots == [] and repo.data.schema_version == config.SCHEMA_VERSION == 10
    repo.save()
    assert json.loads(path.read_text(encoding="utf-8"))["net_worth_snapshots"] == []


# -- HTTP -------------------------------------------------------------------------

@pytest.fixture
def client(data):
    from app.api import deps

    app = create_app()
    app.dependency_overrides[get_today] = lambda: TODAY
    c = TestClient(app)
    repo = deps.get_store().repo()
    repo._data = data
    repo.save()
    return c


def test_endpoints_write_one_snapshot(client):
    from app.api import deps

    assert client.get("/api/net-worth").json()["net_worth"] == 8450
    client.get("/api/net-worth")
    snaps = deps.get_store().repo().data.net_worth_snapshots
    assert [s.month for s in snaps] == ["2026-05"]
    body = client.get("/api/net-worth/history").json()
    assert body["points"][-1]["net_worth"] == 8450 and body["change"]["saved_of_10"] == 9
