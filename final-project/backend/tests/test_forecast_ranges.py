"""Forecast ranges: the 50 % and 80 % bands around the "most likely" balance.

Made-up round numbers only. The model: sigma = sample standard deviation of
the monthly kept amount (cash in − cash out, one-offs left out) over the
finished months; the band half-width h months ahead is z × sigma × √h with
z50 = 0.6745 and z80 = 1.2816.
"""

from __future__ import annotations

import math
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_today
from app.app import create_app
from app.models import AppData, Category, Transaction, YearCategories, YearData
from app.services import forecast_ranges as fr
from app.services import joint, rolling_forecast

from .conftest import TODAY, tx

# Kept amounts with mean 1 000 and deviations +150, −150, +50, −50, 0, 0:
# squares 22 500 + 22 500 + 2 500 + 2 500 = 50 000; / (6 − 1) = 10 000; √ = 100.
SIGMA_100 = [1150.0, 850.0, 1050.0, 950.0, 1000.0, 1000.0]


def months(balances: list[float], start: tuple[int, int] = (2027, 0)) -> list[dict]:
    """Most-likely rows as the routes pass them in: one per month, in order."""
    out = []
    for i, b in enumerate(balances):
        y, m = divmod(start[0] * 12 + start[1] + i, 12)
        out.append({"year": y, "month": m, "balance": b})
    return out


# ---------------------------------------------------------------------------
# Small pieces
# ---------------------------------------------------------------------------

def test_sigma_of_six_months():
    """[100, 300, 200, 400, 0, 200]: mean 1 200 / 6 = 200.
    Deviations −100, 100, 0, 200, −200, 0 → squares 10 000 + 10 000 + 40 000 + 40 000 = 100 000.
    Sample variance 100 000 / 5 = 20 000; sigma = √20 000 = 141.42."""
    assert fr.sample_sigma([100, 300, 200, 400, 0, 200]) == pytest.approx(141.4213562, abs=1e-6)


def test_sigma_of_a_round_case():
    """See SIGMA_100: squares add up to 50 000; 50 000 / 5 = 10 000; √ = 100."""
    assert fr.sample_sigma(SIGMA_100) == pytest.approx(100.0)


def test_sigma_is_zero_when_every_month_is_the_same():
    assert fr.sample_sigma([500.0] * 6) == 0.0


@pytest.mark.parametrize(
    "value, expected",
    [
        (2378.02, 2300),   # below 5 000: down to the 100 below
        (2300.0, 2300),    # already round: stays
        (4999.99, 4900),
        (5000.0, 5000),    # from 5 000: down to the 500 below
        (5499.0, 5000),
        (7720.0, 7500),
        (0.0, 0),
        (-250.0, -300),    # below zero still goes *down* (more careful)
    ],
)
def test_nice_floor(value, expected):
    assert fr.nice_floor(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [(4049.0, 4050), (4024.99, 4000), (4025.0, 4050), (5400.0, 5400), (-120.0, -100)],
)
def test_likely_about_rounds_to_the_nearest_50(value, expected):
    """"Most likely balance in May: about 4 050 €" — nearest 50 €, halves go up."""
    assert fr.about(value) == expected


# ---------------------------------------------------------------------------
# The bands
# ---------------------------------------------------------------------------

def test_bands_widen_with_the_square_root_of_the_horizon():
    """sigma = 100 (SIGMA_100). Most likely: Jan 3 000, Feb 2 800, Mar 2 600, Apr 2 700.

    Half-widths: 50 % = 0.6745 × 100 × √h, 80 % = 1.2816 × 100 × √h.
    - Jan (h=1): 67.45 / 128.16 → 50 %: 2 932.55 – 3 067.45; 80 %: 2 871.84 – 3 128.16
    - Feb (h=2): 80 % = 128.16 × 1.414214 = 181.25 → low80 2 800 − 181.25 = 2 618.75
    - Mar (h=3): 80 % = 128.16 × 1.732051 = 221.98 → low80 2 600 − 221.98 = 2 378.02
    - Apr (h=4): √4 = 2 → 134.90 / 256.32 → 50 %: 2 565.10 – 2 834.90; 80 %: 2 443.68 – 2 956.32
    Lowest 80 % low = 2 378.02 (March) → nice floor 2 300. Horizon ends April 2027.
    """
    r = fr.build(months([3000, 2800, 2600, 2700]), SIGMA_100)
    assert r is not None
    assert r["sigma"] == 100.0 and r["history_months"] == 6
    jan, feb, mar, apr = r["months"]
    assert jan == {
        "key": "2027-01", "month_name": "January 2027", "months_ahead": 1, "likely": 3000.0,
        "low50": 2932.55, "high50": 3067.45, "low80": 2871.84, "high80": 3128.16,
    }
    assert feb["low80"] == 2618.75 and feb["months_ahead"] == 2
    assert mar["low80"] == 2378.02
    assert (apr["low50"], apr["high50"], apr["low80"], apr["high80"]) == (2565.10, 2834.90, 2443.68, 2956.32)
    assert r["floor_80"] == 2300
    assert r["horizon_end_name"] == "April 2027" and r["horizon_end_month"] == "April"
    assert r["likely_end"] == 2700.0 and r["likely_end_about"] == 2700


def test_first_six_months_get_their_own_floor_for_the_overview_card():
    """sigma 0 (every month kept the same), so each band is the line itself.
    Most likely: 5 600, 5 400, 5 200, 5 100, 5 300, 5 250, 4 300, 6 000 (Jan–Aug 2027).
    - All 8 months: lowest 4 300 (below 5 000) → floor 4 300; ends August, likely 6 000.
    - First 6: lowest 5 100 (from 5 000 on: step 500) → floor 5 000; ends June, likely 5 250.
    """
    r = fr.build(months([5600, 5400, 5200, 5100, 5300, 5250, 4300, 6000]), [700.0] * 6)
    assert r is not None and r["sigma"] == 0.0
    assert all(m["low80"] == m["likely"] == m["high80"] for m in r["months"])
    assert r["floor_80"] == 4300 and r["horizon_end_month"] == "August" and r["likely_end"] == 6000
    assert r["first_6"] == {
        "floor_80": 5000, "horizon_end_name": "June 2027", "horizon_end_month": "June",
        "likely_end": 5250.0, "likely_end_about": 5250,
    }


def test_fewer_than_six_months_of_history_gives_no_ranges():
    assert fr.build(months([1000, 1000]), [100.0, 200.0, 300.0, 400.0, 500.0]) is None
    assert fr.build(months([1000, 1000]), [100.0] * 6) is not None  # exactly 6 is enough


def test_no_forecast_months_gives_no_ranges():
    assert fr.build([], SIGMA_100) is None


# ---------------------------------------------------------------------------
# The history of kept amounts
# ---------------------------------------------------------------------------

def one_off(t: Transaction) -> Transaction:
    t.one_off = True
    return t


@pytest.fixture
def history_data() -> AppData:
    """Tracking starts September 2025 (start_month=7); 2026 opens with 1 000.

    Kept per month (cash in − cash out, one-offs left out):
    Sep 25: 1 000 − 800 = 200     Oct: 1 000 − 900 = 100     Nov: 1 000 − 700 = 300
    Dec: 1 000 − 800 = 200 (plus a 5 000 one-off cost, left out)
    Jan 26: 1 000 − 600 = 400     Feb: 1 000 − 1 000 = 0 (plus a 3 000 one-off income, left out)
    Mar 26: 1 000 − 0 = 1 000 — the month still in progress, so it does not count.
    """
    cats = YearCategories(expense=[Category(name="Rent", kind="fixed")], income=[Category(name="Salary")])
    y25 = YearData(
        opening_balance=0, start_month=7, categories=cats,
        transactions=[
            tx(1, "income", 8, 1000, "Salary", year=2025), tx(2, "expense", 8, 800, "Rent", year=2025),
            tx(3, "income", 9, 1000, "Salary", year=2025), tx(4, "expense", 9, 900, "Rent", year=2025),
            tx(5, "income", 10, 1000, "Salary", year=2025), tx(6, "expense", 10, 700, "Rent", year=2025),
            tx(7, "income", 11, 1000, "Salary", year=2025), tx(8, "expense", 11, 800, "Rent", year=2025),
            one_off(tx(9, "expense", 11, 5000, "Rent", year=2025)),
        ],
        next_id=10,
    )
    y26 = YearData(
        opening_balance=1000, start_month=-1, categories=cats.model_copy(deep=True),
        transactions=[
            tx(1, "income", 0, 1000, "Salary"), tx(2, "expense", 0, 600, "Rent"),
            tx(3, "income", 1, 1000, "Salary"), tx(4, "expense", 1, 1000, "Rent"),
            one_off(tx(5, "income", 1, 3000, "Salary")),
            tx(6, "income", 2, 1000, "Salary"),
        ],
        next_id=7,
    )
    d = AppData()
    d.years["2025"] = y25
    d.years["2026"] = y26
    return d


HISTORY_TODAY = date(2026, 3, 10)


def test_kept_history_skips_the_current_month_and_one_offs_across_the_year_end(history_data):
    """Oldest first: Sep 200, Oct 100, Nov 300, Dec 200, Jan 400, Feb 0 (see the fixture)."""
    assert fr.kept_history(history_data, HISTORY_TODAY) == [200.0, 100.0, 300.0, 200.0, 400.0, 0.0]


def test_kept_history_keeps_only_the_latest_months(history_data):
    """With room for 4: Nov 300, Dec 200, Jan 400, Feb 0."""
    assert fr.kept_history(history_data, HISTORY_TODAY, limit=4) == [300.0, 200.0, 400.0, 0.0]


def test_kept_history_counts_the_last_recorded_month_once_it_is_over(history_data):
    """Today in April: March (1 000) is finished now and joins the list."""
    assert fr.kept_history(history_data, date(2026, 4, 2))[-1] == 1000.0


def test_kept_history_is_empty_without_years():
    assert fr.kept_history(AppData(), HISTORY_TODAY) == []


def test_personal_ranges_follow_the_main_forecast_line(history_data):
    """No budgets, so the forecast keeps 0 a month and stays at the March balance:
    1 000 + Jan 400 + Feb (1 000 + 3 000 − 1 000) + Mar 1 000 = 5 400, for April 2026 – March 2027.

    sigma = √20 000 = 141.4214 (same months as test_sigma_of_six_months).
    80 % half-width = 1.2816 × 141.4214 × √h = 181.2456 × √h.
    - h=1 (April): 5 400 − 181.25 = 5 218.75
    - h=6 (September): 181.2456 × 2.449490 = 443.96 → 4 956.04 → first-6 floor 4 900
    - h=12 (March 2027): 181.2456 × 3.464102 = 627.85 → 4 772.15 → floor 4 700
    """
    forecast = rolling_forecast.build(history_data)
    r = fr.for_rolling(forecast, history_data, HISTORY_TODAY)
    assert r is not None and r["line_key"] == "plan"
    assert r["sigma"] == 141.42 and r["history_months"] == 6
    assert len(r["months"]) == 12 and r["months"][0]["key"] == "2026-04"
    assert all(m["likely"] == 5400.0 for m in r["months"])
    assert r["months"][0]["low80"] == 5218.75
    assert r["months"][5]["low80"] == 4956.04
    assert r["months"][11]["low80"] == 4772.15
    assert r["floor_80"] == 4700 and r["horizon_end_name"] == "March 2027"
    assert r["first_6"]["floor_80"] == 4900 and r["first_6"]["horizon_end_month"] == "September"
    assert r["likely_end_about"] == 5400


def test_personal_ranges_do_not_change_the_forecast_itself(history_data):
    before = rolling_forecast.build(history_data)
    fr.for_rolling(before, history_data, HISTORY_TODAY)
    assert before == rolling_forecast.build(history_data)


def test_joint_ranges_follow_the_shared_pot(history_data):
    """The same months read as a Joint profile: no plan, so the pot stays at 5 400
    and the bands match the Personal case above (floor 4 700, first 6 → 4 900)."""
    bill = joint.bill_forecast(history_data, HISTORY_TODAY)
    r = fr.for_joint(bill, history_data, HISTORY_TODAY)
    assert r is not None and r["line_key"] is None
    assert all(m["likely"] == 5400.0 for m in r["months"])
    assert r["floor_80"] == 4700 and r["first_6"]["floor_80"] == 4900


def test_half_width_formula_matches_by_hand():
    """Directly: 1.2816 × 100 × √9 = 384.48."""
    r = fr.build(months([1000.0] * 9), SIGMA_100)
    assert r is not None
    assert r["months"][8]["low80"] == round(1000 - 1.2816 * 100 * math.sqrt(9), 2) == 615.52


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@pytest.fixture
def ready():
    app = create_app()
    app.dependency_overrides[get_today] = lambda: TODAY
    client = TestClient(app)
    assert client.post("/api/setup", json={"year": 2026, "opening_balance": 1000, "start_month": 1}).status_code == 201
    return client


def test_endpoints_send_no_ranges_without_six_months_of_history(ready):
    """A fresh app has no finished months yet, so both screens hide the bands."""
    assert ready.get("/api/forecast").json()["ranges"] is None
    assert ready.get("/api/forecast?goals=false").json()["ranges"] is None
    ready.post("/api/profiles/active", json={"profile": "joint"})
    assert ready.post("/api/setup", json={"year": 2026, "opening_balance": 0, "start_month": 8}).status_code == 201
    assert ready.get("/api/joint/bill").json()["ranges"] is None


def test_forecast_endpoint_sends_ranges_with_enough_history(ready):
    """Six months of 2 000 cash in and 1 500 rent (Mar–Aug; today is 21 Oct) → each
    month keeps 500, so sigma 0 and every band equals the most-likely line."""
    for i, m in enumerate(range(2, 8)):
        ready.post("/api/2026/transactions", json={"type": "income", "date": f"2026-{m + 1:02d}-05", "amount": 2000, "cat": "Salary", "desc": ""})
        ready.post("/api/2026/transactions", json={"type": "expense", "date": f"2026-{m + 1:02d}-06", "amount": 1500, "cat": "Rent", "desc": ""})
    body = ready.get("/api/forecast").json()
    r = body["ranges"]
    assert r is not None and r["history_months"] == 6 and r["sigma"] == 0.0
    planned = [row for row in body["rows"] if not row["actual"]]
    assert [m["key"] for m in r["months"]] == [row["key"] for row in planned]
    assert [m["likely"] for m in r["months"]] == [row["values"]["plan"]["balance"] for row in planned]
