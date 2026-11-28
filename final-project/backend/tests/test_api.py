"""HTTP layer: every router, the setup flow, prefs and auth."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_today
from app.app import create_app
from app.storage import AppStore

from .conftest import TODAY


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_today] = lambda: TODAY
    return TestClient(app)


@pytest.fixture
def ready(client):
    """A fresh app that went through the setup card."""
    r = client.post("/api/setup", json={"year": 2026, "opening_balance": 1000, "start_month": 1})
    assert r.status_code == 201
    return client


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["app"] == "Centwise Final Project"
    assert body["budget_warning_pct"] == 80


def test_first_run_needs_setup_and_writes_nothing(client, isolated_data_dir):
    body = client.get("/api/years").json()
    assert body["needs_setup"] is True and body["years"] == []
    assert body["today"] == "2026-10-21"
    assert not (isolated_data_dir / "data.json").exists()


def test_setup_creates_year_with_starter_categories(ready, isolated_data_dir):
    body = ready.get("/api/years").json()
    assert body["needs_setup"] is False
    assert body["years"][0]["opening_balance"] == 1000
    cats = ready.get("/api/2026/categories").json()
    assert {"name": "Rent", "kind": "fixed", "essential": False, "tax_relevant": False, "transactions": 0} in cats["expense"]
    assert any(c["name"] == "Salary" for c in cats["income"])
    assert (isolated_data_dir / "data.json").exists()
    assert ready.post("/api/setup", json={"year": 2026}).status_code == 409


def test_setup_without_starter_categories(client):
    client.post("/api/setup", json={"year": 2026, "starter_categories": False})
    assert client.get("/api/2026/categories").json() == {"expense": [], "income": []}


def test_transaction_crud_derives_month(ready):
    r = ready.post("/api/2026/transactions", json={
        "type": "expense", "date": "2026-03-14", "amount": 12.345, "cat": "Groceries", "desc": " Market "})
    assert r.status_code == 201
    created = r.json()
    assert created["month"] == 2 and created["amount"] == 12.35 and created["desc"] == "Market"

    r = ready.put(f"/api/2026/transactions/{created['id']}", json={
        "type": "expense", "date": "2026-04-01", "amount": 20, "cat": "Groceries"})
    assert r.json()["month"] == 3

    listing = ready.get("/api/2026/transactions", params={"month": 3}).json()
    assert listing["count"] == 1 and listing["total_expense"] == 20
    assert ready.delete(f"/api/2026/transactions/{created['id']}").status_code == 200
    assert ready.delete(f"/api/2026/transactions/{created['id']}").status_code == 404


def test_transaction_list_has_day_totals_for_the_calendar(ready):
    for t in ({"type": "expense", "date": "2026-03-14", "amount": 12.5, "cat": "Groceries"},
              {"type": "expense", "date": "2026-03-14", "amount": 7.25, "cat": "Groceries"},
              {"type": "income", "date": "2026-03-20", "amount": 100, "cat": "Salary"}):
        assert ready.post("/api/2026/transactions", json=t).status_code == 201
    days = ready.get("/api/2026/transactions", params={"month": 2}).json()["days"]
    assert days == {"2026-03-14": {"income": 0, "expense": 19.75}, "2026-03-20": {"income": 100, "expense": 0}}
    # Filters apply to the day totals too.
    assert ready.get("/api/2026/transactions", params={"month": 2, "type": "income"}).json()["days"] == {
        "2026-03-20": {"income": 100, "expense": 0}}


def test_bills_calendar_endpoint(ready):
    r = ready.post("/api/bills", json={"name": "Phone", "amount": 22, "category": "Bills", "rhythm_months": 1,
                                        "next_due": "2026-10-25", "match": "vodafone"})
    assert r.status_code == 201
    body = ready.get("/api/bills/calendar/2026/9").json()
    assert body["month"] == 9 and body["today"] == "2026-10-21"
    assert [(b["due"], b["paid"], b["ready"]) for b in body["bills"]] == [("2026-10-25", False, True)]
    assert body["total_due"] == 22 and body["goals"] == []
    assert ready.get("/api/bills/calendar/2026/12").status_code == 422


def test_transaction_rejects_wrong_year_and_bad_date(ready):
    r = ready.post("/api/2026/transactions", json={"type": "expense", "date": "2025-12-31", "amount": 5, "cat": "X"})
    assert r.status_code == 422 and "not in 2026" in r.json()["detail"]
    r = ready.post("/api/2026/transactions", json={"type": "expense", "date": "2026-02-30", "amount": 5, "cat": "X"})
    assert r.status_code == 422
    r = ready.post("/api/2026/transactions", json={"type": "expense", "date": "2026-02-03", "amount": 0, "cat": "X"})
    assert r.status_code == 422


def test_new_category_from_transaction_is_budgetable(ready):
    ready.post("/api/2026/transactions", json={"type": "expense", "date": "2026-03-01", "amount": 5, "cat": "Pets"})
    rows = {r["cat"]: r for r in ready.get("/api/2026/budgets").json()["expense"]["rows"]}
    assert rows["Pets"]["values"] == [0.0] * 12


def test_bulk_is_all_or_nothing(ready):
    good = {"type": "expense", "date": "2026-03-01", "amount": 5, "cat": "Groceries"}
    bad = {**good, "date": "2027-01-01"}
    r = ready.post("/api/2026/transactions/bulk", json={"transactions": [good, bad]})
    assert r.status_code == 422 and r.json()["detail"].startswith("Row 2")
    assert ready.get("/api/2026/transactions").json()["count"] == 0

    r = ready.post("/api/2026/transactions/bulk", json={"transactions": [good, good]})
    assert r.status_code == 201
    ids = [t["id"] for t in r.json()["created"]]
    assert len(set(ids)) == 2
    single = ready.post("/api/2026/transactions", json=good).json()
    assert single["id"] not in ids


def test_search_filters(ready):
    for d, cat, desc in [("2026-03-01", "Groceries", "Bakery"), ("2026-03-02", "Leisure", "Cinema")]:
        ready.post("/api/2026/transactions", json={"type": "expense", "date": d, "amount": 5, "cat": cat, "desc": desc})
    assert ready.get("/api/2026/transactions", params={"q": "bak"}).json()["count"] == 1
    assert ready.get("/api/2026/transactions", params={"cat": "Leisure"}).json()["count"] == 1
    assert ready.get("/api/2026/transactions", params={"type": "income"}).json()["count"] == 0


def test_unknown_year_is_404(ready):
    assert ready.get("/api/1999/transactions").status_code == 404


def test_category_rename_moves_history_and_delete_guard(ready):
    ready.post("/api/2026/transactions", json={"type": "expense", "date": "2026-03-01", "amount": 5, "cat": "Leisure"})
    ready.put("/api/2026/budgets", json={"kind": "expense", "cat": "Leisure", "month": 3, "value": 80})
    r = ready.patch("/api/2026/categories/expense/Leisure", json={"name": "Fun", "category_kind": "fixed"})
    assert r.json() == {"cat": "Fun", "kind": "fixed", "essential": False, "tax_relevant": False}
    assert ready.get("/api/2026/transactions").json()["transactions"][0]["cat"] == "Fun"
    rows = {r["cat"]: r for r in ready.get("/api/2026/budgets").json()["expense"]["rows"]}
    assert rows["Fun"]["values"][3] == 80 and "Leisure" not in rows

    assert ready.patch("/api/2026/categories/expense/Fun", json={"name": "Rent"}).status_code == 409
    assert ready.delete("/api/2026/categories/expense/Fun").status_code == 409
    assert ready.delete("/api/2026/categories/expense/Health").status_code == 200
    assert ready.post("/api/2026/categories", json={"kind": "expense", "name": "Rent"}).status_code == 409


def test_category_names_with_slash(ready):
    ready.post("/api/2026/categories", json={"kind": "expense", "name": "Phone/Data"})
    assert ready.patch("/api/2026/categories/expense/Phone/Data", json={"category_kind": "fixed"}).status_code == 200
    assert ready.delete("/api/2026/categories/expense/Phone/Data").status_code == 200


def test_budget_cell_and_unknown_category(ready):
    r = ready.put("/api/2026/budgets", json={"kind": "expense", "cat": "Rent", "month": 5, "value": 450.555})
    assert r.json()["values"][5] == 450.56 and r.json()["monthly_total"] == 450.56
    saved = ready.get("/api/2026/budgets").json()["saved"]
    assert saved["planned"][5] == -450.56 and saved["actual"] == [None] * 12
    assert ready.put("/api/2026/budgets", json={"kind": "expense", "cat": "Nope", "month": 5, "value": 1}).status_code == 404


def test_dashboard_and_projection(ready):
    ready.put("/api/2026/budgets", json={"kind": "income", "cat": "Salary", "month": 4, "value": 2000})
    ready.post("/api/2026/transactions", json={"type": "income", "date": "2026-03-01", "amount": 2000, "cat": "Salary"})
    ready.post("/api/2026/transactions", json={"type": "expense", "date": "2026-03-02", "amount": 700, "cat": "Rent"})
    d = ready.get("/api/2026/dashboard", params={"month": 2}).json()
    assert d["kpis"]["current_balance"] == 2300 and d["kpis"]["savings"] == 1300
    assert d["costs"]["fixed"]["total"] == 700
    assert d["trend"][0]["month_name"] == "Mar"
    assert ready.get("/api/years").json()["settings"]["last_month"] == 2

    p = ready.get("/api/2026/projection").json()
    assert p["rows"][0]["actual"] is True
    may = next(r for r in p["rows"] if r["month"] == 4)
    assert may["income"] == 2000 and may["actual"] is False


def test_year_patch_and_create(ready):
    r = ready.patch("/api/years/2026", json={"opening_balance": 2500.5, "start_month": -1})
    assert r.json()["opening_balance"] == 2500.5 and r.json()["start_month"] == -1
    ready.post("/api/2026/transactions", json={"type": "expense", "date": "2026-03-01", "amount": 5, "cat": "Rent"})
    assert ready.patch("/api/years/2026", json={"start_month": 2}).status_code == 409

    r = ready.post("/api/years", json={"year": 2027})
    assert r.status_code == 201 and r.json()["copied_from"] == 2026
    assert r.json()["created"]["opening_balance"] == 2495.5
    assert ready.post("/api/years", json={"year": 2027}).status_code == 409


def test_goals_flow(ready):
    # Budget 2000 income, 1500 expense for every remaining month -> expects 500/month.
    for m in range(12):
        ready.put("/api/2026/budgets", json={"kind": "income", "cat": "Salary", "month": m, "value": 2000})
        ready.put("/api/2026/budgets", json={"kind": "expense", "cat": "Rent", "month": m, "value": 1500})

    r = ready.post("/api/goals", json={"name": " Laptop ", "target_amount": 900, "target_date": "2027-03-31"})
    assert r.status_code == 201
    goal = r.json()
    assert goal["name"] == "Laptop" and goal["created_date"] == "2026-10-21"

    c = ready.post(f"/api/goals/{goal['id']}/contributions", json={"date": "2026-10-01", "amount": 300})
    assert c.status_code == 201

    listing = ready.get("/api/goals", params={"year": 2026}).json()
    # No transactions recorded: saved 0, 300 assigned -> 300 over.
    assert listing["allocation"] == {
        "year": 2026, "saved_this_year": 0.0, "assigned": 300.0, "unassigned": -300.0, "over_assigned": True}
    g = listing["goals"][0]
    assert g["saved"] == 300 and g["required_monthly_pace"] == 100 and g["status"] == "on_track"
    assert listing["summary"]["expected_monthly_savings"] == 500

    assert ready.patch(f"/api/goals/{goal['id']}", json={"target_amount": -1}).status_code == 422
    r = ready.patch(f"/api/goals/{goal['id']}", json={"target_amount": 400, "notes": "x"})
    assert r.json()["target_amount"] == 400 and r.json()["notes"] == "x"
    assert ready.get("/api/goals").json()["goals"][0]["remaining"] == 100

    assert ready.delete(f"/api/goals/{goal['id']}/contributions/{c.json()['id']}").status_code == 200
    assert ready.delete(f"/api/goals/{goal['id']}/contributions/999").status_code == 404
    assert ready.delete(f"/api/goals/{goal['id']}").status_code == 200
    assert ready.get("/api/goals").json()["goals"] == []
    assert ready.patch("/api/goals/42", json={"name": "x"}).status_code == 404


def test_goal_rejects_bad_input(ready):
    assert ready.post("/api/goals", json={"name": "", "target_amount": 5, "target_date": "2027-01-01"}).status_code == 422
    assert ready.post("/api/goals", json={"name": "A", "target_amount": 0, "target_date": "2027-01-01"}).status_code == 422
    assert ready.post("/api/goals", json={"name": "A", "target_amount": 5, "target_date": "soon"}).status_code == 422


def test_goals_without_year(client):
    body = client.get("/api/goals").json()
    assert body["year"] is None and body["summary"]["expected_monthly_savings"] == 0


# -- prefs --------------------------------------------------------------------

def test_profiles_listing(client):
    body = client.get("/api/profiles").json()
    assert body["active"] == "personal"
    assert body["profiles"] == [{"id": "personal", "label": "Personal"}, {"id": "joint", "label": "Joint"}]


def test_joint_profile_is_separate_from_personal(ready, isolated_data_dir):
    ready.post("/api/2026/transactions", json={"type": "expense", "date": "2026-10-20", "amount": 9.99, "cat": "Rent"})
    personal_file = isolated_data_dir / "data.json"
    before = personal_file.read_text()

    assert ready.post("/api/profiles/active", json={"profile": "joint"}).json()["active"] == "joint"
    assert ready.get("/api/years").json()["needs_setup"] is True  # starts empty
    ready.post("/api/setup", json={"year": 2026, "opening_balance": 500})
    ready.post("/api/2026/transactions", json={"type": "expense", "date": "2026-10-21", "amount": 80, "cat": "Groceries"})
    joint_file = isolated_data_dir / "joint" / "data.json"
    assert joint_file.exists()
    assert len(json.loads(joint_file.read_text())["years"]["2026"]["transactions"]) == 1
    assert personal_file.read_text() == before  # personal data untouched

    # The choice is remembered across restarts.
    assert AppStore().active == "joint"

    ready.post("/api/profiles/active", json={"profile": "personal"})
    assert ready.get("/api/2026/transactions").json()["count"] == 1
    assert ready.get("/api/years").json()["years"][0]["opening_balance"] == 1000


def test_unknown_profile(client):
    assert client.post("/api/profiles/active", json={"profile": "nobody"}).status_code == 404
    assert client.post("/api/profiles/active", json={"profile": "../etc"}).status_code == 404


def test_prefs_default_and_persist(client, isolated_data_dir):
    calendar = {"appearance": "system", "calendar_hidden": [], "calendar_push": False, "calendar_own_ids": {},
                "calendar_last_sync": None}
    assert client.get("/api/prefs").json() == {"show_savings_tile": False, **calendar}
    client.post("/api/profiles/active", json={"profile": "joint"})
    after = {"show_savings_tile": True, **calendar}
    assert client.patch("/api/prefs", json={"show_savings_tile": True}).json() == after
    state = json.loads((isolated_data_dir / "app-state.json").read_text())
    assert state == {"profile": "joint", "prefs": after}
    # A fresh start reads it back.
    assert AppStore().prefs() == after
    assert client.patch("/api/prefs", json={"unknown": 1}).status_code == 422


# -- auth -----------------------------------------------------------------------

def test_token_required_when_configured(client, monkeypatch):
    monkeypatch.setenv("CENTWISE_TOKEN", "secret")
    assert client.get("/api/years").status_code == 401
    assert client.get("/api/years", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/years", headers={"Authorization": "Bearer secret"}).status_code == 200
    assert client.get("/health").status_code == 200  # readiness probe stays open


# -- investment plans ---------------------------------------------------------

LAND = {
    "name": "Land in Paraguay", "category": "Land", "unit": "cuota", "local_currency": "Gs",
    "installment_amount": 2170000, "total_installments": 130, "paid_before": 15, "cost_per_installment": 340,
}


def test_investment_plan_flow(ready):
    ready.post("/api/years", json={"year": 2027})
    r = ready.post("/api/investments", json=LAND)
    assert r.status_code == 201 and r.json()["paid"] == 15 and r.json()["remaining"] == 115
    # The category now exists as an investment in every year.
    for year in (2026, 2027):
        cats = ready.get(f"/api/{year}/categories").json()["expense"]
        assert {"name": "Land", "kind": "investment", "essential": False, "tax_relevant": False, "transactions": 0} in cats
    assert ready.post("/api/investments", json=LAND).status_code == 409           # category already taken
    assert ready.post("/api/investments", json={**LAND, "category": "X", "paid_before": 131}).status_code == 409

    # A new payment into the plan's category counts as one cuota unless it says otherwise.
    pay = {"type": "expense", "date": "2026-10-05", "amount": 332, "cat": "Land", "desc": "cuota"}
    one = ready.post("/api/2026/transactions", json=pay).json()
    assert one["installments"] == 1
    two = ready.post("/api/2026/transactions", json={**pay, "installments": 2}).json()
    assert two["installments"] == 2
    bulk = ready.post("/api/2026/transactions/bulk", json={"transactions": [pay]}).json()
    assert bulk["created"][0]["installments"] == 1
    # Other categories never carry a count, and an edit keeps what it is given.
    other = ready.post("/api/2026/transactions", json={**pay, "cat": "Groceries", "installments": 3}).json()
    assert other["installments"] is None
    edited = ready.put(f"/api/2026/transactions/{one['id']}", json={**pay, "installments": 0}).json()
    assert edited["installments"] == 0

    plans = ready.get("/api/investments?year=2026&month=9").json()
    plan = plans["plans"][0]
    assert plan["paid"] == 18 and plan["invested_month"] == 996 and plans["invested_month"] == 996
    assert plan["paid_this_month"] is True and plan["expected_end"] == "2036-02"

    dash = ready.get("/api/2026/dashboard?month=9").json()
    assert dash["kpis"]["invested"] == 996 and dash["kpis"]["spent"] == 332
    assert dash["kpis"]["cash_out"] == 1328
    assert dash["investments"]["plans"][0]["id"] == plan["id"]
    assert "Land" not in [r["cat"] for r in dash["costs"]["ranked"]]

    patched = ready.patch(f"/api/investments/{plan['id']}", json={"paid_before": 16, "cost_per_installment": 0}).json()
    assert patched["paid"] == 19 and patched["cost_per_installment"] is None and patched["value_at_cost"] is None
    assert ready.patch(f"/api/investments/{plan['id']}", json={"total_installments": 3}).status_code == 409
    assert ready.patch("/api/investments/99", json={"name": "x"}).status_code == 404


def test_plan_category_rules(ready):
    ready.post("/api/years", json={"year": 2027})
    plan = ready.post("/api/investments", json=LAND).json()
    ready.post("/api/2026/transactions", json={"type": "expense", "date": "2026-10-05", "amount": 332, "cat": "Land"})
    # It cannot stop being an investment or be deleted while the plan uses it …
    assert ready.patch("/api/2026/categories/expense/Land", json={"category_kind": "variable"}).status_code == 409
    assert ready.delete("/api/2027/categories/expense/Land").status_code == 409
    # … and a rename reaches every year, so the plan keeps finding its payments.
    assert ready.patch("/api/2026/categories/expense/Land", json={"name": "Terreno"}).status_code == 200
    assert any(c["name"] == "Terreno" for c in ready.get("/api/2027/categories").json()["expense"])
    after = ready.get("/api/investments?year=2026&month=9").json()["plans"][0]
    assert after["category"] == "Terreno" and after["paid"] == 16

    assert ready.delete(f"/api/investments/{plan['id']}").json() == {"deleted": plan["id"]}
    assert ready.get("/api/investments").json()["plans"] == []
    # The payments stay; the category is free again.
    assert ready.get("/api/2026/transactions?cat=Terreno").json()["count"] == 1
    assert ready.patch("/api/2026/categories/expense/Terreno", json={"category_kind": "fixed"}).status_code == 200


def test_investment_needs_a_year(client):
    assert client.post("/api/investments", json=LAND).status_code == 409
    assert client.get("/api/investments").json()["plans"] == []


# -- distributing a month's savings -------------------------------------------

def test_distribution_flow(ready):
    ready.post("/api/2026/transactions", json={"type": "income", "date": "2026-10-01", "amount": 2000, "cat": "Salary"})
    ready.post("/api/2026/transactions", json={"type": "expense", "date": "2026-10-02", "amount": 500, "cat": "Rent"})
    a = ready.post("/api/goals", json={"name": "Laptop", "target_amount": 900, "target_date": "2027-03-31"}).json()
    b = ready.post("/api/goals", json={"name": "Trip", "target_amount": 400, "target_date": "2026-12-31"}).json()

    dash = ready.get("/api/2026/dashboard?month=9").json()["distribution"]
    assert dash["saved"] == 1500 and dash["left_to_assign"] == 1500
    # Suggested: each goal's monthly pace, nearest deadline first (Trip 400/3, Laptop 900/6).
    assert [(s["name"], s["suggested"]) for s in dash["suggested"]] == [("Trip", 133.33), ("Laptop", 150.0)]

    body = {"month": 9, "allocations": [{"goal_id": a["id"], "amount": 300}, {"goal_id": b["id"], "amount": 0}]}
    preview = ready.post("/api/2026/distribution/preview", json=body).json()
    assert preview["adding"] == 300 and preview["left_after"] == 1200 and preview["over"] is False
    too_much = {"month": 9, "allocations": [{"goal_id": a["id"], "amount": 1600}]}
    assert ready.post("/api/2026/distribution/preview", json=too_much).json()["over"] is True
    assert ready.get("/api/goals").json()["goals"][0]["saved"] == 0          # a preview saves nothing

    done = ready.post("/api/2026/distribution", json=body)
    assert done.status_code == 201
    assert done.json()["assigned"] == 1 and done.json()["date"] == "2026-10-21"   # today, the month is running
    assert done.json()["left_to_assign"] == 1200
    after = ready.get("/api/2026/dashboard?month=9").json()
    assert after["distribution"]["to_goals"] == 300
    assert after["kpis"]["earmarked"] == 300 and after["kpis"]["free_balance"] == after["kpis"]["current_balance"] - 300
    laptop = next(g for g in after["goals"]["goals"] if g["name"] == "Laptop")
    assert laptop["saved"] == 300 and laptop["added_this_month"] == 300

    # A finished month is dated on its last day; a future one is refused.
    ready.post("/api/2026/distribution", json={"month": 8, "allocations": [{"goal_id": b["id"], "amount": 10}]})
    trip = next(g for g in ready.get("/api/goals").json()["goals"] if g["name"] == "Trip")
    assert trip["contributions"][0]["date"] == "2026-09-30"
    assert trip["contributions"][0]["note"] == "September 2026 distribution"
    assert ready.post("/api/2026/distribution", json={**body, "month": 10}).status_code == 409
    assert ready.post("/api/2026/distribution", json={"month": 9, "allocations": []}).status_code == 409
    assert ready.post("/api/2026/distribution", json={"month": 9, "allocations": [{"goal_id": 99, "amount": 5}]}).status_code == 404
    ready.patch(f"/api/goals/{b['id']}", json={"status": "completed"})
    assert ready.post("/api/2026/distribution", json={"month": 9, "allocations": [{"goal_id": b["id"], "amount": 5}]}).status_code == 409


def test_budgets_show_the_usual_month(ready):
    for month, amount in (("08", 100), ("09", 300), ("10", 999)):
        ready.post("/api/2026/transactions", json={
            "type": "expense", "date": f"2026-{month}-05", "amount": amount, "cat": "Groceries"})
    body = ready.get("/api/2026/budgets").json()
    row = next(r for r in body["expense"]["rows"] if r["cat"] == "Groceries")
    # Six finished months before October (April-September; tracking began in March).
    # October is still running (today is 21 Oct) and is left out; empty months count as zero.
    # The usual month is the median of 0, 0, 0, 0, 100, 300 -> 0.
    assert body["usual_months"] == 6 and row["usual"] == 0
    for month in ("04", "05", "06", "07"):
        ready.post("/api/2026/transactions", json={
            "type": "expense", "date": f"2026-{month}-05", "amount": 200, "cat": "Groceries"})
    row = next(r for r in ready.get("/api/2026/budgets").json()["expense"]["rows"] if r["cat"] == "Groceries")
    assert row["usual"] == 200  # median of 200, 200, 200, 200, 100, 300
    assert next(r for r in body["expense"]["rows"] if r["cat"] == "Rent")["usual"] == 0


# ---------------------------------------------------------------------------
# Phase 1: income calendar, forecast, import, payee rules, emergency fund
# ---------------------------------------------------------------------------

import base64  # noqa: E402
from pathlib import Path  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "2026-11-13-sparkasse-camt-v8-synthetic.csv"

INCOME_SETTINGS = {
    "hourly_rate": 20,
    "hours_lecture_week": 20,
    "hours_break_week": 40,
    "lecture_periods": [{"start": "2026-10-01", "end": "2027-01-15"}],
    "salary_category": "Salary",
    "contract_pay_lag": 1,
    "extra_hours_delay": 1,
    "health_category": "Insurance",
    "net_method": "payslips",
    "scenarios": [
        {"name": "Best case", "job_end": "2027-08-31", "health_insurance_monthly": 250},
        {"name": "Worst case", "job_end": "2028-01-31", "health_insurance_monthly": 250},
    ],
}


def test_income_calendar_flow(ready):
    assert ready.get("/api/income").json() == {"plan": None, "calendar": None, "active": False}
    body = ready.put("/api/income/settings", json=INCOME_SETTINGS).json()
    assert body["active"] is False and "no_payslips" in body["calendar"]["warnings"]
    assert len(body["calendar"]["rows"]) == 12 and body["calendar"]["rows"][0]["key"] == "2026-10"
    body = ready.post("/api/income/payslips", json={"month": "2026-10", "gross": 1000, "net": 900}).json()
    assert body["active"] is True and body["plan"]["payslips"][0]["id"] == 1
    # Settings can change without losing payslips.
    body = ready.put("/api/income/settings", json={**INCOME_SETTINGS, "hourly_rate": 22}).json()
    assert body["plan"]["hourly_rate"] == 22 and len(body["plan"]["payslips"]) == 1
    assert ready.delete("/api/income/payslips/1").json()["plan"]["payslips"] == []
    assert ready.delete("/api/income/payslips/1").status_code == 404


def test_income_settings_are_validated(ready):
    bad_period = {**INCOME_SETTINGS, "lecture_periods": [{"start": "2027-01-15", "end": "2026-10-01"}]}
    assert ready.put("/api/income/settings", json=bad_period).status_code == 422
    too_many = {**INCOME_SETTINGS, "scenarios": INCOME_SETTINGS["scenarios"] * 2}
    assert ready.put("/api/income/settings", json=too_many).status_code == 422
    assert ready.post("/api/income/payslips", json={"month": "2026-13", "gross": 1, "net": 1}).status_code == 422
    assert ready.post("/api/income/payslips", json={"month": "2026-10", "gross": 1, "net": 2}).status_code == 422


def test_rolling_forecast_endpoint(ready):
    ready.post("/api/2026/transactions", json={"type": "income", "date": "2026-10-05", "amount": 2000, "cat": "Salary"})
    body = ready.get("/api/forecast").json()
    assert body["start"] == "2026-11" and body["end_name"] == "October 2027"
    assert [line["key"] for line in body["lines"]] == ["plan"]
    ready.put("/api/income/settings", json=INCOME_SETTINGS)
    ready.post("/api/income/payslips", json={"month": "2026-10", "gross": 1000, "net": 900})
    body = ready.get("/api/forecast").json()
    assert [line["name"] for line in body["lines"]] == ["Best case", "Worst case"]


def _preview(client):
    content = base64.b64encode(FIXTURE.read_bytes()).decode()
    return client.post("/api/import/preview", json={"filename": FIXTURE.name, "content_base64": content})


def test_import_preview_and_commit(ready):
    r = _preview(ready)
    assert r.status_code == 200
    body = r.json()
    assert (body["new"], body["skipped"]) == (7, 2)
    keep = [
        {k: row[k] for k in ("date", "type", "amount", "cat", "desc", "payee", "bank_ref")}
        for row in body["rows"] if row["status"] == "new"
    ]
    assert ready.post("/api/import/commit", json={"rows": keep}).json() == {"created": 7, "skipped": 0}
    # Importing the same file again finds everything.
    again = _preview(ready).json()
    assert again["new"] == 0
    assert ready.get("/api/2026/categories").json()["expense"][-1]["name"] == "Uncategorised"


def test_import_rejects_other_files(ready):
    bad = base64.b64encode(b"just some text").decode()
    r = ready.post("/api/import/preview", json={"content_base64": bad})
    assert r.status_code == 422 and "CSV-CAMT" in r.json()["detail"]
    assert ready.post("/api/import/preview", json={"content_base64": "%%%"}).status_code == 422
    row = {"date": "2025-01-01", "type": "expense", "amount": 1, "cat": "X"}
    assert ready.post("/api/import/commit", json={"rows": [row]}).status_code == 422


def test_payee_rules_flow(ready):
    body = ready.post("/api/rules", json={"contains": "Muster Markt", "category": "Groceries"}).json()
    assert body["rules"][0]["id"] == 1
    preview = _preview(ready).json()
    assert next(r for r in preview["rows"] if r["line"] == 2)["cat"] == "Groceries"
    body = ready.put("/api/rules/1", json={"contains": "muster", "category": "Shopping", "tx_type": "expense"}).json()
    assert body["rules"][0]["category"] == "Shopping"
    assert ready.post("/api/rules", json={"contains": "  ", "category": "X"}).status_code == 422
    assert ready.delete("/api/rules/1").json()["rules"] == []
    assert ready.delete("/api/rules/1").status_code == 404


def test_rule_suggestion_and_dismiss(ready):
    for day in ("03", "10"):
        ready.post("/api/import/commit", json={"rows": [{
            "date": f"2026-10-{day}", "type": "expense", "amount": 5, "cat": "Groceries", "payee": "Kiosk Beispiel"}]})
    (s,) = ready.get("/api/rules").json()["suggestions"]
    assert s["contains"] == "kiosk beispiel" and s["category"] == "Groceries"
    assert ready.post("/api/rules/suggestions/dismiss", json={"contains": "kiosk beispiel"}).json()["suggestions"] == []


def test_emergency_fund_goal_and_essential_category(ready):
    r = ready.patch("/api/2026/categories/expense/Rent", json={"essential": True})
    assert r.json()["essential"] is True
    a = ready.post("/api/goals", json={"name": "Emergency", "target_amount": 3000, "target_date": "2027-12-31",
                                       "emergency_fund": True}).json()
    b = ready.post("/api/goals", json={"name": "Other", "target_amount": 100, "target_date": "2027-12-31"}).json()
    ready.patch(f"/api/goals/{b['id']}", json={"emergency_fund": True})
    goals = {g["id"]: g for g in ready.get("/api/goals?year=2026").json()["goals"]}
    assert goals[a["id"]]["emergency_fund"] is False and goals[b["id"]]["emergency_fund"] is True
    ready.post("/api/2026/transactions", json={"type": "expense", "date": "2026-10-02", "amount": 600, "cat": "Rent"})
    ready.post(f"/api/goals/{b['id']}/contributions", json={"date": "2026-10-03", "amount": 1200})
    tile = ready.get("/api/2026/dashboard?month=9").json()["emergency"]
    assert tile["state"] == "ready" and tile["months_covered"] == 2.0 and tile["status"] == "Building"


def test_phase_1_data_stays_in_its_profile(ready):
    ready.put("/api/income/settings", json=INCOME_SETTINGS)
    ready.post("/api/rules", json={"contains": "rewe", "category": "Groceries"})
    ready.post("/api/profiles/active", json={"profile": "joint"})
    assert ready.get("/api/income").json()["plan"] is None
    assert ready.get("/api/rules").json()["rules"] == []
    ready.post("/api/profiles/active", json={"profile": "personal"})
    assert ready.get("/api/income").json()["plan"]["hourly_rate"] == 20
    assert len(ready.get("/api/rules").json()["rules"]) == 1


# ---------------------------------------------------------------------------
# Phase 2
# ---------------------------------------------------------------------------

def test_one_off_is_saved_and_kept_through_an_edit(ready):
    r = ready.post("/api/2026/transactions", json={
        "type": "expense", "date": "2026-10-05", "amount": 900, "cat": "Shopping", "one_off": True})
    tx_id = r.json()["id"]
    assert r.json()["one_off"] is True
    r = ready.put(f"/api/2026/transactions/{tx_id}", json={
        "type": "expense", "date": "2026-10-06", "amount": 950, "cat": "Shopping", "one_off": True})
    assert r.json()["one_off"] is True and r.json()["amount"] == 950
    r = ready.put(f"/api/2026/transactions/{tx_id}", json={
        "type": "expense", "date": "2026-10-06", "amount": 950, "cat": "Shopping"})
    assert r.json()["one_off"] is False


def test_sinking_fund_flow(ready):
    bad = {"name": "Fee", "target_amount": 220, "target_date": "2027-02-01", "goal_type": "sinking"}
    assert ready.post("/api/goals", json=bad).status_code == 422
    g = ready.post("/api/goals", json={**bad, "repeat_months": 6}).json()
    assert g["goal_type"] == "sinking" and g["repeat_months"] == 6
    ready.post(f"/api/goals/{g['id']}/contributions", json={"date": "2026-10-01", "amount": 300})
    r = ready.post(f"/api/goals/{g['id']}/pay", json={"date": "2026-10-15", "amount": 220, "category": "Tuition"})
    assert r.status_code == 200
    body = r.json()
    assert body["from_fund"] == 220 and body["next_due"] == "2027-08-01"
    goal = next(x for x in ready.get("/api/goals?year=2026").json()["goals"] if x["id"] == g["id"])
    assert goal["saved"] == 80 and goal["monthly_set_aside"] == 36.67
    assert ready.get("/api/2026/dashboard?month=9").json()["paid_from_funds"]["total"] == 220
    # Deleting the bill gives the money back.
    ready.delete(f"/api/2026/transactions/{body['transaction']['id']}")
    goal = next(x for x in ready.get("/api/goals?year=2026").json()["goals"] if x["id"] == g["id"])
    assert goal["saved"] == 300
    # Switching back to a one-time goal clears the rhythm; asking for a rhythm-less fund is refused.
    assert ready.patch(f"/api/goals/{g['id']}", json={"goal_type": "one_time"}).json()["repeat_months"] is None
    r = ready.patch(f"/api/goals/{g['id']}", json={"goal_type": "sinking"})
    assert r.status_code == 422 and "how often" in r.json()["detail"]


def test_recurring_bills_flow(ready):
    body = {"name": "Phone", "amount": 22, "category": "Phone & Internet", "rhythm_months": 1,
            "next_due": "2026-10-25", "match": "vodafone"}
    assert ready.post("/api/bills", json={**body, "rhythm_months": 2}).status_code == 422
    assert ready.post("/api/bills", json={**body, "goal_id": 99}).status_code == 422
    view = ready.post("/api/bills", json=body).json()
    assert view["bills"][0]["due"] == "2026-10-25"
    # Today is 21 Oct: the bill is due in 4 days and shows on the Overview.
    dash = ready.get("/api/2026/dashboard?month=9").json()
    assert dash["upcoming"]["items"][0]["name"] == "Phone" and dash["upcoming"]["items"][0]["days_left"] == 4
    ready.post("/api/2026/transactions", json={"type": "expense", "date": "2026-10-24", "amount": 22,
                                               "cat": "Phone & Internet", "desc": "Vodafone"})
    assert ready.get("/api/bills").json()["bills"][0]["due"] == "2026-11-25"
    view = ready.put("/api/bills/1", json={**body, "amount": 25}).json()
    assert view["bills"][0]["amount"] == 25
    assert ready.delete("/api/bills/1").json()["bills"] == []
    assert ready.delete("/api/bills/1").status_code == 404


def test_bill_suggestion_dismiss(ready):
    for month in ("07", "08", "09"):
        ready.post("/api/2026/transactions", json={"type": "expense", "date": f"2026-{month}-03", "amount": 9.99,
                                                   "cat": "Subscriptions", "desc": "Streaming Dienst"})
    (s,) = ready.get("/api/bills").json()["suggestions"]
    assert s["key"] == "streaming dienst"
    assert ready.post("/api/bills/suggestions/dismiss", json={"key": s["key"]}).json()["suggestions"] == []


def _joint_ready(client):
    client.post("/api/profiles/active", json={"profile": "joint"})
    assert client.post("/api/setup", json={"year": 2026, "opening_balance": 0}).status_code == 201
    client.post("/api/profiles/active", json={"profile": "personal"})


def test_transfer_to_joint_flow(ready):
    _joint_ready(ready)
    r = ready.post("/api/joint/transfer", json={"date": "2026-10-01", "amount": 300, "note": "October"})
    assert r.status_code == 201
    personal_id = r.json()["personal"]["id"]
    # Editing the Personal half changes the Joint half.
    ready.put(f"/api/2026/transactions/{personal_id}", json={
        "type": "expense", "date": "2026-10-02", "amount": 320, "cat": "Transfer to Joint", "desc": "October"})
    ready.post("/api/profiles/active", json={"profile": "joint"})
    (into,) = ready.get("/api/2026/transactions").json()["transactions"]
    assert into["amount"] == 320 and into["date"] == "2026-10-02" and into["type"] == "income"
    # Deleting the Joint half deletes the Personal half.
    ready.delete(f"/api/2026/transactions/{into['id']}")
    ready.post("/api/profiles/active", json={"profile": "personal"})
    assert ready.get("/api/2026/transactions").json()["count"] == 0


def test_transfer_needs_both_profiles_to_track_the_month(ready):
    r = ready.post("/api/joint/transfer", json={"date": "2026-10-01", "amount": 300})
    assert r.status_code == 422 and "Joint" in r.json()["detail"]
    assert ready.get("/api/2026/transactions").json()["count"] == 0


def test_fair_share_and_settle_up_flow(ready):
    _joint_ready(ready)
    ready.post("/api/profiles/active", json={"profile": "joint"})
    ready.post("/api/2026/transactions", json={"type": "expense", "date": "2026-10-05", "amount": 1000, "cat": "Rent"})
    body = ready.put("/api/joint/fair-share", json={"name_a": "Ana", "name_b": "Ben", "income_a": 2000, "income_b": 3000}).json()
    assert body["fair_share"]["share_a_pct"] == 40
    body = ready.get("/api/joint?year=2026&month=9").json()
    assert body["fair_share"]["shared_costs"] == 1000 and body["fair_share"]["amount_b"] == 600
    ready.post("/api/joint/shared", json={"date": "2026-10-03", "desc": "Groceries", "amount": 100, "paid_by": "a"})
    body = ready.post("/api/joint/settlements", json={"date": "2026-10-09", "from_person": "b", "amount": 20}).json()
    assert body["settle_up"]["amount"] == 40 and body["settle_up"]["text"] == "Ben owes Ana"
    assert ready.post("/api/joint/shared", json={"date": "2026-10-03", "amount": 5, "paid_by": "c"}).status_code == 422
    assert ready.delete("/api/joint/shared/99").status_code == 404
    # Personal has none of it.
    ready.post("/api/profiles/active", json={"profile": "personal"})
    assert ready.get("/api/joint").json()["settle_up"]["expenses"] == []


def test_joint_plan_reaches_personal_and_typed_boxes_stay(ready):
    """Rent 650 in the Joint plan -> each pays 325: income "From <name>" in Joint,
    "Transfer to Joint" in Personal. Today is 21 Oct 2026, so Oct–Dec are open.
    Those boxes fill themselves, but can be typed over (and set back to automatic)."""
    _joint_ready(ready)
    ready.post("/api/profiles/active", json={"profile": "joint"})
    assert ready.put("/api/2026/budgets", json={"kind": "expense", "cat": "Rent", "month": 11, "value": 650}).status_code == 200
    plan = ready.get("/api/2026/budgets").json()
    rows = {r["cat"]: r["values"] for r in plan["income"]["rows"]}
    assert rows["From Josu"][11] == 325 and rows["From Isa"][11] == 325
    assert plan["links"]["joint"]["role"] == "joint" and plan["links"]["joint"]["income"]["From Josu"]["months"][11]
    assert plan["saved"]["planned"][11] == 0
    r = ready.put("/api/2026/budgets", json={"kind": "income", "cat": "From Josu", "month": 11, "value": 300})
    assert r.status_code == 200 and r.json()["manual"][11] is True
    josu = next(x for x in ready.get("/api/2026/budgets").json()["income"]["rows"] if x["cat"] == "From Josu")
    assert josu["values"][11] == 300 and josu["manual"][11]  # the plan no longer overwrites it
    ready.put("/api/2026/budgets", json={"kind": "income", "cat": "From Josu", "month": 11, "auto": True})
    josu = next(x for x in ready.get("/api/2026/budgets").json()["income"]["rows"] if x["cat"] == "From Josu")
    assert josu["values"][11] == 325 and not josu["manual"][11]
    # A % of income would chase itself in Joint.
    assert ready.put("/api/2026/budgets", json={"kind": "expense", "cat": "Rent", "month": 11, "percent": 10}).status_code == 409
    assert ready.put("/api/2026/budgets/row-share", json={"cat": "Rent", "percent": 10}).status_code == 409
    # Names rename the rows, and Personal follows person a.
    ready.put("/api/joint/fair-share", json={"name_a": "Ana", "name_b": "Isa", "income_a": None, "income_b": None})
    rows = {r["cat"]: r["values"] for r in ready.get("/api/2026/budgets").json()["income"]["rows"]}
    assert rows["From Ana"][11] == 325 and rows["From Isa"][11] == 325 and "From Josu" not in rows
    ready.post("/api/profiles/active", json={"profile": "personal"})
    plan = ready.get("/api/2026/budgets").json()
    half = next(r for r in plan["expense"]["rows"] if r["cat"] == "Transfer to Joint")
    assert half["kind"] == "fixed" and half["values"][11] == 325
    assert plan["links"]["joint"]["expense"]["Transfer to Joint"]["name"] == "Ana"
    # The Personal forecast counts the half...
    dec = next(row for row in ready.get("/api/forecast").json()["rows"] if row["key"] == "2026-12")
    assert dec["values"]["plan"]["expenses"] == 325
    # ...or what was typed over it: 300 stays, the forecast uses it; back to automatic -> 325.
    r = ready.put("/api/2026/budgets", json={"kind": "expense", "cat": "Transfer to Joint", "month": 11, "value": 300})
    assert r.status_code == 200 and r.json()["manual"][11] is True
    dec = next(row for row in ready.get("/api/forecast").json()["rows"] if row["key"] == "2026-12")
    assert dec["values"]["plan"]["expenses"] == 300
    assert ready.put("/api/2026/budgets", json={"kind": "expense", "cat": "Transfer to Joint", "month": 11,
                                                "percent": 10}).status_code == 409  # euros only, by hand
    ready.put("/api/2026/budgets", json={"kind": "expense", "cat": "Transfer to Joint", "month": 11, "auto": True})
    dec = next(row for row in ready.get("/api/forecast").json()["rows"] if row["key"] == "2026-12")
    assert dec["values"]["plan"]["expenses"] == 325
    # A transfer lands in person a's row in Joint.
    ready.post("/api/joint/transfer", json={"date": "2026-12-01", "amount": 325})
    ready.post("/api/profiles/active", json={"profile": "joint"})
    (into,) = ready.get("/api/2026/transactions").json()["transactions"]
    assert (into["cat"], into["desc"]) == ("From Ana", "Transfer from Ana")


def test_joint_pages(ready):
    ready.post("/api/profiles/active", json={"profile": "joint"})
    # Tracks from October, so the 12 months run Oct 2026 – Sep 2027.
    assert ready.post("/api/setup", json={"year": 2026, "opening_balance": 0, "start_month": 8}).status_code == 201
    ready.put("/api/2026/budgets", json={"kind": "expense", "cat": "Rent", "month": 11, "value": 650})
    ready.post("/api/goals", json={"name": "Trip", "target_amount": 600, "target_date": "2027-03-31"})
    h = ready.get("/api/joint/household?year=2026&month=11").json()
    assert h["bill"]["costs"] == 650 and h["bill"]["goals"] == 100  # 600 over Oct..Mar
    assert [p["planned"] for p in h["people"]] == [375, 375]
    assert ready.get("/api/years").json()["settings"]["last_month"] == 11
    assert ready.get("/api/joint/household?year=2030&month=0").status_code == 404
    bill = ready.get("/api/joint/bill").json()
    assert bill["names"] == {"a": "Josu", "b": "Isa"} and len(bill["rows"]) == 12
    goals = ready.get("/api/goals?year=2026").json()
    assert goals["goals"][0]["status"] == "on_track" and goals["summary"]["combined_covered"]
    assert goals["goals"][0]["forecast"]["month_name"] == "March 2027"


# ---------------------------------------------------------------------------
# Phase 3
# ---------------------------------------------------------------------------

def test_tax_export_flow(ready):
    ready.patch("/api/2026/categories/expense/Shopping", json={"tax_relevant": True})
    ready.post("/api/2026/transactions", json={"type": "expense", "date": "2026-10-05", "amount": 899, "cat": "Shopping", "desc": "Laptop"})
    view = ready.put("/api/2026/tax/settings", json={"commute_days": 100, "commute_km": 10}).json()
    assert view["expenses_total"] == 899 and view["commute"]["amount"] == 380
    body = ready.get("/api/2026/tax/file").json()
    assert body["filename"] == "2026-tax-export.csv"
    text = base64.b64decode(body["content_base64"]).decode("utf-8-sig")
    assert "05.10.2026;Expense;Shopping;Laptop;899,00" in text
    assert ready.put("/api/2026/tax/settings", json={"commute_days": 400}).status_code == 422
    assert ready.get("/api/2025/tax").status_code == 404


def test_backup_verify_restore_flow(ready, isolated_data_dir, monkeypatch):
    from app.services import backup as backup_service
    monkeypatch.setattr(backup_service, "BACKUP_SCRYPT_N", 2**12)
    monkeypatch.setattr(backup_service.make, "__defaults__", (2**12, None, None))
    ready.post("/api/2026/transactions", json={"type": "expense", "date": "2026-10-05", "amount": 50, "cat": "Rent"})
    assert ready.post("/api/data/backup", json={"password": "short"}).status_code == 422
    file = ready.post("/api/data/backup", json={"password": "a long password"}).json()
    assert file["filename"].endswith("-personal-centwise-backup.pcbackup")
    body = {"password": "a long password", "content_base64": file["content_base64"]}
    result = ready.post("/api/data/backup/verify", json=body).json()
    assert result["ok"] is True and "profiles" not in result
    wrong = ready.post("/api/data/backup/verify", json={**body, "password": "not the password"})
    assert wrong.status_code == 422 and "Wrong password" in wrong.json()["detail"]
    # Change the data, then restore: the transaction from the backup is back.
    tx_id = ready.get("/api/2026/transactions").json()["transactions"][0]["id"]
    ready.delete(f"/api/2026/transactions/{tx_id}")
    restored = ready.post("/api/data/backup/restore", json=body).json()
    assert "personal" in restored["restored"] and restored["safety_copies"]
    assert ready.get("/api/2026/transactions").json()["count"] == 1
    assert list(isolated_data_dir.glob("data-before-restore-*.json"))


def test_full_export(ready):
    ready.post("/api/2026/transactions", json={"type": "expense", "date": "2026-10-05", "amount": 1234.5, "cat": "Rent", "desc": "October"})
    csv_file = ready.get("/api/data/export/transactions").json()
    assert csv_file["filename"].endswith("-personal-transactions.csv")
    text = base64.b64decode(csv_file["content_base64"]).decode("utf-8-sig")
    assert "05.10.2026;Expense;Rent;October;;1.234,50;;;" in text
    data = json.loads(base64.b64decode(ready.get("/api/data/export/json").json()["content_base64"]))
    assert data["schema_version"] == 10 and data["years"]["2026"]["transactions"][0]["amount"] == 1234.5


def test_net_worth_flow(ready):
    acc = ready.post("/api/accounts", json={"name": "Tagesgeld", "kind": "savings"}).json()["accounts"][0]
    view = ready.post(f"/api/accounts/{acc['id']}/values", json={"date": "2026-10-01", "amount": 4500}).json()
    assert next(i for i in view["items"] if i["kind"] == "account")["eur"] == 4500
    view = ready.post(f"/api/accounts/{acc['id']}/values", json={"date": "2026-10-01", "amount": 4600}).json()
    assert len(view["accounts"][0]["values"]) == 1  # same day replaced
    ready.post("/api/rates", json={"currency": "PYG", "per_eur": 7000, "date": "2026-10-01"})
    view = ready.post("/api/rates", json={"currency": "PYG", "per_eur": 7100, "date": "2026-10-01"}).json()
    assert view["rate"]["per_eur"] == 7100 and len(view["rates"]) == 1
    assert ready.post("/api/rates", json={"currency": "USD", "per_eur": 1, "date": "2026-10-01"}).status_code == 422
    ready.post("/api/2026/transactions", json={"type": "expense", "date": "2026-10-06", "amount": 300, "cat": "Shopping",
                                               "foreign_amount": 2000000, "foreign_currency": "PYG"})
    view = ready.get("/api/net-worth").json()
    assert view["exchange"]["payments"][0]["rate_reference"] == 7100
    ready.put(f"/api/accounts/{acc['id']}", json={"name": "Tagesgeld DKB", "kind": "savings"})
    assert ready.get("/api/net-worth").json()["accounts"][0]["name"] == "Tagesgeld DKB"
    assert ready.delete(f"/api/accounts/{acc['id']}/values/2026-10-01").status_code == 200
    assert ready.delete("/api/rates/PYG/2026-10-01").json()["rates"] == []
    assert ready.delete(f"/api/accounts/{acc['id']}").json()["accounts"] == []
    assert ready.delete("/api/accounts/99").status_code == 404


def test_budget_plan_has_fixed_and_variable_subtotals(ready):
    ready.put("/api/2026/budgets", json={"kind": "expense", "cat": "Rent", "month": 4, "value": 650})
    ready.put("/api/2026/budgets", json={"kind": "expense", "cat": "Insurance", "month": 4, "value": 149})
    ready.put("/api/2026/budgets", json={"kind": "expense", "cat": "Groceries", "month": 4, "value": 250.5})
    totals = ready.get("/api/2026/budgets").json()["expense"]["kind_totals"]
    assert totals["fixed"]["monthly"][4] == 799 and totals["fixed"]["total"] == 799
    assert totals["variable"]["monthly"][4] == 250.5 and totals["variable"]["monthly"][5] == 0


def test_budget_plan_shows_the_planned_split(ready):
    ready.put("/api/2026/budgets", json={"kind": "income", "cat": "Salary", "month": 4, "value": 3000})
    ready.put("/api/2026/budgets", json={"kind": "expense", "cat": "Rent", "month": 4, "value": 1200})
    body = ready.get("/api/2026/budgets").json()
    may = body["allocation"]["months"][4]
    shares = {b["key"]: b["share"] for b in may["blocks"]}
    assert shares == {"fixed": 40, "variable": 0, "investment": 0, "savings": 60}
    rent = next(r for r in body["expense"]["rows"] if r["cat"] == "Rent")
    assert rent["shares"][4] == 40 and rent["shares"][5] is None
    assert all(r["shares"] is None for r in body["income"]["rows"])


def test_budget_can_be_set_as_a_percent_of_income(ready):
    ready.put("/api/2026/budgets", json={"kind": "income", "cat": "Salary", "month": 4, "value": 2500})
    r = ready.put("/api/2026/budgets", json={"kind": "expense", "cat": "Groceries", "month": 4, "percent": 12})
    assert r.status_code == 200 and r.json()["values"][4] == 300
    # No income planned in June -> no euros to take a share of.
    r = ready.put("/api/2026/budgets", json={"kind": "expense", "cat": "Groceries", "month": 5, "percent": 12})
    assert r.status_code == 409 and "no planned income" in r.json()["detail"]
    # Either euros or a percent; and income cannot be a % of itself.
    both = {"kind": "expense", "cat": "Groceries", "month": 4, "value": 1, "percent": 1}
    assert ready.put("/api/2026/budgets", json=both).status_code == 422
    assert ready.put("/api/2026/budgets", json={"kind": "expense", "cat": "Groceries", "month": 4}).status_code == 422
    assert ready.put("/api/2026/budgets", json={"kind": "income", "cat": "Salary", "month": 4, "percent": 5}).status_code == 422
    assert ready.put("/api/2026/budgets", json={"kind": "expense", "cat": "Nope", "month": 4, "percent": 5}).status_code == 404


# --- Linked % budgets and the salary from the income calendar ----------------

def _row(body, cat, kind="expense"):
    return next(r for r in body[kind]["rows"] if r["cat"] == cat)


def test_linked_percent_follows_the_income(ready):
    ready.put("/api/2026/budgets", json={"kind": "income", "cat": "Salary", "month": 4, "value": 2500})
    ready.put("/api/2026/budgets", json={"kind": "expense", "cat": "Groceries", "month": 4, "percent": 12})
    # Income changes -> the linked budget follows: 12 % of 3 000.
    ready.put("/api/2026/budgets", json={"kind": "income", "cat": "Salary", "month": 4, "value": 3000})
    groceries = _row(ready.get("/api/2026/budgets").json(), "Groceries")
    assert groceries["values"][4] == 360 and groceries["links"][4] == 12 and groceries["links"][5] is None
    # Typing euros removes the link; the amount then stays put.
    ready.put("/api/2026/budgets", json={"kind": "expense", "cat": "Groceries", "month": 4, "value": 200})
    ready.put("/api/2026/budgets", json={"kind": "income", "cat": "Salary", "month": 4, "value": 4000})
    groceries = _row(ready.get("/api/2026/budgets").json(), "Groceries")
    assert groceries["values"][4] == 200 and groceries["links"][4] is None


def test_whole_row_percent_fills_the_open_months(ready):
    """Tracking starts in February (start_month 1) and nothing is recorded: March–December are open."""
    ready.put("/api/2026/budgets", json={"kind": "income", "cat": "Salary", "month": 6, "value": 2000})
    r = ready.put("/api/2026/budgets/row-share", json={"cat": "Groceries", "percent": 10}).json()
    assert r["months"] == list(range(2, 12))
    assert r["values"][6] == 200 and r["values"][7] == 0 and r["links"][0] is None and r["links"][11] == 10
    # Removing the % keeps the euros.
    r = ready.put("/api/2026/budgets/row-share", json={"cat": "Groceries", "percent": None}).json()
    assert r["values"][6] == 200 and all(v is None for v in r["links"])
    assert ready.put("/api/2026/budgets/row-share", json={"cat": "Nope", "percent": 5}).status_code == 404


def test_links_follow_a_rename_and_go_with_a_delete(ready):
    ready.put("/api/2026/budgets", json={"kind": "income", "cat": "Salary", "month": 4, "value": 1000})
    ready.put("/api/2026/budgets", json={"kind": "expense", "cat": "Leisure", "month": 4, "percent": 5})
    ready.patch("/api/2026/categories/expense/Leisure", json={"name": "Fun"})
    assert _row(ready.get("/api/2026/budgets").json(), "Fun")["links"][4] == 5
    ready.delete("/api/2026/categories/expense/Fun")
    ready.post("/api/2026/categories", json={"kind": "expense", "name": "Fun"})
    assert _row(ready.get("/api/2026/budgets").json(), "Fun")["links"][4] is None


def test_salary_budget_follows_the_income_calendar(ready):
    settings = {**INCOME_SETTINGS, "net_method": "tax_rules", "scenarios": []}
    ready.put("/api/income/settings", json=settings)
    body = ready.get("/api/2026/budgets").json()
    flags = body["links"]["calendar_months"]
    # Today is 21 October 2026; nothing is recorded, so October to December follow the calendar.
    assert flags == [False] * 9 + [True] * 3 and body["links"]["salary_category"] == "Salary"
    salary = _row(body, "Salary", "income")["values"]
    calendar = ready.get("/api/income").json()["calendar"]["rows"]
    received = {r["key"]: r["received"] for r in calendar}
    assert salary[10] == received["2026-11"] > 0 and salary[9] == received["2026-10"]
    # A % budget follows the calendar's net pay.
    ready.put("/api/2026/budgets", json={"kind": "expense", "cat": "Rent", "month": 10, "percent": 50})
    assert _row(ready.get("/api/2026/budgets").json(), "Rent")["values"][10] == round(salary[10] / 2, 2)
    # Typing over a calendar month: it stays (marked as typed) and the forecast uses it;
    # "back to automatic" hands it to the calendar again.
    r = ready.put("/api/2026/budgets", json={"kind": "income", "cat": "Salary", "month": 10, "value": 1500})
    assert r.status_code == 200 and r.json()["manual"][10] is True
    typed = _row(ready.get("/api/2026/budgets").json(), "Salary", "income")
    assert typed["values"][10] == 1500 and typed["manual"][10] and not typed["manual"][11]
    nov = next(row for row in ready.get("/api/forecast").json()["rows"] if row["key"] == "2026-11")
    assert nov["values"]["plan"]["income"] == 1500
    ready.put("/api/2026/budgets", json={"kind": "income", "cat": "Salary", "month": 10, "auto": True})
    back = _row(ready.get("/api/2026/budgets").json(), "Salary", "income")
    assert back["values"][10] == salary[10] and not back["manual"][10]
    # Switching the calendar off hands the row back.
    ready.put("/api/income/settings", json={**settings, "enabled": False})
    assert ready.get("/api/2026/budgets").json()["links"]["calendar_months"] == [False] * 12
    assert ready.put("/api/2026/budgets", json={"kind": "income", "cat": "Salary", "month": 10, "value": 1}).status_code == 200


def test_variable_share_panel(ready):
    """Open months: March–December (nothing recorded, tracking from February)."""
    for m, income in ((2, 2000), (3, 4000)):
        ready.put("/api/2026/budgets", json={"kind": "income", "cat": "Salary", "month": m, "value": income})
    for m in range(2, 12):
        ready.put("/api/2026/budgets", json={"kind": "expense", "cat": "Rent", "month": m, "value": 500})
    ready.put("/api/2026/budgets/row-share", json={"cat": "Groceries", "percent": 10})
    ready.put("/api/2026/budgets", json={"kind": "expense", "cat": "Leisure", "month": 3, "percent": 5})
    panel = ready.get("/api/2026/budgets").json()["links"]["panel"]
    assert panel["months"] == list(range(2, 12))
    assert panel["income"] == {"min": 0, "max": 4000}
    # Fixed costs stay euros: 500 a month = 25 % of 2 000 and 12.5 % of 4 000 (months with income only).
    assert panel["fixed"]["amount"] == {"min": 500, "max": 500} and panel["fixed"]["share"] == {"min": 12.5, "max": 25}
    rows = {r["cat"]: r for r in panel["rows"]}
    assert "Rent" not in rows  # only variable costs get a slider
    assert rows["Groceries"]["percent"] == 10 and rows["Groceries"]["amount"] == {"min": 0, "max": 400}
    assert rows["Leisure"]["percent"] is None and rows["Leisure"]["mixed"] is True
    assert rows["Eating out"]["percent"] is None and rows["Eating out"]["mixed"] is False
    # Savings: March 2 000 − 500 − 200 = 1 300 (65 %); April 4 000 − 500 − 400 − 200 = 2 900 (72.5 %).
    assert panel["savings"]["share"] == {"min": 65, "max": 72.5} and panel["savings"]["guide_min"] == 5


def test_goals_show_up_in_the_forecast(ready):
    ready.post("/api/2026/transactions", json={"type": "income", "date": "2026-10-05", "amount": 2000, "cat": "Salary"})
    goal = ready.post("/api/goals", json={"name": "Laptop", "target_amount": 900, "target_date": "2027-02-10"}).json()
    assert goal["spend_in_forecast"] is None  # the default: a one-time goal is spent on its date
    forecast = ready.get("/api/forecast").json()
    feb = next(r for r in forecast["rows"] if r["key"] == "2027-02")
    assert feb["goals"][0]["name"] == "Laptop" and forecast["goals_spent"] == 900
    assert ready.get("/api/forecast?goals=false").json()["goals_spent"] == 0
    listed = ready.get("/api/goals?year=2026").json()["goals"][0]
    assert listed["forecast"]["month"] == "2027-02" and listed["forecast"]["spent"] is True
    # Opting out keeps the money in the account (and in the forecast).
    ready.patch(f"/api/goals/{goal['id']}", json={"spend_in_forecast": False})
    assert ready.get("/api/forecast").json()["goals_spent"] == 0
    assert ready.get("/api/goals?year=2026").json()["goals"][0]["forecast"]["spent"] is False


def test_investment_budget_follows_the_plan(ready):
    """Today is 21 October 2026, nothing recorded: October–December follow the plan."""
    plan = ready.post("/api/investments", json={**LAND, "cost_per_installment": 340, "total_installments": 20, "paid_before": 18}).json()
    body = ready.get("/api/2026/budgets").json()
    assert body["links"]["plan_months"][LAND["category"]] == [False] * 9 + [True] * 3
    row = _row(body, LAND["category"])["values"]
    # Two instalments are left: October and November, then nothing.
    assert row[9] == 340 and row[10] == 340 and row[11] == 0
    # November typed over (two cuotas, 680): it stays, and takes no plan instalment, so the
    # second instalment moves to December. Back to automatic: Oct, Nov 340, Dec 0 again.
    r = ready.put("/api/2026/budgets", json={"kind": "expense", "cat": LAND["category"], "month": 10, "value": 680})
    assert r.status_code == 200
    row = _row(ready.get("/api/2026/budgets").json(), LAND["category"])
    assert row["values"][9:] == [340, 680, 340] and row["manual"][10]
    ready.put("/api/2026/budgets", json={"kind": "expense", "cat": LAND["category"], "month": 10, "auto": True})
    assert _row(ready.get("/api/2026/budgets").json(), LAND["category"])["values"][9:] == [340, 340, 0]
    # A new euro cost per instalment moves the budget with it.
    ready.patch(f"/api/investments/{plan['id']}", json={"cost_per_installment": 360})
    assert _row(ready.get("/api/2026/budgets").json(), LAND["category"])["values"][9] == 360
    # Without a euro cost the budget is typed by hand again.
    ready.patch(f"/api/investments/{plan['id']}", json={"cost_per_installment": 0})
    assert ready.get("/api/2026/budgets").json()["links"]["plan_months"] == {}


def test_typed_hours_and_vacations_survive_the_settings_form(ready):
    """Hours typed for December 2026 (50) and a vacation Mon 23 – Wed 25 Nov 2026 (3 days)
    show in the calendar; saving the settings form again keeps both; clearing works."""
    settings = {**INCOME_SETTINGS, "net_method": "tax_rules", "scenarios": []}
    ready.put("/api/income/settings", json=settings)
    r = ready.put("/api/income/hours/2026-12", json={"hours": 50})
    assert r.status_code == 200
    dec = {x["key"]: x for x in r.json()["calendar"]["rows"]}["2026-12"]
    assert dec["hours"] == 50 and dec["hours_typed"] is True
    v = ready.post("/api/income/vacations", json={"start": "2026-11-23", "end": "2026-11-25", "note": "Trip"})
    assert v.status_code == 201
    assert v.json()["plan"]["vacations"] == [{"id": 1, "start": "2026-11-23", "end": "2026-11-25", "note": "Trip"}]
    nov = {x["key"]: x for x in v.json()["calendar"]["rows"]}["2026-11"]
    assert nov["vacation_days"] == 3 and nov["vacation_pay"] > 0
    again = ready.put("/api/income/settings", json=settings).json()
    assert again["plan"]["hours_typed"] == {"2026-12": 50} and len(again["plan"]["vacations"]) == 1
    assert ready.put("/api/income/hours/2026-12", json={"hours": None}).json()["plan"]["hours_typed"] == {}
    assert ready.delete("/api/income/vacations/1").json()["plan"]["vacations"] == []
    assert ready.delete("/api/income/vacations/1").status_code == 404
    assert ready.put("/api/income/hours/2026-13", json={"hours": 5}).status_code == 422
    assert ready.put("/api/income/hours/2026-12", json={"hours": 401}).status_code == 422
    assert ready.post("/api/income/vacations", json={"start": "2026-11-25", "end": "2026-11-23"}).status_code == 422
