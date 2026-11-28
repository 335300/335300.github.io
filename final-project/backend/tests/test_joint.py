"""Joint links: Transfer to Joint, fair share, settle-up.

Made-up numbers: incomes 2,000 and 3,000 -> shares 40% / 60%.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.models import (
    AppData, Category, FairShare, SavingsGoal, Settlement, SharedExpense, Transaction, TransferInput,
    YearBudgets, YearCategories, YearData,
)
from app.services import aggregation, joint


def profile(start_month: int = -1) -> AppData:
    d = AppData()
    d.years["2026"] = YearData(start_month=start_month)
    return d


def move(amount=300.0, when="2026-10-01", **kw) -> TransferInput:
    return TransferInput(date=when, amount=amount, **kw)


# -- transfer -------------------------------------------------------------------

def test_transfer_writes_one_linked_record_in_each_profile():
    personal, shared = profile(), profile()
    result = joint.transfer(personal, shared, move(), link_id="L1")
    (out,) = personal.years["2026"].transactions
    (into,) = shared.years["2026"].transactions
    assert (out.type, out.cat, out.amount, out.link_id) == ("expense", "Transfer to Joint", 300, "L1")
    # In Joint it is income of person a, the owner of the Personal profile.
    assert (into.type, into.cat, into.amount, into.link_id) == ("income", "From Josu", 300, "L1")
    assert into.desc == "Transfer from Josu"
    assert personal.years["2026"].find_category("expense", "Transfer to Joint").kind == "fixed"
    assert shared.years["2026"].find_category("income", "From Josu") is not None
    assert result["link_id"] == "L1"


def test_transfer_uses_chosen_categories_and_note():
    personal, shared = profile(), profile()
    joint.transfer(personal, shared, move(note="Rent share", personal_category="Joint", joint_category="From me"))
    assert personal.years["2026"].transactions[0].cat == "Joint"
    assert shared.years["2026"].transactions[0].desc == "Rent share"


def test_transfer_changes_nothing_when_joint_does_not_track_the_month():
    personal, shared = profile(), profile(start_month=10)  # Joint tracks only December
    with pytest.raises(joint.LinkError, match="Joint"):
        joint.transfer(personal, shared, move())
    assert personal.years["2026"].transactions == [] and shared.years["2026"].transactions == []


def test_edit_and_delete_reach_the_other_half():
    personal, shared = profile(), profile()
    joint.transfer(personal, shared, move(), link_id="L1")
    joint.update_linked(shared, "L1", "2026-10-03", 350)
    into = shared.years["2026"].transactions[0]
    assert (into.date, into.month, into.amount) == ("2026-10-03", 9, 350)
    assert joint.delete_linked(shared, "L1") is True
    assert shared.years["2026"].transactions == []
    assert joint.delete_linked(shared, "L1") is False


def test_linked_edit_into_an_untracked_month_is_refused():
    personal, shared = profile(), profile(start_month=8)
    joint.transfer(personal, shared, move(), link_id="L1")
    with pytest.raises(joint.LinkError):
        joint.update_linked(shared, "L1", "2026-05-01", 300)
    assert shared.years["2026"].transactions[0].date == "2026-10-01"


# -- fair share -----------------------------------------------------------------

def test_fair_share_by_income():
    fs = joint.fair_share(FairShare(income_a=2000, income_b=3000), 1500)
    assert (fs["share_a_pct"], fs["share_b_pct"], fs["basis"]) == (40.0, 60.0, "incomes")
    assert (fs["amount_a"], fs["amount_b"]) == (600, 900)


def test_fair_share_is_equal_until_both_incomes_are_known():
    fs = joint.fair_share(FairShare(income_a=2000), 1000)
    assert (fs["share_a_pct"], fs["basis"], fs["amount_b"]) == (50.0, "equal", 500)
    assert joint.fair_share(FairShare(income_a=0, income_b=0), None)["basis"] == "equal"
    assert joint.fair_share(FairShare(), None)["amount_a"] is None


# -- settle-up ------------------------------------------------------------------

def cost(id, amount, paid_by, split="fair"):
    return SharedExpense(id=id, date="2026-10-0" + str(id), desc="x", amount=amount, paid_by=paid_by, split=split)


def test_settle_up_with_fair_shares():
    fs = FairShare(name_a="Ana", name_b="Ben", income_a=2000, income_b=3000)
    # Ana paid 100 -> Ben owes his 60%: 60. Ben paid 50 equally -> Ana owes 25. Net: Ben owes 35.
    result = joint.settle_up(fs, [cost(1, 100, "a"), cost(2, 50, "b", split="equal")], [])
    assert result["balance_a"] == 35 and result["owes"] == "b" and result["gets"] == "a"
    assert result["amount"] == 35 and result["text"] == "Ben owes Ana"
    assert [e["owed_by_other"] for e in result["expenses"]] == [60, 25]


def test_settlements_reduce_the_balance():
    fs = FairShare(income_a=2000, income_b=3000)
    expenses = [cost(1, 100, "a")]
    paid = [Settlement(id=9, date="2026-10-10", from_person="b", amount=60)]
    assert joint.settle_up(fs, expenses, paid)["text"] == "You are settled up"
    over = [Settlement(id=9, date="2026-10-10", from_person="b", amount=80)]
    result = joint.settle_up(fs, expenses, over)
    assert result["balance_a"] == -20 and result["owes"] == "a"


def test_a_paying_b_raises_the_balance():
    result = joint.settle_up(FairShare(), [], [Settlement(id=1, date="2026-10-10", from_person="a", amount=40)])
    assert result["balance_a"] == 40 and result["owes"] == "b"


# -- the shared plan --------------------------------------------------------------
#
# Made-up household: Joint tracks October–December 2026 (start_month 8), opening
# pot 100, rent 650 planned every month. Today is 21 October 2026.

TODAY = date(2026, 10, 21)


def shared_plan(rent=650.0, groceries=0.0, opening=100.0, start_month=8, fs: FairShare | None = None) -> AppData:
    d = AppData(fair_share=fs or FairShare())
    d.years["2026"] = YearData(
        opening_balance=opening, start_month=start_month,
        categories=YearCategories(expense=[Category(name="Rent", kind="fixed"), Category(name="Groceries")]),
        budgets=YearBudgets(expense={"Rent": [rent] * 12, "Groceries": [groceries] * 12}),
    )
    return d


def goal(id=1, target=1200.0, when="2027-03-31", **kw) -> SavingsGoal:
    return SavingsGoal(id=id, name=f"Trip {id}", target_amount=target, target_date=when, created_date="2026-10-01", **kw)


def income(id, month, amount, cat, year=2026):
    return Transaction(id=id, type="income", date=f"{year}-{month + 1:02d}-03", month=month, amount=amount, cat=cat)


def expense(id, month, amount, cat, year=2026):
    return Transaction(id=id, type="expense", date=f"{year}-{month + 1:02d}-04", month=month, amount=amount, cat=cat)


def test_bill_splits_the_plan_half_and_half_until_incomes_are_known():
    row = joint.bill(shared_plan(), (2026, 10), TODAY)
    assert (row["costs"], row["goals"], row["total"], row["a"], row["b"]) == (650, 0, 650, 325, 325)
    fair = joint.bill(shared_plan(fs=FairShare(income_a=2000, income_b=3000)), (2026, 10), TODAY)
    assert (fair["a"], fair["b"]) == (260, 390)
    odd = joint.bill(shared_plan(rent=100.01), (2026, 10), TODAY)
    assert (odd["a"], odd["b"]) == (50.01, 50.0)  # the two parts always add up to the cent


def test_goal_saving_spreads_what_is_missing_up_to_the_deadline():
    d = shared_plan()
    d.goals = [goal(target=1200, when="2027-03-31")]  # Oct..Mar = 6 months -> 200 a month
    assert joint.goal_saving(d, (2026, 9), TODAY) == 200  # October counts
    assert joint.goal_saving(d, (2027, 2), TODAY) == 200  # March, the deadline month
    assert joint.goal_saving(d, (2027, 3), TODAY) == 0    # after it: nothing
    assert joint.goal_saving(d, (2026, 8), TODAY) == 0    # past months: nothing
    assert joint.bill(d, (2026, 10), TODAY)["total"] == 850


def test_goal_saving_of_a_sinking_fund_goes_on_after_the_bill():
    d = shared_plan()
    d.goals = [goal(target=300, when="2026-12-15", goal_type="sinking", repeat_months=3)]
    assert joint.goal_saving(d, (2026, 11), TODAY) == 100  # 300 over Oct, Nov, Dec
    assert joint.goal_saving(d, (2027, 0), TODAY) == 100   # the next round: 300 / 3
    d.goals[0].status = "completed"
    assert joint.goal_saving(d, (2026, 11), TODAY) == 0


def test_contributions_follow_the_bill_in_open_months_only():
    d = shared_plan()
    assert joint.sync_contributions(d, TODAY) is True
    year = d.years["2026"]
    assert year.find_category("income", "From Josu") and year.find_category("income", "From Isa")
    assert year.budgets.income["From Josu"][9:] == [325, 325, 325]       # Oct, Nov, Dec
    assert year.budgets.income["From Isa"][8] == 0                  # September is not tracked
    # Planned contributions cancel the planned costs: nothing is kept.
    assert aggregation.savings_by_month(year)["planned"][9:] == [0, 0, 0]
    assert joint.sync_contributions(d, TODAY) is False                  # already up to date
    # A recorded month keeps its plan.
    year.transactions.append(expense(1, 9, 650, "Rent"))
    year.budgets.expense["Rent"] = [700.0] * 12
    joint.sync_contributions(d, TODAY)
    assert year.budgets.income["From Josu"][9] == 325 and year.budgets.income["From Josu"][10] == 350


def test_personal_half_follows_the_owners_part():
    shared = shared_plan()
    personal = AppData()
    personal.years["2026"] = YearData(transactions=[expense(1, 9, 50, "Food")], next_id=2)
    personal.years["2027"] = YearData()
    assert joint.sync_personal_half(personal, shared, TODAY) is True
    p26, p27 = personal.years["2026"], personal.years["2027"]
    assert p26.find_category("expense", "Transfer to Joint").kind == "fixed"
    assert p26.budgets.expense["Transfer to Joint"][9:] == [0, 325, 325]  # October is recorded
    # Joint has no 2027 yet and does not track January 2026, so its December plan is used.
    assert p27.budgets.expense["Transfer to Joint"][0] == 325
    assert joint.sync_personal_half(personal, shared, TODAY) is False


def test_personal_half_drops_a_percent_link_and_waits_for_a_joint_year():
    personal = AppData()
    personal.years["2026"] = YearData()
    assert joint.sync_personal_half(personal, AppData(), TODAY) is False
    assert personal.years["2026"].find_category("expense", "Transfer to Joint") is None
    personal.years["2026"].budgets.set_share("Transfer to Joint", 11, 10.0)
    joint.sync_personal_half(personal, shared_plan(), TODAY)
    assert personal.years["2026"].budgets.share_row("Transfer to Joint")[11] is None
    assert personal.years["2026"].budgets.expense["Transfer to Joint"][11] == 325


def test_new_names_rename_the_contribution_categories():
    d = shared_plan()
    joint.sync_contributions(d, TODAY)
    d.years["2026"].transactions.append(income(1, 9, 325, "From Josu"))  # the default names: Josu and Isa
    joint.rename_people(d, FairShare(name_a="Ana", name_b="Isa"))
    year = d.years["2026"]
    assert year.find_category("income", "From Josu") is None
    assert year.budgets.income["From Ana"][10] == 325 and "From Josu" not in year.budgets.income
    assert year.transactions[0].cat == "From Ana"
    assert year.find_category("income", "From Isa") is not None


def test_renaming_refuses_twins_and_taken_names_and_allows_a_swap():
    d = shared_plan()
    joint.sync_contributions(d, TODAY)
    with pytest.raises(joint.LinkError, match="different"):
        joint.rename_people(d, FairShare(name_a="Ana", name_b="ana"))
    d.years["2026"].categories.income.append(Category(name="From Ben"))
    with pytest.raises(joint.LinkError, match="already"):
        joint.rename_people(d, FairShare(name_a="Ben", name_b="Isa"))
    assert d.years["2026"].find_category("income", "From Josu") is not None  # nothing changed
    joint.rename_people(d, FairShare(name_a="Isa", name_b="Josu"))      # swapping is fine
    assert {c.name for c in d.years["2026"].categories.income} >= {"From Josu", "From Isa"}


def test_bill_forecast_fills_the_pot_for_a_goal_and_buys_it():
    d = shared_plan()
    d.goals = [goal(target=1200, when="2027-03-31")]
    f = joint.bill_forecast(d, TODAY)
    rows = f["rows"]
    assert (rows[0]["label"], f["start_balance"]) == ("Oct 26", 100)
    # Both pay in their part of rent + 200 for the trip; the pot grows by 200 until March buys the trip.
    assert [r["pot"] for r in rows[:6]] == [300, 500, 700, 900, 1100, 100]
    assert rows[5]["goal_spend"] == 1200 and rows[5]["goals_bought"][0]["name"] == "Trip 1"
    assert f["average"] == {"total": 750, "a": 375, "b": 375, "costs": 650, "goals": 100}
    assert (f["end_pot"], f["lowest_pot"], f["lowest_name"], f["goes_negative"]) == (100, 100, "March 2027", False)
    check = joint.goal_checks(d, TODAY)[1]
    assert (check["month_name"], check["balance"], check["affordable"]) == ("March 2027", 100, True)


def test_bill_forecast_starts_at_the_first_tracked_month_when_nothing_is_recorded():
    d = shared_plan()
    d.years["2027"] = YearData(budgets=YearBudgets(expense={"Rent": [700.0] * 12}))  # next year already set up
    f = joint.bill_forecast(d, TODAY)
    assert f["start_name"] == "October 2026" and f["start_balance"] == 100
    assert [r["costs"] for r in f["rows"][2:4]] == [650, 700]  # December 2026, January 2027


def test_household_shows_who_has_paid_in_and_where_the_money_went():
    d = shared_plan(groceries=300)
    d.years["2026"].transactions = [
        income(1, 9, 475, "From Josu"), income(2, 9, 300, "From Isa"),
        expense(3, 9, 650, "Rent"), expense(4, 9, 120, "Groceries"),
    ]
    h = joint.household(d, 2026, 9, TODAY)
    me, partner = h["people"]
    assert (me["planned"], me["paid_in"], me["to_go"], me["done"]) == (475, 475, 0, True)
    assert (partner["paid_in"], partner["to_go"], partner["progress"], partner["done"]) == (300, 175, 63.2, False)
    m = h["money"]
    assert (m["put_in"], m["from_people"], m["other_in"]) == (775, 775, 0)
    assert (m["spent"], m["planned"], m["left"], m["spent_pct"], m["status"]) == (770, 950, 180, 81.1, "within")
    assert h["pot"]["balance"] == 105
    assert [r["cat"] for r in h["categories"]][:2] == ["Rent", "Groceries"]
    assert h["months"][-1] == {"label": "Oct 26", "year": 2026, "month": 9, "put_in": 775, "spent": 770, "kept": 5}
    assert h["split"] == {"basis": "equal", "share_a_pct": 50.0, "share_b_pct": 50.0}


def test_household_goals_say_what_each_person_puts_in():
    d = shared_plan()
    d.goals = [goal(target=1200, when="2027-03-31"), goal(id=2, target=50, when="2027-01-31", status="abandoned")]
    g = joint.household(d, 2026, 9, TODAY)["goals"]
    (trip,) = g["rows"]
    assert (trip["monthly"], trip["a"], trip["b"]) == (200, 100, 100)
    assert g["monthly"] == {"total": 200, "a": 100, "b": 100}


# -- the forecast borrows next year's plan --------------------------------------
#
# Made-up household started mid-year: Joint 2026 tracks November and December
# only (start_month 9), opening pot 100. Rent 650 is planned for December only —
# November is already recorded (300 in from Josu), so its plan stays 0.
# Incomes 2,000 / 3,000 -> 40 % / 60 %. Today is 19 November 2026.

NOV_19 = date(2026, 11, 19)


def mid_year_household(nov_rent: float = 0.0) -> AppData:
    d = shared_plan(rent=0.0, start_month=9, fs=FairShare(income_a=2000, income_b=3000))
    d.years["2026"].budgets.expense["Rent"] = [0.0] * 10 + [nov_rent, 650.0]
    d.years["2026"].transactions = [income(1, 10, 300, "From Josu")]
    d.years["2026"].next_id = 2
    return d


def test_bill_forecast_never_borrows_an_empty_plan():
    """The forecast runs December 2026 -> November 2027 (12 months after the last
    recorded month). 2027 is not set up, so it borrows from 2026:
    January–October 2027 are not tracked in 2026 -> its December plan (650).
    November 2027: November 2026 is tracked but has no plan (0) -> December too.
    Before the fix November 2027 showed 0 and the tile average was
    11 × 650 ÷ 12 = 595.83 while every other row said 650.

    Every month: costs 650, Josu 40 % = 260, Isa 60 % = 390.
    Pot: 100 opening + 300 in November = 400; each month +260 +390 −650 = 0 -> stays 400.
    Average: 12 × 650 ÷ 12 = 650 (260 + 390)."""
    f = joint.bill_forecast(mid_year_household(), NOV_19)
    rows = f["rows"]
    assert (f["start_name"], f["end_name"], len(rows)) == ("December 2026", "November 2027", 12)
    assert all((r["costs"], r["total"], r["a"], r["b"], r["pot"]) == (650, 650, 260, 390, 400) for r in rows)
    assert f["average"] == {"total": 650, "a": 260, "b": 390, "costs": 650, "goals": 0}


def test_bill_forecast_still_borrows_a_month_that_has_its_own_plan():
    """November 2026 planned at 700 -> November 2027 borrows it (700); the rest stays 650.
    Average: (11 × 650 + 700) ÷ 12 = 7,850 ÷ 12 = 654.17."""
    f = joint.bill_forecast(mid_year_household(nov_rent=700.0), NOV_19)
    assert [r["costs"] for r in f["rows"]] == [650] * 11 + [700]
    assert f["average"]["total"] == 654.17
