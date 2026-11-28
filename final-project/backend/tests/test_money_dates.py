"""Money dates for the Calendar tab: salary, Transfer to Joint, bills, goals.

Made-up household, worked out by hand. Today is Wednesday 18 November 2026.

Weekdays used below (checked on a calendar):
- Sep 30 2026 Wed · Oct 1 Thu · Oct 30 Fri · Oct 31 Sat · Nov 2 Mon · Nov 13 Fri ·
  Nov 15 Sun · Nov 30 Mon · Dec 1 Tue · Dec 31 Thu · Jan 1 2027 Fri ·
  Jan 29 2027 Fri · Jan 31 2027 Sun · Feb 26 2027 Fri · Feb 28 2027 Sun.

Personal (tracks October-December 2026, ``start_month`` 8):
- Budgets: Salary 1000, Rent 400, Phone 20, Transfer to Joint 300 every month.
- Salary arrives on the last working day (pay day 0): a month-end pay is the
  salary of the next month (booked on the 1st). So the pay of booked month B
  arrives on the last working day of the month before B.
- November's salary was booked: 980 on 1 Nov.
- Rent bill 400, monthly from 1 Oct; paid 1 Oct and 2 Nov. Phone bill 20,
  monthly from 10 Nov, never paid.
- Transfer to Joint 325 booked on 2 Nov (for November). None for October.

Joint (tracks October-December 2026): Rent 650 a month, fair share 50/50, so
each person's part is 650 / 2 = 325.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_today
from app.app import create_app
from app.models import (
    AppData,
    Category,
    FairShare,
    IncomePlan,
    PayeeRule,
    RecurringBill,
    SavingsGoal,
    Transaction,
    YearBudgets,
    YearCategories,
    YearData,
)
from app.services import income_calendar as ic
from app.services import money_dates as md

TODAY = date(2026, 11, 18)
OCT, NOV, DEC = 9, 10, 11  # months are 0-11 inside the app


def t(id: int, type_: str, day: str, amount: float, cat: str) -> Transaction:
    d = date.fromisoformat(day)
    return Transaction(id=id, type=type_, date=day, month=d.month - 1, amount=amount, cat=cat, desc="")


def goal(id: int, name: str, target: float, when: str, **kw) -> SavingsGoal:
    return SavingsGoal(id=id, name=name, target_amount=target, target_date=when, created_date="2026-09-01", **kw)


def personal(plan: IncomePlan | None = None, late_rule: bool = True) -> AppData:
    d = AppData()
    d.years["2026"] = YearData(
        opening_balance=0.0, start_month=8,
        categories=YearCategories(
            expense=[Category(name="Rent", kind="fixed"), Category(name="Phone", kind="fixed"),
                     Category(name="Transfer to Joint")],
            income=[Category(name="Salary")],
        ),
        budgets=YearBudgets(
            expense={"Rent": [400.0] * 12, "Phone": [20.0] * 12, "Transfer to Joint": [300.0] * 12},
            income={"Salary": [1000.0] * 12},
        ),
        transactions=[
            t(1, "income", "2026-11-01", 980.0, "Salary"),
            t(2, "expense", "2026-10-01", 400.0, "Rent"),
            t(3, "expense", "2026-11-02", 400.0, "Rent"),
            t(4, "expense", "2026-11-02", 325.0, "Transfer to Joint"),
        ],
        next_id=5,
    )
    d.income_plan = plan or IncomePlan(enabled=False, pay_day=0)  # last working day
    if late_rule:
        d.payee_rules = [PayeeRule(id=1, contains="EMPLOYER", category="Salary", tx_type="income",
                                   next_month_if_late=True)]
    d.recurring_bills = [
        RecurringBill(id=1, name="Rent", amount=400.0, category="Rent", rhythm_months=1, next_due="2026-10-01"),
        RecurringBill(id=2, name="Phone", amount=20.0, category="Phone", rhythm_months=1, next_due="2026-11-10"),
    ]
    d.goals = [
        goal(1, "Laptop", 1200.0, "2026-12-20"),
        goal(2, "Bike", 500.0, "2026-11-05", status="completed"),
        goal(3, "Trip", 800.0, "2026-10-15"),
        goal(4, "Old idea", 100.0, "2026-11-11", status="abandoned"),
        goal(5, "Insurance fund", 240.0, "2026-12-15", goal_type="sinking", repeat_months=12),
    ]
    return d


def shared(fs: FairShare | None = None) -> AppData:
    d = AppData(fair_share=fs or FairShare())
    d.years["2026"] = YearData(
        opening_balance=0.0, start_month=8,
        categories=YearCategories(expense=[Category(name="Rent", kind="fixed")],
                                  income=[Category(name="From Josu"), Category(name="From Isa")]),
        budgets=YearBudgets(expense={"Rent": [650.0] * 12}),
    )
    return d


def rows(result: dict) -> list[tuple]:
    return [(i["date"], i["kind"], i["name"], i["amount"], i["status"]) for i in result["items"]]


# -- pay day and working days ----------------------------------------------------


def test_last_working_day_moves_off_the_weekend():
    """Pay day 0 = last working day: 31 Oct 2026 is a Saturday -> Friday 30 Oct;
    30 Nov is a Monday -> 30 Nov; 31 Jan 2027 is a Sunday -> Friday 29 Jan."""
    assert md.pay_date(2026, OCT, 0) == date(2026, 10, 30)
    assert md.pay_date(2026, NOV, 0) == date(2026, 11, 30)
    assert md.pay_date(2027, 0, 0) == date(2027, 1, 29)


def test_fixed_pay_day_moves_back_to_friday_and_fits_short_months():
    """Day 15 in November 2026 is a Sunday -> Friday 13 Nov. Day 31 in February
    2027 becomes the 28th, a Sunday -> Friday 26 Feb. Day 1 of December 2026 is
    a Tuesday and stays."""
    assert md.pay_date(2026, NOV, 15) == date(2026, 11, 13)
    assert md.pay_date(2027, 1, 31) == date(2027, 2, 26)
    assert md.pay_date(2026, DEC, 1) == date(2026, 12, 1)


def test_working_day_before_the_last_one():
    """Pay day -1 (Josu's salary): the last working day, then one working day back.
    Nov 2026: last working day Mon 30 -> Fri 27 (his example). Oct 2026: 31 Oct is a
    Saturday, last working day Fri 30 -> Thu 29. Jan 2027: 31 Jan is a Sunday -> Fri 29
    -> Thu 28. Feb 2027: 28 Feb is a Sunday -> Fri 26 -> Thu 25. Dec 2026: Thu 31 -> Wed 30."""
    assert md.pay_date(2026, NOV, -1) == date(2026, 11, 27)
    assert md.pay_date(2026, OCT, -1) == date(2026, 10, 29)
    assert md.pay_date(2027, 0, -1) == date(2027, 1, 28)
    assert md.pay_date(2027, 1, -1) == date(2027, 2, 25)
    assert md.pay_date(2026, DEC, -1) == date(2026, 12, 30)
    assert md.late_pay_day(-1) and md.late_pay_day(0) and md.late_pay_day(25) and not md.late_pay_day(24)


def test_josus_pay_day_in_the_list():
    """Pay day -1 with the late rule, 1 Nov - 31 Dec: Thu 29 Oct is before the window.
    Fri 27 Nov is December's pay -> expected 1000. Wed 30 Dec is January's -> expected 1000.
    The transfers come the working day after: Mon 30 Nov (for December, due 325) and
    Thu 31 Dec (for January 2027: Joint 2027 not set up, borrows 2026's 650 -> 325, due)."""
    plan = IncomePlan(enabled=False, pay_day=-1)
    items = md.money_dates(personal(plan), date(2026, 11, 1), date(2026, 12, 31), TODAY, shared=shared())["items"]
    assert [(i["date"], i["kind"], i["for_month"], i["amount"], i["status"]) for i in items
            if i["kind"] in ("salary", "transfer")] == [
        ("2026-11-27", "salary", "2026-12", 1000.0, "expected"),
        ("2026-11-30", "transfer", "2026-12", 325.0, "due"),
        ("2026-12-30", "salary", "2027-01", 1000.0, "expected"),
        ("2026-12-31", "transfer", "2027-01", 325.0, "due"),
    ]


def test_next_working_day_skips_the_weekend():
    """Friday 30 Oct -> Monday 2 Nov; Monday 30 Nov -> Tuesday 1 Dec."""
    assert md.next_working_day(date(2026, 10, 30)) == date(2026, 11, 2)
    assert md.next_working_day(date(2026, 11, 30)) == date(2026, 12, 1)


# -- the whole Personal list -------------------------------------------------------


def test_personal_money_dates_october_to_december():
    """1 Oct - 31 Dec 2026, Personal, with the Joint plan for the transfer.

    Salary (arrives on the last working day, booked the month after):
    - 30 Sep arrival (for Oct) is before the window -> left out.
    - Fri 30 Oct, for November: booked 980 -> done, 980.
    - Mon 30 Nov, for December: not booked -> expected, the December budget 1000.
    - Thu 31 Dec, for January 2027: 2027 is not set up, so the 2026 budget plans
      it -> expected 1000.
    Transfer to Joint (the working day after the salary arrives; with a late pay
    day it is for the next month, i.e. the month the transfer is made in):
    - Thu 1 Oct (after Wed 30 Sep), for October: nothing booked, date passed -> overdue,
      Joint part 650 / 2 = 325.
    - Mon 2 Nov, for November: 325 booked -> done.
    - Tue 1 Dec, for December -> due 325.
    - Fri 1 Jan 2027 is after the window -> left out.
    Bills: Rent 1 Oct paid (1 Oct), 1 Nov paid (2 Nov), 1 Dec due. Phone 10 Nov
    unpaid and before today -> overdue; 10 Dec due.
    Goals: Trip 15 Oct still active -> overdue; Bike 5 Nov completed -> done;
    Old idea abandoned -> left out; Insurance fund (sinking) 15 Dec -> due;
    Laptop 20 Dec -> due.
    Same day: salary, transfer, bill, goal (then the name).

    Still to pay = not-done bills and transfers: 325 + 20 + 325 + 400 + 20 = 1090.
    Still expected = not-done salary: 1000 + 1000 = 2000.
    """
    result = md.money_dates(personal(), date(2026, 10, 1), date(2026, 12, 31), TODAY, shared=shared())
    assert rows(result) == [
        ("2026-10-01", "transfer", "Transfer to Joint", 325.0, "overdue"),
        ("2026-10-01", "bill", "Rent", 400.0, "done"),
        ("2026-10-15", "goal", "Trip", 800.0, "overdue"),
        ("2026-10-30", "salary", "Salary", 980.0, "done"),
        ("2026-11-01", "bill", "Rent", 400.0, "done"),
        ("2026-11-02", "transfer", "Transfer to Joint", 325.0, "done"),
        ("2026-11-05", "goal", "Bike", 500.0, "done"),
        ("2026-11-10", "bill", "Phone", 20.0, "overdue"),
        ("2026-11-30", "salary", "Salary", 1000.0, "expected"),
        ("2026-12-01", "transfer", "Transfer to Joint", 325.0, "due"),
        ("2026-12-01", "bill", "Rent", 400.0, "due"),
        ("2026-12-10", "bill", "Phone", 20.0, "due"),
        ("2026-12-15", "sinking", "Insurance fund", 240.0, "due"),
        ("2026-12-20", "goal", "Laptop", 1200.0, "due"),
        ("2026-12-31", "salary", "Salary", 1000.0, "expected"),
    ]
    assert result["due_total"] == 1090.0
    assert result["expected_total"] == 2000.0
    assert result["pay_day"] == 0 and result["profile"] == "personal"


def test_items_carry_month_keys_and_payment_dates():
    """The salary of 30 Oct is for November, a paid bill knows when it was paid,
    and every item has a stable key (for the iPhone sync later)."""
    items = md.money_dates(personal(), date(2026, 10, 1), date(2026, 12, 31), TODAY, shared=shared())["items"]
    salary = next(i for i in items if i["kind"] == "salary" and i["date"] == "2026-10-30")
    assert salary["for_month"] == "2026-11" and salary["key"] == "salary/2026-11"
    assert salary["direction"] == "in" and salary["done"] is True
    rent = next(i for i in items if i["kind"] == "bill" and i["date"] == "2026-11-01")
    assert rent["paid_on"] == "2026-11-02" and rent["key"] == "bill/1/2026-11-01" and rent["ref_id"] == 1
    assert rent["direction"] == "out"
    transfer = next(i for i in items if i["kind"] == "transfer" and i["date"] == "2026-12-01")
    assert transfer["for_month"] == "2026-12" and transfer["key"] == "transfer/2026-12" and transfer["done"] is False
    laptop = next(i for i in items if i["name"] == "Laptop")
    assert laptop["key"] == "goal/1" and laptop["direction"] == "goal" and laptop["for_month"] is None
    assert len({i["key"] for i in items}) == len(items)


def test_window_keeps_only_dates_inside_it():
    """1-30 Nov only: salary 30 Nov, transfer 2 Nov, Rent 1 Nov, Phone 10 Nov, Bike 5 Nov.
    Still to pay: Phone 20. Still expected: salary 1000."""
    result = md.money_dates(personal(), date(2026, 11, 1), date(2026, 11, 30), TODAY, shared=shared())
    assert [(i["date"], i["kind"]) for i in result["items"]] == [
        ("2026-11-01", "bill"), ("2026-11-02", "transfer"), ("2026-11-05", "goal"),
        ("2026-11-10", "bill"), ("2026-11-30", "salary"),
    ]
    assert (result["due_total"], result["expected_total"]) == (20.0, 1000.0)


# -- salary rules -------------------------------------------------------------------


def test_month_end_pay_is_next_months_salary_without_an_import_rule_too():
    """Josu's salary is typed by hand (dated the 1st of the next month), so there is no
    "book next month" payee rule. A month-end pay is still next month's salary:
    Mon 30 Nov -> December, expected 1000; Thu 31 Dec -> January 2027 (2026's budget
    borrowed), expected 1000."""
    result = md.money_dates(personal(late_rule=False), date(2026, 11, 1), date(2026, 12, 31), TODAY, shared=shared())
    salary = [(i["date"], i["for_month"], i["amount"], i["status"]) for i in result["items"] if i["kind"] == "salary"]
    assert salary == [("2026-11-30", "2026-12", 1000.0, "expected"), ("2026-12-31", "2027-01", 1000.0, "expected")]


def test_early_pay_day_is_the_same_months_salary():
    """Pay day 10: 10 Nov 2026 is a Tuesday, before the 25th, so it is November's pay
    (980 booked -> done); 10 Dec (Thursday) is December's -> expected 1000."""
    plan = IncomePlan(enabled=False, pay_day=10)
    result = md.money_dates(personal(plan), date(2026, 11, 1), date(2026, 12, 31), TODAY, shared=shared())
    salary = [(i["date"], i["for_month"], i["amount"], i["status"]) for i in result["items"] if i["kind"] == "salary"]
    assert salary == [("2026-11-10", "2026-11", 980.0, "done"), ("2026-12-10", "2026-12", 1000.0, "expected")]
    assert result["pay_day"] == 10


def test_expected_pay_follows_the_income_calendar_when_it_is_on():
    """With the calendar on (hourly rate, tax rules), the expected pay of December is
    what the income calendar says arrives in December (its maths is tested in
    test_income_calendar.py), not the budget."""
    plan = IncomePlan(enabled=True, hourly_rate=20.0, hours_lecture_week=20.0, hours_break_week=20.0)
    result = md.money_dates(personal(plan), date(2026, 11, 1), date(2026, 11, 30), TODAY, shared=shared())
    salary = next(i for i in result["items"] if i["kind"] == "salary")
    expected = ic.paid_by_month(plan, plan.payslips, (2026, DEC), 1)[(2026, DEC)]
    assert expected > 0 and salary["amount"] == expected and salary["status"] == "expected"


def test_no_income_plan_uses_the_defaults():
    """Without an income calendar: category "Salary", budget amounts and the default pay
    day, the working day before the last one: November's last working day is Mon 30 Nov,
    so the pay arrives Fri 27 Nov (for December, late rule) -> expected, budget 1000."""
    d = personal()
    d.income_plan = None
    result = md.money_dates(d, date(2026, 11, 1), date(2026, 11, 30), TODAY, shared=shared())
    salary = [(i["date"], i["for_month"], i["amount"]) for i in result["items"] if i["kind"] == "salary"]
    assert salary == [("2026-11-27", "2026-12", 1000.0)]
    assert result["pay_day"] == -1


# -- Transfer to Joint ---------------------------------------------------------------


def test_transfer_follows_the_fair_share():
    """Incomes 2000 and 3000: Josu pays 2000 / 5000 of 650 = 260 (Isa 390)."""
    result = md.money_dates(personal(), date(2026, 12, 1), date(2026, 12, 1), TODAY,
                            shared=shared(FairShare(income_a=2000, income_b=3000)))
    assert rows(result) == [
        ("2026-12-01", "transfer", "Transfer to Joint", 260.0, "due"),
        ("2026-12-01", "bill", "Rent", 400.0, "due"),
    ]


def test_without_joint_data_the_transfer_uses_the_personal_budget():
    """No Joint data passed: the December "Transfer to Joint" budget, 300."""
    result = md.money_dates(personal(), date(2026, 12, 1), date(2026, 12, 1), TODAY)
    transfer = next(i for i in result["items"] if i["kind"] == "transfer")
    assert transfer["amount"] == 300.0


# -- Joint ------------------------------------------------------------------------------


def test_joint_shows_each_persons_money_and_no_salary():
    """Joint, November, pay day 0 (Josu's, passed in): both parts arrive the working
    day after Fri 30 Oct = Mon 2 Nov, for November. Josu's 325 is booked (3 Nov) ->
    done; Isa's 325 -> expected. Joint has no salary and no transfer.
    Still expected: 325."""
    d = shared()
    d.years["2026"].transactions = [t(1, "income", "2026-11-03", 325.0, "From Josu")]
    d.years["2026"].next_id = 2
    result = md.money_dates(d, date(2026, 11, 1), date(2026, 11, 30), TODAY, profile="joint", pay_day=0)
    assert rows(result) == [
        ("2026-11-02", "contribution", "From Isa", 325.0, "expected"),
        ("2026-11-02", "contribution", "From Josu", 325.0, "done"),
    ]
    assert result["expected_total"] == 325.0 and result["due_total"] == 0.0
    keys = {i["key"] for i in result["items"]}
    assert keys == {"from-a/2026-11", "from-b/2026-11"}


def test_joint_bills_and_goals_appear_too():
    """A Joint bill (Internet 30 from 5 Dec) and a shared goal (Sofa 600, 24 Dec)."""
    d = shared()
    d.recurring_bills = [RecurringBill(id=1, name="Internet", amount=30.0, category="Rent", rhythm_months=1,
                                       next_due="2026-12-05")]
    d.goals = [goal(1, "Sofa", 600.0, "2026-12-24")]
    result = md.money_dates(d, date(2026, 12, 2), date(2026, 12, 31), TODAY, profile="joint", pay_day=0)
    assert rows(result) == [
        ("2026-12-05", "bill", "Internet", 30.0, "due"),
        ("2026-12-24", "goal", "Sofa", 600.0, "due"),
    ]


def test_empty_profile_has_no_money_dates():
    result = md.money_dates(AppData(), date(2026, 11, 1), date(2026, 11, 30), TODAY)
    assert result["items"] == [] and result["due_total"] == 0.0 and result["expected_total"] == 0.0


# -- API --------------------------------------------------------------------------------


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_today] = lambda: TODAY
    with TestClient(app) as c:
        yield c


def test_api_money_dates(client):
    """Set up 2026, add a 50 € bill due 20 Nov: it is in the list, still to pay 50."""
    assert client.post("/api/setup", json={"year": 2026, "opening_balance": 100, "start_month": 8}).status_code in (200, 201)
    r = client.post("/api/bills", json={"name": "Gym", "amount": 50, "category": "Rent", "rhythm_months": 1,
                                        "next_due": "2026-11-20"})
    assert r.status_code in (200, 201), r.text
    body = client.get("/api/calendar/money", params={"start": "2026-11-01", "end": "2026-11-30"}).json()
    gym = [i for i in body["items"] if i["kind"] == "bill"]
    assert [(i["date"], i["name"], i["amount"], i["status"]) for i in gym] == [("2026-11-20", "Gym", 50.0, "due")]
    assert body["profile"] == "personal"


def test_api_rejects_a_bad_window(client):
    """End before start, more than 400 days (1 Jan 2026 - 1 Mar 2027 = 424), or no real date:
    refused with the app's usual 422."""
    assert client.get("/api/calendar/money", params={"start": "2026-11-30", "end": "2026-11-01"}).status_code == 422
    assert client.get("/api/calendar/money", params={"start": "2026-01-01", "end": "2027-03-01"}).status_code == 422
    assert client.get("/api/calendar/money", params={"start": "2026-13-01", "end": "2026-12-01"}).status_code == 422


def test_api_joint_uses_the_owners_pay_day(client):
    """Personal's income calendar says pay day 10; the Joint list uses it."""
    client.post("/api/setup", json={"year": 2026, "opening_balance": 0, "start_month": 8})
    r = client.put("/api/income/settings", json={"enabled": False, "pay_day": 10})
    assert r.status_code == 200, r.text
    assert client.post("/api/profiles/active", json={"profile": "joint"}).status_code == 200
    body = client.get("/api/calendar/money", params={"start": "2026-11-01", "end": "2026-11-30"}).json()
    assert body["profile"] == "joint" and body["pay_day"] == 10


def test_api_pay_day_must_be_a_day_of_the_month(client):
    client.post("/api/setup", json={"year": 2026, "opening_balance": 0, "start_month": 8})
    assert client.put("/api/income/settings", json={"pay_day": 32}).status_code == 422
    assert client.put("/api/income/settings", json={"pay_day": -2}).status_code == 422


def test_pay_day_1_on_a_weekend_shows_in_the_month_before():
    """Pay day 1 (not late, so booked in its own month). October window:
    1 Oct 2026 is a Thursday -> October's pay on 1 Oct, not booked -> expected 1000.
    1 Nov 2026 is a Sunday -> November's pay moves back to Friday 30 Oct, inside the
    October window; November's 980 is booked -> done."""
    plan = IncomePlan(enabled=False, pay_day=1)
    result = md.money_dates(personal(plan), date(2026, 10, 1), date(2026, 10, 31), TODAY, shared=shared())
    salary = [(i["date"], i["for_month"], i["amount"], i["status"]) for i in result["items"] if i["kind"] == "salary"]
    assert salary == [("2026-10-01", "2026-10", 1000.0, "expected"), ("2026-10-30", "2026-11", 980.0, "done")]


def test_one_payment_does_not_tick_two_bills():
    """The blind check's case: Liability 50 € (20 Mar) and Household 52 € (22 Mar), both
    Insurance, one 50 € payment on 20 Mar. Liability done; Household overdue (today is
    18 Nov 2026). Still to pay: 52."""
    d = AppData()
    d.years["2026"] = YearData(start_month=-1, transactions=[t(1, "expense", "2026-03-20", 50.0, "Insurance")],
                               next_id=2)
    d.recurring_bills = [
        RecurringBill(id=1, name="Household", amount=52.0, category="Insurance", rhythm_months=12,
                      next_due="2026-03-22"),
        RecurringBill(id=2, name="Liability", amount=50.0, category="Insurance", rhythm_months=12,
                      next_due="2026-03-20"),
    ]
    result = md.money_dates(d, date(2026, 3, 1), date(2026, 3, 31), TODAY)
    assert rows(result) == [
        ("2026-03-20", "bill", "Liability", 50.0, "done"),
        ("2026-03-22", "bill", "Household", 52.0, "overdue"),
    ]
    assert result["due_total"] == 52.0


def test_boxes_typed_by_hand_win_in_the_calendar():
    """Calendar on (it would work out December's pay itself), but December's salary was
    typed by hand at 1,500 -> Mon 30 Nov shows 1,500. Transfer to Joint typed at 280 for
    December -> Tue 1 Dec shows 280 (the plan says 325). In Joint, Isa's December part typed
    at 400 -> 400 (plan 325); Josu's stays the plan's 325."""
    plan = IncomePlan(enabled=True, hourly_rate=20.0, hours_lecture_week=20.0, hours_break_week=20.0, pay_day=0)
    d = personal(plan)
    budgets = d.years["2026"].budgets
    budgets.income["Salary"][DEC] = 1500.0
    budgets.set_manual("income", "Salary", DEC, True)
    budgets.expense["Transfer to Joint"][DEC] = 280.0
    budgets.set_manual("expense", "Transfer to Joint", DEC, True)
    result = md.money_dates(d, date(2026, 11, 30), date(2026, 12, 1), TODAY, shared=shared())
    assert rows(result) == [
        ("2026-11-30", "salary", "Salary", 1500.0, "expected"),
        ("2026-12-01", "transfer", "Transfer to Joint", 280.0, "due"),
        ("2026-12-01", "bill", "Rent", 400.0, "due"),
    ]
    j = shared()
    j.years["2026"].budgets.income["From Isa"] = [0.0] * 12
    j.years["2026"].budgets.income["From Isa"][DEC] = 400.0
    j.years["2026"].budgets.set_manual("income", "From Isa", DEC, True)
    parts = md.money_dates(j, date(2026, 12, 1), date(2026, 12, 1), TODAY, profile="joint", pay_day=0)
    assert [(i["name"], i["amount"]) for i in parts["items"]] == [("From Isa", 400.0), ("From Josu", 325.0)]
