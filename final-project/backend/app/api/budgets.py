"""Budget grids and the categories that make up their rows."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Path, status

from ..config import DEFAULT_PROFILE, JOINT_PROFILE, MONTHS
from ..models import AppData, BudgetCellInput, BudgetRowShareInput, Category, CategoryInput, CategoryPatch, TxType, YearData
from ..services import aggregation, budget_links, cashflow, joint
from ..storage import AppStore, Repository
from .deps import conflict, get_repository, get_store, get_synced_repository, get_today, get_year, not_found, sync_joint_links

router = APIRouter(prefix="/api/{year}", tags=["budgets"])

NO_PERCENT_IN_JOINT = (
    "In the Joint plan, type euros. Its income follows its costs, so a cost linked to a % of income would chase itself."
)


def _joint_rows(store: AppStore, year_num: int, today: date) -> dict[str, Any] | None:
    """Rows of the open profile's plan that follow the Joint plan, or None."""
    shared = store.repo(JOINT_PROFILE).data
    if store.active == JOINT_PROFILE:
        role = "joint"
    elif store.active == DEFAULT_PROFILE and shared.year_numbers():
        role = "personal"
    else:
        return None
    year = store.repo().data.get_year(year_num)
    return joint.linked_rows(year, year_num, today, role, shared.fair_share) if year is not None else None


def _fills_itself(repo: Repository, store: AppStore, year: int, kind: TxType, cat: str, month: int,
                  today: date) -> str | None:
    """What fills this budget box by itself (in words), or None for an ordinary box."""
    joint_rows = _joint_rows(store, year, today)
    follows = joint_rows[kind].get(cat) if joint_rows else None
    if follows and follows["months"][month]:
        return "it follows the Joint plan"
    links = budget_links.describe(repo.data, year, today)
    if kind == "income" and cat == links["salary_category"] and links["calendar_months"][month]:
        return "it comes from the income calendar"
    plan_flags = links["plan_months"].get(cat) if kind == "expense" else None
    if plan_flags and plan_flags[month]:
        return f"it follows the investment plan {links['plans'][cat]['name']!r}"
    return None


def _grid(year_data: YearData, kind: TxType, usual: dict[str, float], usual_months: int) -> dict[str, Any]:
    categories = getattr(year_data.categories, kind)
    rows = [
        {
            "cat": c.name,
            "kind": c.kind,
            # What this category came to in a usual recent month — a yardstick for the plan.
            "usual": usual.get(c.name, 0.0) if usual_months else None,
            "values": year_data.budget_row(kind, c.name),
            # Each month's budget as a % of that month's planned income (cash out only).
            "shares": cashflow.budget_shares(year_data, year_data.budget_row(kind, c.name)) if kind == "expense" else None,
            # The % this cell is linked to (its euros follow the month's income), per month.
            "links": year_data.budgets.share_row(c.name) if kind == "expense" else None,
            # Boxes typed by hand over a figure that fills itself, per month.
            "manual": year_data.budgets.manual_row(kind, c.name),
            "total": round(sum(year_data.budget_row(kind, c.name)), 2),
            "actuals": [
                aggregation.category_totals(year_data, m, kind).get(c.name, 0.0) for m in range(12)
            ],
            "transactions": sum(1 for t in year_data.transactions if t.type == kind and t.cat == c.name),
        }
        for c in categories
    ]
    monthly_totals = [aggregation.budget_total(year_data, m, kind) for m in range(12)]
    return {"rows": rows, "monthly_totals": monthly_totals, "grand_total": round(sum(monthly_totals), 2)}


def _usual(data: AppData, year: int, kind: TxType, today: date) -> tuple[dict[str, float], int]:
    """Average per category over the last finished months up to this year's end."""
    months = cashflow.recent_months(data, year, skip=(today.year, today.month - 1))
    return cashflow.category_baselines(data, months, kind), len(months)


@router.get("/budgets")
def get_budgets(
    year: int = Path(...),
    year_data: YearData = Depends(get_year),
    repo: Repository = Depends(get_synced_repository),
    store: AppStore = Depends(get_store),
    today: date = Depends(get_today),
) -> dict[str, Any]:
    # Salary from the income calendar, linked % budgets and the Joint links are
    # derived figures: bring them up to date before showing the plan.
    if budget_links.sync(repo.data, today):
        repo.save()
    usual_expense, n = _usual(repo.data, year, "expense", today)
    usual_income, _ = _usual(repo.data, year, "income", today)
    return {
        "months": MONTHS,
        "start_month": year_data.start_month,
        "usual_months": n,
        "expense": {**_grid(year_data, "expense", usual_expense, n), "kind_totals": aggregation.budget_kind_rows(year_data)},
        "income": _grid(year_data, "income", usual_income, n),
        "saved": aggregation.savings_by_month(year_data),
        "allocation": cashflow.budget_allocation(year_data),
        "links": {**budget_links.describe(repo.data, year, today), "joint": _joint_rows(store, year, today)},
    }


@router.put("/budgets")
def set_budget_cell(
    payload: BudgetCellInput,
    year: int = Path(...),
    year_data: YearData = Depends(get_year),
    repo: Repository = Depends(get_repository),
    store: AppStore = Depends(get_store),
    today: date = Depends(get_today),
) -> dict[str, Any]:
    """Set a single month's budget for one category.

    With ``percent`` the cell is linked to that share of the month's planned
    income: its euros follow the income from then on. A euro ``value`` removes
    the link.

    A box that fills itself (the salary from the income calendar, an investment
    plan, the Joint plan) can be typed over too: it is then marked as typed by
    hand and the automatic fill leaves it alone. ``auto`` sets it back.
    """
    grid = getattr(year_data.budgets, payload.kind)
    if payload.cat not in grid and year_data.find_category(payload.kind, payload.cat) is None:
        raise not_found(f"Unknown {payload.kind} category {payload.cat!r}")
    if payload.percent is not None and store.active == JOINT_PROFILE:
        raise conflict(NO_PERCENT_IN_JOINT)
    derived = _fills_itself(repo, store, year, payload.kind, payload.cat, payload.month, today)
    if payload.auto:
        year_data.budgets.set_manual(payload.kind, payload.cat, payload.month, False)
        budget_links.sync(repo.data, today)
        repo.save()
        sync_joint_links(store, today)
    elif derived:
        if payload.percent is not None:
            raise conflict(f"{payload.cat} in this month fills itself ({derived}). Type euros to set it by hand.")
        grid.setdefault(payload.cat, [0.0] * 12)
        grid[payload.cat][payload.month] = round(payload.value or 0.0, 2)
        year_data.budgets.set_manual(payload.kind, payload.cat, payload.month, True)
        if payload.kind == "expense":
            year_data.budgets.set_share(payload.cat, payload.month, None)  # a % link would fight it
    elif payload.percent is not None:
        try:
            cashflow.amount_from_share(year_data, payload.month, payload.percent)
        except ValueError as exc:
            raise conflict(str(exc)) from exc
        year_data.budgets.set_share(payload.cat, payload.month, payload.percent)
    else:
        grid.setdefault(payload.cat, [0.0] * 12)
        grid[payload.cat][payload.month] = round(payload.value or 0.0, 2)
        if payload.kind == "expense":
            year_data.budgets.set_share(payload.cat, payload.month, None)
    budget_links.sync(repo.data, today)
    repo.save()
    return {
        "cat": payload.cat,
        "kind": payload.kind,
        "values": grid.get(payload.cat, [0.0] * 12),
        "manual": year_data.budgets.manual_row(payload.kind, payload.cat),
        "links": year_data.budgets.share_row(payload.cat) if payload.kind == "expense" else None,
        "monthly_total": aggregation.budget_total(year_data, payload.month, payload.kind),
    }


@router.put("/budgets/row-share")
def set_row_share(
    payload: BudgetRowShareInput,
    year_data: YearData = Depends(get_year),
    repo: Repository = Depends(get_repository),
    store: AppStore = Depends(get_store),
    today: date = Depends(get_today),
) -> dict[str, Any]:
    """Link one cash-out category to a % of planned income in every month not
    recorded yet. Recorded months keep their budgets, so budget-vs-real stays honest."""
    if store.active == JOINT_PROFILE and payload.percent is not None:
        raise conflict(NO_PERCENT_IN_JOINT)
    if year_data.find_category("expense", payload.cat) is None:
        raise not_found(f"Unknown expense category {payload.cat!r}")
    months = budget_links.open_months(year_data)
    if not months:
        raise conflict("Every month of this year is already recorded")
    for m in months:
        year_data.budgets.set_share(payload.cat, m, payload.percent)
    budget_links.sync(repo.data, today)
    repo.save()
    return {
        "cat": payload.cat,
        "months": months,
        "values": year_data.budget_row("expense", payload.cat),
        "links": year_data.budgets.share_row(payload.cat),
    }


@router.get("/categories")
def list_categories(year_data: YearData = Depends(get_year)) -> dict[str, Any]:
    def rows(kind: TxType) -> list[dict[str, Any]]:
        return [
            {
                "name": c.name,
                "kind": c.kind,
                "essential": c.essential,
                "tax_relevant": c.tax_relevant,
                "transactions": sum(1 for t in year_data.transactions if t.type == kind and t.cat == c.name),
            }
            for c in getattr(year_data.categories, kind)
        ]

    return {"expense": rows("expense"), "income": rows("income")}


@router.post("/categories", status_code=status.HTTP_201_CREATED)
def add_category(
    payload: CategoryInput,
    year_data: YearData = Depends(get_year),
    repo: Repository = Depends(get_repository),
) -> dict[str, Any]:
    name = payload.name.strip()
    if not name:
        raise conflict("A category needs a name")
    if year_data.find_category(payload.kind, name) is not None:
        raise conflict(f"{payload.kind.title()} category {name!r} already exists")
    getattr(year_data.categories, payload.kind).append(
        Category(name=name, kind=payload.category_kind, essential=payload.essential, tax_relevant=payload.tax_relevant)
    )
    getattr(year_data.budgets, payload.kind).setdefault(name, [0.0] * 12)
    repo.save()
    return {"cat": name, "kind": payload.category_kind, "essential": payload.essential, "tax_relevant": payload.tax_relevant}


@router.patch("/categories/{kind}/{name:path}")
def update_category(
    kind: TxType,
    name: str,
    payload: CategoryPatch,
    year_data: YearData = Depends(get_year),
    repo: Repository = Depends(get_repository),
) -> dict[str, Any]:
    """Rename a category, flip its fixed/variable flag or mark it essential.

    A rename rewrites the budget row and every transaction that referenced the
    old name, so history stays attached to the category.
    """
    category = year_data.find_category(kind, name)
    if category is None:
        raise not_found(f"Unknown {kind} category {name!r}")
    new_name = (payload.name or "").strip()
    if new_name and new_name != name and year_data.find_category(kind, new_name) is not None:
        raise conflict(f"{kind.title()} category {new_name!r} already exists")
    plan = repo.data.investment_for_category(name) if kind == "expense" else None

    if payload.category_kind is not None:
        if plan is not None and payload.category_kind != "investment":
            raise conflict(
                f"{name!r} pays for the investment plan {plan.name!r}, so it stays an investment. "
                "Remove the plan first to change it."
            )
        category.kind = payload.category_kind
    if payload.essential is not None:
        category.essential = payload.essential
    if payload.tax_relevant is not None:
        category.tax_relevant = payload.tax_relevant
    if new_name and new_name != name:
        # A plan follows its category by name in every year, so a rename has to
        # reach all of them; an ordinary category is renamed in this year only.
        years = list(repo.data.years.values()) if plan is not None else [year_data]
        if any(y is not year_data and y.find_category(kind, new_name) is not None for y in years):
            raise conflict(f"{kind.title()} category {new_name!r} already exists in another year")
        for y in years:
            found = y.find_category(kind, name)
            if found is None:
                continue
            grid = getattr(y.budgets, kind)
            grid[new_name] = grid.pop(name, [0.0] * 12)
            if kind == "expense" and name in y.budgets.shares:
                y.budgets.shares[new_name] = y.budgets.shares.pop(name)
            y.budgets.rename_manual(kind, name, new_name)
            for tx in y.transactions:
                if tx.type == kind and tx.cat == name:
                    tx.cat = new_name
            found.name = new_name
        if plan is not None:
            plan.category = new_name
    repo.save()
    return {"cat": category.name, "kind": category.kind, "essential": category.essential, "tax_relevant": category.tax_relevant}


@router.delete("/categories/{kind}/{name:path}")
def delete_category(
    kind: TxType,
    name: str,
    year_data: YearData = Depends(get_year),
    repo: Repository = Depends(get_repository),
) -> dict[str, Any]:
    """Remove a category — refused while transactions still reference it."""
    if year_data.find_category(kind, name) is None:
        raise not_found(f"Unknown {kind} category {name!r}")
    plan = repo.data.investment_for_category(name) if kind == "expense" else None
    if plan is not None:
        raise conflict(f"{name!r} pays for the investment plan {plan.name!r}. Remove the plan first.")
    in_use = sum(1 for t in year_data.transactions if t.type == kind and t.cat == name)
    if in_use:
        raise conflict(
            f"{name!r} still has {in_use} transaction(s). "
            "Move or delete them first, or rename the category instead."
        )
    setattr(year_data.categories, kind, [c for c in getattr(year_data.categories, kind) if c.name != name])
    getattr(year_data.budgets, kind).pop(name, None)
    if kind == "expense":
        year_data.budgets.shares.pop(name, None)
    year_data.budgets.manual.pop(f"{kind}:{name}", None)
    repo.save()
    return {"deleted": name, "kind": kind}
