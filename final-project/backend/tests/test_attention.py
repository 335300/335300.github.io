"""The Overview's "Worth a look" banner (services/attention.py) and its move button.

Made-up November 2026 (30 days). Variable budgets: Eating out 100, Groceries 400,
Transport 150, Fun 100; Clothes has no budget; Rent is fixed (never looked at).

Rule: pace = spent ÷ days so far (today counts) × days in the month.
A budget is flagged when it is over, or its pace is over it, or 80 % or more is
used; the flagged one has the highest spent ÷ budget. needed = pace − budget,
rounded up to 5 €. Source = the other variable budget with the most room
(budget − pace), if that room is at least ``needed``.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_today
from app.app import create_app
from app.models import AppData, Category, Transaction, YearBudgets, YearCategories, YearData
from app.services import attention

DAY_20 = date(2026, 11, 20)   # 20 days so far, 10 left
NOV = 10


def spend(id: int, amount: float, cat: str, day: int = 3, month: int = NOV, one_off: bool = False) -> Transaction:
    return Transaction(id=id, type="expense", date=f"2026-{month + 1:02d}-{day:02d}", month=month, amount=amount,
                       cat=cat, one_off=one_off)


def make(spent: dict[str, float]) -> AppData:
    year = YearData(
        categories=YearCategories(expense=[
            Category(name="Rent", kind="fixed"), Category(name="Eating out"), Category(name="Groceries"),
            Category(name="Transport"), Category(name="Fun"), Category(name="Clothes"),
        ]),
        budgets=YearBudgets(expense={
            "Rent": [500.0] * 12, "Eating out": [100.0] * 12, "Groceries": [400.0] * 12,
            "Transport": [150.0] * 12, "Fun": [100.0] * 12,
        }),
        transactions=[spend(i + 1, amount, cat) for i, (cat, amount) in enumerate(spent.items())],
    )
    year.next_id = len(year.transactions) + 1
    d = AppData()
    d.years["2026"] = year
    return d


BASE = {"Rent": 500, "Groceries": 320, "Transport": 40, "Fun": 50, "Clothes": 30}


def test_on_pace_to_go_over_with_a_move():
    """Day 20 of 30.
    Eating out 90 of 100 = 90 %, pace 90 ÷ 20 × 30 = 135 -> over its pace; needed 135 − 100 = 35.
    Groceries 320 of 400 = 80 %, pace 480 (also a candidate, but 80 % < 90 %).
    Room (budget − pace): Transport 150 − 60 = 90 (>= 35), Fun 100 − 75 = 25 -> source Transport."""
    r = attention.build(make({**BASE, "Eating out": 90}), 2026, NOV, DAY_20)
    assert r["status"] == "problem" and r["reason"] == "pace"
    assert (r["category"], r["spent"], r["budget"], r["left"], r["used_pct"]) == ("Eating out", 90, 100, 10, 90.0)
    assert r["over"] is None   # 90 of 100: not over (only on pace to be)
    assert (r["pace"], r["days_in_month"], r["day"], r["days_left"]) == (135, 30, 20, 10)
    assert r["needed"] == 35
    assert (r["source"], r["source_budget"], r["source_spent"], r["source_pace"]) == ("Transport", 150, 40, 60)
    assert r["can_move"] is True and r["cannot_move_reason"] is None


def test_over_budget():
    """Eating out 112.40 of 100: over. Pace 112.40 ÷ 20 × 30 = 168.60; 68.60 rounds up to 70.
    Transport has room 90 >= 70."""
    r = attention.build(make({**BASE, "Eating out": 112.40}), 2026, NOV, DAY_20)
    assert (r["reason"], r["category"], r["left"], r["used_pct"]) == ("over", "Eating out", -12.4, 112.4)
    assert r["over"] == 12.4   # spent 112.40 − budget 100 = 12.40: how much over, as a positive amount
    assert (r["pace"], r["needed"], r["source"], r["can_move"]) == (168.6, 70, "Transport", True)


def test_no_budget_has_enough_room():
    """Eating out 150: pace 225, needed 125. Most room: Transport 90 < 125 -> no source, no move."""
    r = attention.build(make({**BASE, "Eating out": 150}), 2026, NOV, DAY_20)
    assert (r["category"], r["needed"], r["source"], r["can_move"]) == ("Eating out", 125, None, False)
    assert r["cannot_move_reason"] == "no_room"


def test_close_to_the_plan_but_on_pace():
    """Day 28: Eating out 85 of 100 = 85 %, pace 85 ÷ 28 × 30 = 91.07 (within). Groceries 320 = 80 %,
    pace 342.86. Highest use: Eating out, reason "close"; nothing needed, so no move."""
    r = attention.build(make({**BASE, "Eating out": 85}), 2026, NOV, date(2026, 11, 28))
    assert (r["status"], r["reason"], r["category"], r["used_pct"]) == ("problem", "close", "Eating out", 85.0)
    assert (r["pace"], r["needed"], r["source"], r["days_left"]) == (91.07, 0, None, 2)
    assert r["can_move"] is False and r["cannot_move_reason"] == "nothing_needed"


def test_all_clear():
    """Day 20: Eating out 50 (pace 75), Groceries 200 (pace 300), Transport 40, Fun 50 (pace 75):
    all under 80 % and on pace. Clothes (30, no budget) and Rent (fixed) are not looked at."""
    r = attention.build(make({**BASE, "Eating out": 50, "Groceries": 200}), 2026, NOV, DAY_20)
    assert r["status"] == "all_clear" and r["category"] is None and r["can_move"] is False
    assert r["over"] is None
    assert r["checked"] == 4


def test_boundary_80_percent():
    """Day 24 of 30: Eating out 80 of 100 = exactly 80 %, pace 80 ÷ 24 × 30 = 100 (= budget, not over)
    -> flagged "close". 79.99 -> 79.99 %, pace 99.99 -> not flagged."""
    day_24 = date(2026, 11, 24)
    quiet = {**BASE, "Groceries": 200}
    r = attention.build(make({**quiet, "Eating out": 80}), 2026, NOV, day_24)
    assert (r["category"], r["reason"], r["pace"]) == ("Eating out", "close", 100)
    assert attention.build(make({**quiet, "Eating out": 79.99}), 2026, NOV, day_24)["status"] == "all_clear"


def test_one_offs_count_against_the_budget():
    """A one-off of 60 in Eating out still uses the budget: 60 of 100 on day 20 -> pace 90, 60 % -> clear;
    plus 30 regular = 90 -> same as the first test."""
    d = make({**BASE, "Eating out": 30})
    d.years["2026"].transactions.append(spend(99, 60, "Eating out", one_off=True))
    assert attention.build(d, 2026, NOV, DAY_20)["category"] == "Eating out"


def test_only_the_current_month():
    d = make({**BASE, "Eating out": 90})
    assert attention.build(d, 2026, 9, DAY_20) is None      # October: past
    assert attention.build(d, 2026, 11, DAY_20) is None     # December: future
    assert attention.build(d, 2025, NOV, DAY_20) is None    # year not tracked


def test_no_move_for_linked_or_self_filling_cells():
    d = make({**BASE, "Eating out": 90})
    d.years["2026"].budgets.set_share("Transport", NOV, 5.0)
    r = attention.build(d, 2026, NOV, DAY_20)
    assert r["source"] == "Transport" and r["can_move"] is False and r["cannot_move_reason"] == "linked"
    d.years["2026"].budgets.set_share("Transport", NOV, None)
    r = attention.build(d, 2026, NOV, DAY_20, locked={"Eating out"})
    assert r["can_move"] is False and r["cannot_move_reason"] == "fills_itself"


@pytest.mark.parametrize(("value", "expected"), [(0, 0), (-3, 0), (35, 35), (35.01, 40), (68.6, 70), (4.99, 5)])
def test_round_up_to_5(value, expected):
    assert attention.round_up_5(value) == expected


def test_move_budget():
    """Move 35: Transport 150 -> 115, Eating out 100 -> 135; other months untouched."""
    d = make({})
    year = d.years["2026"]
    assert attention.move_budget(year, NOV, "Transport", "Eating out", 35) == {"Transport": 115, "Eating out": 135}
    assert year.budgets.expense["Transport"][NOV] == 115 and year.budgets.expense["Eating out"][NOV] == 135
    assert year.budgets.expense["Transport"][9] == 150


# -- HTTP -------------------------------------------------------------------------

@pytest.fixture
def client():
    from app.api import deps

    app = create_app()
    app.dependency_overrides[get_today] = lambda: DAY_20
    c = TestClient(app)
    repo = deps.get_store().repo()
    repo._data = make({**BASE, "Eating out": 90})
    repo.save()
    return c


def test_endpoint_and_move(client):
    r = client.get("/api/2026/attention", params={"month": NOV}).json()
    assert r["category"] == "Eating out" and r["needed"] == 35 and r["source"] == "Transport" and r["can_move"]
    assert client.get("/api/2026/attention", params={"month": 9}).json() is None

    stale = {"month": NOV, "from_cat": "Transport", "to_cat": "Eating out", "amount": 40}
    assert client.post("/api/2026/attention/move", json=stale).status_code == 409   # not what was offered

    body = client.post("/api/2026/attention/move", json={**stale, "amount": 35}).json()
    assert body["budgets"] == {"Transport": 115, "Eating out": 135}
    # Eating out now 90 of 135 (pace 135 = budget, 66.67 %) -> next look: Groceries (80 %, pace 480).
    assert body["attention"]["category"] == "Groceries"
    grid = client.get("/api/2026/budgets").json()["expense"]["rows"]
    rows = {row["cat"]: row["values"][NOV] for row in grid}
    assert rows["Transport"] == 115 and rows["Eating out"] == 135


def test_move_refused_for_a_linked_cell(client):
    from app.api import deps

    repo = deps.get_store().repo()
    repo.data.years["2026"].budgets.set_share("Transport", NOV, 5.0)
    repo.save()
    move = {"month": NOV, "from_cat": "Transport", "to_cat": "Eating out", "amount": 35}
    assert client.post("/api/2026/attention/move", json=move).status_code == 409
