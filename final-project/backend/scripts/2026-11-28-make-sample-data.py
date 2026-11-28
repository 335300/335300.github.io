#!/usr/bin/env python3
"""Fill an empty data folder with a made-up sample year for both profiles.

    cd backend
    .venv/bin/python scripts/2026-11-28-make-sample-data.py ../sample-data
    .venv/bin/python scripts/2026-11-28-make-sample-data.py ../sample-data --force   # start again

Every figure here is invented (round, realistic numbers for a working student in
Germany and a shared household). Nothing comes from real statements or payslips.

The data is written through the app's own API (FastAPI's TestClient), exactly as
if someone had typed it in the app: the same validation, the same Joint links,
the same budget syncing. The random parts use a fixed seed, so every run gives
the same file.

What it creates (January to November 2026, "today" = 28 Nov 2026):

Personal  salary from a student job (with payslips and the income calendar),
          student health insurance, phone, subscriptions, transport, food,
          a semester-fee sinking fund, an emergency fund, a laptop goal (bought
          in September), a trip goal, a plot of land paid in instalments (PYG),
          monthly ETF savings, recurring bills, payee rules, a Tagesgeld and an
          ETF depot for the net worth page, and a monthly Transfer to Joint.
Joint     rent, utilities, internet, groceries, household and eating out paid
          from the shared account; the monthly money "From Josu" (transfer) and
          "From Isa"; the fair-share incomes; a shared holiday goal; recurring
          bills; two shared costs paid privately and one settle-up.
"""

from __future__ import annotations

import argparse
import os
import random
import shutil
import sys
from datetime import date
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

YEAR = 2026
TODAY = date(2026, 11, 28)
LAST_MONTH = 11  # November is the last month with data (1-based)
SEED = 2026

# Folders this script must never write into (the real apps' data).
FORBIDDEN = ("Personal Centwise", "Centwise")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("folder", type=Path, help="data folder to fill (created if missing)")
    p.add_argument("--force", action="store_true", help="delete the folder's existing data first")
    return p.parse_args()


def prepare_folder(folder: Path, force: bool) -> Path:
    folder = folder.expanduser().resolve()
    support = (Path.home() / "Library" / "Application Support").resolve()
    if folder.parent == support and folder.name in FORBIDDEN:
        sys.exit(f"Refusing to write into {folder}: that is a real app's data folder.")
    if (folder / "data.json").exists() or (folder / "joint" / "data.json").exists():
        if not force:
            sys.exit(f"{folder} already has data. Use --force to replace it with fresh sample data.")
        for name in ("data.json", "joint", "backups", "app-state.json"):
            target = folder / name
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
    folder.mkdir(parents=True, exist_ok=True)
    return folder


class Api:
    """Tiny wrapper: every call must succeed, or the script stops with the reason."""

    def __init__(self, client) -> None:
        self.c = client

    def _do(self, method: str, url: str, body=None):
        r = self.c.request(method, url, json=body)
        if r.status_code >= 300:
            raise SystemExit(f"{method} {url} failed ({r.status_code}): {r.text}\nbody: {body}")
        return r.json() if r.content else None

    def get(self, url):
        return self._do("GET", url)

    def post(self, url, body=None):
        return self._do("POST", url, body)

    def put(self, url, body=None):
        return self._do("PUT", url, body)

    def patch(self, url, body=None):
        return self._do("PATCH", url, body)

    def delete(self, url):
        return self._do("DELETE", url)

    def profile(self, name: str) -> None:
        self.post("/api/profiles/active", {"profile": name})


def d(month: int, day: int, year: int = YEAR) -> str:
    """Date string; month is 1-based."""
    return date(year, month, day).isoformat()


def months() -> range:
    return range(1, LAST_MONTH + 1)


def expense(cat: str, month: int, day: int, amount: float, desc: str = "", **extra) -> dict:
    return {"type": "expense", "date": d(month, day), "amount": round(amount, 2), "cat": cat, "desc": desc, **extra}


def income(cat: str, month: int, day: int, amount: float, desc: str = "", **extra) -> dict:
    return {"type": "income", "date": d(month, day), "amount": round(amount, 2), "cat": cat, "desc": desc, **extra}


def set_budget(api: Api, kind: str, cat: str, values: list[float]) -> None:
    for m, value in enumerate(values):
        api.put(f"/api/{YEAR}/budgets", {"kind": kind, "cat": cat, "month": m, "value": value})


# ---------------------------------------------------------------- Personal --

# Work month (1-12 of 2026, 0 = Dec 2025) -> (gross, net). Lecture months 20 h/week,
# semester breaks 32 h/week, at 22 €/h. Invented, plausible payslip figures.
LECTURE = (1906.00, 1611.40)
BREAK = (3050.00, 2352.80)
WORK_MONTHS = {
    0: LECTURE, 1: LECTURE, 2: BREAK, 3: BREAK, 4: LECTURE, 5: LECTURE, 6: LECTURE,
    7: LECTURE, 8: BREAK, 9: BREAK, 10: LECTURE,
}

LAND_GS = 1_600_000          # one instalment, in guaraníes
LAND_EUR = 200.00            # what one instalment cost in euros (rate ≈ 8.000 Gs)
TRANSFER_TO_JOINT = 740.00   # Josu's monthly part of the Joint plan (≈ 40 %)
ISA_MONTHLY = 1100.00        # Isa's monthly part (≈ 60 %)


def personal(api: Api, rng: random.Random) -> None:
    api.profile("personal")
    api.post("/api/setup", {"year": YEAR, "opening_balance": 1850, "start_month": -1, "starter_categories": True})
    y = f"/api/{YEAR}"

    # Categories: no rent here (rent is paid from the Joint account).
    api.delete(f"{y}/categories/expense/Rent")
    for name, kind, essential, tax in (
        ("Health insurance", "fixed", True, False),
        ("Tuition", "fixed", True, True),
        ("Work equipment", "variable", False, True),
        ("Land instalments", "investment", False, False),
        ("ETF savings", "investment", False, False),
    ):
        api.post(f"{y}/categories", {"kind": "expense", "name": name, "category_kind": kind,
                                     "essential": essential, "tax_relevant": tax})
    for name in ("Insurance", "Phone & Internet", "Groceries", "Transport"):
        api.patch(f"{y}/categories/expense/{name}", {"essential": True})

    # Goals first, so bills and payments can point at them.
    emergency = api.post("/api/goals", {"name": "Emergency fund", "target_amount": 3000,
                                        "target_date": "2027-12-31", "emergency_fund": True,
                                        "notes": "Three months of essential costs."})
    semester = api.post("/api/goals", {"name": "Semester fee", "target_amount": 320,
                                       "target_date": "2026-08-14", "goal_type": "sinking",
                                       "repeat_months": 6, "notes": "Paid every semester."})
    laptop = api.post("/api/goals", {"name": "New laptop", "target_amount": 900, "target_date": "2026-09-30"})
    trip = api.post("/api/goals", {"name": "Trip to Paraguay", "target_amount": 1800,
                                   "target_date": "2027-07-15", "notes": "Flights in summer 2027."})

    # Investment plan: a plot of land paid in instalments (cuotas).
    api.post("/api/investments", {
        "name": "Plot of land", "category": "Land instalments", "unit": "cuota", "local_currency": "Gs",
        "installment_amount": LAND_GS, "total_installments": 96, "paid_before": 14,
        "cost_per_installment": LAND_EUR, "market_value_local": 190_000_000,
        "notes": "Sample plan: 96 monthly cuotas.",
    })

    txs: list[dict] = []
    for m in months():
        gross, net = WORK_MONTHS[m - 1]
        wobble = rng.uniform(-25, 25)
        # Pay for the month before arrives at its end and is booked on the 1st.
        txs.append(income("Salary", m, 1, net + wobble, "Student job"))
        txs.append(expense("Health insurance", m, 1, 142.50, "Student health insurance"))
        txs.append(expense("Phone & Internet", m, 3, 19.99, "Mobile contract"))
        txs.append(expense("Subscriptions", m, 6, 10.99, "Music streaming"))
        txs.append(expense("Subscriptions", m, 20, 29.90, "Gym"))
        txs.append(expense("Transport", m, 2, 63.00, "Deutschlandticket"))
        txs.append(expense("Land instalments", m, 10, LAND_EUR, "Cuota",
                           installments=1, foreign_amount=LAND_GS, foreign_currency="PYG"))
        if m >= 6:
            txs.append(expense("ETF savings", m, 15, 75.00, "ETF savings plan"))
        for _ in range(rng.randint(2, 4)):
            txs.append(expense("Eating out", m, rng.randint(4, 27), rng.uniform(12, 38), "Lunch / dinner"))
        for _ in range(rng.randint(2, 3)):
            txs.append(expense("Groceries", m, rng.randint(2, 27), rng.uniform(9, 24), "Snacks and lunch"))
        if rng.random() < 0.7:
            txs.append(expense("Shopping", m, rng.randint(5, 26), rng.uniform(20, 75), "Clothes / small things"))
        for _ in range(rng.randint(1, 2)):
            txs.append(expense("Leisure", m, rng.randint(5, 27), rng.uniform(10, 45), "Cinema / concert / sport"))
        if rng.random() < 0.4:
            txs.append(expense("Health", m, rng.randint(5, 25), rng.uniform(6, 25), "Pharmacy"))

    txs.append(expense("Tuition", 2, 13, 320.00, "Semester fee summer 2026"))
    txs.append(expense("Insurance", 3, 15, 72.00, "Personal liability insurance (yearly)"))
    txs.append(expense("Work equipment", 4, 22, 89.00, "Headset for remote work"))
    txs.append(expense("Transport", 7, 18, 46.00, "Train to a friend's wedding", one_off=True))
    txs.append(income("Other income", 5, 12, 100.00, "Birthday gift"))
    txs.append(income("Other income", 7, 24, 412.30, "Tax refund 2025", one_off=True))
    txs.append(expense("Shopping", 9, 26, 879.00, "New laptop", one_off=True))
    txs.sort(key=lambda t: t["date"])
    api.post(f"{y}/transactions/bulk", {"transactions": txs})

    # Goal savings (earmarks: the money stays in the account).
    for m in months():
        api.post(f"/api/goals/{emergency['id']}/contributions", {"date": d(m, 2), "amount": 100, "note": "Monthly"})
        if m >= 3:
            api.post(f"/api/goals/{semester['id']}/contributions", {"date": d(m, 2), "amount": 55, "note": "Monthly"})
        if 4 <= m <= 9:
            api.post(f"/api/goals/{laptop['id']}/contributions", {"date": d(m, 2), "amount": 150, "note": "Monthly"})
        if m >= 6:
            api.post(f"/api/goals/{trip['id']}/contributions", {"date": d(m, 2), "amount": 120, "note": "Monthly"})
    # The winter semester fee is paid from its fund (the fund pays the bill).
    api.post(f"/api/goals/{semester['id']}/pay", {"date": d(8, 13), "amount": 320, "category": "Tuition",
                                                    "desc": "Semester fee winter 2026/27"})
    api.patch(f"/api/goals/{laptop['id']}", {"status": "completed"})

    # Budgets (cash out per month; the Salary budget follows the income calendar).
    flat = {
        "Health insurance": 142.50, "Phone & Internet": 20, "Subscriptions": 41, "Transport": 63,
        "Eating out": 80, "Groceries": 45, "Shopping": 60, "Leisure": 50, "Health": 15,
        "Land instalments": LAND_EUR, "Work equipment": 0,
    }
    for cat, value in flat.items():
        set_budget(api, "expense", cat, [value] * 12)
    set_budget(api, "expense", "Insurance", [0, 0, 72] + [0] * 9)
    set_budget(api, "expense", "Tuition", [0, 320, 0, 0, 0, 0, 0, 320, 0, 0, 0, 0])
    set_budget(api, "expense", "ETF savings", [0] * 5 + [75] * 7)
    set_budget(api, "income", "Other income", [0] * 12)

    # Income calendar: 22 €/h, 20 h in lecture periods, 32 h in the breaks.
    api.put("/api/income/settings", {
        "enabled": True, "hourly_rate": 22, "hours_lecture_week": 20, "hours_break_week": 32,
        "lecture_periods": [
            {"start": "2025-10-13", "end": "2026-02-06"},
            {"start": "2026-04-13", "end": "2026-07-24"},
            {"start": "2026-10-12", "end": "2027-02-05"},
            {"start": "2027-04-12", "end": "2027-07-23"},
        ],
        "salary_category": "Salary", "contract_pay_lag": 1, "extra_hours_delay": 1,
        "health_category": "Health insurance", "net_method": "tax_rules", "church_tax_rate": 0,
        "scenarios": [
            {"name": "Graduate in September 2027", "job_end": "2027-09-30",
             "health_insurance_monthly": 235, "new_net_salary": 2900},
            {"name": "Graduate in March 2028", "job_end": "2028-03-31",
             "health_insurance_monthly": 235, "new_net_salary": 2900},
        ],
    })
    for m in range(0, 11):  # payslips Dec 2025 .. Oct 2026
        gross, net = WORK_MONTHS[m]
        month = "2025-12" if m == 0 else f"{YEAR}-{m:02d}"
        api.post("/api/income/payslips", {"month": month, "gross": gross, "net": net, "note": "Sample payslip"})
    api.post("/api/income/vacations", {"start": "2026-08-10", "end": "2026-08-21", "note": "Summer holiday"})

    # Recurring bills.
    for bill in (
        {"name": "Student health insurance", "amount": 142.50, "category": "Health insurance",
         "rhythm_months": 1, "next_due": "2026-12-01", "match": "health insurance"},
        {"name": "Mobile contract", "amount": 19.99, "category": "Phone & Internet",
         "rhythm_months": 1, "next_due": "2026-12-03", "match": "Mobile"},
        {"name": "Deutschlandticket", "amount": 63.00, "category": "Transport",
         "rhythm_months": 1, "next_due": "2026-12-02", "match": "Deutschlandticket"},
        {"name": "Gym", "amount": 29.90, "category": "Subscriptions",
         "rhythm_months": 1, "next_due": "2026-12-20", "match": "Gym"},
        {"name": "Liability insurance", "amount": 72.00, "category": "Insurance",
         "rhythm_months": 12, "next_due": "2027-03-15", "match": "liability"},
        {"name": "Semester fee", "amount": 320.00, "category": "Tuition",
         "rhythm_months": 6, "next_due": "2027-02-12", "match": "Semester fee", "goal_id": semester["id"]},
    ):
        api.post("/api/bills", bill)

    # Payee rules used by the bank import.
    for rule in (
        {"contains": "REWE", "category": "Groceries", "tx_type": "expense"},
        {"contains": "DB Vertrieb", "category": "Transport", "tx_type": "expense"},
        {"contains": "Lieferando", "category": "Eating out", "tx_type": "expense"},
        {"contains": "Lohn/Gehalt", "category": "Salary", "tx_type": "income", "next_month_if_late": True},
    ):
        api.post("/api/rules", rule)

    # Net worth: accounts kept by hand and the guaraní exchange rate.
    # Accounts get ids 1, 2, 3 in the order they are added (fresh file).
    tagesgeld, depot, cash = 1, 2, 3
    api.post("/api/accounts", {"name": "Tagesgeld", "kind": "savings", "currency": "EUR",
                               "notes": "Instant-access savings"})
    api.post("/api/accounts", {"name": "ETF depot", "kind": "investment", "currency": "EUR"})
    api.post("/api/accounts", {"name": "Cash", "kind": "cash", "currency": "EUR"})
    for m in months():
        last = 28 if m == 2 else 30
        api.post(f"/api/accounts/{tagesgeld}/values", {"date": d(m, last), "amount": 2000 + 50 * m})
        if m >= 6:
            api.post(f"/api/accounts/{depot}/values",
                     {"date": d(m, last), "amount": round(75 * (m - 5) * (1 + 0.006 * (m - 5)), 2)})
    api.post(f"/api/accounts/{cash}/values", {"date": d(11, 1), "amount": 80})
    for day, rate in (("2026-01-05", 8150), ("2026-06-01", 7980), ("2026-11-02", 7820)):
        api.post("/api/rates", {"currency": "PYG", "per_eur": rate, "date": day})

    api.patch("/api/prefs", {"show_savings_tile": True})


# ------------------------------------------------------------------- Joint --

def joint(api: Api, rng: random.Random) -> None:
    api.profile("joint")
    api.post("/api/setup", {"year": YEAR, "opening_balance": 600, "start_month": -1, "starter_categories": True})
    y = f"/api/{YEAR}"
    for name in ("Transport", "Shopping", "Health"):
        api.delete(f"{y}/categories/expense/{name}")
    api.delete(f"{y}/categories/income/Salary")
    for name, kind, essential in (("Utilities", "fixed", True), ("Household", "variable", False)):
        api.post(f"{y}/categories", {"kind": "expense", "name": name, "category_kind": kind, "essential": essential})
    for name in ("Rent", "Insurance", "Phone & Internet", "Groceries"):
        api.patch(f"{y}/categories/expense/{name}", {"essential": True})

    # Fair share: net incomes per month (invented). Josu's part ≈ 40 %.
    api.put("/api/joint/fair-share", {"name_a": "Josu", "name_b": "Isa", "income_a": 1750, "income_b": 2600})

    holiday = api.post("/api/goals", {"name": "Holiday in Italy", "target_amount": 2000,
                                      "target_date": "2027-06-30", "notes": "Our summer trip."})

    txs: list[dict] = []
    for m in months():
        txs.append(income("From Isa", m, 1, ISA_MONTHLY, "Monthly share"))
        txs.append(expense("Rent", m, 3, 980.00, "Rent incl. service charges"))
        txs.append(expense("Utilities", m, 5, 140.00, "Electricity and heating"))
        txs.append(expense("Phone & Internet", m, 10, 39.99, "Home internet"))
        txs.append(expense("Subscriptions", m, 15, 13.99, "Video streaming"))
        for _ in range(rng.randint(4, 6)):
            txs.append(expense("Groceries", m, rng.randint(1, 28), rng.uniform(45, 105), "Supermarket"))
        for _ in range(rng.randint(1, 2)):
            txs.append(expense("Household", m, rng.randint(2, 27), rng.uniform(12, 45), "Cleaning / kitchen"))
        for _ in range(rng.randint(1, 2)):
            txs.append(expense("Eating out", m, rng.randint(5, 28), rng.uniform(35, 80), "Dinner together"))
        if rng.random() < 0.5:
            txs.append(expense("Leisure", m, rng.randint(5, 28), rng.uniform(15, 50), "Day out"))
    txs.append(expense("Insurance", 4, 1, 96.00, "Household contents insurance (yearly)"))
    txs.append(expense("Household", 10, 12, 249.00, "New washing machine (our share)", one_off=True))
    txs.sort(key=lambda t: t["date"])
    api.post(f"{y}/transactions/bulk", {"transactions": txs})

    for m in months():
        api.post(f"/api/goals/{holiday['id']}/contributions", {"date": d(m, 4), "amount": 100, "note": "Monthly"})

    flat = {"Rent": 980, "Utilities": 140, "Phone & Internet": 40, "Subscriptions": 14,
            "Groceries": 400, "Household": 60, "Eating out": 90, "Leisure": 30}
    for cat, value in flat.items():
        set_budget(api, "expense", cat, [value] * 12)
    set_budget(api, "expense", "Insurance", [0, 0, 0, 96] + [0] * 8)

    for bill in (
        {"name": "Rent", "amount": 980.00, "category": "Rent", "rhythm_months": 1, "next_due": "2026-12-03", "match": "Rent"},
        {"name": "Electricity and heating", "amount": 140.00, "category": "Utilities", "rhythm_months": 1,
         "next_due": "2026-12-05", "match": "Electricity"},
        {"name": "Home internet", "amount": 39.99, "category": "Phone & Internet", "rhythm_months": 1,
         "next_due": "2026-12-10", "match": "internet"},
        {"name": "Video streaming", "amount": 13.99, "category": "Subscriptions", "rhythm_months": 1,
         "next_due": "2026-12-15", "match": "streaming"},
        {"name": "Household insurance", "amount": 96.00, "category": "Insurance", "rhythm_months": 12,
         "next_due": "2027-04-01", "match": "contents insurance"},
    ):
        api.post("/api/bills", bill)

    # Shared costs paid from a personal account, and one settle-up.
    api.post("/api/joint/shared", {"date": "2026-10-18", "desc": "Shelf for the living room", "amount": 189.00,
                                   "paid_by": "b", "split": "fair"})
    api.post("/api/joint/shared", {"date": "2026-11-07", "desc": "Concert tickets", "amount": 120.00,
                                   "paid_by": "a", "split": "equal"})
    api.post("/api/joint/settlements", {"date": "2026-11-20", "from_person": "a", "amount": 40.00,
                                        "note": "Settled part of the shelf"})


def transfers(api: Api) -> None:
    """Personal → Joint, every month: one record in each profile, linked."""
    api.profile("personal")
    for m in months():
        api.post("/api/joint/transfer", {"date": d(m, 1), "amount": TRANSFER_TO_JOINT, "note": "Monthly share"})


def past_plans(api: Api) -> None:
    """The plan each recorded month had before it happened.

    The app fills the Salary, "Transfer to Joint" and "From <name>" budgets by
    itself only for months not recorded yet. A real user's past months got
    those figures while they were still ahead; here every month is recorded at
    once, so January to November are set as typed figures. December (still
    open) keeps filling itself.
    """
    recorded = range(LAST_MONTH)  # 0-based months Jan..Nov
    api.profile("personal")
    for m in recorded:
        api.put(f"/api/{YEAR}/budgets", {"kind": "income", "cat": "Salary", "month": m,
                                          "value": WORK_MONTHS[m][1]})
        api.put(f"/api/{YEAR}/budgets", {"kind": "expense", "cat": "Transfer to Joint", "month": m,
                                          "value": TRANSFER_TO_JOINT})
    api.profile("joint")
    for m in recorded:
        api.put(f"/api/{YEAR}/budgets", {"kind": "income", "cat": "From Josu", "month": m, "value": TRANSFER_TO_JOINT})
        api.put(f"/api/{YEAR}/budgets", {"kind": "income", "cat": "From Isa", "month": m, "value": ISA_MONTHLY})


def main() -> None:
    args = parse_args()
    folder = prepare_folder(args.folder, args.force)
    os.environ["CENTWISE_DATA_DIR"] = str(folder)
    os.environ.pop("CENTWISE_TOKEN", None)
    os.environ["CENTWISE_CALENDAR"] = "fake"

    from fastapi.testclient import TestClient

    from app.api.deps import get_today
    from app.app import create_app

    app = create_app()
    app.dependency_overrides[get_today] = lambda: TODAY
    api = Api(TestClient(app))
    rng = random.Random(SEED)

    personal(api, rng)
    joint(api, rng)
    transfers(api)
    past_plans(api)
    api.profile("personal")
    # Open on November in both profiles.
    api.get(f"/api/{YEAR}/dashboard?month={LAST_MONTH - 1}")
    api.profile("joint")
    api.get(f"/api/joint/household?year={YEAR}&month={LAST_MONTH - 1}")
    api.profile("personal")

    # Keep only the finished files; the backups of each step are not useful here.
    for b in (folder / "backups", folder / "joint" / "backups"):
        shutil.rmtree(b, ignore_errors=True)
    print(f"Sample data written to {folder}")


if __name__ == "__main__":
    main()
