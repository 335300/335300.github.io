"""Investment plans: assets paid for in instalments."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, status

from ..models import AppData, Category, InvestmentInput, InvestmentPatch, InvestmentPlan
from ..services import budget_links, investments as investments_service
from ..storage import Repository
from .deps import conflict, get_repository, get_today, not_found

router = APIRouter(prefix="/api/investments", tags=["investments"])


def _plan(repo: Repository, plan_id: int) -> InvestmentPlan:
    plan = repo.data.find_investment(plan_id)
    if plan is None:
        raise not_found(f"Investment plan {plan_id} not found")
    return plan


def _claim_category(data: AppData, name: str) -> None:
    """Make ``name`` an investment category in every year.

    A plan's payments are found by category name across years, so the category
    must exist — as an investment — wherever a payment could be recorded.
    """
    for year in data.years.values():
        found = year.find_category("expense", name)
        if found is None:
            year.categories.expense.append(Category(name=name, kind="investment"))
            year.budgets.expense.setdefault(name, [0.0] * 12)
        else:
            found.kind = "investment"


def _view(repo: Repository, plan: InvestmentPlan, today: date) -> dict[str, Any]:
    year = repo.data.settings.last_year or today.year
    month = repo.data.settings.last_month if repo.data.settings.last_month is not None else today.month - 1
    return investments_service.build(plan, repo.data, year, month, today)


@router.get("")
def list_investments(
    year: int | None = Query(default=None),
    month: int | None = Query(default=None, ge=0, le=11),
    repo: Repository = Depends(get_repository),
    today: date = Depends(get_today),
) -> dict[str, Any]:
    """Every plan with its progress, seen from ``year``/``month`` (default: today)."""
    year = today.year if year is None else year
    month = today.month - 1 if month is None else month
    return investments_service.build_all(repo.data, year, month, today)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_investment(
    payload: InvestmentInput,
    repo: Repository = Depends(get_repository),
    today: date = Depends(get_today),
) -> dict[str, Any]:
    if not repo.data.years:
        raise conflict("Set up a year first")
    if repo.data.investment_for_category(payload.category) is not None:
        raise conflict(f"The category {payload.category!r} already pays for another plan")
    if payload.paid_before > payload.total_installments:
        raise conflict("More instalments are marked as paid than the plan has")
    plan = InvestmentPlan(
        id=repo.data.take_investment_id(), created_date=today.isoformat(), **payload.model_dump()
    )
    _claim_category(repo.data, plan.category)
    repo.data.investments.append(plan)
    budget_links.sync(repo.data, today)
    repo.save()
    return _view(repo, plan, today)


@router.patch("/{plan_id}")
def update_investment(
    plan_id: int,
    payload: InvestmentPatch,
    repo: Repository = Depends(get_repository),
    today: date = Depends(get_today),
) -> dict[str, Any]:
    plan = _plan(repo, plan_id)
    changes = payload.model_dump(exclude_none=True)
    for field in ("cost_per_installment", "market_value_local"):
        if changes.get(field) == 0:
            changes[field] = None
    # Validate the edited copy first, so a bad edit never touches the stored plan.
    updated = InvestmentPlan.model_validate({**plan.model_dump(), **changes})
    if updated.paid_before > updated.total_installments:
        raise conflict("More instalments are marked as paid than the plan has")
    repo.data.investments = [updated if p.id == plan_id else p for p in repo.data.investments]
    budget_links.sync(repo.data, today)
    repo.save()
    return _view(repo, updated, today)


@router.delete("/{plan_id}")
def delete_investment(
    plan_id: int, repo: Repository = Depends(get_repository), today: date = Depends(get_today)
) -> dict[str, Any]:
    """Remove the plan. Its payments stay as transactions in their category."""
    _plan(repo, plan_id)
    repo.data.investments = [p for p in repo.data.investments if p.id != plan_id]
    budget_links.sync(repo.data, today)
    repo.save()
    return {"deleted": plan_id}
