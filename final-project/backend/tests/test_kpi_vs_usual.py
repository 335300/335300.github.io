"""KPI tiles against the usual month, in euros (services/kpi_compare.py).

Made-up year 2026, tracking from January, opening balance 1,000.
Categories: Rent (fixed), Food (variable), Land (investment); Salary, Gift (income).

| month | cash in            | Rent | Food            | Land | costs | cash out | kept | wealth built | balance |
|-------|--------------------|------|-----------------|------|-------|----------|------|--------------|---------|
| Jan   | 2,000              | 500  | 300             | 200  | 800   | 1,000    | 1,000| 1,200        | 2,000   |
| Feb   | 2,200              | 500  | 400             | 200  | 900   | 1,100    | 1,100| 1,300        | 3,100   |
| Mar   | 1,800 + 1,000 one-off gift | 500 | 300      | 200  | 800   | 1,000    | 800 (regular) | 1,000 (regular) | 4,900 |
| Apr   | 2,000              | 500  | 200             | 0    | 700   | 700      | 1,300| 1,300        | 6,200   |
| May   | 2,015 + 500 one-off gift   | 500 | 300 + 400 one-off | 200 | 1,200 | 1,400 | 1,115 | 1,315 | 7,315 |

Usual (median of Jan-Apr, one-offs left out; 4 months -> mean of the middle two):
- cash in  1,800 2,000 2,000 2,200 -> 2,000   (with the one-off gift it would be 2,100)
- cash out   700 1,000 1,000 1,100 -> 1,000
- kept       800 1,000 1,100 1,300 -> 1,050
- wealth built 1,000 1,200 1,300 1,300 -> 1,250
- balance  2,000 3,100 4,900 6,200 -> 4,000   (a balance has no one-offs)

May without one-offs: cash in 2,015; cash out 1,000; kept 1,015; wealth built 2,015 - 800 = 1,215.
"""

from __future__ import annotations

import pytest

from app.models import AppData, Category, Transaction, YearCategories, YearData
from app.services import kpi_compare


def t(id: int, type: str, month: int, amount: float, cat: str, one_off: bool = False, year: int = 2026) -> Transaction:
    return Transaction(id=id, type=type, date=f"{year}-{month + 1:02d}-10", month=month, amount=amount, cat=cat,
                       one_off=one_off)


def cats() -> YearCategories:
    return YearCategories(
        expense=[Category(name="Rent", kind="fixed"), Category(name="Food"), Category(name="Land", kind="investment")],
        income=[Category(name="Salary"), Category(name="Gift")],
    )


@pytest.fixture
def data() -> AppData:
    rows = [
        # Jan
        ("income", 0, 2000, "Salary", False), ("expense", 0, 500, "Rent", False),
        ("expense", 0, 300, "Food", False), ("expense", 0, 200, "Land", False),
        # Feb
        ("income", 1, 2200, "Salary", False), ("expense", 1, 500, "Rent", False),
        ("expense", 1, 400, "Food", False), ("expense", 1, 200, "Land", False),
        # Mar
        ("income", 2, 1800, "Salary", False), ("income", 2, 1000, "Gift", True), ("expense", 2, 500, "Rent", False),
        ("expense", 2, 300, "Food", False), ("expense", 2, 200, "Land", False),
        # Apr
        ("income", 3, 2000, "Salary", False), ("expense", 3, 500, "Rent", False), ("expense", 3, 200, "Food", False),
        # May (the month shown)
        ("income", 4, 2015, "Salary", False), ("income", 4, 500, "Gift", True), ("expense", 4, 500, "Rent", False),
        ("expense", 4, 300, "Food", False), ("expense", 4, 400, "Food", True), ("expense", 4, 200, "Land", False),
    ]
    txs = [t(i + 1, *r) for i, r in enumerate(rows)]
    d = AppData()
    d.years["2026"] = YearData(opening_balance=1000, categories=cats(), transactions=txs, next_id=len(txs) + 1)
    return d


def test_may_against_the_usual_month(data):
    """See the table in the module docstring."""
    r = kpi_compare.vs_usual(data, 2026, 4)
    assert r["months"] == 4
    assert r["cash_in"] == {"current": 2515, "current_regular": 2015, "one_off": 500, "usual": 2000,
                            "diff": 15, "pct": 0.75, "direction": "same"}      # 15 < max(10, 2 % of 2,000 = 40)
    assert r["cash_out"] == {"current": 1400, "current_regular": 1000, "one_off": 400, "usual": 1000,
                             "diff": 0, "pct": 0.0, "direction": "same"}
    assert r["kept"] == {"current": 1115, "current_regular": 1015, "one_off": 100, "usual": 1050,
                         "diff": -35, "pct": -3.33, "direction": "down"}       # 35 >= max(10, 21)
    assert r["wealth_built"] == {"current": 1315, "current_regular": 1215, "one_off": 100, "usual": 1250,
                                 "diff": -35, "pct": -2.8, "direction": "down"}  # 35 >= max(10, 25)
    assert r["balance"] == {"current": 7315, "current_regular": 7315, "one_off": 0, "usual": 4000,
                            "diff": 3315, "pct": 82.88, "direction": "up"}


def test_tile_values_match_the_dashboard_kpis(data):
    """`current` is exactly what the tiles already show."""
    from app.services import dashboard

    payload = dashboard.build(data, 2026, 4)
    k, v = payload["kpis"], payload["vs_usual"]
    assert v["cash_in"]["current"] == k["cash_in"]
    assert v["cash_out"]["current"] == k["cash_out"]
    assert v["kept"]["current"] == k["savings"]
    assert v["wealth_built"]["current"] == k["wealth_built"]
    assert v["balance"]["current"] == k["current_balance"]


def test_one_offs_in_earlier_months_do_not_move_the_usual(data):
    """Without the March gift being one-off, usual cash in would be median(1,800+1,000, 2,000, 2,000, 2,200) = 2,100."""
    assert kpi_compare.vs_usual(data, 2026, 4)["cash_in"]["usual"] == 2000
    for tx in data.years["2026"].transactions:
        tx.one_off = False
    assert kpi_compare.vs_usual(data, 2026, 4)["cash_in"]["usual"] == 2100


def test_first_month_has_nothing_to_compare(data):
    r = kpi_compare.vs_usual(data, 2026, 0)
    assert r["months"] == 0
    for key in ("balance", "cash_in", "cash_out", "kept", "wealth_built"):
        assert r[key]["usual"] is None and r[key]["diff"] is None
        assert r[key]["pct"] is None and r[key]["direction"] is None
    assert r["cash_in"]["current"] == 2000


def test_year_change_reaches_back(data):
    """January 2027 (cash in 2,000) compares with the 6 months before: 2026 Jan-May
    (May is the last recorded one), regular cash in 2,000 2,200 1,800 2,000 2,015 ->
    sorted 1,800 2,000 2,000 2,015 2,200 -> median 2,000. Diff 0 -> same."""
    data.years["2027"] = YearData(opening_balance=7315, categories=cats(),
                                  transactions=[t(1, "income", 0, 2000, "Salary", year=2027)], next_id=2)
    r = kpi_compare.vs_usual(data, 2027, 0)
    assert r["months"] == 5
    assert r["cash_in"]["usual"] == 2000 and r["cash_in"]["direction"] == "same"


@pytest.mark.parametrize(
    ("diff", "usual", "expected"),
    [
        (9.99, 100, "same"),     # threshold max(10, 2) = 10
        (10, 100, "up"),         # exactly 10 is no longer "about the same"
        (-19.99, 1000, "same"),  # threshold max(10, 20) = 20
        (-20, 1000, "down"),
        (5, 0, "same"),          # a usual of 0: only the 10 € floor applies
        (50, -500, "up"),        # negative usual (kept can be negative): 2 % of 500 = 10
        (None, None, None),
    ],
)
def test_about_the_same_threshold(diff, usual, expected):
    assert kpi_compare.direction(diff, usual) == expected


# -- "usual" with no real history (months_with_data) ---------------------------
#
# A fresh profile: 2026 tracked from January, opening balance 1,000, and only
# May holds transactions (Salary 2,000, Rent 500, Food 200). January–April are
# tracked but empty, so they are the 4 baseline months — with no data in them.

KPIS = ("balance", "cash_in", "cash_out", "kept", "wealth_built")


def fresh(*extra: Transaction) -> AppData:
    txs = [t(1, "income", 4, 2000, "Salary"), t(2, "expense", 4, 500, "Rent"), t(3, "expense", 4, 200, "Food"),
           *extra]
    d = AppData()
    d.years["2026"] = YearData(opening_balance=1000, categories=cats(), transactions=txs, next_id=len(txs) + 1)
    return d


def test_no_earlier_month_with_data_gives_no_usual():
    """May: 4 baseline months (Jan–Apr), none with a transaction -> months_with_data 0.
    Before this rule usual cash in was median(0, 0, 0, 0) = 0 and May read
    "2,000 more than usual". Now usual, diff, pct and direction are None;
    the month's own figures stay: cash in 2,000; cash out 700; kept 1,300;
    balance 1,000 + 1,300 = 2,300."""
    r = kpi_compare.vs_usual(fresh(), 2026, 4)
    assert (r["months"], r["months_with_data"]) == (4, 0)
    for key in KPIS:
        assert (r[key]["usual"], r[key]["diff"], r[key]["pct"], r[key]["direction"]) == (None, None, None, None)
    assert (r["cash_in"]["current"], r["cash_out"]["current"], r["kept"]["current"]) == (2000, 700, 1300)
    assert r["balance"]["current"] == 2300


def test_a_month_with_only_one_offs_does_not_count_as_data():
    """A one-off gift of 1,000 in March is left out of every usual -> still 0 months with data."""
    r = kpi_compare.vs_usual(fresh(t(4, "income", 2, 1000, "Gift", one_off=True)), 2026, 4)
    assert (r["months"], r["months_with_data"]) == (4, 0)
    assert r["cash_in"]["usual"] is None and r["cash_in"]["direction"] is None


def test_one_month_with_data_keeps_the_usual_rule():
    """Food 100 in February only -> months_with_data 1. The usual rule itself is unchanged:
    cash out median(0, 100, 0, 0) = 0; May regular cash out 700 -> diff 700, up;
    pct None (usual 0)."""
    r = kpi_compare.vs_usual(fresh(t(4, "expense", 1, 100, "Food")), 2026, 4)
    assert (r["months"], r["months_with_data"]) == (4, 1)
    assert (r["cash_out"]["usual"], r["cash_out"]["diff"], r["cash_out"]["pct"], r["cash_out"]["direction"]) \
        == (0, 700, None, "up")


def test_months_with_data_in_the_full_history(data):
    """The module table: Jan–Apr all hold transactions -> 4 of 4. January: no baseline -> 0 of 0."""
    assert kpi_compare.vs_usual(data, 2026, 4)["months_with_data"] == 4
    assert kpi_compare.vs_usual(data, 2026, 0)["months_with_data"] == 0
