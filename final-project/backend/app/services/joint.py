"""The Joint links: transfers, fair share, the shared plan and settling up.

Profiles stay separate databases; these are the only places they meet.

- **Transfer to Joint** (:func:`transfer`) is the one action that writes to two
  profiles: an expense in Personal and the matching income in Joint, sharing a
  ``link_id``. :func:`linked` finds the other half, so an edit or a delete can
  reach it. In Joint the money arrives as income "From <name>" of person a —
  the owner of the Personal profile.
- **Fair share** (:func:`fair_share`): each person pays shared costs in
  proportion to their net income. Until both incomes are entered it is 50/50.
- **The shared plan** (:func:`bill`): every month the Joint plan's cash out plus
  what it puts aside for shared goals is split by the fair share. Each person's
  part becomes their planned income "From <name>" in Joint
  (:func:`sync_contributions`), so contributions cancel the planned costs, and
  person a's part becomes the "Transfer to Joint" budget in Personal
  (:func:`sync_personal_half`). Both only fill months not recorded yet.
- **Settle-up** (:func:`settle_up`): costs one person paid for both from a
  personal account. The other person owes their part (half, or their fair
  share); settlements between the two reduce it. These costs are kept apart
  from the Joint transactions, because the joint account never paid them.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from ..config import FORECAST_MONTHS, JOINT_CONTRIBUTION_PREFIX, JOINT_HISTORY_MONTHS, MONTHS, TRANSFER_PERSONAL_CATEGORY
from ..models import AppData, Category, CategoryKind, FairShare, Person, SharedExpense, Settlement, Transaction, TransferInput, TxType, YearData
from . import budget_links, cashflow, dashboard, goal_forecast, rolling_forecast
from . import goals as goals_service
from . import income_calendar as ic
from .aggregation import budget_total, category_totals

YM = tuple[int, int]


def _round2(v: float) -> float:
    return round(v, 2)


class LinkError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Transfer to Joint
# ---------------------------------------------------------------------------

def _tracked_year(data: AppData, d: date, profile_label: str) -> YearData:
    year = data.get_year(d.year)
    if year is None or d.month - 1 <= year.start_month:
        raise LinkError(f"{d.isoformat()} is in a month the {profile_label} profile does not track.")
    return year


def _ensure(year: YearData, kind: TxType, name: str, category_kind: CategoryKind = "variable") -> None:
    if year.find_category(kind, name) is None:
        getattr(year.categories, kind).append(Category(name=name, kind=category_kind))
        getattr(year.budgets, kind).setdefault(name, [0.0] * 12)


def transfer(personal: AppData, joint: AppData, payload: TransferInput, link_id: str | None = None) -> dict[str, Any]:
    """Add both halves of a transfer. Checks both profiles before changing either."""
    d = date.fromisoformat(payload.date)
    p_year = _tracked_year(personal, d, "Personal")
    j_year = _tracked_year(joint, d, "Joint")
    link = link_id or uuid.uuid4().hex
    p_cat = payload.personal_category or TRANSFER_PERSONAL_CATEGORY
    j_cat = payload.joint_category or contribution_categories(joint.fair_share)["a"]

    _ensure(p_year, "expense", p_cat, "fixed")
    _ensure(j_year, "income", j_cat)
    out = Transaction(id=p_year.take_id(), type="expense", date=payload.date, month=d.month - 1,
                      amount=payload.amount, desc=payload.note or "Transfer to Joint", cat=p_cat, link_id=link)
    into = Transaction(id=j_year.take_id(), type="income", date=payload.date, month=d.month - 1,
                       amount=payload.amount, desc=payload.note or f"Transfer from {joint.fair_share.name_a}",
                       cat=j_cat, link_id=link)
    p_year.transactions.append(out)
    j_year.transactions.append(into)
    return {"link_id": link, "personal": out.model_dump(), "joint": into.model_dump()}


def linked(data: AppData, link_id: str) -> tuple[int, Transaction] | None:
    """The transaction carrying ``link_id`` in this profile, if any."""
    for y, year in data.years.items():
        for t in year.transactions:
            if t.link_id == link_id:
                return int(y), t
    return None


def update_linked(other: AppData, link_id: str, new_date: str, amount: float) -> None:
    """Give the other half the same date and amount. Raises before changing
    anything when the new date's month is not tracked there."""
    found = linked(other, link_id)
    if found is None:
        return
    old_year, t = found
    d = date.fromisoformat(new_date)
    target = _tracked_year(other, d, "other")
    source = other.years[str(old_year)]
    if target is not source:
        source.transactions = [x for x in source.transactions if x is not t]
        t = t.model_copy(update={"id": target.take_id()})
        target.transactions.append(t)
    t.date, t.month, t.amount = new_date, d.month - 1, round(amount, 2)


def delete_linked(other: AppData, link_id: str) -> bool:
    found = linked(other, link_id)
    if found is None:
        return False
    y, t = found
    year = other.years[str(y)]
    year.transactions = [x for x in year.transactions if x is not t]
    return True


# ---------------------------------------------------------------------------
# Fair share and settle-up
# ---------------------------------------------------------------------------

def shares(fs: FairShare) -> tuple[float, float, str]:
    """(share of a, share of b, basis). 50/50 until both incomes are known."""
    a, b = fs.income_a or 0.0, fs.income_b or 0.0
    if fs.income_a is None or fs.income_b is None or a + b <= 0:
        return 0.5, 0.5, "equal"
    return a / (a + b), b / (a + b), "incomes"


def fair_share(fs: FairShare, shared_costs: float | None) -> dict[str, Any]:
    """Each person's share of the shared costs, in percent and euros a month."""
    share_a, share_b, basis = shares(fs)
    return {
        **fs.model_dump(),
        "basis": basis,
        "share_a_pct": round(share_a * 100, 1),
        "share_b_pct": round(share_b * 100, 1),
        "shared_costs": shared_costs,
        "amount_a": _round2(shared_costs * share_a) if shared_costs else None,
        "amount_b": _round2(shared_costs * share_b) if shared_costs else None,
    }


def _other(p: Person) -> Person:
    return "b" if p == "a" else "a"


def settle_up(fs: FairShare, expenses: list[SharedExpense], settlements: list[Settlement]) -> dict[str, Any]:
    """Who owes whom, after the shared costs and the settlements so far.

    ``balance_a`` > 0 means b owes a that much; < 0 means a owes b. Each cost
    puts the non-payer's part (half, or their fair share today) on their side.
    """
    share = dict(zip(("a", "b"), shares(fs)[:2]))
    balance_a = 0.0
    rows = []
    for e in sorted(expenses, key=lambda e: (e.date, e.id)):
        other = _other(e.paid_by)
        part = 0.5 if e.split == "equal" else share[other]
        owed = _round2(e.amount * part)
        balance_a += owed if e.paid_by == "a" else -owed
        rows.append({**e.model_dump(), "owed_by_other": owed})
    for s in settlements:
        # b paying a lowers what b owes a; a paying b raises it.
        balance_a += -s.amount if s.from_person == "b" else s.amount
    balance_a = _round2(balance_a)
    names = {"a": fs.name_a, "b": fs.name_b}
    if balance_a > 0:
        owes, gets = "b", "a"
    elif balance_a < 0:
        owes, gets = "a", "b"
    else:
        owes = gets = None
    return {
        "expenses": rows,
        "settlements": [s.model_dump() for s in sorted(settlements, key=lambda s: (s.date, s.id))],
        "balance_a": balance_a,
        "owes": owes,
        "gets": gets,
        "amount": abs(balance_a),
        "text": (f"{names[owes]} owes {names[gets]}" if owes and gets else "You are settled up"),
    }


# ---------------------------------------------------------------------------
# The shared plan: who pays which part
# ---------------------------------------------------------------------------

def contribution_categories(fs: FairShare) -> dict[Person, str]:
    """The Joint income category each person's money arrives in ("From Ana")."""
    return {"a": f"{JOINT_CONTRIBUTION_PREFIX}{fs.name_a}", "b": f"{JOINT_CONTRIBUTION_PREFIX}{fs.name_b}"}


def _plan_source(data: AppData, ym: YM) -> tuple[YearData, int] | None:
    """Where the plan of month ``ym`` is read.

    Its own year when that is set up. Otherwise the year the forecast borrows
    from (:func:`rolling_forecast.budget_year`), same month — or that year's
    December when that month has no plan to borrow: it is not tracked, or it
    is tracked but nothing was planned in it (a year started mid-way has no
    plan for its first months; a month recorded before the plan was typed
    keeps an empty plan). Without this a borrowed empty month showed 0 € in
    the forecast and pulled the average down.
    """
    y, m = ym
    own = data.get_year(y)
    if own is not None:
        return own, m
    source = rolling_forecast.budget_year(data, y)
    if source is None:
        return None
    year, _ = source
    if m > year.start_month and budget_total(year, m, "expense") > 0:
        return year, m
    return year, 11


def goal_saving(data: AppData, ym: YM, today: date) -> float:
    """What the shared plan puts aside for savings goals in month ``ym``.

    Each active goal gets its monthly pace (what is still missing ÷ the months
    left, counting the current one) from the current month up to its deadline
    month, so the pot holds the target when it is due. After that a sinking
    fund starts its next round at target ÷ months between bills. Past months
    get nothing, and so does a goal whose date has passed.
    """
    now = ic.ym_index(ic.ym_of(today))
    index = ic.ym_index(ym)
    if index < now:
        return 0.0
    total = 0.0
    for g in data.goals:
        if g.status != "active":
            continue
        deadline = date.fromisoformat(g.target_date)
        if index <= ic.ym_index(ic.ym_of(deadline)):
            remaining = max(0.0, g.target_amount - g.saved())
            pace = goals_service.required_monthly_pace(remaining, goals_service.months_remaining(deadline, today))
            total += pace or 0.0
        elif g.goal_type == "sinking" and g.repeat_months:
            total += g.target_amount / g.repeat_months
    return _round2(total)


def _split(total: float, fs: FairShare) -> tuple[float, float]:
    """``total`` split by the fair share; the two parts always add up to it."""
    a = _round2(total * shares(fs)[0])
    return a, _round2(total - a)


def bill(data: AppData, ym: YM, today: date) -> dict[str, Any]:
    """One month of the shared plan and each person's part of it.

    ``costs`` is the month's planned cash out (costs and investments),
    ``goals`` what the plan puts aside for shared goals; ``total`` is split by
    the fair share into ``a`` and ``b``.
    """
    source = _plan_source(data, ym)
    costs = budget_total(source[0], source[1], "expense") if source else 0.0
    goals = goal_saving(data, ym, today)
    total = _round2(costs + goals)
    a, b = _split(total, data.fair_share)
    return {
        "key": ic.ym_key(ym), "label": ic.ym_label(ym), "month_name": ic.ym_name(ym),
        "year": ym[0], "month": ym[1],
        "costs": _round2(costs), "goals": goals, "total": total, "a": a, "b": b,
    }


def _other_income(data: AppData, ym: YM) -> float:
    """Planned income in Joint that is not one of the two contributions."""
    source = _plan_source(data, ym)
    if source is None:
        return 0.0
    year, m = source
    own = set(contribution_categories(data.fair_share).values())
    return _round2(sum(row[m] for name, row in year.budgets.income.items() if name not in own and m < len(row)))


def sync_contributions(data: AppData, today: date) -> bool:
    """Joint: each person's planned income follows their part of the bill.

    In every month not recorded yet (from the current month on) the row
    "From <name>" is set to that person's part, so the planned contributions
    cancel the planned costs and goal saving. Recorded months keep their plan,
    so budget vs real stays honest. Adds the two income categories where they
    are missing. True if anything changed.
    """
    cats = contribution_categories(data.fair_share)
    changed = False
    for y in data.year_numbers():
        year = data.years[str(y)]
        for cat in cats.values():
            if year.find_category("income", cat) is None:
                year.categories.income.append(Category(name=cat))
                changed = True
            year.budgets.income.setdefault(cat, [0.0] * 12)
        for m in range(12):
            if not budget_links.open_month(year, y, m, today):
                continue
            part = bill(data, (y, m), today)
            for person, cat in cats.items():
                if year.budgets.is_manual("income", cat, m):
                    continue  # typed by hand
                row = year.budgets.income[cat]
                if row[m] != part[person]:
                    row[m] = part[person]
                    changed = True
    return changed


def sync_personal_half(personal: AppData, shared: AppData, today: date) -> bool:
    """Personal: the "Transfer to Joint" budget follows person a's part of the
    Joint bill, in every month not recorded yet. Nothing happens while Joint
    has no year. True if anything changed."""
    if not shared.year_numbers():
        return False
    cat = TRANSFER_PERSONAL_CATEGORY
    changed = False
    for y in personal.year_numbers():
        year = personal.years[str(y)]
        months = [m for m in range(12) if budget_links.open_month(year, y, m, today)]
        if not months:
            continue
        if year.find_category("expense", cat) is None:
            year.categories.expense.append(Category(name=cat, kind="fixed"))
            changed = True
        row = year.budgets.expense.setdefault(cat, [0.0] * 12)
        for m in months:
            if year.budgets.is_manual("expense", cat, m):
                continue  # typed by hand
            if year.budgets.share_row(cat)[m] is not None:  # a % link would fight the Joint plan
                year.budgets.set_share(cat, m, None)
                changed = True
            value = bill(shared, (y, m), today)["a"]
            if row[m] != value:
                row[m] = value
                changed = True
    return changed


def linked_rows(year: YearData, year_num: int, today: date, role: str, fs: FairShare) -> dict[str, Any]:
    """The budget rows of ``year`` that follow the Joint plan, with the months
    in which they cannot be typed (the months :func:`sync_contributions` /
    :func:`sync_personal_half` fill). ``role`` is ``"joint"`` or ``"personal"``;
    ``fs`` is always the Joint profile's names and split."""
    months = [budget_links.open_month(year, year_num, m, today) for m in range(12)]
    if role == "joint":
        cats = contribution_categories(fs)
        return {
            "role": role,
            "income": {cats["a"]: {"name": fs.name_a, "months": months}, cats["b"]: {"name": fs.name_b, "months": months}},
            "expense": {},
        }
    return {"role": role, "income": {}, "expense": {TRANSFER_PERSONAL_CATEGORY: {"name": fs.name_a, "months": months}}}


def rename_people(data: AppData, new: FairShare) -> None:
    """New names rename each person's "From <name>" income category — with its
    budget row and transactions — in every year, so their history stays theirs.

    Raises :class:`LinkError`, changing nothing, when both names give the same
    category or a new name's category is already used for something else.
    """
    before, after = contribution_categories(data.fair_share), contribution_categories(new)
    if after["a"].casefold() == after["b"].casefold():
        raise LinkError("Use two different names.")
    moves = {before[p]: after[p] for p in ("a", "b") if before[p] != after[p]}
    if not moves:
        return
    for year in data.years.values():
        names = {c.name for c in year.categories.income}
        for old, target in moves.items():
            if old in names and target in names and target not in moves:
                raise LinkError(f"There is already an income category {target!r}. Rename or remove it first.")
    for year in data.years.values():
        moving = {o: n for o, n in moves.items() if year.find_category("income", o) is not None}
        if not moving:
            continue
        rows = {o: year.budgets.income.pop(o, [0.0] * 12) for o in moving}
        typed = {o: year.budgets.manual.pop(f"income:{o}", None) for o in moving}
        for c in year.categories.income:
            if c.name in moving:
                c.name = moving[c.name]
        for old, target in moving.items():
            year.budgets.income[target] = rows[old]
            if typed[old]:
                year.budgets.manual[f"income:{target}"] = typed[old]
        for t in year.transactions:
            if t.type == "income" and t.cat in moving:
                t.cat = moving[t.cat]


# ---------------------------------------------------------------------------
# The two Joint pages
# ---------------------------------------------------------------------------

def _progress(part: float, whole: float) -> float:
    """``part`` as a % of ``whole`` for a bar (0–100)."""
    if whole <= 0:
        return 100.0 if part > 0 else 0.0
    return round(min(100.0, max(0.0, part / whole * 100)), 1)


def _goal_rows(data: AppData, today: date) -> dict[str, Any]:
    """The shared goals, each with what the plan asks of each person a month."""
    fs = data.fair_share
    built = goals_service.build_all(data.goals, goal_saving(data, ic.ym_of(today), today), today)
    rows = []
    for g in built["goals"]:
        if g["status"] in ("completed", "abandoned"):
            continue
        pace = g["required_monthly_pace"] if g["remaining"] > 0 else None
        a, b = _split(pace, fs) if pace else (None, None)
        rows.append({
            "id": g["id"], "name": g["name"], "saved": g["saved"], "target_amount": g["target_amount"],
            "remaining": g["remaining"], "progress_pct": g["progress_pct"], "target_date": g["target_date"],
            "status": g["status"], "monthly": pace, "a": a, "b": b,
        })
    total = _round2(sum(r["monthly"] or 0.0 for r in rows))
    a, b = _split(total, fs)
    return {"rows": rows, "monthly": {"total": total, "a": a, "b": b}}


def household(data: AppData, year_num: int, month: int, today: date) -> dict[str, Any]:
    """The Joint Overview in one payload.

    The pot (balance), this month's money in and out against the plan, how
    much each person has paid in of their part, where the money went, the last
    months and the shared goals. Every figure the page shows comes from here.
    """
    year = data.years[str(year_num)]
    k = dashboard.kpis(data, year, year_num, month)
    fs = data.fair_share
    share_a, share_b, basis = shares(fs)
    cats = contribution_categories(fs)
    income = category_totals(year, month, "income")
    this = bill(data, (year_num, month), today)

    people = []
    for person, name, share in (("a", fs.name_a, share_a), ("b", fs.name_b, share_b)):
        planned, paid = this[person], income.get(cats[person], 0.0)
        people.append({
            "person": person, "name": name, "share_pct": round(share * 100, 1), "category": cats[person],
            "planned": planned, "paid_in": paid, "to_go": _round2(max(0.0, planned - paid)),
            "progress": _progress(paid, planned), "done": planned > 0 and paid >= planned,
        })
    from_people = _round2(sum(p["paid_in"] for p in people))

    planned_out, spent = k["cash_out_budget"], k["cash_out"]
    status = "none" if planned_out == 0 and spent == 0 else ("over" if spent > planned_out else "within")
    by_category = dashboard.budget_vs_real(year, month, "expense")
    history = cashflow.history(data, year_num, month)["rows"][-JOINT_HISTORY_MONTHS:]
    return {
        "year": year_num,
        "month": month,
        "month_name": MONTHS[month],
        "pot": {
            "balance": k["current_balance"], "earmarked": k["earmarked"], "free": k["free_balance"],
            "negative": k["negative_balance"],
        },
        "money": {
            "put_in": k["cash_in"], "from_people": from_people, "other_in": _round2(k["cash_in"] - from_people),
            "spent": spent, "planned": planned_out, "left": _round2(planned_out - spent),
            "spent_pct": _progress(spent, planned_out), "status": status, "kept": k["savings"],
        },
        "split": {"basis": basis, "share_a_pct": round(share_a * 100, 1), "share_b_pct": round(share_b * 100, 1)},
        "bill": this,
        "people": people,
        "categories": by_category["rows"],
        "categories_total": by_category["total"],
        "months": [
            {"label": r["label"], "year": r["year"], "month": r["month"], "put_in": r["income"], "spent": r["cash_out"],
             "kept": r["net"]}
            for r in history
        ],
        "goals": _goal_rows(data, today),
    }


def bill_forecast(data: AppData, today: date, horizon: int = FORECAST_MONTHS) -> dict[str, Any]:
    """The Joint Forecast: the next months of the shared plan.

    Starts where the rolling forecast starts (the month after the last recorded
    one). Each month: shared costs, goal saving, each person's part, and the
    pot after it — assuming both pay in their part — less any goal bought then.
    """
    fs = data.fair_share
    share_a, share_b, basis = shares(fs)
    base = {
        "names": {"a": fs.name_a, "b": fs.name_b},
        "split": {"basis": basis, "share_a_pct": round(share_a * 100, 1), "share_b_pct": round(share_b * 100, 1)},
    }
    last = rolling_forecast.last_recorded(data)
    if last is None:
        return {**base, "rows": [], "start_balance": 0.0, "start_name": None, "end_name": None,
                "average": None, "end_pot": 0.0, "lowest_pot": 0.0, "lowest_name": None, "goes_negative": False}
    first = ic.ym_add(last, 1)
    start = balance = rolling_forecast.tracked_balance(data)
    bought = goal_forecast.purchases(data.goals, first, horizon)
    rows = []
    for i in range(horizon):
        ym = ic.ym_add(first, i)
        row = bill(data, ym, today)
        other = _other_income(data, ym)
        goals_bought = bought.get(ym, [])
        spend = _round2(sum(g["amount"] for g in goals_bought))
        balance = _round2(balance + row["a"] + row["b"] + other - row["costs"] - spend)
        rows.append({**row, "other_income": other, "goals_bought": goals_bought, "goal_spend": spend, "pot": balance})

    def avg(key: str) -> float:
        return _round2(sum(r[key] for r in rows) / len(rows))

    total = avg("total")
    a, b = _split(total, fs)
    lowest = min(rows, key=lambda r: r["pot"])
    return {
        **base,
        "rows": rows,
        "start_balance": _round2(start),
        "start_name": ic.ym_name(first),
        "end_name": ic.ym_name(ic.ym_add(first, horizon - 1)),
        "average": {"total": total, "a": a, "b": b, "costs": avg("costs"), "goals": avg("goals")},
        "end_pot": balance,
        "lowest_pot": lowest["pot"],
        "lowest_name": lowest["month_name"],
        "goes_negative": any(r["pot"] < 0 for r in rows),
    }


def goal_checks(data: AppData, today: date) -> dict[int, dict[str, Any]]:
    """Each shared goal seen through :func:`bill_forecast` — the same shape as
    :func:`rolling_forecast.goal_checks`. A goal that is bought is affordable
    when the pot stays at or above zero after it; a kept goal when the pot
    holds its target in its deadline month."""
    forecast = bill_forecast(data, today)
    rows = forecast["rows"]
    if not rows:
        return {}
    first = ic.ym_index((rows[0]["year"], rows[0]["month"]))
    out: dict[int, dict[str, Any]] = {}
    for g in data.goals:
        if g.status != "active":
            continue
        spends = g.spends_in_forecast()
        if spends:
            row = next((r for r in rows if any(p["goal_id"] == g.id for p in r["goals_bought"])), None)
        else:
            due = ic.ym_index(ic.ym_of(date.fromisoformat(g.target_date))) - first
            row = rows[max(0, due)] if due < len(rows) else None
        if row is None:
            continue
        out[g.id] = {
            "month": row["key"], "month_name": row["month_name"], "spent": spends, "balance": row["pot"],
            "affordable": row["pot"] >= 0 if spends else row["pot"] >= g.target_amount, "line": None,
        }
    return out
